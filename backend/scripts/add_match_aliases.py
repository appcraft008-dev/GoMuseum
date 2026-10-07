"""一次性:给「英文标题其实是法语」的作品补英文匹配别名(spec §5)。

10-07 实测 3504 件(13%)的 title_i18n.en 与 fr 归一化后相同——Wikidata 无英文标签时回退成了
法语;AI 看图说英文名(「The Evening Air」)对不上库里的「L'Air du soir」。

只写 museum_objects.attributes.match_aliases(只用于匹配,不显示);不碰标题、作者等共享实体、
不碰任何 audio_key。跑前 dry-run 看件数与样例(只译第一批,不花全量的钱);--apply 必带
--backup(写入面全部行的原 attributes)。幂等:已有 match_aliases 的件跳过。
译文与原文归一化相同(人名/同形词,如 Sarah Bernhardt)不写。

用法(容器内):
    python scripts/add_match_aliases.py                       # dry-run
    python scripts/add_match_aliases.py --apply --backup /tmp/match_aliases_backup.json
"""

import argparse
import json
import sys

sys.path.insert(0, "/app")

from sqlalchemy.orm.attributes import flag_modified  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models.museum_object import MuseumObject  # noqa: E402
from app.services.matching.normalize import normalize  # noqa: E402

_SYSTEM = (
    "Translate each French artwork title in the JSON array into the English title an "
    "English-speaking museum visitor would most likely use. Keep proper names as they "
    "are. Return ONLY a JSON array of strings, same length and order. No commentary."
)
MODEL = "gpt-4o-mini"


def targets(db):
    out = []
    for o in db.query(MuseumObject).order_by(MuseumObject.qid):
        a = o.attributes or {}
        ti = a.get("title_i18n") or {}
        if a.get("match_aliases") or not ti.get("fr") or not ti.get("en"):
            continue
        if normalize(ti["en"]) == normalize(ti["fr"]):
            out.append(o)
    return out


def translate_batch(titles, complete):
    try:
        data = json.loads(complete(_SYSTEM, json.dumps(titles, ensure_ascii=False)))
    except Exception:
        return [None] * len(titles)
    if not isinstance(data, list) or len(data) != len(titles):
        return [None] * len(titles)
    return [t if isinstance(t, str) and t.strip() else None for t in data]


def run(db, complete, apply, backup, batch=40):
    objs = targets(db)
    rep = {"targets": len(objs), "written": 0, "same_as_source": 0, "failed": 0}
    if backup:
        with open(backup, "w", encoding="utf-8") as f:
            rows = [{"qid": o.qid, "attributes": o.attributes} for o in objs]
            json.dump(rows, f, ensure_ascii=False)
    for k in range(0, len(objs), batch):
        chunk = objs[k : k + batch]
        frs = [o.attributes["title_i18n"]["fr"] for o in chunk]
        for o, fr, en in zip(chunk, frs, translate_batch(frs, complete)):
            if en is None:
                rep["failed"] += 1
            elif normalize(en) == normalize(fr):
                rep["same_as_source"] += 1
            elif apply:
                o.attributes = {**o.attributes, "match_aliases": [en]}
                flag_modified(o, "attributes")
                rep["written"] += 1
            if not apply:
                print(f"  {o.qid}: {fr!r} -> {en!r}")
        if not apply:
            break  # dry-run 只译第一批看样例
        db.commit()
    return rep


def _complete():
    import asyncio

    from app.services.content_generation_service import _get_openai_client
    from app.services.llm_usage import record_llm_usage

    client = _get_openai_client()

    def complete(system, user):
        async def _run():
            r = await client.chat.completions.create(
                model=MODEL,
                temperature=0,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                timeout=60,
            )
            u = r.usage
            record_llm_usage(
                "names",
                MODEL,
                u.prompt_tokens if u else 0,
                u.completion_tokens if u else 0,
            )
            return r.choices[0].message.content or ""

        return asyncio.run(_run())

    return complete


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--backup")
    args = ap.parse_args()
    if args.apply and not args.backup:
        sys.exit("--apply 必须带 --backup(纪律 37)")
    db = SessionLocal()
    try:
        print(run(db, _complete(), args.apply, args.backup))
    finally:
        db.close()
