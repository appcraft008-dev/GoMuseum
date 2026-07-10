"""测试集构建:分层抽样(非名作70%) + Commons他人照片 + 合成畸变 + 库外干扰组。
网络部分(Commons/SPARQL/下载)幂等:文件已存在即跳过,可断点续跑。"""

from __future__ import annotations

import io
import json
import random
import time
from pathlib import Path

import requests
from PIL import Image

from scripts.recognition_bench.distort import distort_all

DATA = Path(__file__).parent / "data"
UA = {"User-Agent": "GoMuseumBench/1.0 (appcraft008@gmail.com)"}
_3D = {"sculpture", "decorative_arts", "textile", "artifact"}
WD_API = "https://www.wikidata.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
SPARQL = "https://query.wikidata.org/sparql"


def stratified_sample(objects, n=100, famous_cut=200, famous_frac=0.3, seed=42):
    rng = random.Random(seed)
    famous_pool, nonfamous_pool = objects[:famous_cut], objects[famous_cut:]
    n_famous = min(round(n * famous_frac), len(famous_pool))
    n_non = min(n - n_famous, len(nonfamous_pool))
    picked = rng.sample(famous_pool, n_famous) + rng.sample(nonfamous_pool, n_non)
    out = []
    for o in picked:
        fame = "famous" if o in famous_pool else "nonfamous"
        out.append({**o, "fame": fame, "dim": "3d" if o["category"] in _3D else "2d"})
    return out


def _get(url, **params):
    time.sleep(0.2)
    r = requests.get(url, params=params, headers=UA, timeout=30)
    r.raise_for_status()
    return r


def _download(url: str, dest: Path) -> bool:
    if dest.exists():
        return True
    try:
        r = _get(url)
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        img.thumbnail((1024, 1024))
        dest.parent.mkdir(parents=True, exist_ok=True)
        img.save(dest, "JPEG", quality=90)
        return True
    except Exception as e:  # 单张失败不断整体
        print(f"  skip {url}: {e}")
        return False


def commons_alt_photos(qid: str, max_n: int = 5) -> list[str]:
    """qid → P18 官方图文件名 + P373/commons 分类 → 分类内其他图片文件的缩略 URL。"""
    ent = _get(
        WD_API,
        action="wbgetentities",
        ids=qid,
        props="claims|sitelinks",
        format="json",
    ).json()["entities"][qid]
    claims = ent.get("claims", {})

    def _claim_str(pid):
        c = claims.get(pid)
        return c[0]["mainsnak"]["datavalue"]["value"] if c else None

    p18 = _claim_str("P18")
    cat = _claim_str("P373")
    if not cat:
        link = (ent.get("sitelinks") or {}).get("commonswiki", {}).get("title", "")
        cat = link.removeprefix("Category:") if link.startswith("Category:") else None
    if not cat:
        return []
    members = _get(
        COMMONS_API,
        action="query",
        list="categorymembers",
        cmtitle=f"Category:{cat}",
        cmtype="file",
        cmlimit=50,
        format="json",
    ).json()["query"]["categorymembers"]
    urls = []
    for m in members:
        title = m["title"]
        fname = title.removeprefix("File:")
        if p18 and fname.replace(" ", "_") == p18.replace(" ", "_"):
            continue  # 排除官方图本尊
        if not fname.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        info = _get(
            COMMONS_API,
            action="query",
            titles=title,
            prop="imageinfo",
            iiprop="url",
            iiurlwidth=1024,
            format="json",
        ).json()["query"]["pages"]
        page = next(iter(info.values()))
        ii = (page.get("imageinfo") or [{}])[0]
        if ii.get("thumburl"):
            urls.append(ii["thumburl"])
        if len(urls) >= max_n:
            break
    return urls


def louvre_distractors(exclude: set[str], n: int = 50) -> list[tuple[str, str]]:
    """卢浮宫(Q19675)有图画作 → [(qid, image_url)],排除 orsay 目录 qid。"""
    query = (
        "SELECT ?item ?image WHERE { ?item wdt:P195 wd:Q19675; wdt:P31 wd:Q3305213; "
        "wdt:P18 ?image } LIMIT 120"
    )
    rows = _get(SPARQL, query=query, format="json").json()["results"]["bindings"]
    out = []
    for r in rows:
        qid = r["item"]["value"].rsplit("/", 1)[-1]
        if qid in exclude:
            continue
        out.append((qid, r["image"]["value"]))
        if len(out) >= n:
            break
    return out


def main():
    manifest = json.loads((DATA / "manifest.json").read_text())
    objects = manifest["objects"]
    sample = stratified_sample(objects)
    rows = []
    for o in sample:
        qdir = DATA / "testset" / o["qid"]
        tags = {"true_qid": o["qid"], "fame": o["fame"], "dim": o["dim"]}
        # 真实游客照(Commons 他人照片;冷门件常为 0,如实分桶)
        try:
            for i, url in enumerate(commons_alt_photos(o["qid"])):
                dest = qdir / f"real_{i}.jpg"
                if _download(url, dest):
                    rows.append({"path": str(dest), "source": "real", **tags})
        except Exception as e:
            print(f"commons fail {o['qid']}: {e}")
        # 合成畸变(官方图第一张)
        ref = DATA / "testset" / o["qid"] / "_ref.jpg"
        if _download(o["images"][0], ref):
            img = Image.open(ref)
            for name, v in distort_all(img, seed=42).items():
                dest = qdir / f"syn_{name}.jpg"
                if not dest.exists():
                    v.save(dest, "JPEG", quality=90)
                rows.append({"path": str(dest), "source": "synthetic", **tags})
        print(f"{o['qid']} done ({len(rows)} rows)")
    # 库外干扰组
    exclude = {o["qid"] for o in objects}
    for qid, url in louvre_distractors(exclude):
        dest = DATA / "ooc" / f"{qid}.jpg"
        if _download(url, dest):
            rows.append(
                {
                    "path": str(dest),
                    "true_qid": None,
                    "source": "ooc",
                    "fame": None,
                    "dim": None,
                }
            )
    (DATA / "testset.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    print(f"testset.json: {len(rows)} rows")


if __name__ == "__main__":
    main()
