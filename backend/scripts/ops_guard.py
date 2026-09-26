"""staging 轻量化护栏(spec 2026-07-17):staging 永不为数据规模付 LLM 费。
机制验证=小样本;规模数据用 sync_staging_from_prod.py 从 prod 搬运,别重算。"""

STAGING_SAMPLE_LIMIT = 50
_HINT = "(全量请 --allow-full;规模数据用 sync_staging_from_prod.py 搬运,别重算)"


def staging_limit(target, limit, allow_full):
    """带 LLM 的批命令:staging 默认收紧到小样本;prod/显式 allow_full 原样返回。"""
    if target != "staging" or allow_full:
        return limit
    if limit is None or limit > STAGING_SAMPLE_LIMIT:
        print(f"⚠️ staging 护栏:limit → {STAGING_SAMPLE_LIMIT} {_HINT}")
        return STAGING_SAMPLE_LIMIT
    return limit


def staging_require_allow_full(target, allow_full):
    """无 limit 概念的全库 LLM 脚本(rescan 系):staging 必须显式确认。"""
    if target == "staging" and not allow_full:
        raise SystemExit(f"❌ staging 护栏:全库 LLM 操作需显式 --allow-full {_HINT}")


# ─── 契约纪律 37:跑 prod 批命令前的「写入面清单 + 快照 + 音频放行」 ────────────────
#
# 2026-09-14 / 09-26 两次 `generate --force` 顺带改写跨馆作者、清掉简介音频;
# 动手前只备份了「以为在改的」作品表。这里把纪律 37 的 ②③④ 变成命令开跑前自动做的事:
#   ② 按**代码实际会写的表**列出写入面,并数清其中**已有音频**的条数
#   ③ 快照这些行到 R2(不依赖 VPS 本地备份;保留期不受每日 pg_dump 轮转影响)
#   ① 的放行额度(--allow-audio-loss N)由这里交给 audio_guard


def apply_audio_loss_allowance(n) -> None:
    """--allow-audio-loss N:本进程最多允许 N 条已有音频失效(默认 0 = 一条都不许)。"""
    from app.services import audio_guard

    if n:
        audio_guard.allow(n)
        print(
            f"⚠️ 音频损失闸:本次显式放行最多 {n} 条已有音频失效(会记入 audio_invalidations)"
        )


def _rows(db, model, *filters) -> list[dict]:
    cols = [c.name for c in model.__table__.columns]
    return [
        {c: getattr(r, c) for c in cols} for r in db.query(model).filter(*filters).all()
    ]


def write_surface_and_snapshot(db, label: str, object_ids: list) -> dict:
    """打印写入面清单(纪律 37 ②),并把这批对象会被写到的行快照进 R2(④)。

    写入面按 generate/translate 的实际写路径列:object_content_sections、
    object_suggested_questions、artists(**跨馆共享**,只会补缺,但照样快照)。
    返回摘要;快照失败直接抛 —— 没有快照就不该开跑。
    """
    import gzip
    import json
    from datetime import datetime, timezone

    from app.models.artist import Artist
    from app.models.content import ObjectContentSection, ObjectSuggestedQuestion
    from app.models.museum_object import MuseumObject
    from app.services.storage import get_object_storage

    ids = list(object_ids)
    secs = _rows(db, ObjectContentSection, ObjectContentSection.object_id.in_(ids))
    qas = _rows(db, ObjectSuggestedQuestion, ObjectSuggestedQuestion.object_id.in_(ids))
    aqids = {
        (o.attributes or {}).get("artist_qid")
        for o in db.query(MuseumObject).filter(MuseumObject.id.in_(ids))
    } - {None}
    arts = _rows(db, Artist, Artist.qid.in_(aqids)) if aqids else []
    summary = {
        "objects": len(ids),
        "sections": len(secs),
        "sections_with_audio": sum(1 for r in secs if r["audio_key"]),
        "qa": len(qas),
        "qa_with_audio": sum(1 for r in qas if r["audio_key"]),
        "artists_shared": len(arts),
        "artist_bio_audio": sum(len(r["bio_audio"] or {}) for r in arts),
    }
    print(
        "📋 写入面清单(纪律 37):"
        f" 作品 {summary['objects']} | 段 {summary['sections']}"
        f"(已有音频 {summary['sections_with_audio']})"
        f" | 问答 {summary['qa']}(已有音频 {summary['qa_with_audio']})"
        f" | 跨馆共享作者 {summary['artists_shared']}"
        f"(简介音频 {summary['artist_bio_audio']} 条,只补缺不覆盖)"
    )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    from app.core.config import settings

    # staging 与 prod 共用一个 R2 桶 —— 按环境分目录,别让 staging 的快照混进 prod 的
    key = f"ops-snapshots/{settings.ENVIRONMENT}/{stamp}_{label}.json.gz"
    payload = {
        "label": label,
        "created_at": stamp,
        "summary": summary,
        "object_content_sections": secs,
        "object_suggested_questions": qas,
        "artists": arts,
    }
    data = gzip.compress(
        json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    )
    get_object_storage().put(key, data, "application/gzip")
    summary["snapshot_key"] = key
    print(f"💾 已快照到 R2: {key}({len(data) / 1e6:.1f} MB)")
    return summary
