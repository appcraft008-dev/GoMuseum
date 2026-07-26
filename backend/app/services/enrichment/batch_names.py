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
MAX_BATCH_REQUESTS = 50_000  # OpenAI Batch 单 job 硬上限,超了提交即拒(不是软限流)
USAGE_MODEL = "gpt-4o@batch"


@dataclass
class BatchTask:
    custom_id: str  # "<title|artist>|<key>|<lang>"
    name: str  # 待翻译的轴心名
    lang: str


def collect_missing(
    db, slug, langs, *, fetch_labels=None, fetch_creators=None, limit=None
):
    from app.models.artist import Artist
    from app.models.museum import Museum
    from app.models.museum_object import MuseumObject
    from app.services.enrichment.backfill import _clean_i18n, _fetch_creators
    from app.services.enrichment.material import fetch_wikidata_labels_batch

    m = db.query(Museum).filter_by(slug=slug).one_or_none()
    if not m:
        return []
    objs = db.query(MuseumObject).filter_by(museum_id=m.id).all()
    if limit:
        objs = objs[:limit]
    # P170 作者身份解析:与同步 names 路径(backfill)对齐。此前 batch 路径只读
    # 已有的 artist_qid、从不抓取,新馆 catalog 不产 artist_qid → 作者一个都建不了
    # (卢浮宫实测 17283 件仅 1 件有 artist_qid,10041 件作者名无中文)。
    # 路径不等价是最难发现的缺陷:流程全绿、数字漂亮,缺的东西无声无息。
    creators = (fetch_creators or _fetch_creators)(
        [o.qid for o in objs if not (o.attributes or {}).get("artist_qid")]
    )
    # 标签批量预取(上大馆硬前提):单件版是 N+1——卢浮宫 17283 件 = 17283 次串行
    # SPARQL,实测 ~5h 且 CPU 只占 12%(全在等网络)。批量 200/次 → 往返少 200 倍。
    # 注入了 fetch_labels 的调用方(测试)仍走单件语义,不破坏既有契约。
    label_cache: dict = {}
    if fetch_labels is None:
        label_cache = fetch_wikidata_labels_batch([o.qid for o in objs], langs)

    def _labels(qid):
        if fetch_labels is not None:
            return fetch_labels(qid, langs)
        return label_cache.get(qid, {})

    tasks: list[BatchTask] = []
    artist_qids: set = set()
    artist_name_en: dict = {}  # 作者QID → 作品行上的 en 名(建 Artist 行的轴心)
    for i, o in enumerate(objs):
        attrs = dict(o.attributes or {})
        ti = _clean_i18n(attrs.get("title_i18n"))
        aq = attrs.get("artist_qid") or creators.get(o.qid)
        if aq:
            if attrs.get("artist_qid") != aq:
                attrs = {**attrs, "artist_qid": aq}
                o.attributes = attrs  # 解析结果当场落库(幂等,重跑不再抓)
            artist_qids.add(aq)
            if o.artist_en:
                artist_name_en.setdefault(aq, o.artist_en)
        missing = [lg for lg in langs if not ti.get(lg)]
        if missing:
            try:
                labels = _labels(o.qid)
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
    # 作者标签同样批量预取(作者 QID 不在对象缓存里,漏了会让作者拿不到权威名)
    if fetch_labels is None and artist_qids:
        label_cache.update(fetch_wikidata_labels_batch(sorted(artist_qids), langs))
    for aq in sorted(artist_qids):
        art = db.query(Artist).filter_by(qid=aq).first()
        if not art:  # 新馆首跑无 Artist 行 → 建行(与同步路径一致,否则作者全丢)
            art = Artist(qid=aq)
            db.add(art)
        if not art.name_en and artist_name_en.get(aq):
            art.name_en = artist_name_en[aq]
        ni = _clean_i18n(art.name_i18n)
        # 权威标签优先(名家在 Wikidata 多语齐全,免翻译且更准)
        if any(not ni.get(lg) for lg in langs):
            try:
                for lg, v in (_labels(aq) or {}).items():
                    if v and not ni.get(lg):
                        ni[lg] = v
            except Exception:  # 单个作者抓取失败跳过(纪律①),重跑再补
                pass
            art.name_i18n = ni
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
        # 分块:OpenAI 单 job 硬上限 5万请求(2026-07-25 卢浮宫 17283件×多语实测
        # maximum_requests_exceeded,提交即拒)。先全部提交(OpenAI 侧并行),再逐块收。
        chunks = [
            tasks[i : i + MAX_BATCH_REQUESTS]
            for i in range(0, len(tasks), MAX_BATCH_REQUESTS)
        ]
        ids = [submit(c, client) for c in chunks]
        job_id = ",".join(ids)
        save_state(state_path, job_id, len(tasks))
        logger.info(
            "batch %s 已提交 %d 任务(%d 块,状态: %s)",
            job_id,
            len(tasks),
            len(chunks),
            state_path,
        )
    lines = []
    for jid in job_id.split(","):  # 逐块轮询+收集(支持 --batch-job 多 id 续传)
        lines.extend(poll(jid.strip(), client, interval=poll_interval))
    out = apply(db, lines)
    out["tasks"] = len(lines)
    out["job_id"] = job_id
    return out
