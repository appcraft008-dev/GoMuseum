"""存量音频改用不可推测 key(2026-07-27,付费墙前提)。

旧 key `object-audio/{qid}/{lang}/{section}.mp3` 可由 qid 直接拼出 —— 而 R2 的公开
dev URL 是整桶级的(图片必须公开),于是任何人都能绕过鉴权直取音频(实测 HTTP 200)。
本脚本把存量对象在 R2 里复制到新随机 key、更新 DB、删旧对象。

幂等:已是新格式(带 `-<token>.mp3`)的跳过。失败的留旧 key,重跑再试。

用法(容器内):
  python scripts/rekey_audio.py            # dry-run
  python scripts/rekey_audio.py --apply
"""

import re
import sys

sys.path.insert(0, "/app")

from app.core.database import SessionLocal  # noqa: E402
from app.models.content import (  # noqa: E402
    ObjectContentSection,
    ObjectSuggestedQuestion,
)
from app.services.content_repo import audio_key  # noqa: E402
from app.services.storage import get_object_storage  # noqa: E402

# 新格式:最后一段是 `<name>-<token>.mp3`,token 至少 16 位 urlsafe
_NEW = re.compile(r"-[A-Za-z0-9_-]{16,}\.mp3$")


def _rekey(storage, old: str) -> str | None:
    """复制到新 key 并删旧。返回新 key;失败返回 None(留旧的,重跑再试)。"""
    stem = re.sub(r"\.mp3$", "", old)
    new = audio_key(*stem.split("/"))
    data = storage.get(old)
    if not data:
        return None
    storage.put(new, data, "audio/mpeg")
    try:
        storage.delete(old)
    except Exception:
        pass  # 删不掉只是留个孤儿文件,不影响正确性
    return new


def main(apply: bool) -> None:
    db = SessionLocal()
    storage = get_object_storage()
    done = skipped = failed = 0
    for model in (ObjectContentSection, ObjectSuggestedQuestion):
        for row in db.query(model).filter(model.audio_key.isnot(None)):
            if _NEW.search(row.audio_key):
                skipped += 1
                continue
            if not apply:
                done += 1
                continue
            new = _rekey(storage, row.audio_key)
            if new:
                row.audio_key = new
                done += 1
            else:
                failed += 1
        if apply:
            db.commit()
    mode = "已迁移" if apply else "dry-run(加 --apply 生效)"
    print(f"{mode}: 改key {done} | 已是新格式跳过 {skipped} | 失败 {failed}")


if __name__ == "__main__":
    main("--apply" in sys.argv)
