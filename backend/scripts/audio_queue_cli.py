"""音频生成队列 CLI —— 给自托管批量生成(VoxCPM2)消费。

**本脚本不生成音频**,只回答"该生成哪些、按什么顺序"。生成侧读它的 JSON 输出,
生成完调质量闸,过闸才落库。分工清楚,两边不打架。

用法:
  # 看覆盖率(迁移进度不该靠猜)
  python scripts/audio_queue_cli.py coverage --langs zh,en,fr

  # 出队列:先只做 zh、先做一个馆(保证一次参观内部音色一致)
  python scripts/audio_queue_cli.py plan --langs zh --engine voxcpm2 \\
      --museum louvre --limit 500 --json

  # 只补缺失、不做音色升级(冷启动阶段最该先跑这个)
  python scripts/audio_queue_cli.py plan --langs zh --engine voxcpm2 --no-upgrades
"""

import argparse
import json
import sys
from collections import Counter

sys.path.insert(0, "/app")

from app.core.database import SessionLocal  # noqa: E402
from app.services.enrichment.audio_queue import (  # noqa: E402
    build_queue,
    coverage,
)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("coverage")
    c.add_argument("--langs", default="zh")

    p = sub.add_parser("plan")
    p.add_argument("--langs", default="zh")
    p.add_argument("--engine", default="voxcpm2", help="目标引擎")
    p.add_argument("--museum", default=None, help="限定单馆(建议:整馆整语言推进)")
    p.add_argument("--head", type=int, default=2000, help="头部件数量(全段预生成)")
    p.add_argument("--limit", type=int, default=5000)
    p.add_argument("--no-upgrades", action="store_true", help="只补缺失,不做音色升级")
    p.add_argument("--json", action="store_true")

    ns = ap.parse_args()
    langs = [x.strip() for x in ns.langs.split(",") if x.strip()]
    db = SessionLocal()
    try:
        if ns.cmd == "coverage":
            cov = coverage(db, langs)
            titles = {
                "guide": "主讲解段(guide)",
                "artist_bio": "作者介绍(按作者共享,一条影响该作者所有作品)",
            }
            for kind in ("guide", "artist_bio"):
                by_lang = cov.get(kind)
                if not by_lang:
                    continue
                print(f"{titles.get(kind, kind)}音频覆盖率 —— 按语言 × 引擎")
                for lang, d in sorted(by_lang.items()):
                    total = sum(d.values())
                    parts = "  ".join(f"{k}={v}" for k, v in sorted(d.items()))
                    print(f"  {lang:8s} 共 {total:6d}   {parts}")
                print()
            return

        jobs = build_queue(
            db,
            languages=langs,
            target_engine=ns.engine,
            head_size=ns.head,
            museum_slug=ns.museum,
            include_upgrades=not ns.no_upgrades,
            limit=ns.limit,
        )
        if ns.json:
            print(
                json.dumps(
                    [
                        {
                            "qid": j.qid,
                            "language": j.language,
                            "section": j.section,
                            "kind": j.kind,
                            "museum": j.museum_slug,
                            "reason": j.reason,
                            "priority": j.priority,
                        }
                        for j in jobs
                    ],
                    ensure_ascii=False,
                )
            )
            return
        by_reason = Counter(j.reason for j in jobs)
        print(f"待生成 {len(jobs)} 个单元(目标引擎 {ns.engine})")
        for r, n in by_reason.most_common():
            note = {
                "hero_missing": "主讲解缺音频 —— 最急,它是识别后自动播的",
                "head_full": "头部件的深度段/问答",
                "engine_upgrade": "已有音频但引擎不符(音色统一)",
            }.get(r, "")
            print(f"  {r:16s} {n:6d}  {note}")
        print("\n前 10 条:")
        for j in jobs[:10]:
            print(
                f"  [{j.priority:3d}] {j.museum_slug}/{j.qid} {j.language} {j.section}"
            )
    finally:
        db.close()


if __name__ == "__main__":
    main()
