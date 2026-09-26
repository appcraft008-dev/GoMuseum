"""每日音频盘点(契约纪律 37 第③层):已挂音频的条数只该涨,不该无声地掉。

## 为什么需要

2026-09-14 那次 `--force` 把 4 位跨馆作者的简介音频从库里脱钩,**12 天没人发现**,
直到用户点播放觉得「不像之前秒播」—— 而那时原文已过备份保留期。
音频损失闸(第①层)拦的是**走 ORM 的写入**;psql 手写 UPDATE、批量语句、以后漏接闸的
新代码都拦不住。这里从结果侧兜底:每天把「每个音频槽位挂着哪个 key」记一份,和前一天比。

## 什么算损失

槽位 = (段 | 问答 | 作者简介) × 语种。**昨天有 key、今天没有**才算损失;
换成另一个 key(tts-1 → VoxCPM2 重录)是升级,不算。
损失再分两类:
- **已登记**:`audio_invalidations` 里有这个 key —— 走了闸、有人放行过,但仍要告知
- **来源不明**:台账里没有 —— 有写入**绕过了闸**,最高级别

## 运行

cron 在每日 pg_dump 之后跑(见 deployment/production/backup.sh):
  docker exec gomuseum_prod_backend python -m scripts.audio_inventory
退出码:0 无损失 | 1 有损失且已发告警 | 2 有损失但告警发不出去(未配置/发信失败)
快照存 R2 `ops-inventory/`(不依赖 VPS 本地文件)。首次运行只建基线。
"""

from __future__ import annotations

import collections
import gzip
import json
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/app")

LATEST = "ops-inventory/latest.json.gz"


def collect(db) -> dict:
    """{slot: {"key", "engine", "museum", "label"}}。"""
    from app.models.artist import Artist
    from app.models.content import ObjectContentSection, ObjectSuggestedQuestion
    from app.models.museum import Museum
    from app.models.museum_object import MuseumObject

    museum_of = {
        oid: slug
        for oid, slug in db.query(MuseumObject.id, Museum.slug).join(
            Museum, Museum.id == MuseumObject.museum_id
        )
    }
    qid_of = dict(db.query(MuseumObject.id, MuseumObject.qid))
    slots: dict = {}
    for r in db.query(ObjectContentSection).filter(
        ObjectContentSection.audio_key.isnot(None)
    ):
        slots[f"section|{r.object_id}|{r.language}|{r.section_code}"] = dict(
            key=r.audio_key,
            engine=r.audio_engine,
            museum=museum_of.get(r.object_id),
            label=f"{qid_of.get(r.object_id)} {r.language} {r.section_code}",
        )
    for r in db.query(ObjectSuggestedQuestion).filter(
        ObjectSuggestedQuestion.audio_key.isnot(None)
    ):
        slots[f"qa|{r.object_id}|{r.language}|{r.sort}"] = dict(
            key=r.audio_key,
            engine=r.audio_engine,
            museum=museum_of.get(r.object_id),
            label=f"{qid_of.get(r.object_id)} {r.language} qa#{r.sort}",
        )
    for a in db.query(Artist).filter(Artist.bio_audio.isnot(None)):
        for lang, key in (a.bio_audio or {}).items():
            if key:
                slots[f"artist|{a.qid}|{lang}"] = dict(
                    key=key,
                    engine=(a.bio_audio_engine or {}).get(lang),
                    museum="(跨馆作者)",
                    label=f"{a.name_en or a.qid} {lang} 简介",
                )
    return slots


def diff(prev: dict, now: dict, ledger_keys: set) -> dict:
    """昨天有 key、今天没有的槽位 → 损失;按是否在失效台账里分两类。"""
    lost = [(s, v) for s, v in prev.items() if s not in now]
    explained = [(s, v) for s, v in lost if v["key"] in ledger_keys]
    unexplained = [(s, v) for s, v in lost if v["key"] not in ledger_keys]
    return {"explained": explained, "unexplained": unexplained}


def _totals(slots: dict) -> collections.Counter:
    return collections.Counter(
        (s.split("|", 1)[0], v.get("engine") or "?") for s, v in slots.items()
    )


def render(prev: dict, now: dict, d: dict, prev_at: str) -> tuple[str, str]:
    n_un, n_ex = len(d["unexplained"]), len(d["explained"])
    if n_un:
        subject = f"⛔ GoMuseum 音频盘点:{n_un} 条来源不明的音频损失(绕过了音频损失闸)"
    else:
        subject = f"⚠️ GoMuseum 音频盘点:{n_ex} 条已登记的音频失效"
    lines = [
        f"对比基线:{prev_at}  →  现在:{datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC",
        f"挂着的音频:{len(prev)} → {len(now)}",
        "",
    ]
    for title, items in (
        ("来源不明(台账里没有 —— 有写入绕过了闸,优先查)", d["unexplained"]),
        ("已登记(audio_invalidations 有记录,可按台账挂回)", d["explained"]),
    ):
        if not items:
            continue
        lines.append(f"## {title}:{len(items)} 条")
        by = collections.Counter((v["museum"], s.split("|", 1)[0]) for s, v in items)
        for (museum, kind), c in by.most_common():
            lines.append(f"  {museum} / {kind}: {c}")
        for s, v in items[:30]:
            lines.append(f"    - {v['label']} ({v.get('engine')}) {v['key']}")
        if len(items) > 30:
            lines.append(f"    … 另有 {len(items) - 30} 条")
        lines.append("")
    lines.append("按引擎统计(今天):")
    for (kind, eng), c in sorted(_totals(now).items()):
        lines.append(f"  {kind:8s} {eng:8s} {c}")
    lines.append("")
    lines.append(
        "恢复:已登记的按 audio_invalidations(key + old_text)挂回;"
        "来源不明的查当天的 psql/批量语句,并用每日 pg_dump 按主键逐字段恢复(纪律 37 ④)。"
    )
    return subject, "\n".join(lines)


def main() -> int:
    from app.core.config import settings
    from app.core.database import SessionLocal
    from app.models.audio_invalidation import AudioInvalidation
    from app.services import mailer
    from app.services.storage import get_object_storage

    st = get_object_storage()
    db = SessionLocal()
    try:
        now = collect(db)
        raw = st.get(LATEST)
        prev_doc = json.loads(gzip.decompress(raw)) if raw else None
        ledger = (
            {
                k
                for (k,) in db.query(AudioInvalidation.audio_key).filter(
                    AudioInvalidation.created_at
                    >= datetime.fromisoformat(prev_doc["at"]).replace(tzinfo=None)
                )
            }
            if prev_doc
            else set()
        )
    finally:
        db.close()

    stamp = datetime.now(timezone.utc)
    doc = {"at": stamp.isoformat(), "slots": now}
    blob = gzip.compress(json.dumps(doc, ensure_ascii=False).encode("utf-8"))
    st.put(f"ops-inventory/{stamp:%Y%m%d}.json.gz", blob, "application/gzip")

    if prev_doc is None:
        st.put(LATEST, blob, "application/gzip")
        print(f"首次运行:建立基线,挂着的音频 {len(now)} 条")
        return 0

    d = diff(prev_doc["slots"], now, ledger)
    print(
        f"挂着的音频 {len(prev_doc['slots'])} → {len(now)};"
        f"损失:来源不明 {len(d['unexplained'])},已登记 {len(d['explained'])}"
    )
    if not d["unexplained"] and not d["explained"]:
        st.put(LATEST, blob, "application/gzip")
        return 0

    subject, body = render(prev_doc["slots"], now, d, prev_doc["at"])
    print(subject)
    print(body)
    to = getattr(settings, "OPS_ALERT_EMAIL", None)
    try:
        if not to:
            raise mailer.MailNotConfigured("OPS_ALERT_EMAIL 未配置")
        mailer.send(to, subject, body)
    except Exception as e:
        # 发不出去就**不推进基线**:明天再比时这批损失还在,不会因为「今天没发出去」被吞掉
        print(f"❌ 告警发送失败:{e}(基线未推进,明天会再报一次)")
        return 2
    st.put(LATEST, blob, "application/gzip")
    print(f"✓ 告警已发送至 {to}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
