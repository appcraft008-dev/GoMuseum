"""一次性:从 prod 目录导出构造匹配评测集(产物提交进仓库,脚本留档可复现)。

输入:prod `museum_objects` 导出(每行 JSON:qid,m,en,zh,i18n,a_en,a_zh,a_i18n,a_name_en,inv,pop),
导出 SQL 见 docs/superpowers/specs/2026-10-07-matching-core-design.md §2。
输出(本目录):catalog_sample.jsonl(抽样目录,只含公开目录字段)、search_cases.json、recog_cases.json。
种子固定 20261007,与 spec §2 的评测同一套构造。

    python tests/eval/matching/build_fixture.py --catalog /path/to/catalog2.jsonl
"""

import argparse
import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[2]))

from app.services.matching.normalize import normalize  # noqa: E402

SEED = 20261007
KEEP = (
    "qid",
    "m",
    "en",
    "zh",
    "i18n",
    "a_en",
    "a_zh",
    "a_i18n",
    "a_name_en",
    "inv",
    "pop",
)
SAMPLE = 4000
WHOLE_MUSEUMS = {"orangerie", "rijksmuseum"}
STOP = {
    "the", "of", "and", "with", "in", "on", "a", "an", "de", "la", "le", "les", "du",
    "des", "et", "au", "aux", "en", "un", "une", "à", "dans", "sur", "pour", "par", "l", "d",
}  # fmt: skip
HIFREQ = [
    "portrait", "vierge", "saint jean", "femme", "paysage", "nature morte", "louis xiv",
    "christ", "rubens", "corot", "monet", "vase", "tête", "bust of", "head of", "studio",
]  # fmt: skip
NEG = [
    ("The Starry Night", "Vincent van Gogh"), ("The Persistence of Memory", "Salvador Dalí"),
    ("Girl with a Pearl Earring", "Johannes Vermeer"), ("The Scream", "Edvard Munch"),
    ("The Hay Wain", "John Constable"), ("Guernica", "Pablo Picasso"),
    ("American Gothic", "Grant Wood"), ("Las Meninas", "Diego Velázquez"),
    ("The Garden of Earthly Delights", "Hieronymus Bosch"), ("Sunflowers", "Vincent van Gogh"),
    ("A Sunday Afternoon on the Island of La Grande Jatte", "Georges Seurat"),
    ("Nighthawks", "Edward Hopper"), ("The Great Wave off Kanagawa", "Katsushika Hokusai"),
    ("The Arnolfini Portrait", "Jan van Eyck"), ("The Creation of Adam", "Michelangelo"),
    ("The Fighting Temeraire", "J. M. W. Turner"), ("Christina's World", "Andrew Wyeth"),
    ("The Son of Man", "René Magritte"), ("Composition VIII", "Wassily Kandinsky"),
    ("Wanderer above the Sea of Fog", "Caspar David Friedrich"),
    ("The Third of May 1808", "Francisco Goya"), ("Saturn Devouring His Son", "Francisco Goya"),
    ("Impression, Sunrise", "Claude Monet"), ("Café Terrace at Night", "Vincent van Gogh"),
    ("Self-Portrait with Bandaged Ear", "Vincent van Gogh"),
    ("Les Demoiselles d'Avignon", "Pablo Picasso"), ("The Night Café", "Vincent van Gogh"),
    ("Bathers at Asnières", "Georges Seurat"), ("Mont Sainte-Victoire", "Paul Cézanne"),
    ("The Sleeping Gypsy", "Henri Rousseau"),
]  # fmt: skip
# 10-06 prod 真实垃圾输入(像素画/动画截图)的 AI 读图结果
JUNK = [
    (["Pixelated House", "House in Pixel Art Style", "Green House Illustration"], ["Unknown"] * 3),
    (["Pixel Art House", "8-Bit House Design", "Retro Style Cottage"], ["Unknown"] * 3),
    (["The Venture Bros.", "Action Hank", "The Tick"], ["Jackson Publick and Doc Hammer", "Evan Dorkin", "Ben Edlund"]),
    (["Duke Nukem", "Aqua Teen Hunger Force", "Cartoon Network's The Venture Bros."], ["N/A", "Dave Willis, Matt Maiellaro", "Jackson Publick, Doc Hammer"]),
    (["Brock Samson", 'Character from "The Venture Bros."', "Animated Character"], ["Adam Reed", "Television Show", "Unknown"]),
    (["No Title Available", "Pixel Art House", "Green House Design"], ["Unknown"] * 3),
    (["Pixelated House", "Digital Landscape", "Block House"], ["Unknown"] * 3),
]  # fmt: skip


def names_of(d):
    return {v for v in (d.get("i18n") or {}).values() if v} | {
        x for x in (d.get("en"), d.get("zh")) if x
    }


def artist_names(d):
    out = {v for v in (d.get("a_i18n") or {}).values() if v}
    return out | {x for x in (d.get("a_name_en"), d.get("a_en"), d.get("a_zh")) if x}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    cat = []
    for line in open(ap.parse_args().catalog, encoding="utf-8"):
        try:
            cat.append(json.loads(line))
        except ValueError:
            pass  # psql 头尾行
    rng = random.Random(SEED)

    def sample(pred, n):
        pool = [d for d in cat if pred(d)]
        by = {}
        for d in pool:
            by.setdefault(d["m"], []).append(d)
        out = []
        for _, ds in sorted(by.items()):
            k = max(3, round(n * len(ds) / len(pool)))
            out += rng.sample(ds, min(k, len(ds)))
        return out

    def words(s):
        return [w for w in re.split(r"\s+", s.strip()) if w]

    def typo(s):
        ws = list(s)
        idx = [i for i, c in enumerate(ws) if c.isalpha()]
        if len(idx) < 6:
            return s
        i = rng.choice(idx[1:-1])
        ws[i], ws[i + 1] = ws[i + 1], ws[i]
        return "".join(ws)

    allnames = {normalize(n) for d in cat for n in names_of(d)}
    neg = [(t, a) for t, a in NEG if normalize(t) not in allnames]

    # --- 识别用例(spec §2.1 同构造) ---
    recog = []

    def add(kind, target, q, a, drop=None):
        ds = rng.sample(neg, 2)
        recog.append(
            {
                "kind": kind,
                "target": target,
                "queries": [q] + [t for t, _ in ds],
                "hints": [a] + [x for _, x in ds],
                "drop": drop,
            }
        )

    def main_artist(d):
        return d.get("a_name_en") or d.get("a_en") or sorted(artist_names(d))[0]

    for d in sample(
        lambda d: d.get("en")
        and len(words(d["en"])) >= 2
        and artist_names(d)
        and not re.search(r"\d{3}", d["en"]),
        120,
    ):
        a = main_artist(d)
        add("exact", d["qid"], d["en"], a)
        w = words(d["en"])
        if len(w) >= 3:
            add("partial", d["qid"], " ".join(w[: max(2, len(w) * 2 // 3)]), a)
        add("typo", d["qid"], typo(d["en"]), a)
    for d in sample(
        lambda d: d.get("en")
        and (d.get("i18n") or {}).get("fr")
        and normalize(d["en"]) != normalize(d["i18n"]["fr"])
        and artist_names(d),
        120,
    ):
        same = sorted(n for n in names_of(d) if normalize(n) == normalize(d["en"]))
        add("alias_missing", d["qid"], d["en"], main_artist(d), drop=same)
    for t, a in neg:
        recog.append(
            {
                "kind": "neg_famous",
                "target": None,
                "queries": [t] + [x for x, _ in rng.sample(neg, 2)],
                "hints": [a],
                "drop": None,
            }
        )
    for q, h in JUNK:
        recog.append(
            {"kind": "neg_junk", "target": None, "queries": q, "hints": h, "drop": None}
        )
    recog.append(
        {
            "kind": "label_bilingual",
            "target": "Q17492552",
            "queries": ["L'Air du soir", "The Evening Air"],
            "hints": ["Henri-Edmond Cross"],
            "drop": None,
        }
    )
    # 别名缺失的目标不再兼作其它用例(删了名字会影响别的用例)
    dropped = {c["target"] for c in recog if c["drop"]}
    recog = [c for c in recog if c["drop"] or c["target"] not in dropped]

    # --- 搜索用例(spec §2.2 同构造) ---
    search = []
    for d in sample(lambda d: d.get("en") or (d.get("i18n") or {}).get("fr"), 200):
        t = d.get("en") or d["i18n"]["fr"]
        w = words(t)
        content = [x for x in w[1:] if len(x) >= 5 and x.lower() not in STOP]
        if len(w) >= 2:
            search.append({"kind": "prefix2", "target": d["qid"], "q": " ".join(w[:2])})
            search.append(
                {"kind": "typo", "target": d["qid"], "q": typo(" ".join(w[:3]))}
            )
        if content:
            search.append(
                {"kind": "middle_word", "target": d["qid"], "q": rng.choice(content)}
            )
        if len(w) >= 3:
            search.append(
                {"kind": "words_skip", "target": d["qid"], "q": w[0] + " " + w[2]}
            )
        a = d.get("a_name_en") or d.get("a_en")
        if a and content:
            search.append(
                {
                    "kind": "artist+word",
                    "target": d["qid"],
                    "q": a.split()[-1] + " " + rng.choice(content),
                }
            )
        if d.get("zh"):
            search.append({"kind": "zh_part", "target": d["qid"], "q": d["zh"][:4]})
    search += [{"kind": "hifreq", "target": None, "q": q} for q in HIFREQ]

    # --- 抽样目录:分层抽样 + 全部用例目标 + 与目标同名的其它件(保留 1.0 并列的真实形态) ---
    by_qid = {d["qid"]: d for d in cat}
    targets = {c["target"] for c in recog + search if c["target"]}
    tnames = {normalize(n) for q in targets if q in by_qid for n in names_of(by_qid[q])}
    keep = {d["qid"] for d in cat if d["m"] in WHOLE_MUSEUMS}
    keep |= {d["qid"] for d in sample(lambda d: d["m"] not in WHOLE_MUSEUMS, SAMPLE)}
    keep |= targets & set(by_qid)
    keep |= {d["qid"] for d in cat if {normalize(n) for n in names_of(d)} & tnames}
    with open(HERE / "catalog_sample.jsonl", "w", encoding="utf-8") as f:
        for d in cat:
            if d["qid"] in keep:
                f.write(
                    json.dumps({k: d.get(k) for k in KEEP}, ensure_ascii=False) + "\n"
                )
    for name, obj in (("search_cases.json", search), ("recog_cases.json", recog)):
        with open(HERE / name, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=0)
    print(
        f"catalog {len(keep)}  search {len(search)}  recog {len(recog)}  neg kept {len(neg)}"
    )


if __name__ == "__main__":
    main()
