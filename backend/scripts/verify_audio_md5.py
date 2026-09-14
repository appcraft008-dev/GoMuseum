"""灌入后核对:R2 上的对象 md5 == 生成侧判定过的那一份。在 prod 容器内跑。

契约「音频批量生产与灌入」⑧-b 要求的第三条独立路径(前两条是 CLI 自报的 written
数、DB 各类计数)。**单看 CLI 的 written 不足以采信** —— 它只知道自己写了什么,
不知道 DB 和对象存储的终态。

## 两个设计点都是踩出来的

**用 md5 不是字节大小**(契约 ⑩):CBR mp3 换音色重灌前后字节数可以一模一样,
2026-08-31 用大小校验报"30 条一致、0 条不符",其中 3 条替换前后根本没验到。
**验证指标必须对你要验证的那个差异敏感,否则通过等于没验。**

**三张表都要查**:section / qa / artist_bio 的 audio_key 分别落在
ObjectContentSection / ObjectSuggestedQuestion / Artist.bio_audio。只查 section
会静默漏掉后两类 —— 2026-09-14 卢浮宫七语那批 285 条里有 90 条 qa、21 条 bio,
占 39%,旧版脚本对它们完全失明(而且报告照样全绿)。

**不要走 /content 端点验音频**:它按设计只返回 `has_audio` 布尔,从不下发
audio_url(付费墙,音频链走带鉴权的 /audio)。拿 audio_url 去验会得到一片假失败,
这个坑 2026-08 踩过两次。查 DB 的 audio_key + 对象存储,既绕开鉴权、验的又是
落库真相、还不受任何缓存干扰。

用法:
  # 生成机导出 {文件名: md5}(直接取 _state.json 里判定时记的那个 md5)
  python -c "import json;s=json.load(open('out/_state.json'));\
print(json.dumps({k:v['md5'] for k,v in s.items() if v.get('ok')}))" > md5s.json
  scp md5s.json vps:/tmp/ && ssh vps 'docker cp /tmp/md5s.json <容器>:/tmp/'
  ssh vps 'docker exec <容器> python /app/scripts/verify_audio_md5.py /tmp/md5s.json'

退出码 0 = 全部一致;1 = 有异常(名单打在上面)。
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter

sys.path.insert(0, "/app")

from app.core.database import SessionLocal  # noqa: E402
from app.models.artist import Artist  # noqa: E402
from app.models.content import (  # noqa: E402
    ObjectContentSection,
    ObjectSuggestedQuestion,
)
from app.models.museum_object import MuseumObject  # noqa: E402
from app.services.storage import get_object_storage  # noqa: E402


def kind_of(section: str) -> str:
    """段落类型 —— 决定去哪张表找 audio_key。与灌入端的分派口径一致。"""
    if section == "artist_bio":
        return "artist_bio"
    return "qa" if section.startswith("qa_") else "section"


def db_key(db, qid: str, language: str, section: str) -> str | None:
    """取该条在库里的 audio_key;取不到返回 None。

    ⚠️ artist_bio 的 qid 是**作者 qid**(音频按作者共享一份),不是作品 qid。
    """
    kind = kind_of(section)
    if kind == "artist_bio":
        art = db.query(Artist).filter_by(qid=qid).one_or_none()
        return (art.bio_audio or {}).get(language) if art else None
    obj = db.query(MuseumObject).filter_by(qid=qid).one_or_none()
    if obj is None:
        return None
    if kind == "qa":
        row = (
            db.query(ObjectSuggestedQuestion)
            .filter_by(
                object_id=obj.id, language=language, sort=int(section.split("_", 1)[1])
            )
            .one_or_none()
        )
    else:
        row = (
            db.query(ObjectContentSection)
            .filter_by(object_id=obj.id, language=language, section_code=section)
            .one_or_none()
        )
    return row.audio_key if row else None


def main() -> int:
    local: dict[str, str] = json.load(open(sys.argv[1]))
    db, storage = SessionLocal(), get_object_storage()
    ok = 0
    kinds: Counter[str] = Counter()
    bad: list[tuple[str, str]] = []
    try:
        for name, md5 in sorted(local.items()):
            qid, language, section = name[:-4].split("__")
            key = db_key(db, qid, language, section)
            if not key:
                bad.append((name, "库里无 audio_key"))
                continue
            try:
                data = storage.get(key)
            except Exception as exc:  # 取不到要说清是哪一类,别混进"md5 不符"
                bad.append((name, f"对象存储报错: {type(exc).__name__}"))
                continue
            if data is None:
                bad.append((name, "对象存储里没有这个 key"))
            elif hashlib.md5(data).hexdigest() != md5:
                bad.append((name, "md5 不符"))
            else:
                ok += 1
                kinds[kind_of(section)] += 1
    finally:
        db.close()

    print(f"逐条 md5 核对: {ok}/{len(local)} 通过")
    print(f"  按类: {dict(kinds)}")
    if bad:
        print(f"异常 {len(bad)} 条:")
        for name, reason in bad[:20]:
            print("  ", name, reason)
        if len(bad) > 20:
            print(f"  …… 另有 {len(bad) - 20} 条")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
