"""R2 孤儿音频回收 —— 离线对账,**默认只报不删**。

## 孤儿从哪来

1. 正文更新 → `audio_key = None`(音频失效),但 R2 文件留着
2. 引擎升级替换 → 写入新 key,旧文件留着

单件时可忽略($0.3/月),但**批量迁移到自托管 TTS 会把量级放大几个数量级**
(全量替换 ≈ 每段都留一个孤儿)。

## 为什么是离线对账,不是失效时即时删

失效那一刻可能有客户端**正拿着旧 URL 播放**(直链取自 R2,我们无从知晓)。
即时删 = 正在听的人音频中断。离线 + 宽限期让在途播放自然结束。

## 安全护栏(比功能本身重要 —— 这是不可逆删除)

- **默认 dry-run**,必须显式 `--apply` 才真删
- **宽限期**(默认 7 天):比宽限期新的对象一律不动,覆盖在途播放与
  "刚写入但事务尚未提交"的竞态
- **引用集合为空则中止**:DB 查询出错/连错库会让"引用集合"变空,
  照删就是清空整个音频库。宁可不删
- **删除比例上限**:一次删掉超过总量 [--max-ratio] 的对象则中止并要求人工确认
- 先列 R2 再读 DB:列举期间新写入的 key 必定已在 DB 里,不会被误判

用法:
  python scripts/gc_orphan_audio.py                    # 只报告
  python scripts/gc_orphan_audio.py --apply --grace-days 7
"""

import argparse
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/app")

from app.core.database import SessionLocal  # noqa: E402
from app.models.artist import Artist  # noqa: E402
from app.models.content import (  # noqa: E402
    ObjectContentSection,
    ObjectSuggestedQuestion,
)
from app.services.storage import get_object_storage  # noqa: E402

AUDIO_PREFIX = "object-audio/"


def referenced_keys(db) -> set[str]:
    """DB 里**所有**在用的音频 key。

    ⚠️ 音频 key 存在三个地方,漏一个就会删掉正在用的文件:
      1. object_content_sections.audio_key
      2. object_suggested_questions.audio_key
      3. artists.bio_audio —— **{lang: key} 的 JSON**,最容易漏
    """
    keys: set[str] = set()
    for (k,) in db.query(ObjectContentSection.audio_key).filter(
        ObjectContentSection.audio_key.isnot(None)
    ):
        keys.add(k)
    for (k,) in db.query(ObjectSuggestedQuestion.audio_key).filter(
        ObjectSuggestedQuestion.audio_key.isnot(None)
    ):
        keys.add(k)
    for (d,) in db.query(Artist.bio_audio).filter(Artist.bio_audio.isnot(None)):
        for v in (d or {}).values():
            if v:
                keys.add(v)
    return keys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真删(默认只报告)")
    ap.add_argument("--grace-days", type=int, default=7)
    ap.add_argument(
        "--max-ratio",
        type=float,
        default=0.5,
        help="一次删除占比上限,超过则中止(防对账逻辑出错清库)",
    )
    ns = ap.parse_args()

    storage = get_object_storage()
    cutoff = datetime.now(timezone.utc) - timedelta(days=ns.grace_days)

    # 先列 R2:列举期间新写入的 key 必然已进 DB,下面读 DB 时会被算作已引用
    objects = list(storage.list_keys(AUDIO_PREFIX))
    if not objects:
        print("R2 上没有音频对象,无事可做")
        return 0

    db = SessionLocal()
    try:
        refs = referenced_keys(db)
    finally:
        db.close()

    # ⚠️ 引用集合为空 = 大概率是 DB 查询出错或连错库。照删就是清空音频库。
    if not refs:
        print(
            f"❌ 中止:DB 里一个音频引用都没查到,而 R2 上有 {len(objects)} 个对象。\n"
            "   这几乎一定是查询出错或连错库,不是真的全成孤儿。"
        )
        return 1

    orphans, kept_young = [], 0
    for key, size, mtime in objects:
        if key in refs:
            continue
        if isinstance(mtime, datetime) and mtime > cutoff:
            kept_young += 1  # 宽限期内:可能有人正拿着旧 URL 在播
            continue
        orphans.append((key, size))

    total_mb = sum(s for _, s in orphans) / 1e6
    ratio = len(orphans) / len(objects)
    print(f"R2 音频对象 {len(objects)} 个,DB 引用 {len(refs)} 个")
    print(f"宽限期内跳过 {kept_young} 个(<{ns.grace_days} 天,可能有人在播)")
    print(f"孤儿 {len(orphans)} 个 / {total_mb:.1f} MB(占比 {ratio:.1%})")
    for k, s in orphans[:10]:
        print(f"  {k}  {s/1e6:.2f} MB")
    if len(orphans) > 10:
        print(f"  … 另有 {len(orphans)-10} 个")

    if not orphans:
        return 0
    if ratio > ns.max_ratio:
        print(
            f"\n❌ 中止:孤儿占比 {ratio:.1%} 超过上限 {ns.max_ratio:.0%}。\n"
            "   正常情况不该有这么多 —— 先确认对账逻辑没问题,"
            "确认无误再调高 --max-ratio。"
        )
        return 1
    if not ns.apply:
        print("\n(dry-run。确认无误后加 --apply 真删)")
        return 0

    deleted = 0
    for key, _ in orphans:
        try:
            storage.delete(key)
            deleted += 1
        except Exception as e:  # 单个失败不该中断整轮
            print(f"  删除失败 {key}: {e}")
    print(f"\n✅ 已删除 {deleted}/{len(orphans)} 个,回收约 {total_mb:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
