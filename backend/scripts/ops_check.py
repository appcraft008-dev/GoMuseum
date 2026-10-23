"""容量监控(spec 2026-10-21-elastic-scaling-design §7,阶段 0):每 5 分钟采样、告警、阶段触发提醒。

## 为什么需要

扩容按触发条件做(spec §11),触发条件得有人看得见:名额满、连接数、TTS 并发、识别变慢……
光写日志没人看(探活两个月没人发现 Joconde 断供)。这里每 5 分钟采一次样写进 app_events
(ops_sample),健康类告警(浏览变慢、5xx、识别变慢、磁盘/内存/CPU、连接数、生成失败、
AI 兜底次数、三笔账)和「该进入阶段 N 了」的提醒按限频发邮件,记一条 ops_alert。
处理办法见 docs/ops/capacity-runbook.md。

## 运行

宿主机 cron 每 5 分钟跑 deployment/production/ops-check.sh:宿主机指标在 shell 里取,
nginx 日志从 stdin 喂进来:
  ... | docker exec -i gomuseum_prod_backend python -m scripts.ops_check \\
        --cpu 12 --mem 40 --disk 30 [--dry-run | --no-mail]
--dry-run:不写库、不发信,只打印会告警的 key。
--no-mail:照常采样,该发的告警只记 ops_alert(mailed=False)不发信(上线头 7 天,R13)。

退出码:0 正常 | 2 有告警但发不出去(OPS_ALERT_EMAIL 未配置或发信失败)
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Iterable

sys.path.insert(0, "/app")

from app.core.database import SessionLocal  # noqa: E402
from app.services import ops_alert  # noqa: E402

RUNBOOK = "见 docs/ops/capacity-runbook.md"
HEALTH_H = 6
TRIGGER_H = 168
# spec §0.2 的识别基线(秒);AI 兜底(text)不告警,只进报告
RECOG_BASELINE = {"vector": 1.0, "vector_canvas": 4.0, "vector_crops": 4.2}
RECOG_ENGINES = ("vector", "vector_canvas", "vector_crops", "text")
GEN_CHANNELS = ("generate", "gate", "translate", "qa", "vision")
# 向量检索耗时只看最新这么多条:近 7 天整表拉回 Python 会随识别量线性变重
_VQ_LIMIT = 2000


def _redis():
    from app.services.recognition.service import _get_redis

    return _get_redis()


def p95(xs: list[float]) -> float | None:
    """最近秩法。"""
    if not xs:
        return None
    return sorted(xs)[math.ceil(0.95 * len(xs)) - 1]


# ---------- nginx ----------
_LINE = re.compile(r'\[([^\]]+)\] "(\S+) (\S+)[^"]*" (\d{3}) ')
_URT = re.compile(r" urt=(.*)$")
_NUM = re.compile(r"\d+(?:\.\d+)?")
_FULL_MUSEUM = re.compile(r"^/api/v1/museums/[^/]+$")


def nginx_stats(lines: Iterable[str], now: datetime, minutes: int) -> dict:
    """浏览/内容接口(GET /api/v1/*)在窗口内的请求数、urt p95、5xx 数、出过 5xx 的分钟数。
    剔除音频长连接、老 App 的 5MB 全量馆包、已知慢接口 history/recent(R4)。
    时间按每行自带的时区算(10-25 起 +0200 → +0100)。"""
    start = now - timedelta(minutes=minutes)
    n, n5xx, times, bad_min = 0, 0, [], set()
    for line in lines:
        m = _LINE.search(line)
        if not m:
            continue
        t_raw, method, target, status = m.groups()
        try:
            t = datetime.strptime(t_raw, "%d/%b/%Y:%H:%M:%S %z")
        except ValueError:
            continue
        path = target.split("?", 1)[0]
        if (
            t < start
            or method != "GET"
            or not path.startswith("/api/v1/")
            or "/audio" in path
            or _FULL_MUSEUM.match(path)
            or path == "/api/v1/history/recent"
        ):
            continue
        n += 1
        if int(status) >= 500:
            n5xx += 1
            bad_min.add(t.astimezone(timezone.utc).replace(second=0))
        u = _URT.search(line)
        nums = _NUM.findall(u.group(1)) if u else []
        if nums:
            times.append(sum(float(x) for x in nums))
    return {"n": n, "p95": p95(times), "n5xx": n5xx, "n5xx_min": len(bad_min)}


def pool_peak(redis, now) -> int | None:
    """最近 5 分钟:同一分钟各进程相加,再取最大。"""
    if redis is None:
        return None
    try:
        best = None
        for i in range(5):
            minute = (now - timedelta(minutes=i)).strftime("%Y%m%d%H%M")
            keys = list(redis.scan_iter(match=f"ops:pool_peak:{minute}:*"))
            if keys:
                total = sum(int(v or 0) for v in redis.mget(keys))
                best = total if best is None else max(best, total)
        return best
    except Exception:
        return None


# ---------- 采样 ----------
def take_sample(db, now, lines: list[str], host: dict) -> dict:
    from sqlalchemy import func, text

    from app.models.recognition_event import RecognitionEvent

    s15 = nginx_stats(lines, now, 15)
    s5 = nginx_stats(lines, now, 5)
    conn = (None, None, None)
    if db.get_bind().dialect.name == "postgresql":
        conn = tuple(
            db.execute(
                text(
                    "select count(*), count(*) filter (where state <> 'idle'), "
                    "current_setting('max_connections')::int from pg_stat_activity "
                    "where backend_type = 'client backend'"
                )
            ).one()
        )
    naive = now.astimezone(timezone.utc).replace(tzinfo=None)
    recog_5m = (
        db.query(func.count(RecognitionEvent.id))
        .filter(RecognitionEvent.created_at >= naive - timedelta(minutes=5))
        .scalar()
    )
    return {
        "cpu": host.get("cpu"),
        "mem": host.get("mem"),
        "disk": host.get("disk"),
        "req_n": s15["n"],
        "req_p95": s15["p95"],
        "req_5xx": s15["n5xx"],
        "req_5xx_min": s15["n5xx_min"],
        "req5_n": s5["n"],
        "req5_p95": s5["p95"],
        "conn_total": conn[0],
        "conn_in_use": conn[1],
        "conn_max": conn[2],
        "pool_peak": pool_peak(_redis(), now),
        "recog_5m": int(recog_5m or 0),
    }


# ---------- 汇总 ----------
def _events(db, names, since, until=None):
    """(created_at, props);props 在 Python 里读(测试是 SQLite,线上是 PG)。"""
    from app.models.app_event import AppEvent

    q = db.query(AppEvent.created_at, AppEvent.props).filter(
        AppEvent.name.in_(names), AppEvent.created_at >= since
    )
    if until is not None:
        q = q.filter(AppEvent.created_at < until)
    return [(t, p or {}) for t, p in q.order_by(AppEvent.created_at).all()]


def _utc_date(t):
    return (t.astimezone(timezone.utc) if t.tzinfo else t).date()


def _days(rows, pred=lambda p: True) -> int:
    return len({_utc_date(t) for t, p in rows if not p.get("exempt") and pred(p)})


def _ledger(db, now) -> dict:
    from app.models.llm_usage import LLMUsage
    from app.services.llm_usage import cost_usd

    today = now.date()
    rows = db.query(LLMUsage).filter(LLMUsage.day >= today.replace(day=1)).all()
    led = {"gen_day": 0.0, "gen_month": 0.0, "tts_day": 0.0, "recog_day": 0.0}
    unknown = set()
    for r in rows:
        if not r.channel.endswith("@app"):
            continue  # 离线脚本是运营者主动花的钱,不算
        ch = r.channel[: -len("@app")]
        usd, known = cost_usd(r.model, int(r.tokens_in or 0), int(r.tokens_out or 0))
        is_today = r.day == today
        if is_today and not known:
            unknown.add(r.model)
        if ch in GEN_CHANNELS:
            led["gen_month"] += usd
            if is_today:
                led["gen_day"] += usd
        elif is_today and ch == "tts":
            led["tts_day"] += usd
        elif is_today and ch in ("recognition", "label"):
            led["recog_day"] += usd
    led["unknown_models"] = sorted(unknown)
    return led


def collect(db, now) -> dict:
    from sqlalchemy import func

    from app.core.config import settings
    from app.models.app_event import AppEvent
    from app.models.museum_object import MuseumObject
    from app.models.object_embedding import ObjectEmbedding
    from app.models.recognition_event import RecognitionEvent as RE

    naive = now.astimezone(timezone.utc).replace(tzinfo=None)
    d7 = now - timedelta(days=7)
    day0 = naive.replace(hour=0, minute=0, second=0, microsecond=0)

    recog = {}
    for e in RECOG_ENGINES:
        ms = [
            v
            for (v,) in db.query(RE.duration_ms)
            .filter(
                RE.engine == e,
                RE.duration_ms.isnot(None),
                RE.created_at >= naive - timedelta(days=7),
            )
            .order_by(RE.created_at.desc())
            .limit(30)
            .all()
        ]
        p = p95(ms)
        recog[e] = {"n": len(ms), "p95": p / 1000 if p is not None else None}

    def text_count(lo, hi=None):
        q = db.query(func.count(RE.id)).filter(RE.engine == "text", RE.created_at >= lo)
        if hi is not None:
            q = q.filter(RE.created_at < hi)
        return int(q.scalar() or 0)

    def gen(hours):
        rows = _events(db, ["lazy_finished"], now - timedelta(hours=hours))
        return {"n": len(rows), "fail": sum(1 for _, p in rows if not p.get("ok"))}

    finished = _events(db, ["lazy_finished"], d7)
    started = _events(db, ["lazy_started"], d7)
    done_ids = {p.get("run_id") for _, p in finished}
    stale = _events(db, ["lazy_started"], d7, now - timedelta(minutes=15))
    gen_bad = sum(1 for _, p in finished if not p.get("exempt") and not p.get("ok"))
    gen_bad += sum(
        1 for _, p in stale if not p.get("exempt") and p.get("run_id") not in done_ids
    )

    samples = _events(db, ["ops_sample"], d7)
    peaks = [
        v
        for _, p in samples
        for v in (p.get("conn_in_use"), p.get("pool_peak"))
        if v is not None
    ]
    cpu_prev = [
        p["cpu"]
        for _, p in _events(db, ["ops_sample"], now - timedelta(minutes=14), now)
        if p.get("cpu") is not None
    ]

    vq = [
        t["vq"] / 1000
        for (t,) in db.query(RE.timings)
        .filter(RE.timings.isnot(None), RE.created_at >= naive - timedelta(days=7))
        .order_by(RE.created_at.desc())
        .limit(_VQ_LIMIT)
        .all()
        if isinstance(t, dict) and isinstance(t.get("vq"), (int, float))
    ]

    cap = Counter(
        p.get("tier")
        for _, p in _events(db, ["lazy_cap_hit"], d7)
        if p.get("layer") == "ip"
    )
    last = (
        db.query(func.max(AppEvent.created_at))
        .filter(AppEvent.name == "ops_sample")
        .scalar()
    )
    return {
        "recog_p95": recog,
        "ai_today": text_count(day0),
        "ai_avg30": text_count(day0 - timedelta(days=30), day0) / 30,
        "gen_1h": gen(1),
        "gen_2h": gen(2),
        "gen_bad_7d": gen_bad,
        "slot_full_days": _days(
            _events(db, ["lazy_slot_full", "lazy_fanout_slot_full"], d7)
        ),
        "busy_gen_days": _days(started, lambda p: (p.get("running") or 0) >= 4),
        "tts_busy_days": len({_utc_date(t) for t, _ in _events(db, ["tts_busy"], d7)}),
        "conn_peak_7d": max(peaks) if peaks else None,
        "cpu_prev": cpu_prev,
        "vq_7d": {"n": len(vq), "p95": p95(vq)},
        # ponytail: 两个全表 count,prod 10-23 实测 25ms / 83ms(27k 作品、41k 向量)。它们各自的
        # 阶段线(作品 15 万、向量 10 万)到了就换方案,所以涨不到秒级;真变重再改成每小时算一次
        "vectors": int(
            db.query(func.count(ObjectEmbedding.id))
            .filter(ObjectEmbedding.model == settings.RECOG_MODEL)
            .scalar()
            or 0
        ),
        "objects": int(db.query(func.count(MuseumObject.id)).scalar() or 0),
        "ip_cap_hits": {"guest": cap["guest"], "registered": cap["registered"]},
        "ledger": _ledger(db, now),
        "last_sample_at": last.isoformat() if last else None,
        "alerts_7d": dict(
            Counter(p.get("key") for _, p in _events(db, ["ops_alert"], d7))
        ),
    }


def render_capacity(m: dict) -> list[str]:
    """ops_report 的容量段:每个触发指标的现值、阈值、越线后进入哪个阶段(spec §7 报告)。"""
    from app.core.config import settings

    def fmt(v, nd=2):
        return "—" if v is None else f"{v:.{nd}f}"

    rp = m["recog_p95"]
    led = m["ledger"]
    vq = m["vq_7d"]
    lines = [
        "├─ 容量(近 7 天;阶段提醒照 spec §11 做,先写实施计划经用户批准)",
        f"│  名额满天数 {m['slot_full_days']}(≥3 → 阶段 1)"
        f" · 生成失败/中断 {m['gen_bad_7d']}(>5 → 阶段 3)"
        f" · 同时生成≥4 的天数 {m['busy_gen_days']}"
        f"(并发 {settings.LAZY_CONCURRENCY},≥4 后才判断 → 阶段 3)",
        f"│  连接峰值 {m['conn_peak_7d'] if m['conn_peak_7d'] is not None else '—'}"
        f"(>40 → 阶段 2) · TTS 同时合成≥4 的天数 {m['tts_busy_days']}(≥3 → 阶段 2)",
        f"│  向量检索 p95 {fmt(vq['p95'])}s n={vq['n']}(>0.5s → 阶段 2)"
        f" · 当前模型向量 {m['vectors']}(>100000 → 阶段 2,>700000 → §5.3 档③)",
        f"│  作品 {m['objects']},离换外部搜索引擎的 150000 还差"
        f" {max(0, 150_000 - m['objects'])}(§5.4)",
        "│  识别 p95(最新 30 条,基线×1.5 告警) "
        + " · ".join(
            f"{e} {fmt(rp[e]['p95'])}s n={rp[e]['n']}" for e in RECOG_ENGINES if e in rp
        ),
        f"│  AI 兜底 今天 {m['ai_today']} 次 · 前 30 天日均 {m['ai_avg30']:.1f}"
        f"(> max(20, 3×日均) 告警)",
        f"│  懒生成 1 小时 {m['gen_1h']['fail']}/{m['gen_1h']['n']} 失败"
        f" · 2 小时 {m['gen_2h']['fail']}/{m['gen_2h']['n']} 失败",
        f"│  IP 额度用满 游客 {m['ip_cap_hits'].get('guest', 0)}"
        f" · 正式账号 {m['ip_cap_hits'].get('registered', 0)}(>0 → 评估放宽,§4.2)",
        f"│  账(@app) 生成 今天 ${led['gen_day']:.2f}/${settings.BUDGET_GEN_DAILY_USD:.0f}"
        f" 本月 ${led['gen_month']:.2f}/${settings.BUDGET_GEN_MONTHLY_USD:.0f}"
        f" · 语音今天 ${led['tts_day']:.2f} · 识别兜底今天 ${led['recog_day']:.2f}"
        f" · 未知单价 {led['unknown_models'] or '无'}",
        f"│  最近一次采样 {m['last_sample_at'] or '无(cron 没在跑?)'}",
        "│  近 7 天告警(发了或本该发) "
        + (" · ".join(f"{k} {n}" for k, n in sorted(m["alerts_7d"].items())) or "无"),
    ]
    return lines


# ---------- 判断 ----------
def _mail(subject, measured, threshold, action):
    return (
        f"[GoMuseum] {subject}",
        f"测到:{measured}\n阈值:{threshold}\n处理办法:{action}\n{RUNBOOK}",
    )


def _last3(sample, m):
    vals = list(m.get("cpu_prev") or [])
    if sample.get("cpu") is not None:
        vals.append(sample["cpu"])
    return vals[-3:] if len(vals) >= 3 else None


def evaluate(sample: dict, m: dict) -> list[tuple[str, int, str, str]]:
    """(key, 限频小时数, subject, body)。健康告警 6 小时一次,阶段提醒 7 天一次。"""
    from app.core.config import settings

    out = []

    def health(key, subject, measured, threshold, action):
        out.append((key, HEALTH_H, *_mail(subject, measured, threshold, action)))

    def stage(key, n, measured, threshold, extra=""):
        action = f"照 spec §11 阶段 {n} 做,先写实施计划经用户批准。{extra}"
        out.append(
            (key, TRIGGER_H, *_mail(f"该进入阶段 {n} 了", measured, threshold, action))
        )

    s = sample
    req_n = s.get("req_n") or 0
    if req_n >= 20 and (s.get("req_p95") or 0) > 1.0:
        health(
            "browse-p95",
            "浏览接口变慢",
            f"15 分钟 p95 {s['req_p95']:.2f}s(n={req_n})",
            "p95 > 1.0s,至少 20 个请求",
            "先按路径看是哪个接口慢;整体都慢就加 web 进程",
        )
    n5 = s.get("req_5xx") or 0
    if (
        req_n >= 20
        and n5 >= 5
        and n5 / req_n > 0.01
        and (s.get("req_5xx_min") or 0) >= 3
    ):
        health(
            "browse-5xx",
            "接口 5xx 增多",
            f"15 分钟 {n5}/{req_n} 个 5xx,分布在 {s['req_5xx_min']} 个分钟",
            "≥5 个、占比 >1%、至少 3 个不同分钟",
            "docker logs --since 20m gomuseum_prod_backend 查异常",
        )
    for e, base in RECOG_BASELINE.items():
        r = m["recog_p95"].get(e) or {}
        if (r.get("n") or 0) >= 20 and (r.get("p95") or 0) > 1.5 * base:
            health(
                f"recog-p95-{e}",
                f"识别变慢({e})",
                f"最新 {r['n']} 条 p95 {r['p95']:.2f}s",
                f"> 基线 {base}s × 1.5",
                "看 CPU(docker stats,同机其他项目也算进去);持续超线就按 spec 阶段 5 拆出 recognizer",
            )
    for k in ("disk", "mem"):
        if s.get(k) is not None and s[k] > 80:
            health(
                f"host-{k}",
                f"宿主机{'磁盘' if k == 'disk' else '内存'}占用高",
                f"{s[k]}%",
                "> 80%",
                "清理备份目录、旧镜像,或者加资源",
            )
    last3 = _last3(s, m)
    if last3 and all(v > 70 for v in last3):
        health(
            "host-cpu",
            "宿主机 CPU 持续高",
            f"最近 3 次采样 {last3}",
            "3 次都 > 70%",
            "用 docker stats 找出占 CPU 的容器",
        )
    if s.get("conn_total") is not None and s.get("conn_max"):
        if s["conn_total"] > 0.8 * s["conn_max"]:
            health(
                "db-conn",
                "数据库连接数接近上限",
                f"{s['conn_total']}/{s['conn_max']}",
                "> 80% max_connections",
                "按扩容总规则第 1 条调整连接池或 max_connections",
            )
    g1, g2 = m["gen_1h"], m["gen_2h"]
    if (g1["fail"] >= 5 and g1["fail"] / g1["n"] > 0.2) or (
        g2["fail"] >= 3 and g2["fail"] == g2["n"]
    ):
        health(
            "gen-fail",
            "懒生成失败增多",
            f"1 小时 {g1['fail']}/{g1['n']} 失败;2 小时 {g2['fail']}/{g2['n']} 失败",
            "1 小时 ≥5 次且 >20%,或 2 小时 ≥3 次且一次成功都没有",
            "在 docker logs 里查 lazy generation failed。transient 去看上游状态页和额度;"
            "internal 是我们的 bug;err_kind 为空的是请求语言一段都没出(R14),先看 OpenAI",
        )
    ai_line = max(20, 3 * m["ai_avg30"])
    if m["ai_today"] > ai_line:
        health(
            "recog-ai-daily",
            "识别 AI 兜底次数异常",
            f"今天 {m['ai_today']} 次(前 30 天日均 {m['ai_avg30']:.1f})",
            f"> {ai_line:.0f}",
            "按 user_id 分组看有没有人在刷识别;必要时收紧 nginx 的识别限流",
        )
    led = m["ledger"]
    ratio = settings.BUDGET_ALERT_RATIO
    budget_action = "阶段 0 不会自动停,只有段数日上限兜底。看是谁在大量生成,再决定是调预算还是离线预生成"
    for span, used, limit in (
        ("day", led["gen_day"], settings.BUDGET_GEN_DAILY_USD),
        ("month", led["gen_month"], settings.BUDGET_GEN_MONTHLY_USD),
    ):
        for pct, line in ((80, ratio * limit), (100, limit)):
            if limit > 0 and used >= line:
                health(
                    f"budget-gen-{span}-{pct}",
                    f"内容生成{'今日' if span == 'day' else '本月'}花费到预算 {pct}%",
                    f"${used:.2f}",
                    f"${line:.2f}(预算 ${limit:.2f})",
                    budget_action,
                )
    tts_limit = settings.ALERT_TTS_DAILY_USD
    if tts_limit > 0 and led["tts_day"] >= ratio * tts_limit:
        health(
            "budget-tts-day",
            "语音今日花费偏高",
            f"${led['tts_day']:.2f}",
            f"${ratio * tts_limit:.2f}",
            "只告警。看未缓存的首播量,以及有没有人在刷 /audio;到 200 人规模前要按实际量重标这条线(R7)",
        )
    recog_limit = settings.ALERT_RECOG_DAILY_USD
    if recog_limit > 0 and led["recog_day"] >= ratio * recog_limit:
        health(
            "budget-recog-day",
            "识别兜底今日花费偏高",
            f"${led['recog_day']:.2f}",
            f"${ratio * recog_limit:.2f}",
            "只告警。按 user_id 分组看有没有人在刷识别;必要时收紧 nginx 的识别限流",
        )
    for model in led["unknown_models"]:
        health(
            f"price-unknown-{model}",
            f"价目表里没有模型 {model}",
            f"今天的 @app 用量里出现 {model},已按最贵价计",
            "价目表(llm_usage.DEFAULT_LLM_PRICES + .env LLM_PRICES)",
            "到官方价目页查这个模型的单价,在 .env 的 LLM_PRICES 里加上这一个模型"
            "(会和代码默认表合并,R8),然后重启后端",
        )

    # 阶段触发提醒
    if m["slot_full_days"] >= 3:
        stage(
            "trigger-t1",
            1,
            f"近 7 天 {m['slot_full_days']} 天出现过名额满",
            "≥ 3 天",
            ".env 里两个并发数改成 4,重启 web,观察一天日志和连接数。",
        )
    conns = [
        v
        for v in (m.get("conn_peak_7d"), s.get("conn_in_use"), s.get("pool_peak"))
        if v is not None
    ]
    if conns and max(conns) > 40:
        stage("trigger-t2-conn", 2, f"在用连接峰值 {max(conns)}", "> 40")
    if m["tts_busy_days"] >= 3:
        stage(
            "trigger-t2-tts",
            2,
            f"近 7 天 {m['tts_busy_days']} 天 TTS 同时合成 ≥4",
            "≥ 3 天",
        )
    vq = m["vq_7d"]
    if vq["n"] >= 50 and (vq["p95"] or 0) > 0.5:
        stage(
            "trigger-t2-vq", 2, f"向量检索 p95 {vq['p95']:.2f}s(n={vq['n']})", "> 0.5s"
        )
    if m["vectors"] > 100_000:
        stage(
            "trigger-t2-vectors",
            2,
            f"当前模型向量 {m['vectors']} 条",
            "> 100,000(§5.3 档①)",
        )
    if m["vectors"] > 700_000:
        out.append(
            (
                "trigger-vectors-700k",
                TRIGGER_H,
                *_mail(
                    "向量数到 §5.3 档③",
                    f"当前模型向量 {m['vectors']} 条",
                    "> 700,000",
                    "照 spec §5.3 档③ 做,先写实施计划经用户批准",
                ),
            )
        )
    if settings.LAZY_CONCURRENCY >= 4 and m["busy_gen_days"] >= 3:
        stage(
            "trigger-t3-concurrency",
            3,
            f"近 7 天 {m['busy_gen_days']} 天全站同时生成 ≥4 件",
            "≥ 3 天(阶段 1 之后才判断)",
        )
    if m["gen_bad_7d"] > 5:
        stage(
            "trigger-t3-failures", 3, f"近 7 天失败或中断 {m['gen_bad_7d']} 次", "> 5"
        )
    if last3 and sum(last3) / 3 > 50:
        stage("trigger-t5-cpu", 5, f"最近 3 次采样 CPU {last3}", "均值 > 50%")
    if (
        (s.get("recog_5m") or 0) >= 20
        and (s.get("req5_n") or 0) >= 20
        and (s.get("req5_p95") or 0) > 1.0
    ):
        stage(
            "trigger-t5-recog",
            5,
            f"5 分钟识别 {s['recog_5m']} 次,同时浏览 p95 {s['req5_p95']:.2f}s",
            "识别 ≥20 次且浏览 p95 > 1.0s",
        )
    for tier, n in m["ip_cap_hits"].items():
        if n > 0:
            out.append(
                (
                    f"trigger-ip-cap-{tier}",
                    TRIGGER_H,
                    *_mail(
                        f"懒生成 IP 额度被用满({tier})",
                        f"近 7 天 {n} 次",
                        "> 0",
                        "照 spec §4.2 评估要不要放宽这一档的 IP 额度",
                    ),
                )
            )
    if m["objects"] > 150_000:
        out.append(
            (
                "trigger-search-engine",
                TRIGGER_H,
                *_mail(
                    "作品数到了换外部搜索引擎的线",
                    f"作品 {m['objects']} 件",
                    "> 150,000",
                    "照 spec §5.4 换外部搜索引擎,先写实施计划经用户批准",
                ),
            )
        )
    return out


def due(db, key: str, hours: int, now, mailed: bool) -> bool:
    """最近 hours 小时内没有同 key、同 mailed 的 ops_alert(R13:只记不发的记录不拦真邮件)。"""
    return not any(
        p.get("key") == key and bool(p.get("mailed")) == mailed
        for _, p in _events(db, ["ops_alert"], now - timedelta(hours=hours))
    )


def _num(v):
    return float(v) if v not in (None, "") else None


def main(argv: list[str] | None = None) -> int:
    from app.services.event_log import log_event

    ap = argparse.ArgumentParser()
    for k in ("--cpu", "--mem", "--disk"):
        ap.add_argument(k, default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-mail", action="store_true")
    ns = ap.parse_args(argv)
    lines = [] if sys.stdin.isatty() else sys.stdin.read().splitlines()
    host = {"cpu": _num(ns.cpu), "mem": _num(ns.mem), "disk": _num(ns.disk)}
    now = datetime.now(timezone.utc)
    mailed = not ns.no_mail
    db = SessionLocal()
    failed, acted, sample = [], [], {}
    try:
        sample = take_sample(db, now, lines, host)
        found = evaluate(sample, collect(db, now))
        if not ns.dry_run:
            log_event(db, "ops_sample", **sample)
        for key, hours, subject, body in found:
            if not due(db, key, hours, now, mailed):
                continue
            if ns.dry_run or ns.no_mail:
                print(f"{key}: {subject}")
                if ns.no_mail and not ns.dry_run:  # --dry-run 优先:一行不写
                    log_event(db, "ops_alert", key=key, mailed=False)
                acted.append(key)
                continue
            try:
                ops_alert.send(subject, body)
            except Exception as e:
                print(f"{key}: 发不出去 {e!r}")
                failed.append(key)
                continue
            log_event(db, "ops_alert", key=key, mailed=True)
            acted.append(key)
    finally:
        db.close()
    print(
        f"ops_check cpu={host['cpu']} mem={host['mem']} disk={host['disk']} "
        f"req_n={sample.get('req_n')} req_p95={sample.get('req_p95')} "
        f"conn={sample.get('conn_total')}/{sample.get('conn_max')} "
        f"pool_peak={sample.get('pool_peak')} "
        f"{'dry-run' if ns.dry_run else 'no-mail' if ns.no_mail else 'mail'} "
        f"alerts={acted} failed={failed}"
    )
    return 2 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
