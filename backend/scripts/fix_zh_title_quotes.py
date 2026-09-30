"""存量修复:zh / zh-hant 正文与问答里用「」包住**本作品标题**的,改成《》。

来源是翻译 prompt 曾把规范名注入成 `「{title}」`(#567 已修根因),模型照抄成了标点模板。
其它语言 2026-09-14 已用 SQL 修过;中文当时留着,因为**繁体里「」本来就是正常引号**
(对话、引文),不能整体替换 —— 所以判据收窄到「」里恰好是这件作品自己在该语言的标题,
那正是注入污染的精确形状。其余「」一律不动。

**不碰 audio_key**:引号不发音,音频内容本身是对的(同 09-14 的判断)。
写入前把改动行的原文备份到 --backup(JSON),可按主键逐行还原。

用法(容器内):
    python scripts/fix_zh_title_quotes.py                                # dry-run
    python scripts/fix_zh_title_quotes.py --apply --backup /tmp/zh_quotes_backup.json
幂等:改过的行不再含「标题」,重跑为 0。
"""

import argparse
import json
import sys

sys.path.insert(0, "/app")

from app.core.database import SessionLocal  # noqa: E402
from app.models.content import (  # noqa: E402
    ObjectContentSection,
    ObjectSuggestedQuestion,
)
from app.models.museum_object import MuseumObject  # noqa: E402

LANGS = ("zh", "zh-hant")


def fix_text(text: str | None, title: str | None) -> str | None:
    if not text or not title:
        return text
    return text.replace(f"「{title}」", f"《{title}》")


def plan(db) -> list[tuple]:
    """[(row, {字段: 新值}, 有无音频)]。只读。"""
    out = []
    for model, fields in (
        (ObjectContentSection, ("body",)),
        (ObjectSuggestedQuestion, ("question", "answer")),
    ):
        rows = (
            db.query(model, MuseumObject.attributes)
            .join(MuseumObject, model.object_id == MuseumObject.id)
            .filter(model.language.in_(LANGS))
            .all()
        )
        for row, attrs in rows:
            title = ((attrs or {}).get("title_i18n") or {}).get(row.language)
            new = {f: fix_text(getattr(row, f), title) for f in fields}
            new = {f: v for f, v in new.items() if v != getattr(row, f)}
            if new:
                out.append((row, new, bool(row.audio_key)))
    return out


def apply(db, items, backup_path: str) -> None:
    backup = [
        {
            "table": row.__tablename__,
            "id": str(row.id),
            **{f: getattr(row, f) for f in new},
        }
        for row, new, _ in items
    ]
    with open(backup_path, "w") as f:
        json.dump(backup, f, ensure_ascii=False)
    for row, new, _ in items:
        for f, v in new.items():
            setattr(row, f, v)  # 只改文本;audio_key 原样保留
    db.commit()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--backup", help="--apply 时必填:改动前原文备份 JSON 路径")
    a = p.parse_args()
    if a.apply and not a.backup:
        raise SystemExit("--apply 必须带 --backup")
    db = SessionLocal()
    items = plan(db)
    for lang in LANGS:
        for model in (ObjectContentSection, ObjectSuggestedQuestion):
            sel = [
                i for i in items if isinstance(i[0], model) and i[0].language == lang
            ]
            print(
                f"{lang:8s} {model.__tablename__:28s} {len(sel):5d} 行"
                f"(其中有音频 {sum(i[2] for i in sel)},音频保留不作废)"
            )
    if a.apply:
        apply(db, items, a.backup)
        print(f"已写入 {len(items)} 行;原文备份在 {a.backup}")
    else:
        print("dry-run(加 --apply --backup <路径> 生效)")
