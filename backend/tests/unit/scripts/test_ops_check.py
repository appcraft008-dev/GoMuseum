"""ops_check:采样、6 项告警 + 三笔账告警、阶段触发提醒(spec §7)。"""

import io
import uuid
from datetime import datetime, timedelta, timezone

import fakeredis
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base
from app.models.app_event import AppEvent
from app.models.llm_usage import LLMUsage
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.models.object_embedding import ObjectEmbedding
from app.models.recognition_event import RecognitionEvent
from scripts import ops_check as oc

NOW = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)


def _line(t, path, status=200, urt="0.100", method="GET"):
    return (
        f'203.0.113.9 - - [{t}] "{method} {path} HTTP/1.1" {status} 512 "-" '
        f'"Dart/3.5" "-" rt=0.100 urt={urt}'
    )


# ---------- nginx ----------
def test_nginx_counts_only_browse_gets_in_window():
    t = "23/Oct/2026:13:55:00 +0200"  # 11:55Z,在 15 分钟窗口内
    lines = [
        _line(t, "/api/v1/museums/orsay/objects/Q1/content?language=fr", urt="0.200"),
        _line(t, "/api/v1/search?q=monet", urt="0.400"),
        _line(
            t,
            "/api/v1/museums/orsay/objects/Q1/audio/stream?section=guide",
            urt="9.000",
        ),
        _line(t, "/api/v1/museums/orsay/objects/Q1/audio?section=guide", urt="12.000"),
        _line(t, "/api/v1/museums/orsay", urt="3.000"),  # 5MB 全量馆包
        _line(t, "/api/v1/recognize", method="POST", urt="5.000"),
        _line("23/Oct/2026:13:40:00 +0200", "/api/v1/museums", urt="8.000"),  # 窗口外
        '"\\x05\\x01\\x00" 400',  # 扫描器
    ]
    assert oc.nginx_stats(lines, NOW, 15) == {
        "n": 2,
        "p95": pytest.approx(0.4),
        "n5xx": 0,
        "n5xx_min": 0,
    }


def test_nginx_window_uses_each_lines_offset():
    """10-25 起日志从 CEST(+0200)换成 CET(+0100)。"""
    lines = [
        _line("23/Oct/2026:12:55:00 +0100", "/api/v1/museums"),  # 11:55Z,窗口内
        _line("23/Oct/2026:12:55:00 +0200", "/api/v1/museums"),  # 10:55Z,窗口外
    ]
    assert oc.nginx_stats(lines, NOW, 15)["n"] == 1


def test_nginx_urt_dash_and_multiple_upstreams():
    t = "23/Oct/2026:13:58:00 +0200"
    lines = [
        _line(t, "/api/v1/museums", status=502, urt="-"),
        _line(t, "/api/v1/museums", urt="0.500, 0.300"),
    ]
    assert oc.nginx_stats(lines, NOW, 15) == {
        "n": 2,
        "p95": pytest.approx(0.8),
        "n5xx": 1,
        "n5xx_min": 1,
    }


def test_nginx_counts_distinct_minutes_with_5xx():
    lines = [
        _line("23/Oct/2026:13:50:10 +0200", "/api/v1/museums", status=502, urt="-"),
        _line("23/Oct/2026:13:50:40 +0200", "/api/v1/museums", status=502, urt="-"),
        _line("23/Oct/2026:13:52:00 +0200", "/api/v1/museums", status=500, urt="0.1"),
    ]
    s = oc.nginx_stats(lines, NOW, 15)
    assert (s["n5xx"], s["n5xx_min"]) == (3, 2)


def test_p95_nearest_rank():
    assert oc.p95([i / 10 for i in range(1, 21)]) == pytest.approx(1.9)
    assert oc.p95([]) is None


def test_pool_peak_sums_processes_per_minute_and_takes_max():
    r = fakeredis.FakeRedis(decode_responses=True)
    r.set("ops:pool_peak:202610231158:h-1", 3)
    r.set("ops:pool_peak:202610231158:h-2", 4)
    r.set("ops:pool_peak:202610231159:h-1", 9)
    r.set("ops:pool_peak:202610231150:h-1", 50)  # 5 分钟以前
    assert oc.pool_peak(r, NOW) == 9
    assert oc.pool_peak(None, NOW) is None


# ---------- evaluate ----------
def _sample(**kw):
    s = dict(
        cpu=10,
        mem=20,
        disk=25,
        req_n=100,
        req_p95=0.2,
        req_5xx=0,
        req_5xx_min=0,
        req5_n=30,
        req5_p95=0.2,
        conn_total=10,
        conn_in_use=2,
        conn_max=100,
        pool_peak=3,
        recog_5m=0,
    )
    return {**s, **kw}


def _m(**kw):
    m = dict(
        recog_p95={
            e: {"n": 30, "p95": 0.5}
            for e in ("vector", "vector_canvas", "vector_crops", "text")
        },
        ai_today=5,
        ai_avg30=17.1,
        gen_1h={"n": 10, "fail": 0},
        gen_2h={"n": 10, "fail": 0},
        gen_bad_7d=0,
        slot_full_days=0,
        busy_gen_days=0,
        tts_busy_days=0,
        conn_peak_7d=12,
        cpu_prev=[10, 12],
        vq_7d={"n": 100, "p95": 0.2},
        vectors=26678,
        objects=27383,
        ip_cap_hits={"guest": 0, "registered": 0},
        ledger={
            "gen_day": 1.0,
            "gen_month": 20.0,
            "tts_day": 0.1,
            "recog_day": 0.05,
            "unknown_models": [],
        },
        last_sample_at=None,
        alerts_7d={},
    )
    return {**m, **kw}


def _keys(sample=None, m=None):
    return {k for k, *_ in oc.evaluate(sample or _sample(), m or _m())}


def _recog(engine, n, p95):
    return _m(recog_p95={**_m()["recog_p95"], engine: {"n": n, "p95": p95}})


def _ledger(**kw):
    return _m(ledger={**_m()["ledger"], **kw})


def test_quiet_system_raises_nothing():
    assert _keys() == set()


def test_browse_p95_needs_20_requests():
    assert "browse-p95" in _keys(_sample(req_n=20, req_p95=1.2))
    assert "browse-p95" not in _keys(_sample(req_n=19, req_p95=5.0))


def test_browse_5xx_needs_5_errors_over_1pct_across_3_minutes():
    assert "browse-5xx" in _keys(_sample(req_n=400, req_5xx=5, req_5xx_min=3))
    assert "browse-5xx" not in _keys(
        _sample(req_n=400, req_5xx=9, req_5xx_min=2)
    )  # 发版重启
    assert "browse-5xx" not in _keys(_sample(req_n=20, req_5xx=4, req_5xx_min=4))
    assert "browse-5xx" not in _keys(_sample(req_n=600, req_5xx=5, req_5xx_min=5))


def test_recog_p95_against_baseline_times_1_5():
    assert "recog-p95-vector_canvas" in _keys(m=_recog("vector_canvas", 20, 6.1))
    assert "recog-p95-vector_canvas" not in _keys(m=_recog("vector_canvas", 19, 9.0))
    assert not any(k.startswith("recog-p95") for k in _keys(m=_recog("text", 30, 60.0)))


def test_host_cpu_needs_three_samples_all_over_70():
    assert "host-cpu" in _keys(_sample(cpu=75), _m(cpu_prev=[71, 80]))
    assert "host-cpu" not in _keys(_sample(cpu=75), _m(cpu_prev=[60, 80]))
    assert "host-cpu" not in _keys(_sample(cpu=99), _m(cpu_prev=[99]))


def test_t5_cpu_mean_over_50():
    assert "trigger-t5-cpu" in _keys(_sample(cpu=40), _m(cpu_prev=[60, 60]))
    assert "trigger-t5-cpu" not in _keys(_sample(cpu=40), _m(cpu_prev=[50, 50]))


def test_missing_host_metrics_do_not_alert_or_crash():
    keys = _keys(
        _sample(
            cpu=None,
            mem=None,
            disk=None,
            conn_total=None,
            conn_in_use=None,
            conn_max=None,
            pool_peak=None,
        ),
        _m(cpu_prev=[], conn_peak_7d=None),
    )
    assert not [
        k
        for k in keys
        if k.startswith(("host-", "db-", "trigger-t5", "trigger-t2-conn"))
    ]


def test_disk_mem_and_db_connections():
    assert {"host-disk", "host-mem"} <= _keys(_sample(disk=81, mem=81))
    assert "db-conn" in _keys(_sample(conn_total=81, conn_max=100))
    assert "db-conn" not in _keys(_sample(conn_total=80, conn_max=100))


def test_gen_fail_ratio_rule_and_total_outage_rule():
    assert "gen-fail" in _keys(m=_m(gen_1h={"n": 20, "fail": 5}))
    assert "gen-fail" not in _keys(m=_m(gen_1h={"n": 10, "fail": 4}))
    assert "gen-fail" not in _keys(m=_m(gen_1h={"n": 30, "fail": 5}))
    assert "gen-fail" in _keys(m=_m(gen_2h={"n": 3, "fail": 3}))  # 低流量下的整体失效
    assert "gen-fail" not in _keys(m=_m(gen_2h={"n": 4, "fail": 3}))  # 有一次成功


def test_ai_daily_over_3x_30_day_average_with_floor_20():
    assert "recog-ai-daily" in _keys(m=_m(ai_today=52, ai_avg30=17.1))
    assert "recog-ai-daily" not in _keys(m=_m(ai_today=51, ai_avg30=17.1))
    assert "recog-ai-daily" in _keys(m=_m(ai_today=21, ai_avg30=1.0))
    assert "recog-ai-daily" not in _keys(m=_m(ai_today=20, ai_avg30=1.0))


def test_budget_alerts_at_80_and_100(monkeypatch):
    for k, v in (
        ("BUDGET_GEN_DAILY_USD", 30.0),
        ("BUDGET_GEN_MONTHLY_USD", 300.0),
        ("BUDGET_ALERT_RATIO", 0.8),
        ("ALERT_TTS_DAILY_USD", 2.0),
        ("ALERT_RECOG_DAILY_USD", 1.0),
    ):
        monkeypatch.setattr(settings, k, v)
    k24 = _keys(m=_ledger(gen_day=24.0))
    assert "budget-gen-day-80" in k24 and "budget-gen-day-100" not in k24
    assert {"budget-gen-day-80", "budget-gen-day-100"} <= _keys(m=_ledger(gen_day=30.0))
    assert "budget-gen-month-80" in _keys(m=_ledger(gen_month=240.0))
    assert "budget-tts-day" in _keys(m=_ledger(tts_day=1.6))
    assert "budget-recog-day" in _keys(m=_ledger(recog_day=0.8))
    assert "price-unknown-gpt-7" in _keys(m=_ledger(unknown_models=["gpt-7"]))
    monkeypatch.setattr(settings, "ALERT_RECOG_DAILY_USD", 0.0)  # 0 = 关闭(R7)
    assert "budget-recog-day" not in _keys(m=_ledger(recog_day=100.0))


def test_stage_triggers():
    assert "trigger-t1" in _keys(m=_m(slot_full_days=3))
    assert "trigger-t1" not in _keys(m=_m(slot_full_days=2))
    assert "trigger-t2-conn" in _keys(m=_m(conn_peak_7d=41))
    assert "trigger-t2-conn" not in _keys(m=_m(conn_peak_7d=40))
    assert "trigger-t2-conn" in _keys(_sample(pool_peak=41))
    assert "trigger-t2-tts" in _keys(m=_m(tts_busy_days=3))
    assert "trigger-t2-vq" in _keys(m=_m(vq_7d={"n": 50, "p95": 0.51}))
    assert "trigger-t2-vq" not in _keys(m=_m(vq_7d={"n": 49, "p95": 9.0}))
    assert "trigger-t2-vectors" in _keys(m=_m(vectors=100_001))
    assert "trigger-vectors-700k" in _keys(m=_m(vectors=700_001))
    assert "trigger-t3-failures" in _keys(m=_m(gen_bad_7d=6))
    assert "trigger-t3-failures" not in _keys(m=_m(gen_bad_7d=5))
    assert "trigger-t5-recog" in _keys(_sample(recog_5m=20, req5_n=20, req5_p95=1.1))
    assert "trigger-ip-cap-guest" in _keys(
        m=_m(ip_cap_hits={"guest": 1, "registered": 0})
    )
    assert "trigger-search-engine" in _keys(m=_m(objects=150_001))


def test_t3_concurrency_only_after_stage_1(monkeypatch):
    monkeypatch.setattr(settings, "LAZY_CONCURRENCY", 2)
    assert "trigger-t3-concurrency" not in _keys(m=_m(busy_gen_days=3))
    monkeypatch.setattr(settings, "LAZY_CONCURRENCY", 4)
    assert "trigger-t3-concurrency" in _keys(m=_m(busy_gen_days=3))


def test_throttle_hours_and_every_mail_says_what_to_do():
    found = oc.evaluate(_sample(disk=90), _m(slot_full_days=3))
    assert {k: h for k, h, *_ in found} == {"host-disk": 6, "trigger-t1": 168}
    for _, _, subject, body in found:
        assert subject.startswith("[GoMuseum]") and "处理办法" in body


# ---------- collect(SQLite) ----------
@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Museum.__table__,
            MuseumObject.__table__,
            ObjectImage.__table__,
            ObjectEmbedding.__table__,
            AppEvent.__table__,
            RecognitionEvent.__table__,
            LLMUsage.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def _ev(db, name, at, **props):
    db.add(AppEvent(name=name, created_at=at, props=props))
    db.commit()


def test_exempt_excluded_from_triggers_but_counted_in_health(db):
    for d in range(3):
        _ev(
            db,
            "lazy_slot_full",
            NOW - timedelta(days=d),
            qid="Q1",
            kind="lazy generation",
            exempt=True,
        )
    _ev(
        db,
        "lazy_finished",
        NOW - timedelta(minutes=10),
        qid="Q1",
        run_id="a",
        ok=False,
        exempt=True,
    )
    m = oc.collect(db, NOW)
    assert m["slot_full_days"] == 0
    assert m["gen_bad_7d"] == 0
    assert m["gen_1h"] == {"n": 1, "fail": 1}
    assert m["gen_2h"] == {"n": 1, "fail": 1}


def test_interrupted_generation_counts_after_15_minutes(db):
    _ev(
        db,
        "lazy_started",
        NOW - timedelta(minutes=20),
        qid="Q1",
        run_id="old",
        running=1,
        exempt=False,
    )
    _ev(
        db,
        "lazy_started",
        NOW - timedelta(minutes=5),
        qid="Q2",
        run_id="new",
        running=2,
        exempt=False,
    )
    _ev(
        db,
        "lazy_started",
        NOW - timedelta(minutes=30),
        qid="Q3",
        run_id="done",
        running=1,
        exempt=False,
    )
    _ev(
        db,
        "lazy_finished",
        NOW - timedelta(minutes=29),
        qid="Q3",
        run_id="done",
        ok=True,
        exempt=False,
    )
    assert oc.collect(db, NOW)["gen_bad_7d"] == 1


def test_vectors_count_only_current_model(db, monkeypatch):
    monkeypatch.setattr(settings, "RECOG_MODEL", "dinov3-vits16")
    for model in ("dinov3-vits16", "dinov3-vits16", "dinov2-vits14"):
        db.add(
            ObjectEmbedding(
                object_id=uuid.uuid4(), image_id=uuid.uuid4(), model=model, vec=b"x"
            )
        )
    db.commit()
    assert oc.collect(db, NOW)["vectors"] == 2


def test_ledger_counts_app_channels_on_utc_day(db, monkeypatch):
    from app.services import llm_usage

    monkeypatch.setattr(llm_usage, "DEFAULT_LLM_PRICES", {"m": (1.0, 0.0)})
    today, yesterday = NOW.date(), NOW.date() - timedelta(days=1)
    for day, ch, tin in [
        (today, "generate@app", 1_000_000),
        (today, "translate", 5_000_000),  # 离线脚本,不计
        (today, "tts@app", 2_000_000),
        (today, "recognition@app", 300_000),
        (today, "label@app", 200_000),
        (yesterday, "qa@app", 4_000_000),  # 只进本月
    ]:
        db.add(
            LLMUsage(
                day=day, channel=ch, model="m", calls=1, tokens_in=tin, tokens_out=0
            )
        )
    db.add(
        LLMUsage(
            day=today,
            channel="vision@app",
            model="new-model",
            calls=1,
            tokens_in=0,
            tokens_out=0,
        )
    )
    db.commit()
    led = oc.collect(db, NOW)["ledger"]
    assert led["gen_day"] == pytest.approx(1.0)
    assert led["gen_month"] == pytest.approx(5.0)
    assert led["tts_day"] == pytest.approx(2.0)
    assert led["recog_day"] == pytest.approx(0.5)
    assert led["unknown_models"] == ["new-model"]


def test_recognition_p95_uses_latest_30_within_7_days(db):
    naive = NOW.replace(tzinfo=None)
    for i in range(10):  # 更早的慢样本:被最新 30 条挤出去
        db.add(
            RecognitionEvent(
                phash=f"slow{i}",
                outcome="match",
                engine="vector_canvas",
                duration_ms=60_000,
                created_at=naive - timedelta(days=3),
            )
        )
    for i in range(30):
        db.add(
            RecognitionEvent(
                phash=f"p{i}",
                outcome="match",
                engine="vector_canvas",
                duration_ms=1000 * (i + 1),
                created_at=naive - timedelta(hours=1),
            )
        )
    db.add(
        RecognitionEvent(
            phash="old",
            outcome="match",
            engine="vector",
            duration_ms=99_000,
            created_at=naive - timedelta(days=8),
        )
    )  # 7 天外
    for d in range(1, 31):
        db.add(
            RecognitionEvent(
                phash=f"t{d}",
                outcome="match",
                engine="text",
                duration_ms=5000,
                created_at=naive - timedelta(days=d),
            )
        )
    for i in range(3):
        db.add(
            RecognitionEvent(
                phash=f"today{i}",
                outcome="match",
                engine="text",
                duration_ms=5000,
                created_at=naive - timedelta(minutes=10),
            )
        )
    db.commit()
    m = oc.collect(db, NOW)
    assert m["recog_p95"]["vector_canvas"] == {"n": 30, "p95": pytest.approx(29.0)}
    assert m["recog_p95"]["vector"] == {"n": 0, "p95": None}
    assert (m["ai_today"], m["ai_avg30"]) == (3, pytest.approx(1.0))


# ---------- main ----------
@pytest.fixture()
def wired(db, monkeypatch):
    sent = []
    monkeypatch.setattr(oc.ops_alert, "send", lambda s, b: sent.append(s))
    monkeypatch.setattr(oc, "SessionLocal", lambda: db)
    monkeypatch.setattr(oc, "_redis", lambda: None)
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    return sent


def _alerts(db):
    return [e.props for e in db.query(AppEvent).filter_by(name="ops_alert")]


def test_alert_sent_once_per_window(db, wired):
    assert oc.main(["--disk", "95"]) == 0
    assert oc.main(["--disk", "95"]) == 0
    assert len(wired) == 1  # 第二次还在 6 小时内
    assert _alerts(db) == [{"key": "host-disk", "mailed": True}]
    assert db.query(AppEvent).filter_by(name="ops_sample").count() == 2


def test_dry_run_sends_and_writes_nothing(db, wired, capsys):
    assert oc.main(["--disk", "95", "--dry-run"]) == 0
    assert wired == [] and db.query(AppEvent).count() == 0
    assert "host-disk" in capsys.readouterr().out


def test_no_mail_records_but_sends_nothing(db, wired):
    """上线头 7 天:照常采样、按限频记下「本该发的」,不发信(R13)。"""
    assert oc.main(["--disk", "95", "--no-mail"]) == 0
    assert oc.main(["--disk", "95", "--no-mail"]) == 0
    assert wired == []
    assert _alerts(db) == [{"key": "host-disk", "mailed": False}]
    assert db.query(AppEvent).filter_by(name="ops_sample").count() == 2
    # 切到发信模式:只记不发的记录不拦真邮件,正在持续的状况立刻发第一封
    assert oc.main(["--disk", "95"]) == 0
    assert len(wired) == 1


def test_mail_not_configured_returns_2(db, wired, monkeypatch):
    from app.services import mailer

    def boom(subject, body):
        raise mailer.MailNotConfigured("OPS_ALERT_EMAIL 未配置")

    monkeypatch.setattr(oc.ops_alert, "send", boom)
    assert oc.main(["--disk", "95"]) == 2
    assert _alerts(db) == []  # 没发出去就不记,下次再试


def test_render_capacity_lists_every_trigger_metric():
    text = "\n".join(
        oc.render_capacity(
            _m(
                last_sample_at="2026-10-23T11:55:00+00:00",
                alerts_7d={"browse-p95": 3},
            )
        )
    )
    for word in (
        "名额满",
        "连接峰值",
        "TTS",
        "向量检索",
        "作品",
        "生成",
        "AI 兜底",
        "账",
        "IP 额度",
    ):
        assert word in text, word
    assert "26678" in text and "122617" in text  # 作品离 15 万还差 150000 - 27383
    assert "2026-10-23T11:55" in text  # 最近一次采样:cron 停了一眼能看出来
    assert "browse-p95" in text and "3" in text  # 近 7 天每条规则发了或本该发几封


def test_dry_run_with_no_mail_writes_nothing(db, wired):
    """手工预演时容易两个一起给:--dry-run 优先,一行不写(Fable 终审 I1)。"""
    assert oc.main(["--disk", "95", "--no-mail", "--dry-run"]) == 0
    assert wired == [] and db.query(AppEvent).count() == 0


def test_vq_uses_latest_samples_only(db, monkeypatch):
    """近 7 天的 timings 不整表拉回 Python,只取最新 N 条(Fable 终审 M4)。"""
    monkeypatch.setattr(oc, "_VQ_LIMIT", 3)
    naive = NOW.replace(tzinfo=None)
    for i in range(2):
        db.add(
            RecognitionEvent(
                phash=f"o{i}",
                outcome="match",
                engine="vector",
                timings={"vq": 9000},
                created_at=naive - timedelta(days=2),
            )
        )
    for i in range(3):
        db.add(
            RecognitionEvent(
                phash=f"n{i}",
                outcome="match",
                engine="vector",
                timings={"vq": 100},
                created_at=naive - timedelta(hours=1),
            )
        )
    db.commit()
    assert oc.collect(db, NOW)["vq_7d"] == {"n": 3, "p95": pytest.approx(0.1)}
