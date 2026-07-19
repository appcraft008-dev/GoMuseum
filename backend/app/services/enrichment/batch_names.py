"""names 的 Batch 模式(成本工程②,spec 2026-07-19-batch-names)。
collect 同步抓权威标签当场落库(部分进度不怕 batch 失败),仅缺的出翻译任务;
submit/poll/apply 走 OpenAI Batch(半价);apply 剥号+只补缺+分批 commit。
失败行=仍缺→幂等重跑,零新机制。"""

from __future__ import annotations

import io
import json
import logging
import time
from dataclasses import dataclass

from app.services.enrichment.translator import strip_name
from app.services.llm_usage import record_llm_usage

logger = logging.getLogger(__name__)

MODEL = "gpt-4o"
USAGE_MODEL = "gpt-4o@batch"


@dataclass
class BatchTask:
    custom_id: str  # "<title|artist>|<key>|<lang>"
    name: str  # 待翻译的轴心名
    lang: str


def collect_missing(db, slug, langs, *, fetch_labels=None, limit=None):
    from app.models.artist import Artist
    from app.models.museum import Museum
    from app.models.museum_object import MuseumObject
    from app.services.enrichment.backfill import _clean_i18n
    from app.services.enrichment.material import fetch_wikidata_labels

    fetch_labels = fetch_labels or fetch_wikidata_labels
    m = db.query(Museum).filter_by(slug=slug).one_or_none()
    if not m:
        return []
    objs = db.query(MuseumObject).filter_by(museum_id=m.id).all()
    if limit:
        objs = objs[:limit]
    tasks: list[BatchTask] = []
    artist_qids: set = set()
    for i, o in enumerate(objs):
        attrs = dict(o.attributes or {})
        ti = _clean_i18n(attrs.get("title_i18n"))
        if aq := attrs.get("artist_qid"):
            artist_qids.add(aq)
        missing = [lg for lg in langs if not ti.get(lg)]
        if missing:
            try:
                labels = fetch_labels(o.qid, langs)
            except Exception:  # 单件网络失败跳过(纪律①),重跑再补
                continue
            for lg in langs:
                if not ti.get(lg) and labels.get(lg):
                    ti[lg] = labels[lg]  # 权威当场落库
            if o.title_en and not ti.get("en"):
                ti["en"] = o.title_en
            o.attributes = {**attrs, "title_i18n": ti}
            pivot = ti.get("en") or next((ti[x] for x in langs if ti.get(x)), None)
            if pivot:
                for lg in langs:
                    if not ti.get(lg):
                        tasks.append(BatchTask(f"title|{o.qid}|{lg}", pivot, lg))
        if (i + 1) % 200 == 0:
            db.commit()  # 分批落盘(纪律②)
    for aq in sorted(artist_qids):
        art = db.query(Artist).filter_by(qid=aq).first()
        if not art:
            continue
        ni = _clean_i18n(art.name_i18n)
        pivot = ni.get("en") or art.name_en
        if not pivot:
            continue
        if art.name_en and not ni.get("en"):
            ni["en"] = art.name_en
            art.name_i18n = ni
        for lg in langs:
            if lg != "en" and not ni.get(lg):
                tasks.append(BatchTask(f"artist|{aq}|{lg}", pivot, lg))
    db.commit()
    return tasks


def _jsonl(tasks):
    from app.services.enrichment.prompts import build_name_translation_prompt

    lines = []
    for t in tasks:
        system, user = build_name_translation_prompt(t.name, t.lang)
        lines.append(
            json.dumps(
                {
                    "custom_id": t.custom_id,
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": {
                        "model": MODEL,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                        "temperature": 0.3,
                    },
                },
                ensure_ascii=False,
            )
        )
    return "\n".join(lines)


def submit(tasks, client) -> str:
    f = client.files.create(file=io.BytesIO(_jsonl(tasks).encode()), purpose="batch")
    b = client.batches.create(
        input_file_id=f.id,
        endpoint="/v1/chat/completions",
        completion_window="24h",
    )
    return b.id


def poll(job_id, client, interval=60):
    while True:
        b = client.batches.retrieve(job_id)
        if b.status == "completed":
            text = client.files.content(b.output_file_id).text
            return [json.loads(x) for x in text.splitlines() if x.strip()]
        if b.status in ("failed", "expired", "cancelled"):
            raise RuntimeError(f"batch {job_id} 终态 {b.status}")
        logger.info("batch %s status=%s,继续等待", job_id, b.status)
        time.sleep(interval)


def apply(db, lines) -> dict:
    from app.models.artist import Artist
    from app.models.museum_object import MuseumObject

    applied = skipped = 0
    for i, ln in enumerate(lines):
        try:
            cid = ln["custom_id"]
            body = (ln.get("response") or {}).get("body") or {}
            text = strip_name(body["choices"][0]["message"]["content"])
            if not text:
                raise ValueError("empty")
            etype, key, lang = cid.split("|", 2)
            u = body.get("usage") or {}
            record_llm_usage(
                "names",
                USAGE_MODEL,
                u.get("prompt_tokens", 0),
                u.get("completion_tokens", 0),
            )
            if etype == "title":
                o = db.query(MuseumObject).filter_by(qid=key).one_or_none()
                if o is None:
                    raise ValueError("no object")
                ti = dict((o.attributes or {}).get("title_i18n") or {})
                if not ti.get(lang):  # 只补缺不覆盖
                    ti[lang] = text
                    o.attributes = {**(o.attributes or {}), "title_i18n": ti}
            else:
                a = db.query(Artist).filter_by(qid=key).one_or_none()
                if a is None:
                    raise ValueError("no artist")
                ni = dict(a.name_i18n or {})
                if not ni.get(lang):
                    ni[lang] = text
                    a.name_i18n = ni
            applied += 1
        except Exception:
            skipped += 1  # 坏行=仍缺→幂等重跑再补(纪律①)
        if (i + 1) % 200 == 0:
            db.commit()
    db.commit()
    return {"applied": applied, "skipped": skipped}


def save_state(path, job_id, task_count):
    with open(path, "w") as f:
        json.dump({"job_id": job_id, "task_count": task_count, "at": time.time()}, f)


def load_state(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def run(
    db,
    slug,
    langs,
    *,
    client=None,
    limit=None,
    job_id=None,
    state_path=None,
    poll_interval=60,
) -> dict:
    if client is None:
        from openai import OpenAI

        from app.core.config import settings

        client = OpenAI(api_key=settings.OPENAI_API_KEY)
    state_path = state_path or f"/tmp/{slug}_names_batch.json"
    if job_id is None:
        tasks = collect_missing(db, slug, langs, limit=limit)
        if not tasks:
            return {"tasks": 0, "applied": 0, "skipped": 0}
        job_id = submit(tasks, client)
        save_state(state_path, job_id, len(tasks))
        logger.info("batch %s 已提交 %d 任务(状态: %s)", job_id, len(tasks), state_path)
    lines = poll(job_id, client, interval=poll_interval)
    out = apply(db, lines)
    out["tasks"] = len(lines)
    out["job_id"] = job_id
    return out
