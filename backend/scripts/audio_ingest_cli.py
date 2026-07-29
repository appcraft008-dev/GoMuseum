"""把外部生成好的音频灌入系统 —— 过质量闸 → 传 R2 → 写 DB(含引擎标记)。

## 为什么要这个命令

自托管生成跑在**另一台机器**上(Mac mini),那台机器不该、也不方便直连 prod 数据库。
分工:那边只管生成 mp3 文件,这边负责验、传、落库。生成侧完全不碰 DB 和 R2 凭证。

## 工作流

  # ① VPS 上出队列
  python scripts/audio_queue_cli.py plan --langs zh --engine voxcpm2 \\
      --museum louvre --json > jobs.json

  # ② 传到生成机,按约定文件名生成:  {qid}__{language}__{section}.mp3
  #    例:Q152509__zh__guide.mp3   Q152509__zh__qa_0.mp3

  # ③ 音频传回 VPS,灌入
  python scripts/audio_ingest_cli.py --jobs jobs.json --dir ./out \\
      --engine voxcpm2                    # 默认 dry-run,只报告
  python scripts/audio_ingest_cli.py --jobs jobs.json --dir ./out \\
      --engine voxcpm2 --apply

## 质量闸不过 = 不落库,保留旧版本

拿自托管模型覆盖已能用的音频有下行风险:模型回归会**静默**毁掉音频库,
而且不可逆(旧文件替换后成孤儿)。所以"生成了"不等于"能用"。
"""

import argparse
import json
import sys
from collections import Counter

sys.path.insert(0, "/app")

from app.core.database import SessionLocal  # noqa: E402
from app.models.content import (  # noqa: E402
    ObjectContentSection,
    ObjectSuggestedQuestion,
)
from app.models.museum_object import MuseumObject  # noqa: E402
from app.services.content_repo import audio_key  # noqa: E402
from app.services.enrichment.audio_quality import (  # noqa: E402
    check_audio,
    estimate_duration_sec,
)
from app.services.storage import get_object_storage  # noqa: E402


def _filename(qid: str, language: str, section: str) -> str:
    return f"{qid}__{language}__{section}.mp3"


def _source_text(db, obj_id, language: str, section: str) -> str | None:
    """质量闸要对照原文判断时长是否合理,所以必须取回文本。"""
    if section.startswith("qa_"):
        sort = int(section.split("_", 1)[1])
        row = (
            db.query(ObjectSuggestedQuestion)
            .filter_by(object_id=obj_id, language=language, sort=sort)
            .one_or_none()
        )
        return f"{row.question}\n\n{row.answer}" if row else None
    row = (
        db.query(ObjectContentSection)
        .filter_by(object_id=obj_id, language=language, section_code=section)
        .one_or_none()
    )
    return row.body if row else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", required=True, help="audio_queue_cli plan --json 的输出")
    ap.add_argument("--dir", required=True, help="音频文件目录")
    ap.add_argument("--engine", required=True, help="生成引擎标记,如 voxcpm2")
    ap.add_argument("--apply", action="store_true", help="真写(默认 dry-run)")
    ns = ap.parse_args()

    import pathlib

    jobs = json.load(open(ns.jobs))
    root = pathlib.Path(ns.dir)
    storage = get_object_storage()
    db = SessionLocal()
    stats = Counter()
    rejected: list[tuple[str, str]] = []

    try:
        for j in jobs:
            qid, lang, sec = j["qid"], j["language"], j["section"]
            f = root / _filename(qid, lang, sec)
            if not f.exists():
                stats["missing"] += 1
                continue

            obj = db.query(MuseumObject).filter_by(qid=qid).one_or_none()
            if not obj:
                stats["unknown_qid"] += 1
                continue

            data = f.read_bytes()
            text = _source_text(db, obj.id, lang, sec)

            # 替换场景:拿旧版本时长做偏差检查(最能抓住截断/重复/语速失控)
            prev_dur = None
            if sec.startswith("qa_"):
                sort = int(sec.split("_", 1)[1])
                row = (
                    db.query(ObjectSuggestedQuestion)
                    .filter_by(object_id=obj.id, language=lang, sort=sort)
                    .one_or_none()
                )
            else:
                row = (
                    db.query(ObjectContentSection)
                    .filter_by(object_id=obj.id, language=lang, section_code=sec)
                    .one_or_none()
                )
            if row is None:
                stats["no_row"] += 1
                continue
            if row.audio_engine == ns.engine:
                stats["already_done"] += 1  # 幂等:重跑无副作用
                continue
            if row.audio_key:
                old = storage.size(row.audio_key)
                if old:
                    prev_dur = estimate_duration_sec(old)

            verdict = check_audio(
                data, text=text or "", language=lang, previous_duration_sec=prev_dur
            )
            if not verdict.ok:
                stats["rejected"] += 1
                rejected.append((f"{qid}/{lang}/{sec}", verdict.reason))
                continue

            stats["ok"] += 1
            if not ns.apply:
                continue

            key = audio_key("object-audio", qid, lang, sec)
            storage.put(key, data, "audio/mpeg")  # 传成功才写 key
            row.audio_key = key
            row.audio_engine = ns.engine
            db.commit()
            stats["written"] += 1
    finally:
        db.close()

    print(f"引擎 {ns.engine} · 任务 {len(jobs)}")
    for k in (
        "ok",
        "written",
        "already_done",
        "rejected",
        "missing",
        "no_row",
        "unknown_qid",
    ):
        if stats[k]:
            print(f"  {k:14s} {stats[k]}")
    if rejected:
        print("\n未过质量闸(保留旧版本,不落库):")
        for name, reason in rejected[:20]:
            print(f"  {name:44s} {reason}")
        if len(rejected) > 20:
            print(f"  … 另有 {len(rejected)-20} 条")
    if not ns.apply:
        print("\n(dry-run。确认无误后加 --apply 真写)")
    return 1 if stats["rejected"] and not stats["ok"] else 0


if __name__ == "__main__":
    sys.exit(main())
