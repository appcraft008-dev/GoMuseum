"""存量修复:英文 guide 最后一句在讲「现藏于本馆」→ 删掉那一句(与生成侧 drop_museum_ending 同一判据)。

写入走 `_upsert_section`:英文正文变了 → 同段译文降级 needs_review、该段 audio_key 清空
(契约纪律 33)。之后跑 `onboard translate --langs <其余语种>` 从新英文重翻补回。
音频损失闸照常生效:会作废已有音频就被拦下(dry-run 会先报出条数)。

用法(容器内):
    python scripts/fix_guide_museum_ending.py --museum petit_palais           # dry-run
    python scripts/fix_guide_museum_ending.py --museum petit_palais --apply
幂等:删过的段最后一句已不提本馆,重跑为 0。
"""

import argparse
import sys

sys.path.insert(0, "/app")

from app.core.database import SessionLocal  # noqa: E402
from app.models.content import ObjectContentSection  # noqa: E402
from app.models.museum import Museum  # noqa: E402
from app.models.museum_object import MuseumObject  # noqa: E402
from app.services.content_repo import _upsert_section  # noqa: E402
from app.services.enrichment.quality import drop_museum_ending  # noqa: E402
from app.services.museum_repo import museum_name  # noqa: E402


def plan(db, slug: str) -> list[tuple]:
    """[(obj, en_row, new_body, 会作废的音频条数)]。只读。"""
    m = db.query(Museum).filter_by(slug=slug).one_or_none()
    if m is None:
        raise SystemExit(f"museum not found: {slug}")
    name = museum_name(m, "en")
    out = []
    rows = (
        db.query(ObjectContentSection, MuseumObject)
        .join(MuseumObject, ObjectContentSection.object_id == MuseumObject.id)
        .filter(
            MuseumObject.museum_id == m.id,
            ObjectContentSection.language == "en",
            ObjectContentSection.section_code == "guide",
            ObjectContentSection.status == "published",
        )
        .all()
    )
    for row, obj in rows:
        new = drop_museum_ending(row.body, name)
        if new == row.body:
            continue
        # 作废面:英文 guide 本身 + 会被降级的各语种已发布 guide 译文
        audio = (
            db.query(ObjectContentSection)
            .filter(
                ObjectContentSection.object_id == obj.id,
                ObjectContentSection.section_code == "guide",
                ObjectContentSection.status == "published",
                ObjectContentSection.audio_key.isnot(None),
            )
            .count()
        )
        out.append((obj, row, new, audio))
    return out


def apply(db, items) -> None:
    for obj, row, new, _ in items:
        _upsert_section(
            db, obj, "en", "guide", new, "published", row.model, row.grounding_ratio
        )
    db.commit()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--museum", required=True)
    p.add_argument("--apply", action="store_true")
    a = p.parse_args()
    db = SessionLocal()
    items = plan(db, a.museum)
    for obj, row, new, audio in items:
        print(f"{obj.qid}  音频 {audio}  删: {row.body[len(new):].strip()}")
    n_audio = sum(i[3] for i in items)
    print(
        f"\n{a.museum}: {len(items)} 件英文 guide 要删最后一句;"
        f"同件 guide 各语种会作废音频 {n_audio} 条"
    )
    if a.apply:
        apply(db, items)
        print("已写入。下一步: onboard translate --langs <其余语种> 重翻 guide")
    else:
        print("dry-run(加 --apply 生效)")
