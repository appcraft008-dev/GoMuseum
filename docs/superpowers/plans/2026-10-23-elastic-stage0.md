# 弹性扩容 阶段 0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 做完 spec §11 阶段 0 的 9 项：触发指标看得见、6 项告警和三笔账告警能发出、共用 WiFi 不误伤、大模型调用 90 秒超时、懒生成并发可配、staging 限资源、prod 数据库连接上限 100 → 400。

**Architecture:** 代码只做加法，默认值等于今天的行为。有两处是有意放宽：游客登录从每进程 5 次/时放宽到 30 次/时；nginx 限流放宽，识别改走单独的限流区。代码合入后由 CD 自动部署。监控的做法是宿主机 cron 每 5 分钟跑一次 `ops-check.sh`：宿主机指标在 shell 里取，nginx 日志从 stdin 喂给容器里的 `python -m scripts.ops_check`；后者查库、写一条 `ops_sample`，满足条件就发告警邮件，并记一条 `ops_alert`。触发指标的数据来自 web 进程新写的 6 种 `app_events`，外加两个 Redis 计数。nginx、staging compose、prod 数据库参数这三样是手工步骤，按 §11 的三步上线（代码合入 → 手工改 compose/nginx → 切开关）。

**Tech Stack:** FastAPI / SQLAlchemy / pytest（SQLite StaticPool + fakeredis）/ poetry；宿主机 bash、cron、nginx；docker compose 5.1。

**Spec:** `docs/superpowers/specs/2026-10-21-elastic-scaling-design.md`（v10，用户 10-23 批准）。阶段 0 的范围以 §11 表格第 0 行为准，细节分散在 §4.1、§4.2、§4.4、§5.1、§7、§8、§10、§12。

## Global Constraints

- **契约不变**：不增删任何接口字段，审核中的 V69 和已装的老 App 无感（CLAUDE.md「契约前向兼容」）。
- **容量数字都是配置项**：写在 `.env`，重启生效；默认值等于今天的值（spec §0.1）。新配置项和默认值如下：
  - `LAZY_CONCURRENCY=2`、`LAZY_FANOUT_CONCURRENCY=2`
  - `CAP_PER_USER=160`、`CAP_PER_IP=300`、`CAP_PER_IP_REGISTERED=600`
  - `GUEST_LOGIN_RATE="30/hour"`
  - `LLM_TIMEOUT_S=90`
  - `LLM_PRICES`：单价在实施时核对
  - `BUDGET_GEN_DAILY_USD=30`、`BUDGET_GEN_MONTHLY_USD=300`、`BUDGET_ALERT_RATIO=0.8`
  - `ALERT_TTS_DAILY_USD=2`、`ALERT_RECOG_DAILY_USD=1`
- **这次不动**（属于阶段 2 或以后）：`WEIGHT_GENERATION=8`、`WEIGHT_TRANSLATION=3`、`_LAZY_DAILY_SECTION_CAP=1000`、`_FANOUT_DAILY_SECTION_CAP=3000`、`_FANOUT_WORKERS=4`、TTS 线程池 8、数据库连接池 20+40、slowapi 其余各条限额和它的进程内计数。
- 不引入新依赖，不引入新中间件（spec §0.1 第 3 条）。
- **埋点和记账绝不破坏业务**：一律走 `log_event` / `record_llm_usage`；Redis 不可用时放行（fail-open），代价只是少记指标。
- 通道名 `recognition`、`label` 不能改：`LLM_CHANNEL_MODELS` 靠它们选模型（§4.1）。
- 价目表单价在实施时到官方价目页核对，不凭记忆填（§4.1）。计日一律按 UTC（§4.1）。
- **compose 改动必须当场生效**：在同一个窗口里执行 `up -d <服务>`。否则下一次 CD 会在不受控的时间点重建容器（§11）。
- ⛔ **prod 写操作逐次批准**：装 cron、改 nginx、重启数据库，每一步执行前都单独请用户批准。staging→main 由用户合并。上 prod 前先确认 prod 上没有长任务在跑（§11 末行）。
- **git 写操作只在 worktree 里做**：路径 `/Users/hongyang/Projects/GoMuseum-elastic`，分支 `feature/elastic-scaling-spec`。主仓库目录 `/Users/hongyang/Projects/GoMuseum` 不做任何 git 写操作。
- 后端测试命令：在 `backend/` 下执行 `poetry run pytest <path> -q --no-cov`。
- worktree 里 husky 钩子不跑：每次提交前手动执行 `poetry run black <改过的 .py> && poetry run isort <改过的 .py>`。
- 提交信息遵循 Conventional Commits，结尾带两行：
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01EQgJmCjbBm5Z2hmZMXmurZ
  ```

## 新事件与 Redis 键（各任务共用的约定）

| 事件（`app_events.name`） | 谁写、什么时候写 | props |
|---|---|---|
| `lazy_slot_full` | `_run_locked` 拿不到 `_SEM`。同一件 10 分钟内只记一次；Redis 不可用时不记 | `qid`、`kind`（`"lazy generation"` / `"lazy translation"`）、`exempt` |
| `lazy_fanout_slot_full` | `_fanout` 拿不到 `_FANOUT_SEM`。去重规则同上 | `qid`、`exempt` |
| `lazy_started` | 懒生成（不含懒翻译）拿到 `_SEM` 之后 | `qid`、`run_id`（uuid4 hex）、`running`（Redis 计数加 1 后的值；Redis 不可用为 `None`）、`exempt` |
| `lazy_finished` | 同一次懒生成的 work 结束后（成功或抛 `Exception` 都记；`BaseException` 不记，按「中断」统计） | `qid`、`run_id`、`ok`、`err_kind`（`"transient"` / `"internal"` / `None`）、`dur_s`、`pub` {语言: 已发布段数}、`held` {语言: needs_review 段数}、`exempt` |
| `lazy_cap_hit` | `maybe_trigger` 扣额度被拒 | `qid`、`layer`（`"user"` / `"ip"`）、`tier`（`"guest"` / `"registered"`）、`kind`、`exempt`（恒为 False） |
| `tts_busy` | `tts_service._drain` 本进程同时合成数 ≥ 4。每进程每分钟最多一条 | `active` |
| `ops_sample` | `ops_check` 每次运行（`--dry-run` 不写） | `cpu`、`mem`、`disk`、`req_n`、`req_p95`、`req_5xx`、`req5_n`、`req5_p95`、`conn_total`、`conn_in_use`、`conn_max`、`pool_peak`、`recog_5m` |
| `ops_alert` | `ops_check` 发出一封告警之后 | `key` |

| Redis 键 | 用途 |
|---|---|
| `ops:once:{事件名}:{qid}`，SET NX EX 600 | 名额满事件去重 |
| `ops:lazy_running`，INCR / DECR，每次 INCR 后 EXPIRE 900 | 全站同时在生成的件数（§7 T3）。DECR 后小于 0 就置 0 |
| `ops:pool_peak:{YYYYmmddHHMM}:{hostname}-{pid}`，EX 900 | 每进程每分钟的连接池在用峰值（§7 T2） |
| `lazy:ipr:{ip}:{UTC 日}` | 正式账号的 IP 层额度（新增）。游客继续用原来的 `lazy:ip:` |

## 设计取舍（spec 没写死、由本计划定）

- **R1 告警限频的记录放在 `app_events`（`ops_alert`），不用 §7 写的宿主机文件 `/opt/gomuseum/alerts/{key}.last`**。原因：邮件要在容器里发（SMTP 配置在容器的 `.env` 里），容器看不到宿主机文件。记在库里还有个好处，ops_report 能直接列出发过哪些告警。代价：数据库挂掉时 ops_check 整个跑不起来，这种情况靠外部探活兜底。
- **R2** ops-check.sh 和现有 4 个 cron 脚本一样，按容器名 `gomuseum_prod_backend` 执行 `docker exec`（§2：已有服务保持 `container_name`）。
- **R3 6 项健康告警算上运营预览账号的流量**；只有触发指标排除 `exempt`（§7「所有触发事件都带 exempt……统计时排除」说的是触发指标）。比如测试账号的生成也在失败，同样说明密钥或上游出了问题。
- **R4 spec 没写的窗口和最小样本数**：
  - 浏览/内容接口：15 分钟窗口，至少 20 个请求；5xx 要求至少 5 个且占比 > 1%（发版重启那 20 秒会有零星 502）。
  - 识别向量各路径：24 小时窗口，每条路径至少 20 个样本。
  - AI 兜底日次数：超过 max(20, 3 × 前 30 天日均) 才告警。
  - CPU 告警：最近 3 个 5 分钟采样都 > 70%。T5 触发：这 3 个采样的均值 > 50%。
  - 「中断」：`lazy_started` 15 分钟后还没有同 `run_id` 的 `lazy_finished`。
- **R5** `tts_busy` 不带 `exempt`：它是进程级的并发数，归不到某个账号。
- **R6** `_SEM` 由懒生成和懒翻译共用，两种情况拿不到名额都记 `lazy_slot_full`，用 `kind` 区分。T1 要回答的是「`_SEM` 够不够」。
- **R7** `ALERT_TTS_DAILY_USD=2`：prod 近 30 天 `tts@app` 单日最多 16,752 字（10-19），按 $30/百万字约 $0.50，告警线取约 4 倍。`ALERT_RECOG_DAILY_USD=1`：识别兜底至今没记过账（B8），先按 10-19 峰值 110 次估一个数，上 prod 7 天后用真实账重定，已记入台账。
- **R8** `LLM_PRICES` 的默认值（核对过的单价）写在代码里，`.env` 可以覆盖。所以上线不需要改 `.env`。
- **R9** T3 的「同时生成 ≥ 4 件」只在 `LAZY_CONCURRENCY ≥ 4`（即阶段 1 之后）才判断，spec 原文就是「阶段 1 之后」。
- **R10** `chat()` 在调用方没给超时时用 `LLM_TIMEOUT_S`。识别兜底自己传了 30 秒，保持不变。效果等于「生成类通道 90 秒」，但不用逐个通道列出来。
- **R11** 价目表里没有的模型，输入按全表最高输入价、输出按全表最高输出价计（TTS 按字计价的条目也在表里，所以算出来会偏高），并告警。宁可多算。
- **R12** staging 的 compose 收进仓库（`deployment/staging/docker-compose.yml`），作为手工改 VPS 时的评审依据。这和 prod 的做法一样。

## Review Focus

1. **夏令时切换**：10-25 起 nginx 日志的时区从 `+0200` 变成 `+0100`，统计窗口必须按每一行自带的时区算，否则切换当天浏览告警全错。测试：Task 9 `test_nginx_window_uses_each_lines_offset`。
2. **告警风暴**：同一条告警 6 小时内只发一封，触发提醒 7 天一次；`--dry-run` 一封不发、一行不写；邮件发不出去时不记 `ops_alert`，下次还会再试。测试：Task 9 的 `test_alert_sent_once_per_window`、`test_dry_run_sends_and_writes_nothing`、`test_mail_not_configured_returns_2`。
3. **Redis 不可用**：
   - 名额满事件不记，不能每 4 秒往库里写一行；
   - `lazy_started` 照记，`running=None`；
   - 连接池峰值上报不抛异常。

   测试：Task 6 的 `test_slot_full_not_logged_without_redis`、`test_started_logged_without_redis`，Task 8 的 `test_flush_without_redis_or_on_error_never_raises`。
4. **第一次运行或宿主机指标缺失**（`--cpu ""`、采样不足 3 个、SQLite 下拿不到连接数）：不报 CPU、连接相关的告警，也不崩。测试：Task 9 `test_missing_host_metrics_do_not_alert_or_crash`。
5. **按身份选额度档**：游客令牌走游客档，正式账号走正式档。内容接口必须按 `user.is_guest` 选，选反了游客会拿到 600 的宽额度。测试：Task 5 `test_endpoint_passes_guest_flag`。

## 不在本计划（对应 spec 的后续阶段）

TTS 和大模型的 429 事件（阶段 2、3）；预算到 100% 停止生成（阶段 4）；记账独立连接池和记账失败计数（阶段 2）；slowapi 改存 Redis（阶段 2）；worker 存活、最老等待时长、内容生成预算这 3 项告警（阶段 4）；ops_report 里的补语言积压、因预算被拒的作品（阶段 4）。

---

## 执行前准备

- [ ] worktree 和分支：`cd /Users/hongyang/Projects/GoMuseum-elastic && git status --short && git branch --show-current`。预期工作区干净，分支是 `feature/elastic-scaling-spec`，已合入 10-23 的 staging（#1054）。
- [ ] 装依赖：这个 worktree 的 poetry 环境 10-23 查过是空的，先执行 `cd backend && poetry install`。验证：`poetry run python -c "import fastapi, slowapi, fakeredis"` 没有输出。
- [ ] 跑一遍全量基线：`poetry run pytest -q --no-cov -p no:cacheprovider > <工作区>/baseline.txt 2>&1; tail -5 <工作区>/baseline.txt`。`<工作区>` 是 executing-plans 的 `sdd-workspace` 脚本打印出来的目录。把已有的失败记进 ledger，之后不算本计划造成的。

### Task 1: 懒生成并发数改成配置项（§11 ⑥）

**Files:**
- Modify: `backend/app/core/config.py`。在 `OPENAI_TIMEOUT` 那组后面新开一节「# ── 弹性扩容(spec 2026-10-21-elastic-scaling-design)──」，本计划所有新配置都放在这一节
- Modify: `backend/app/services/enrichment/lazy.py:24`（`_FANOUT_SEM`）、`:32`（`_SEM`）
- Test: `backend/tests/unit/services/test_lazy_concurrency_config.py`（新建）

**Interfaces:**
- Produces: `settings.LAZY_CONCURRENCY: int = 2`、`settings.LAZY_FANOUT_CONCURRENCY: int = 2`。`lazy._SEM` / `lazy._FANOUT_SEM` 的容量等于这两个值，进程启动时读一次。lazy.py 顶部改为 `from app.core.config import settings`（函数里原有的延迟 import 可以留着），后面的任务和测试会用到 `lazy.settings`。

- [ ] **Step 1: 写测试**

```python
"""懒生成并发数是配置项(spec §10):进程启动时读 .env,默认仍为 2(阶段 1 改 4)。"""

import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[3]


def _capacity(extra_env):
    env = {k: v for k, v in os.environ.items() if not k.startswith("LAZY_")}
    code = (
        "from app.services.enrichment import lazy\n"
        "n = lambda s: sum(s.acquire(blocking=False) for _ in range(10))\n"
        "print(n(lazy._SEM), n(lazy._FANOUT_SEM))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        env={**env, **extra_env},
        cwd=BACKEND,
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.split()


def test_default_is_two():
    assert _capacity({}) == ["2", "2"]


def test_read_from_env():
    assert _capacity({"LAZY_CONCURRENCY": "4", "LAZY_FANOUT_CONCURRENCY": "3"}) == [
        "4",
        "3",
    ]
```

- [ ] **Step 2: 确认失败**：`poetry run pytest tests/unit/services/test_lazy_concurrency_config.py -q --no-cov`。预期 `test_read_from_env` FAIL（`['2', '2'] != ['4', '3']`）。`test_default_is_two` 是守卫，改前就该通过。
- [ ] **Step 3: 实现**：在 config 里加上两项；`_SEM = threading.Semaphore(settings.LAZY_CONCURRENCY)`，`_FANOUT_SEM` 同理。把两处 `ponytail:` 注释里写死的「2」改成「见 LAZY_CONCURRENCY」。
- [ ] **Step 4: 确认通过**：上一条命令 PASS；再跑 `poetry run pytest tests/integration/test_lazy_generation.py tests/integration/test_lazy_fanout.py -q --no-cov`，全部 PASS。
- [ ] **Step 5: 提交**：`feat(lazy): 懒生成并发数改成配置项 LAZY_CONCURRENCY / LAZY_FANOUT_CONCURRENCY`

### Task 2: 游客登录限速放宽到每进程 30 次/时（§11 ③）

**Files:**
- Modify: `backend/app/core/config.py`（新增 `GUEST_LOGIN_RATE: str = "30/hour"`，注释写上：每进程计数，两个 web 进程合计约 60；阶段 2 计数改存 Redis 后才是全站 60）
- Modify: `backend/app/api/v1/endpoints/auth.py:189`
- Test: `backend/tests/integration/test_guest_login_rate.py`（新建）

**Interfaces:**
- Produces: `settings.GUEST_LOGIN_RATE`

- [ ] **Step 1: 写测试**

```python
"""游客登录限速(spec §4.2):原来每进程 5 次/时,共用 WiFi 的团体一来就不够用。"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.rate_limit import limiter
from app.main import app
from app.models.app_event import AppEvent
from app.models.user import User
from app.models.user_benefits import UserBenefits


@pytest.fixture()
def client(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[User.__table__, UserBenefits.__table__, AppEvent.__table__],
    )
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    monkeypatch.setattr(limiter, "enabled", True)  # conftest 默认关了限流
    limiter.reset()
    yield TestClient(app)
    limiter.reset()
    app.dependency_overrides.pop(get_db, None)


def test_guest_login_allows_30_per_hour_from_one_ip(client):
    for i in range(30):
        r = client.post("/api/v1/auth/guest", json={"device_id": f"dev-{i}"})
        assert r.status_code == 200, (i, r.text)
    assert client.post("/api/v1/auth/guest", json={"device_id": "dev-30"}).status_code == 429
```

- [ ] **Step 2: 确认失败**：`poetry run pytest tests/integration/test_guest_login_rate.py -q --no-cov`。预期 FAIL，`i == 5` 时拿到 429。
- [ ] **Step 3: 实现**：`@limiter.limit(settings.GUEST_LOGIN_RATE)`，在 import 时读取，`.env` 改了要重启才生效，和其他配置一致。
- [ ] **Step 4: 确认通过**：上一条命令 PASS；`tests/integration/test_quota_abuse.py` 也 PASS。
- [ ] **Step 5: 提交**：`feat(auth): 游客登录限速放宽到每进程 30 次/时,改成配置项 GUEST_LOGIN_RATE`

### Task 3: `chat()` 默认 90 秒超时（§11 ⑤）

**Files:**
- Modify: `backend/app/core/config.py`（新增 `LLM_TIMEOUT_S: float = 90`，注释：每次尝试的秒数，SDK 另有 2 次重试）
- Modify: `backend/app/services/openai_models.py:40-58`（`chat()` 开头）
- Test: `backend/tests/unit/services/test_llm_timeout.py`（新建）

**Interfaces:**
- Produces: `chat()` 的行为：kwargs 里没有 `timeout` 时取 `settings.LLM_TIMEOUT_S`。OpenAI 和 Claude 两条路径都生效（`_claude` 已经认 `timeout`）。

- [ ] **Step 1: 写测试**

```python
"""大模型调用显式超时(spec §3.4 / B12):SDK 默认 600 秒外加 2 次重试,
一次挂住的调用能占住生成线程半小时。"""

import socketserver
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import openai
import pytest

from app.services import content_generation_service as cgs
from app.services import openai_models


class _Hang(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self):
        self.server.hits += 1
        time.sleep(5)  # 远长于测试里的超时:模拟挂住的上游

    def log_message(self, *a):
        pass


class _Server(ThreadingHTTPServer):
    def server_bind(self):  # 跳过 getfqdn 反查(本机可卡 35s)
        socketserver.TCPServer.server_bind(self)


@pytest.fixture()
def hanging(monkeypatch):
    srv = _Server(("127.0.0.1", 0), _Hang)
    srv.hits = 0
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("OPENAI_BASE_URL", f"http://127.0.0.1:{srv.server_address[1]}/v1")
    monkeypatch.setattr(cgs.settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(cgs._openai_tl, "client", None, raising=False)
    monkeypatch.setattr(openai_models.settings, "LLM_CHANNEL_MODELS", {})
    yield srv
    srv.shutdown()


def _ask(**kw):
    return openai_models.chat("gpt-4o-mini", [{"role": "user", "content": "hi"}], **kw)


def test_hanging_call_fails_after_llm_timeout(hanging, monkeypatch):
    monkeypatch.setattr(openai_models.settings, "LLM_TIMEOUT_S", 0.3)
    t = time.monotonic()
    with pytest.raises(openai.APITimeoutError):
        _ask(channel="generate")
    assert time.monotonic() - t < 8  # 3 次 × 0.3 秒 + SDK 退避
    assert hanging.hits == 3  # 1 次 + SDK 默认重试 2 次


def test_explicit_timeout_still_wins(hanging, monkeypatch):
    """识别兜底自己传 30 秒(recognition/vision.py),默认值不能盖掉它。"""
    monkeypatch.setattr(openai_models.settings, "LLM_TIMEOUT_S", 60)
    t = time.monotonic()
    with pytest.raises(openai.APITimeoutError):
        _ask(channel="recognition", timeout=0.3)
    assert time.monotonic() - t < 8
```

- [ ] **Step 2: 确认失败**：`poetry run pytest tests/unit/services/test_llm_timeout.py -q --no-cov`。预期第一条 FAIL：抛的是 `APIConnectionError` 而不是 `APITimeoutError`，因为服务端 5 秒后断开，三次加起来 15 秒以上。第二条是守卫，改前就该通过。
- [ ] **Step 3: 实现**：`chat()` 第一行加 `kw.setdefault("timeout", settings.LLM_TIMEOUT_S)`，放在按模型名分流之前。
- [ ] **Step 4: 确认通过**：上一条命令 PASS；`tests/unit/services/test_openai_client_cross_loop.py` 也 PASS。
- [ ] **Step 5: 提交**：`feat(llm): chat() 没给超时时默认 LLM_TIMEOUT_S=90 秒`

### Task 4: 价目表 + 识别兜底记账（§11 ⑦ 前半）

**Files:**
- Modify: `backend/app/core/config.py`（新增 `LLM_PRICES: dict[str, tuple[float, float]]`，值为「模型 → (输入 $/百万 token, 输出 $/百万 token)」；TTS 模型填「$/百万字符」，输出填 0）
- Modify: `backend/app/services/llm_usage.py`（新增 `cost_usd`）
- Modify: `backend/app/services/recognition/vision.py:70-84`（`_default_complete`）
- Modify: `backend/scripts/llm_cost_report.py`（删掉 `PRICES`，改用 `cost_usd`）
- Test: `backend/tests/unit/services/test_llm_usage.py`（追加）、`backend/tests/unit/services/recognition/test_vision_usage.py`（新建）、`backend/tests/unit/scripts/test_llm_cost_report.py`（新建）

**Interfaces:**
- Produces: `cost_usd(model: str, tokens_in: int, tokens_out: int) -> tuple[float, bool]`，返回（美元，模型是否在价目表里）。未知模型的输入按表里最高输入价、输出按最高输出价计（R11）。Task 9 消费它。

- [ ] **Step 1: 核对单价**：到官方价目页核对下面 8 个模型（来源：prod `llm_usage` 近 30 天出现过的，10-23 只读查），写进 `LLM_PRICES` 默认值，每个模型旁边注明来源 URL 和核对日期。
  - Claude 的两个用 claude-api skill 查，它就是官方价目来源：`claude-haiku-5-5`、`claude-sonnet-5-5`。
  - OpenAI 查 https://platform.openai.com/docs/pricing：`gpt-4o`、`gpt-4o-mini`、`gpt-6-luna`、`gpt-6.1-sol`、`tts-1`。
  - Google 查 https://cloud.google.com/text-to-speech/pricing：`google-chirp3-hd`（每月前 100 万字免费，账上不扣）。
  - 旧表里的 `gpt-4o@batch` 保留，取 `gpt-4o` 的一半。
  - 某个模型官方页查不到时，不写进表（它会按最贵价计并告警），在 ledger 记一条 Ruling，并把它从下面 Step 2 的测试列表里删掉。

- [ ] **Step 2: 写测试**

追加到 `tests/unit/services/test_llm_usage.py`：

```python
from app.core.config import settings
from app.services.llm_usage import cost_usd


def test_cost_of_known_model(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PRICES", {"m1": (1.0, 4.0), "m2": (3.0, 15.0)})
    usd, known = cost_usd("m1", 1_000_000, 500_000)
    assert known is True and usd == pytest.approx(3.0)


def test_unknown_model_priced_at_most_expensive(monkeypatch):
    """spec §4.1:价目表里没有的模型按表里最贵的价算(ops_check 另发告警)。"""
    monkeypatch.setattr(settings, "LLM_PRICES", {"m1": (1.0, 4.0), "m2": (3.0, 15.0)})
    usd, known = cost_usd("brand-new", 1_000_000, 1_000_000)
    assert known is False and usd == pytest.approx(18.0)


def test_default_prices_cover_models_in_use():
    for m in ("gpt-4o", "gpt-4o-mini", "gpt-6-luna", "gpt-6.1-sol",
              "claude-haiku-5-5", "claude-sonnet-5-5", "tts-1", "google-chirp3-hd"):
        assert m in settings.LLM_PRICES, m
```

新建 `tests/unit/services/recognition/test_vision_usage.py`：

```python
"""识别兜底的 AI 用量要记账(spec §4.1 补记账;B8:原来只取 chat()[0],tokens 丢了)。"""

import pytest

from app.services import llm_usage, openai_models
from app.services.recognition import vision


@pytest.mark.parametrize("mode,channel", [("artwork", "recognition"), ("label", "label")])
def test_fallback_usage_recorded_under_its_channel(monkeypatch, mode, channel):
    seen = []
    monkeypatch.setattr(
        openai_models, "chat", lambda *a, **k: ('{"candidates": []}', "gpt-6-luna", 1200, 80)
    )
    monkeypatch.setattr(llm_usage, "record_llm_usage", lambda *a, **k: seen.append(a))
    vision.identify("aGk=", mode=mode)
    assert seen == [(channel, "gpt-6-luna", 1200, 80)]
```

新建 `tests/unit/scripts/test_llm_cost_report.py`：建 SQLite 的 `LLMUsage` 表，插两行今天的数据：`gate@app` / `claude-haiku-5-5` / 输入 1,000,000、输出 0；`vision@app` / `new-model` / 输入 1000、输出 0。把 `settings.LLM_PRICES` 设为 `{"claude-haiku-5-5": (1.0, 5.0)}`，然后断言 `report(db, 30)` 里：
- claude 那一行含 `1.00`（旧 `PRICES` 里没有这个模型，会算成 0）；
- new-model 那一行以 `?` 结尾（按最贵价计）。

- [ ] **Step 3: 确认失败**：`poetry run pytest tests/unit/services/test_llm_usage.py tests/unit/services/recognition/test_vision_usage.py tests/unit/scripts/test_llm_cost_report.py -q --no-cov`。预期 `cost_usd` 导入失败；`seen == []`；报告里 claude 那一行是 `0.00`。
- [ ] **Step 4: 实现**
  - `cost_usd`：按上面 Interfaces 写。
  - `_default_complete`：先 `text, real, tin, tout = chat(...)`，在函数内 `from app.services.llm_usage import record_llm_usage`（写法同 `content_enricher.py:179`），然后 `record_llm_usage(channel or "recognition", real, tin, tout)`，最后返回 `text`。超时仍是 30 秒。
  - `llm_cost_report`：每行金额用 `cost_usd` 算，未知模型在行尾加 ` ?`；合计行的说明改成「价目见 settings.LLM_PRICES」。
- [ ] **Step 5: 确认通过**：Step 3 那条命令 PASS；`poetry run pytest tests/unit/services/recognition -q --no-cov` PASS。
- [ ] **Step 6: 提交**：`feat(cost): 价目表改成配置项 LLM_PRICES(核对过的现行单价),识别兜底补记账`

### Task 5: 懒生成额度按身份分档 + `lazy_cap_hit`（§11 ④）

**Files:**
- Modify: `backend/app/core/config.py`（新增 `CAP_PER_USER: int = 160`、`CAP_PER_IP: int = 300`、`CAP_PER_IP_REGISTERED: int = 600`）
- Modify: `backend/app/services/enrichment/lazy.py:47-50`（常量改成从 settings 读）、`:629-686`（`_charge`）、`:704-777`（`maybe_trigger`）
- Modify: `backend/app/api/v1/endpoints/museums.py:152-161`
- Test: `backend/tests/unit/services/test_lazy_caps.py`（追加）、`backend/tests/integration/test_lazy_generation.py`（fixture 加 `AppEvent.__table__`，追加测试）、`backend/tests/integration/test_object_content_endpoint.py`（追加）

**Interfaces:**
- Produces:
  - `lazy.CAP_PER_USER`、`lazy.CAP_PER_IP`、`lazy.CAP_PER_IP_REGISTERED`：模块常量，值等于 settings。保留模块级名字，现有测试直接 import 它们。
  - `_charge(user_id, ip, weight, redis=None, item=None, guest=True) -> str | None`。`guest=False` 时 IP 层用 `lazy:ipr:{ip}:{日}`、上限 `CAP_PER_IP_REGISTERED`，返回值语义不变。默认 `guest=True`，即身份不明时走更严的那一档。
  - `maybe_trigger(..., is_guest=True)`：透传给 `_charge(guest=is_guest)`；被拒时写 `lazy_cap_hit`（props 见上方事件表；`kind` 取 `"lazy generation"` 或 `"lazy translation"`）。

- [ ] **Step 1: 写测试**

追加到 `tests/unit/services/test_lazy_caps.py`（顶部 import 补上 `CAP_PER_IP_REGISTERED`，以及 `from app.core.config import settings`）：

```python
def test_caps_default_from_settings():
    assert (lazy.CAP_PER_USER, lazy.CAP_PER_IP, lazy.CAP_PER_IP_REGISTERED) == (
        settings.CAP_PER_USER, settings.CAP_PER_IP, settings.CAP_PER_IP_REGISTERED
    ) == (160, 300, 600)


def test_registered_accounts_share_wider_ip_layer(r):
    n = 0
    while _charge(f"u{n}", "9.9.9.9", 8, redis=r, guest=False) is None:
        n += 1
    assert n == CAP_PER_IP_REGISTERED // WEIGHT_GENERATION  # 75 件
    assert r.keys("lazy:ip:*") == []  # 不占游客那一份


def test_guest_ip_full_does_not_block_registered(r):
    r.set(f"lazy:ip:9.9.9.9:{lazy._today()}", CAP_PER_IP)
    assert _charge("g1", "9.9.9.9", 8, redis=r, guest=True) == "ip"
    assert _charge("reg", "9.9.9.9", 8, redis=r, guest=False) is None


def test_registered_ip_full_does_not_block_guest(r):
    r.set(f"lazy:ipr:9.9.9.9:{lazy._today()}", CAP_PER_IP_REGISTERED)
    assert _charge("reg", "9.9.9.9", 8, redis=r, guest=False) == "ip"
    assert _charge("g1", "9.9.9.9", 8, redis=r, guest=True) is None
```

追加到 `tests/integration/test_lazy_generation.py`。fixture 的 `tables=[...]` 里加上 `AppEvent.__table__`，并在文件顶部 import：

```python
def test_cap_hit_logs_event_with_tier(session):
    from app.services.enrichment.lazy import CAP_PER_IP_REGISTERED, _today

    r = fakeredis.FakeRedis(decode_responses=True)
    r.set(f"lazy:ipr:1.2.3.4:{_today()}", CAP_PER_IP_REGISTERED)
    reason = maybe_trigger(
        session, "Q1", schedule=lambda *a: None, environment="staging",
        user_id="u1", ip="1.2.3.4", is_guest=False, redis=r,
    )
    assert reason == "daily_cap"
    assert [e.props for e in session.query(AppEvent).filter_by(name="lazy_cap_hit")] == [
        {"qid": "Q1", "layer": "ip", "tier": "registered",
         "kind": "lazy generation", "exempt": False}
    ]
```

在 `tests/integration/test_object_content_endpoint.py` 里，给 `test_endpoint_passes_user_ip_and_preview_flag` 追加一行 `assert seen["is_guest"] is False`（那个假用户没有 `is_guest` 属性），再新增一个用例：

```python
def test_endpoint_passes_guest_flag(client, monkeypatch):
    """游客令牌必须走游客档:选反了,游客拿到正式账号 600 段的 IP 额度。"""
    import app.services.enrichment.lazy as lazy
    from app.services.auth_service import AuthService

    _make_stub(monkeypatch)
    seen = {}
    monkeypatch.setattr(lazy, "maybe_trigger", lambda db, qid, **kw: seen.update(kw))
    monkeypatch.setattr(
        AuthService, "get_current_user",
        staticmethod(lambda db, t: type("U", (), {"id": "g-1", "is_guest": True})()),
    )
    client.get("/api/v1/museums/orsay/objects/Q1/content?language=zh",
               headers={"Authorization": "Bearer x"})
    assert seen["is_guest"] is True
```

- [ ] **Step 2: 确认失败**：`poetry run pytest tests/unit/services/test_lazy_caps.py tests/integration/test_lazy_generation.py tests/integration/test_object_content_endpoint.py -q --no-cov`。预期新测试失败：导入失败，或 `guest`、`is_guest` 是未知参数，或拿不到 `seen["is_guest"]`。
- [ ] **Step 3: 实现**：照 Interfaces 改。端点那边传 `is_guest=bool(getattr(user, "is_guest", False))`。`lazy_cap_hit` 在 `_clear_lock` 之后用 `log_event` 写。
- [ ] **Step 4: 确认通过**：Step 2 那条命令全部 PASS（老用例也要过：它们不传 `guest`，仍然走 `lazy:ip:`）。
- [ ] **Step 5: 提交**：`feat(lazy): 懒生成额度按身份分档,正式账号 IP 层 600 段且与游客分开计数;额度用尽记 lazy_cap_hit`

### Task 6: 懒生成触发事件（§11 ① 的 lazy_* 四种）

**Files:**
- Modify: `backend/app/services/enrichment/lazy.py`：
  - `_run_locked`（227–264）
  - `run_lazy_generation`（267–279）
  - `_fanout`（325–461，slot 满的分支在 353–355）
  - `_run_fanout`（464–480）
  - `run_lazy_translation`（483–493）
  - `maybe_trigger`：三处 `schedule(...)`
- Test: `backend/tests/unit/services/test_lazy_error_kind.py`（新建）、`backend/tests/integration/test_lazy_generation.py`（追加，并改 3 处断言）、`backend/tests/integration/test_lazy_fanout.py`（fixture 加 `AppEvent.__table__`，追加，并改 1 处断言）

**Interfaces:**
- Consumes: Task 5 的 fixture（已含 `AppEvent`）、`log_event`。
- Produces:
  - `_error_kind(exc: BaseException) -> str`：返回 `"transient"` 或 `"internal"`。沿 `__cause__` / `__context__` 往上找，以下任一成立就是 transient：
    - 是 `TimeoutError`、`ConnectionError`、`openai.APITimeoutError`、`openai.APIConnectionError`、`anthropic.APITimeoutError`、`anthropic.APIConnectionError`、`requests.exceptions.Timeout`、`requests.exceptions.ConnectionError`、`httpx.TimeoutException`、`httpx.NetworkError` 之一；
    - `getattr(exc, "status_code", None)` 等于 429 或 ≥ 500。

    其余都是 internal。阶段 4 的 `error_kind` 列会复用它（§3.4）。
  - 签名改为：
    - `run_lazy_generation(qid, language=None, exempt=False, *, session_factory=None, close=True)`
    - `run_lazy_translation(qid, language, exempt=False, *, ...)`
    - `_run_fanout(qid, exempt=False, *, ...)`
    - `_fanout(db, qid, *, ..., exempt=False)`
    - `_run_locked(qid, work, label, *, session_factory=None, close=True, exempt=False, track=False)`
  - `maybe_trigger` 改成按位置传 exempt：`schedule(run_lazy_generation, qid, language, exempt)`、`schedule(run_lazy_translation, qid, language, exempt)`、`schedule(_run_fanout, qid, exempt)`。不用关键字参数，因为现有测试的 `schedule=lambda fn, *a:` 不接收关键字参数。
  - 事件的 props 见上方事件表。`run_lazy_generation` 传 `track=True`，只有它写 `lazy_started` / `lazy_finished`。
  - `pub` / `held` 取这一件全部段，按（语言, 状态）计数。懒生成只会落在 stub 上，所以全部段就是这一次写的。

- [ ] **Step 1: 写测试**

新建 `tests/unit/services/test_lazy_error_kind.py`：

```python
"""失败类别(spec §3.1 error_kind):transient = 超时、429、5xx、连接错误,其余 internal。"""

import anthropic
import httpx
import openai
import pytest
import requests

from app.services.enrichment import lazy

_REQ = httpx.Request("POST", "https://api.example/v1/chat")


def _status(cls, code):
    return cls("x", response=httpx.Response(code, request=_REQ), body=None)


def _wrapped(inner):
    try:
        raise RuntimeError("pipeline") from inner
    except RuntimeError as e:
        return e


@pytest.mark.parametrize(
    "exc,kind",
    [
        (TimeoutError(), "transient"),
        (ConnectionError(), "transient"),
        (openai.APITimeoutError(request=_REQ), "transient"),
        (openai.APIConnectionError(request=_REQ), "transient"),
        (anthropic.APITimeoutError(request=_REQ), "transient"),
        (_status(openai.RateLimitError, 429), "transient"),
        (_status(openai.InternalServerError, 503), "transient"),
        (_status(openai.BadRequestError, 400), "internal"),
        (requests.exceptions.ReadTimeout(), "transient"),
        (ValueError("bad json"), "internal"),
        (_wrapped(TimeoutError()), "transient"),
    ],
)
def test_error_kind(exc, kind):
    assert lazy._error_kind(exc) == kind
```

追加到 `tests/integration/test_lazy_generation.py`：

```python
def _events(s, name):
    return [e.props for e in s.query(AppEvent).filter_by(name=name)]


def _fake_redis(monkeypatch):
    import app.services.enrichment.lazy as lazy

    r = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(lazy, "_redis", lambda: r)
    return r


def _hold_sem():
    import app.services.enrichment.lazy as lazy

    for _ in range(lazy.settings.LAZY_CONCURRENCY):
        lazy._SEM.acquire()


def _release_sem():
    import app.services.enrichment.lazy as lazy

    for _ in range(lazy.settings.LAZY_CONCURRENCY):
        lazy._SEM.release()


def test_slot_full_logged_once_per_item_per_10_min(session, monkeypatch):
    import app.services.enrichment.lazy as lazy

    r = _fake_redis(monkeypatch)

    def run():
        try_acquire_lock(session, _obj(session))
        lazy.run_lazy_generation("Q1", "zh", True, session_factory=lambda: session, close=False)

    _hold_sem()
    try:
        for _ in range(3):  # App 每 4 秒轮询一次
            run()
        assert _events(session, "lazy_slot_full") == [
            {"qid": "Q1", "kind": "lazy generation", "exempt": True}
        ]
        r.delete("ops:once:lazy_slot_full:Q1")  # 10 分钟过去
        run()
        assert len(_events(session, "lazy_slot_full")) == 2
    finally:
        _release_sem()


def test_slot_full_not_logged_without_redis(session):
    """去重靠 Redis;Redis 挂了宁可不记,也不能每 4 秒往库里写一行。conftest 默认 _redis() 为 None。"""
    import app.services.enrichment.lazy as lazy

    _hold_sem()
    try:
        for _ in range(3):
            try_acquire_lock(session, _obj(session))
            lazy.run_lazy_generation("Q1", session_factory=lambda: session, close=False)
    finally:
        _release_sem()
    assert _events(session, "lazy_slot_full") == []


def test_generation_logs_started_and_finished(session, monkeypatch):
    import app.services.enrichment.lazy as lazy

    r = _fake_redis(monkeypatch)

    def fake_generate(db, qid, language=None):
        o = db.query(MuseumObject).filter_by(qid=qid).one()
        o.content_status = "ready"
        for lang, code, status in (
            ("en", "guide", "published"),
            ("fr", "guide", "published"),
            ("en", "background", "needs_review"),
        ):
            db.add(ObjectContentSection(object_id=o.id, language=lang,
                                        section_code=code, body="x", status=status))
        db.flush()
        return {}

    monkeypatch.setattr(lazy, "_generate", fake_generate)
    monkeypatch.setattr(lazy, "_run_fanout", lambda *a, **k: None)
    try_acquire_lock(session, _obj(session))
    lazy.run_lazy_generation("Q1", "fr", session_factory=lambda: session, close=False)
    [st] = _events(session, "lazy_started")
    [fin] = _events(session, "lazy_finished")
    assert (st["qid"], st["running"], st["exempt"]) == ("Q1", 1, False)
    assert fin["run_id"] == st["run_id"]
    assert (fin["ok"], fin["err_kind"]) == (True, None)
    assert fin["pub"] == {"en": 1, "fr": 1} and fin["held"] == {"en": 1}
    assert fin["dur_s"] >= 0
    assert r.get("ops:lazy_running") == "0"


@pytest.mark.parametrize(
    "exc,kind", [(TimeoutError("upstream"), "transient"), (ValueError("bad json"), "internal")]
)
def test_generation_failure_logs_finished_not_ok(session, monkeypatch, exc, kind):
    """spec §12 监控:生成失败时一定有一条 ok=false 的 lazy_finished。"""
    import app.services.enrichment.lazy as lazy

    def boom(db, qid, language=None):
        raise exc

    monkeypatch.setattr(lazy, "_generate", boom)
    try_acquire_lock(session, _obj(session))
    lazy.run_lazy_generation("Q1", session_factory=lambda: session, close=False)
    [fin] = _events(session, "lazy_finished")
    assert (fin["ok"], fin["err_kind"]) == (False, kind)


def test_started_logged_without_redis(session, monkeypatch):
    import app.services.enrichment.lazy as lazy

    monkeypatch.setattr(lazy, "_generate", lambda db, qid, language=None: {})
    try_acquire_lock(session, _obj(session))
    lazy.run_lazy_generation("Q1", session_factory=lambda: session, close=False)
    [st] = _events(session, "lazy_started")
    assert st["running"] is None


def test_translation_logs_no_started_or_finished(session, monkeypatch):
    import app.services.enrichment.lazy as lazy

    monkeypatch.setattr(lazy, "_translate", lambda db, qid, lang: {})
    o = _obj(session)
    o.content_status = "ready"
    session.commit()
    try_acquire_lock(session, o, require_status=("ready",))
    lazy.run_lazy_translation("Q1", "de", session_factory=lambda: session, close=False)
    assert _events(session, "lazy_started") == [] and _events(session, "lazy_finished") == []
```

追加到 `tests/integration/test_lazy_fanout.py`。fixture 的 `tables=[...]` 里加上 `AppEvent.__table__`：

```python
def test_fanout_slot_full_logs_event(session, monkeypatch):
    r = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(lazy, "_redis", lambda: r)
    held = [lazy._FANOUT_SEM.acquire(blocking=False)
            for _ in range(lazy.settings.LAZY_FANOUT_CONCURRENCY)]
    assert all(held)
    try:
        for _ in range(2):
            assert lazy._fanout(session, "Q1", langs=["en", "fr", "de"], translator=_Tr(),
                                session_factory=lambda: session, close=False,
                                executor=_Serial(), exempt=True) == {}
    finally:
        for _ in held:
            lazy._FANOUT_SEM.release()
    assert [e.props for e in session.query(AppEvent).filter_by(name="lazy_fanout_slot_full")] == [
        {"qid": "Q1", "exempt": True}
    ]
```

再改 4 处现有断言：后台任务多了一个按位置传的 `exempt`，非预览账号是 `False`。

- `test_lazy_generation.py` 第 91 行：改为 `assert scheduled == [("Q1", "fr", False)]`
- `test_lazy_generation.py` 第 166 行：改为 `[("run_lazy_translation", ("Q1", "de", False))]`
- `test_lazy_generation.py` 第 393 行：改为 `[("run_lazy_translation", ("Q1", "zh", False))]`
- `test_lazy_fanout.py` 第 279 行：改为 `assert (lazy._run_fanout, ("Q1", False)) in calls`

- [ ] **Step 2: 确认失败**：`poetry run pytest tests/unit/services/test_lazy_error_kind.py tests/integration/test_lazy_generation.py tests/integration/test_lazy_fanout.py -q --no-cov`。预期：新测试失败（`_error_kind` 不存在、没有事件、`exempt` 是未知参数）；改过的 4 处断言也失败（参数还是两元组）。
- [ ] **Step 3: 实现**：照 Interfaces 改，几条要点：
  - 名额满：在 `_clear_lock` 之后用 `_log_once(db, name, qid, **props)` 记。它先 `SET ops:once:{name}:{qid} NX EX 600`，Redis 为 None 或报错就不记。
  - `lazy_started`：拿到 `_SEM`、开好会话之后立刻记。
  - `lazy_finished`：在 `_tag_lazy_rows`、`_clear_lock` 之后记。
  - `ops:lazy_running` 的 DECR 放在释放 `_SEM` 的 `finally` 里，`BaseException` 时也要减回去。
- [ ] **Step 4: 确认通过**：Step 2 那条命令全部 PASS；再跑 `poetry run pytest tests/integration/test_object_content_endpoint.py tests/unit/services/test_lazy_caps.py -q --no-cov`，PASS。
- [ ] **Step 5: 提交**：`feat(lazy): 记懒生成触发事件 lazy_slot_full / lazy_fanout_slot_full / lazy_started / lazy_finished(带 exempt)`

### Task 7: TTS 同时合成数 `tts_busy`（§7 T2）

**Files:**
- Modify: `backend/app/services/tts_service.py:180-196`（`_drain`）
- Test: `backend/tests/unit/services/test_tts_busy.py`（新建）

**Interfaces:**
- Produces（模块级）：
  - `_active: int`（本进程正在合成的路数）
  - `_BUSY_AT = 4`
  - `_busy_logged: float`（上次记事件的 monotonic 时刻，初值 `-inf`）
  - `_note_busy(n: int, now: float) -> bool`：`n ≥ 4`，并且距离上次记录 ≥ 60 秒，才调用 `_log_busy(n)` 并返回 True。
  - `_log_busy(n: int, session_factory=None) -> None`：默认用 `SessionLocal` 开一个短会话写 `tts_busy`，任何异常只记 warning。
  - `_drain` 在整个函数外包一层 try/finally：进入时 `_active += 1`，并对加完后的值调用 `_note_busy`；退出时 `_active -= 1`。读写都用一把锁。

- [ ] **Step 1: 写测试**

```python
"""TTS 同时合成数(spec §7 T2):本进程同时合成达到 4 路记一条 tts_busy,每分钟最多一条。"""

import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.app_event import AppEvent
from app.services import tts_service as tts


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.setattr(tts, "_busy_logged", float("-inf"))
    monkeypatch.setattr(tts, "_active", 0)


def test_note_busy_threshold_and_once_a_minute(monkeypatch):
    seen = []
    monkeypatch.setattr(tts, "_log_busy", lambda n: seen.append(n))
    assert tts._note_busy(3, now=100.0) is False
    assert tts._note_busy(4, now=100.0) is True
    assert tts._note_busy(6, now=159.9) is False
    assert tts._note_busy(5, now=160.0) is True
    assert seen == [4, 5]


def test_log_busy_writes_event():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine, tables=[AppEvent.__table__])
    S = sessionmaker(bind=engine)
    tts._log_busy(4, session_factory=S)
    assert [e.props for e in S().query(AppEvent).filter_by(name="tts_busy")] == [{"active": 4}]


def test_drain_counts_active_and_releases_on_error():
    seen = []

    def it():
        seen.append(tts._active)
        yield b"x"
        raise RuntimeError("boom")

    loop = asyncio.new_event_loop()
    try:
        tts._drain(loop, asyncio.Queue(), it, object())
    finally:
        loop.close()
    assert seen == [1] and tts._active == 0
```

- [ ] **Step 2: 确认失败**：`poetry run pytest tests/unit/services/test_tts_busy.py -q --no-cov`，预期报属性不存在。
- [ ] **Step 3: 实现**：照 Interfaces 写。
- [ ] **Step 4: 确认通过**：上一条命令 PASS；`tests/unit/services/test_tts_service.py` 也 PASS。
- [ ] **Step 5: 提交**：`feat(tts): 本进程同时合成达到 4 路时记 tts_busy(每分钟最多一条)`

### Task 8: 连接池在用峰值写进 Redis（§7 T2）

**Files:**
- Modify: `backend/app/core/database.py:46-51`（`receive_checkout` 里加一行）和文件末尾
- Modify: `backend/app/main.py:45-50`（`_startup` 里启动上报线程，写法照旁边那些 try 块）
- Test: `backend/tests/unit/test_pool_peak.py`（新建）

**Interfaces:**
- Produces（`app.core.database`）：
  - `POOL_PEAK_KEY = "ops:pool_peak:{minute}:{proc}"`
  - `note_checkout(checked_out: int) -> None`：更新本进程当前这一分钟的峰值。不加锁，并发时最多少记 1，写一条 `ponytail:` 注释说明。
  - `flush_pool_peak(redis, current: int, now: datetime) -> int | None`：把 `max(峰值, current)` 写到 `POOL_PEAK_KEY`，EX 900；`minute` 取 `now` 的 `%Y%m%d%H%M`，`proc` 取 `{hostname}-{pid}`。写完把峰值重置成 `current`，这样跨分钟还被占着的连接会算进下一分钟。返回写入的值；redis 为 None 或报错时返回 None，不抛异常。
  - `start_pool_peak_reporter() -> None`：起一个守护线程，每 60 秒用 `_get_redis()`（函数内延迟 import）和 `engine.pool.checkedout()` 调一次 `flush_pool_peak`，异常只记 warning。
  - Task 9 的读取方用 `POOL_PEAK_KEY` 的前缀 `ops:pool_peak:`。

- [ ] **Step 1: 写测试**

```python
"""连接池在用峰值(spec §7「在用连接峰值」):每进程每分钟的最高值写进 Redis。
5 分钟一次的 pg_stat_activity 采样看不到几十秒的尖峰。"""

from datetime import datetime, timedelta, timezone

import fakeredis
import pytest

from app.core import database

NOW = datetime(2026, 10, 23, 12, 34, 56, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.setattr(database, "_pool_peak", 0)


def test_flush_writes_minute_peak_and_resets_to_current():
    r = fakeredis.FakeRedis(decode_responses=True)
    for n in (3, 5, 2):
        database.note_checkout(n)
    assert database.flush_pool_peak(r, current=2, now=NOW) == 5
    [key] = r.keys("ops:pool_peak:202610231234:*")
    assert r.get(key) == "5" and 0 < r.ttl(key) <= 900
    # 跨分钟仍被占着的 2 个连接算进下一分钟
    assert database.flush_pool_peak(r, current=1, now=NOW + timedelta(minutes=1)) == 2


def test_flush_without_redis_or_on_error_never_raises():
    class Boom:
        def set(self, *a, **k):
            raise ConnectionError("down")

    assert database.flush_pool_peak(None, current=0, now=NOW) is None
    assert database.flush_pool_peak(Boom(), current=0, now=NOW) is None
```

- [ ] **Step 2: 确认失败**：`poetry run pytest tests/unit/test_pool_peak.py -q --no-cov`，预期报属性不存在。
- [ ] **Step 3: 实现**：照 Interfaces 写。`receive_checkout` 里加 `note_checkout(engine.pool.checkedout())`，原来那行 debug 日志不动。
- [ ] **Step 4: 确认通过**：上一条命令 PASS；`tests/unit/test_main_lifespan.py` 也 PASS。
- [ ] **Step 5: 提交**：`feat(db): 每进程每分钟的连接池在用峰值写进 Redis(扩容触发指标)`

### Task 9: `scripts/ops_check.py` + `ops-check.sh`（§11 ① 告警、⑦ 三笔账告警）

**Files:**
- Modify: `backend/app/core/config.py`（新增 `BUDGET_GEN_DAILY_USD: float = 30`、`BUDGET_GEN_MONTHLY_USD: float = 300`、`BUDGET_ALERT_RATIO: float = 0.8`、`ALERT_TTS_DAILY_USD: float = 2`、`ALERT_RECOG_DAILY_USD: float = 1`，注释引 R7）
- Create: `backend/scripts/ops_check.py`
- Create: `deployment/production/ops-check.sh`
- Test: `backend/tests/unit/scripts/test_ops_check.py`（新建）

**Interfaces:**
- Consumes: 上方事件表和 Redis 键表、Task 4 的 `cost_usd`、Task 8 的 `POOL_PEAK_KEY`、`ops_alert.send(subject, body)`、`log_event`、`settings.RECOG_MODEL`、`settings.LAZY_CONCURRENCY`。
- Produces（Task 10 用 `collect` 和下面定的键）：
  - `p95(xs: list[float]) -> float | None`：用最近秩法，`sorted(xs)[ceil(0.95·n) − 1]`。
  - `nginx_stats(lines: Iterable[str], now: datetime, minutes: int) -> dict`，返回 `{"n", "p95", "n5xx"}`。
  - `pool_peak(redis, now) -> int | None`：取最近 5 个分钟键，同一分钟内各进程的值相加，再在这几分钟里取最大值。
  - `take_sample(db, now, lines: list[str], host: dict) -> dict`：返回 ops_sample 的各字段（见事件表）。
  - `collect(db, now) -> dict`：各键见下表。
  - `evaluate(sample: dict, m: dict) -> list[tuple[str, int, str, str]]`：返回 (key, 限频小时数, subject, body) 的列表。
  - `due(db, key: str, hours: int, now) -> bool`：最近 `hours` 小时内没有这个 key 的 `ops_alert` 时返回 True。
  - `main(argv: list[str] | None = None) -> int`：参数 `--cpu`、`--mem`、`--disk`（字符串，空串当 None）和 `--dry-run`。退出码 0 = 正常；2 = 有告警但发不出去（`MailNotConfigured` 或发信失败），和 `audio_inventory` 一致。
  - `_redis()`：照 lazy.py 的写法，延迟 import `_get_redis`，方便测试替换。
  - 模块顶层要 `from app.core.database import SessionLocal` 和 `from app.services import ops_alert`，测试会替换 `oc.SessionLocal`、`oc.ops_alert.send`、`oc._redis`。

**`nginx_stats` 的规则：**
- 行格式是 `main_rt`（`deployment/production/nginx-api.gomuseum.app.conf`）。时间取 `[...]` 里的 `%d/%b/%Y:%H:%M:%S %z`，按每行自带的时区算。
- 只统计 `GET` 请求，并且路径（去掉 `?` 之后的部分）以 `/api/v1/` 开头。
- 剔除两类：路径里含 `/audio` 的（`/audio` 和 `/audio/stream` 都是长连接）；匹配 `^/api/v1/museums/[^/]+$` 的（老 App 拉的 5MB 全量馆包，§0.3）。
- `urt=` 后面可能是 `-`，也可能有多个值（`0.5, 0.3` 或 `0.5 : 0.3`），取其中所有数字之和。一个数字都没有的行不进 p95，但照样计入 n 和 5xx。
- 解析不了的行（扫描器发的二进制请求）跳过。

**`take_sample` 各字段：**
- `cpu`、`mem`、`disk`：取自 `host`。
- `req_*`：15 分钟窗口；`req5_*`：5 分钟窗口。
- `conn_total`、`conn_in_use`、`conn_max`：只在 PG 上查，其他方言给 None。查法：`select count(*), count(*) filter (where state <> 'idle'), current_setting('max_connections')::int from pg_stat_activity where backend_type = 'client backend'`。
- `pool_peak`：用 `pool_peak(_redis(), now)`。
- `recog_5m`：最近 5 分钟的 `recognition_events` 行数。

**`collect` 的键：**

| 键 | 定义 |
|---|---|
| `recog_p95` | 近 24 小时的 `recognition_events`，按 engine ∈ {`vector`, `vector_canvas`, `vector_crops`, `text`} 分组，每组 `{"n": 条数, "p95": duration_ms 的 p95 ÷ 1000}`；没有样本时 n=0、p95=None |
| `ai_today`、`ai_avg30` | engine=`text` 的条数：前者从 UTC 今天 0 点起算；后者是 [今天 0 点 − 30 天, 今天 0 点) 内的总数 ÷ 30 |
| `gen_1h` | 近 1 小时的 `lazy_finished`，**包含** exempt（R3）：`{"n": 总数, "fail": ok 为假的数}` |
| `gen_bad_7d` | 近 7 天、排除 exempt：ok 为假的 `lazy_finished` 数，加上「15 分钟前就开始、却没有同 `run_id` 的 `lazy_finished`」的 `lazy_started` 数 |
| `slot_full_days` | 近 7 天、排除 exempt，出现过 `lazy_slot_full` 或 `lazy_fanout_slot_full` 的 UTC 日数 |
| `busy_gen_days` | 近 7 天、排除 exempt，出现过 `running ≥ 4` 的 `lazy_started` 的 UTC 日数 |
| `tts_busy_days` | 近 7 天出现过 `tts_busy` 的 UTC 日数 |
| `conn_peak_7d` | 近 7 天 `ops_sample` 里 `conn_in_use` 和 `pool_peak` 的最大值；没有样本时为 None |
| `cpu_prev` | created_at ∈ [now − 14 分钟, now) 的 `ops_sample` 的 cpu 值，去掉 None，按时间排序 |
| `vq_7d` | 近 7 天 `recognition_events.timings["vq"]`（毫秒）÷ 1000，`{"n", "p95"}` |
| `vectors` | `object_embeddings` 里 `model == settings.RECOG_MODEL` 的行数，只数当前模型（§5.3） |
| `objects` | `museum_objects` 的行数 |
| `ip_cap_hits` | 近 7 天 layer=`ip` 的 `lazy_cap_hit` 次数，`{"guest": n, "registered": n}` |
| `ledger` | 取 `llm_usage` 本月（UTC）的行，逐行用 `cost_usd` 计价，只算 `@app` 通道：`gen_day` 和 `gen_month` 统计 generate、gate、translate、qa、vision；`tts_day` 统计 tts；`recog_day` 统计 recognition、label。`unknown_models` 是今天 `@app` 行里不在价目表的模型，去重后排序 |

时间比较要注意：`app_events.created_at` 带时区，用 aware UTC 比；`recognition_events.created_at` 不带时区但存的是 UTC，用 `now.replace(tzinfo=None)` 比；`llm_usage.day` 用 `now.date()` 比。时间比较一律放在 SQL 的 WHERE 里做，Python 里只取 `.date()`：SQLite 读回来的是 naive datetime，在 Python 里和 aware 比较会抛 TypeError。props 一律在 Python 里读，不写 JSON 路径的 SQL：测试跑在 SQLite 上，线上是 PG。

**`evaluate` 的告警**（限频 6 小时。每封邮件写明测到的值、阈值、「处理办法：……」，并注明「见 docs/ops/capacity-runbook.md」；subject 以 `[GoMuseum]` 开头）：

| key | 条件 | 处理办法 |
|---|---|---|
| `browse-p95` | `req_n ≥ 20` 且 `req_p95 > 1.0` | 先按路径看是哪个接口慢；整体都慢就加 web 进程 |
| `browse-5xx` | `req_n ≥ 20`、`req_5xx ≥ 5` 且 `req_5xx / req_n > 1%` | `docker logs --since 20m gomuseum_prod_backend` 查异常 |
| `recog-p95-{engine}` | engine ∈ {vector 1.0, vector_canvas 4.0, vector_crops 4.2}（§0.2 基线，单位秒），`n ≥ 20` 且 `p95 > 1.5 × 基线`。AI 兜底（text）不告警，只进报告 | 看 CPU（`docker stats`，同机其他项目也算）；持续超线就按 spec 阶段 5 拆出 recognizer |
| `host-disk` / `host-mem` | 超过 80 | 清理备份目录和旧镜像，或者加资源 |
| `host-cpu` | `cpu_prev` 加上本次 cpu 一共 3 个值，并且都 > 70 | 用 `docker stats` 找出占 CPU 的容器 |
| `db-conn` | `conn_total > 0.8 × conn_max` | 按扩容总规则第 1 条调整连接池或 `max_connections` |
| `gen-fail` | `fail ≥ 5` 且 `fail / n > 20%` | 在 docker logs 里查 `lazy generation failed`。transient 去看上游状态页和额度；internal 是我们的 bug |
| `recog-ai-daily` | `ai_today > max(20, 3 × ai_avg30)` | 按 user_id 分组看有没有人在刷识别，必要时收紧 nginx 的识别限流 |
| `budget-gen-day-80` / `-100` | `gen_day` 达到 80% / 100% × `BUDGET_GEN_DAILY_USD` | 阶段 0 不会自动停（只有段数日上限兜底）。看是谁在大量生成，再决定是调预算还是离线预生成 |
| `budget-gen-month-80` / `-100` | `gen_month` 达到 80% / 100% × `BUDGET_GEN_MONTHLY_USD` | 同上 |
| `budget-tts-day` | `tts_day ≥ 0.8 × ALERT_TTS_DAILY_USD` | 只告警。看未缓存的首播量，以及有没有人在刷 `/audio` |
| `budget-recog-day` | `recog_day ≥ 0.8 × ALERT_RECOG_DAILY_USD` | 只告警，处理同 `recog-ai-daily` |
| `price-unknown-{model}` | `unknown_models` 里每有一个模型就发一条 | 到官方价目页查这个模型的单价，补进 `.env` 的 `LLM_PRICES`，再重启后端 |

**`evaluate` 的阶段提醒**（限频 168 小时。subject 同样以 `[GoMuseum]` 开头，写「该进入阶段 N 了」；body 写测到的值、阈值，以及「处理办法：照 spec §11 阶段 N 做，先写实施计划经用户批准」）：

| key | 条件 | 对应 |
|---|---|---|
| `trigger-t1` | `slot_full_days ≥ 3` | 阶段 1：`.env` 里两个并发改成 4，重启 web，观察一天日志和连接数 |
| `trigger-t2-conn` | `max(conn_peak_7d, sample.conn_in_use, sample.pool_peak) > 40` | 阶段 2 |
| `trigger-t2-tts` | `tts_busy_days ≥ 3` | 阶段 2 |
| `trigger-t2-vq` | `vq_7d.n ≥ 50` 且 `vq_7d.p95 > 0.5` | 阶段 2 |
| `trigger-t2-vectors` | `vectors > 100_000` | 阶段 2（§5.3 档①） |
| `trigger-vectors-700k` | `vectors > 700_000` | §5.3 档③ |
| `trigger-t3-concurrency` | `settings.LAZY_CONCURRENCY ≥ 4` 且 `busy_gen_days ≥ 3`（R9） | 阶段 3 |
| `trigger-t3-failures` | `gen_bad_7d > 5` | 阶段 3 |
| `trigger-t5-cpu` | `cpu_prev` 加本次一共 3 个值，均值 > 50 | 阶段 5 |
| `trigger-t5-recog` | `recog_5m ≥ 20`、`req5_n ≥ 20` 且 `req5_p95 > 1.0` | 阶段 5 |
| `trigger-ip-cap-{tier}` | `ip_cap_hits[tier] > 0` | §4.2：评估要不要放宽这一档的 IP 额度 |
| `trigger-search-engine` | `objects > 150_000` | §5.4：换外部搜索引擎 |

**`main` 的流程**：
1. 解析参数，读 stdin。stdin 是 tty 时当作没有日志。
2. 依次调用 `take_sample`、`collect`、`evaluate`。
3. 不是 dry-run 时，先 `log_event(db, "ops_sample", **sample)`。
4. 对 `evaluate` 返回的每一条：
   - `due()` 为 False 的跳过；
   - dry-run 时只打印 key 和 subject；
   - 否则 `ops_alert.send`，发成功后才 `log_event(db, "ops_alert", key=key)`。发信抛异常时记下，最后返回 2。
5. 最后打印一行摘要：采样的关键值，以及发了哪些 key。

- [ ] **Step 1: 写测试**（`tests/unit/scripts/test_ops_check.py`）

```python
"""ops_check:采样、6 项告警 + 三笔账告警、阶段触发提醒(spec §7)。"""

import io
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
        f'"Dart/3.5" "-" rt={urt} urt={urt}'
    )


# ---------- nginx ----------
def test_nginx_counts_only_browse_gets_in_window():
    t = "23/Oct/2026:13:55:00 +0200"  # 11:55Z,在 15 分钟窗口内
    lines = [
        _line(t, "/api/v1/museums/orsay/objects/Q1/content?language=fr", urt="0.200"),
        _line(t, "/api/v1/search?q=monet", urt="0.400"),
        _line(t, "/api/v1/museums/orsay/objects/Q1/audio/stream?section=guide", urt="9.000"),
        _line(t, "/api/v1/museums/orsay/objects/Q1/audio?section=guide", urt="12.000"),
        _line(t, "/api/v1/museums/orsay", urt="3.000"),  # 5MB 全量馆包
        _line(t, "/api/v1/recognize", method="POST", urt="5.000"),
        _line("23/Oct/2026:13:40:00 +0200", "/api/v1/museums", urt="8.000"),  # 窗口外
        '"\\x05\\x01\\x00" 400',  # 扫描器
    ]
    assert oc.nginx_stats(lines, NOW, 15) == {"n": 2, "p95": pytest.approx(0.4), "n5xx": 0}


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
    assert oc.nginx_stats(lines, NOW, 15) == {"n": 2, "p95": pytest.approx(0.8), "n5xx": 1}


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
    s = dict(cpu=10, mem=20, disk=25, req_n=100, req_p95=0.2, req_5xx=0,
             req5_n=30, req5_p95=0.2, conn_total=10, conn_in_use=2,
             conn_max=100, pool_peak=3, recog_5m=0)
    return {**s, **kw}


def _m(**kw):
    m = dict(
        recog_p95={e: {"n": 50, "p95": 0.5}
                   for e in ("vector", "vector_canvas", "vector_crops", "text")},
        ai_today=5, ai_avg30=17.1, gen_1h={"n": 10, "fail": 0}, gen_bad_7d=0,
        slot_full_days=0, busy_gen_days=0, tts_busy_days=0, conn_peak_7d=12,
        cpu_prev=[10, 12], vq_7d={"n": 100, "p95": 0.2}, vectors=26678,
        objects=27383, ip_cap_hits={"guest": 0, "registered": 0},
        ledger={"gen_day": 1.0, "gen_month": 20.0, "tts_day": 0.1,
                "recog_day": 0.05, "unknown_models": []},
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


def test_browse_5xx_needs_5_errors_and_over_1pct():
    assert "browse-5xx" in _keys(_sample(req_n=400, req_5xx=5))
    assert "browse-5xx" not in _keys(_sample(req_n=20, req_5xx=4))
    assert "browse-5xx" not in _keys(_sample(req_n=600, req_5xx=5))


def test_recog_p95_against_baseline_times_1_5():
    assert "recog-p95-vector_canvas" in _keys(m=_recog("vector_canvas", 20, 6.1))
    assert "recog-p95-vector_canvas" not in _keys(m=_recog("vector_canvas", 19, 9.0))
    assert not any(k.startswith("recog-p95") for k in _keys(m=_recog("text", 99, 60.0)))


def test_host_cpu_needs_three_samples_all_over_70():
    assert "host-cpu" in _keys(_sample(cpu=75), _m(cpu_prev=[71, 80]))
    assert "host-cpu" not in _keys(_sample(cpu=75), _m(cpu_prev=[60, 80]))
    assert "host-cpu" not in _keys(_sample(cpu=99), _m(cpu_prev=[99]))


def test_t5_cpu_mean_over_50():
    assert "trigger-t5-cpu" in _keys(_sample(cpu=40), _m(cpu_prev=[60, 60]))
    assert "trigger-t5-cpu" not in _keys(_sample(cpu=40), _m(cpu_prev=[50, 50]))


def test_missing_host_metrics_do_not_alert_or_crash():
    keys = _keys(
        _sample(cpu=None, mem=None, disk=None, conn_total=None, conn_in_use=None,
                conn_max=None, pool_peak=None),
        _m(cpu_prev=[], conn_peak_7d=None),
    )
    assert not [k for k in keys if k.startswith(("host-", "db-", "trigger-t5", "trigger-t2-conn"))]


def test_disk_mem_and_db_connections():
    assert {"host-disk", "host-mem"} <= _keys(_sample(disk=81, mem=81))
    assert "db-conn" in _keys(_sample(conn_total=81, conn_max=100))
    assert "db-conn" not in _keys(_sample(conn_total=80, conn_max=100))


def test_gen_fail_needs_5_failures_and_over_20pct():
    assert "gen-fail" in _keys(m=_m(gen_1h={"n": 20, "fail": 5}))
    assert "gen-fail" not in _keys(m=_m(gen_1h={"n": 10, "fail": 4}))
    assert "gen-fail" not in _keys(m=_m(gen_1h={"n": 30, "fail": 5}))


def test_ai_daily_over_3x_30_day_average_with_floor_20():
    assert "recog-ai-daily" in _keys(m=_m(ai_today=52, ai_avg30=17.1))
    assert "recog-ai-daily" not in _keys(m=_m(ai_today=51, ai_avg30=17.1))
    assert "recog-ai-daily" in _keys(m=_m(ai_today=21, ai_avg30=1.0))
    assert "recog-ai-daily" not in _keys(m=_m(ai_today=20, ai_avg30=1.0))


def test_budget_alerts_at_80_and_100(monkeypatch):
    for k, v in (("BUDGET_GEN_DAILY_USD", 30.0), ("BUDGET_GEN_MONTHLY_USD", 300.0),
                 ("BUDGET_ALERT_RATIO", 0.8), ("ALERT_TTS_DAILY_USD", 2.0),
                 ("ALERT_RECOG_DAILY_USD", 1.0)):
        monkeypatch.setattr(settings, k, v)
    k24 = _keys(m=_ledger(gen_day=24.0))
    assert "budget-gen-day-80" in k24 and "budget-gen-day-100" not in k24
    assert {"budget-gen-day-80", "budget-gen-day-100"} <= _keys(m=_ledger(gen_day=30.0))
    assert "budget-gen-month-80" in _keys(m=_ledger(gen_month=240.0))
    assert "budget-tts-day" in _keys(m=_ledger(tts_day=1.6))
    assert "budget-recog-day" in _keys(m=_ledger(recog_day=0.8))
    assert "price-unknown-gpt-7" in _keys(m=_ledger(unknown_models=["gpt-7"]))


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
    assert "trigger-ip-cap-guest" in _keys(m=_m(ip_cap_hits={"guest": 1, "registered": 0}))
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
    Base.metadata.create_all(bind=engine, tables=[
        Museum.__table__, MuseumObject.__table__, ObjectImage.__table__,
        ObjectEmbedding.__table__, AppEvent.__table__, RecognitionEvent.__table__,
        LLMUsage.__table__,
    ])
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def _ev(db, name, at, **props):
    db.add(AppEvent(name=name, created_at=at, props=props))
    db.commit()


def test_exempt_excluded_from_triggers_but_counted_in_health(db):
    for d in range(3):
        _ev(db, "lazy_slot_full", NOW - timedelta(days=d), qid="Q1",
            kind="lazy generation", exempt=True)
    _ev(db, "lazy_finished", NOW - timedelta(minutes=10), qid="Q1", run_id="a",
        ok=False, exempt=True)
    m = oc.collect(db, NOW)
    assert m["slot_full_days"] == 0
    assert m["gen_bad_7d"] == 0
    assert m["gen_1h"] == {"n": 1, "fail": 1}


def test_interrupted_generation_counts_after_15_minutes(db):
    _ev(db, "lazy_started", NOW - timedelta(minutes=20), qid="Q1", run_id="old", running=1, exempt=False)
    _ev(db, "lazy_started", NOW - timedelta(minutes=5), qid="Q2", run_id="new", running=2, exempt=False)
    _ev(db, "lazy_started", NOW - timedelta(minutes=30), qid="Q3", run_id="done", running=1, exempt=False)
    _ev(db, "lazy_finished", NOW - timedelta(minutes=29), qid="Q3", run_id="done", ok=True, exempt=False)
    assert oc.collect(db, NOW)["gen_bad_7d"] == 1


def test_vectors_count_only_current_model(db, monkeypatch):
    import uuid

    monkeypatch.setattr(settings, "RECOG_MODEL", "dinov3-vits16")
    for model in ("dinov3-vits16", "dinov3-vits16", "dinov2-vits14"):
        db.add(ObjectEmbedding(object_id=uuid.uuid4(), image_id=uuid.uuid4(),
                               model=model, vec=b"x"))
    db.commit()
    assert oc.collect(db, NOW)["vectors"] == 2


def test_ledger_counts_app_channels_on_utc_day(db, monkeypatch):
    monkeypatch.setattr(settings, "LLM_PRICES", {"m": (1.0, 0.0)})
    today, yesterday = NOW.date(), NOW.date() - timedelta(days=1)
    for day, ch, tin in [
        (today, "generate@app", 1_000_000),
        (today, "translate", 5_000_000),  # 离线脚本,不计
        (today, "tts@app", 2_000_000),
        (today, "recognition@app", 300_000),
        (today, "label@app", 200_000),
        (yesterday, "qa@app", 4_000_000),  # 只进本月
    ]:
        db.add(LLMUsage(day=day, channel=ch, model="m", calls=1, tokens_in=tin, tokens_out=0))
    db.add(LLMUsage(day=today, channel="vision@app", model="new-model", calls=1,
                    tokens_in=0, tokens_out=0))
    db.commit()
    led = oc.collect(db, NOW)["ledger"]
    assert led["gen_day"] == pytest.approx(1.0)
    assert led["gen_month"] == pytest.approx(5.0)
    assert led["tts_day"] == pytest.approx(2.0)
    assert led["recog_day"] == pytest.approx(0.5)
    assert led["unknown_models"] == ["new-model"]


def test_recognition_p95_and_ai_counts(db):
    naive = NOW.replace(tzinfo=None)
    for i in range(20):
        db.add(RecognitionEvent(phash=f"p{i}", outcome="match", engine="vector_canvas",
                                duration_ms=1000 * (i + 1), created_at=naive - timedelta(hours=1)))
    db.add(RecognitionEvent(phash="old", outcome="match", engine="vector_canvas",
                            duration_ms=99_000, created_at=naive - timedelta(hours=25)))
    for d in range(1, 31):
        db.add(RecognitionEvent(phash=f"t{d}", outcome="match", engine="text",
                                duration_ms=5000, created_at=naive - timedelta(days=d)))
    for i in range(3):
        db.add(RecognitionEvent(phash=f"today{i}", outcome="match", engine="text",
                                duration_ms=5000, created_at=naive - timedelta(minutes=10)))
    db.commit()
    m = oc.collect(db, NOW)
    assert m["recog_p95"]["vector_canvas"] == {"n": 20, "p95": pytest.approx(19.0)}
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


def test_alert_sent_once_per_window(db, wired):
    assert oc.main(["--disk", "95"]) == 0
    assert oc.main(["--disk", "95"]) == 0
    assert len(wired) == 1  # 第二次还在 6 小时内
    assert [e.props for e in db.query(AppEvent).filter_by(name="ops_alert")] == [{"key": "host-disk"}]
    assert db.query(AppEvent).filter_by(name="ops_sample").count() == 2


def test_dry_run_sends_and_writes_nothing(db, wired, capsys):
    assert oc.main(["--disk", "95", "--dry-run"]) == 0
    assert wired == [] and db.query(AppEvent).count() == 0
    assert "host-disk" in capsys.readouterr().out


def test_mail_not_configured_returns_2(db, wired, monkeypatch):
    from app.services import mailer

    def boom(subject, body):
        raise mailer.MailNotConfigured("OPS_ALERT_EMAIL 未配置")

    monkeypatch.setattr(oc.ops_alert, "send", boom)
    assert oc.main(["--disk", "95"]) == 2
    assert db.query(AppEvent).filter_by(name="ops_alert").count() == 0  # 没发出去,下次再试
```

- [ ] **Step 2: 确认失败**：`poetry run pytest tests/unit/scripts/test_ops_check.py -q --no-cov`，预期 `ModuleNotFoundError: scripts.ops_check`。
- [ ] **Step 3: 实现 `scripts/ops_check.py`**：照上面的 Interfaces 和三张表写。模块 docstring 照 `scripts/audio_inventory.py` 的结构写：为什么需要、怎么运行、退出码。
- [ ] **Step 4: 确认通过**：Step 2 的命令 PASS。
- [ ] **Step 5: 写 `deployment/production/ops-check.sh`**，内容如下（`chmod +x`）：

```bash
#!/bin/bash
# GoMuseum 容量监控(每 5 分钟),由 cron 调用。spec 2026-10-21-elastic-scaling-design §7;
# 告警含义与处理办法见 docs/ops/capacity-runbook.md。
#
# ⚠️ 安装要手工拷到 VPS(CD 只 rsync backend/),位置沿用 /opt/gomuseum/:
#   scp -i ~/.ssh/deepmeeting_deploy deployment/production/ops-check.sh \
#       root@<VPS>:/opt/gomuseum/ops-check.sh
#   ssh ... 'chmod +x /opt/gomuseum/ops-check.sh'
#   crontab -e   # 与 backup.sh 同一个 crontab
#   */5 * * * * /opt/gomuseum/ops-check.sh >> /var/log/gomuseum-ops-check.log 2>&1
# 装完先用 cron 的短 PATH 实跑一次:env -i PATH=/usr/bin:/bin /opt/gomuseum/ops-check.sh --dry-run
# ⚠️ 改了这个文件之后要重新 scp。
#
# 宿主机指标在这里取(容器看不到宿主机),nginx 日志从 stdin 喂给容器里的 ops_check,
# 告警邮件由容器里的 ops_alert 发。额外参数(如 --dry-run)原样转给 ops_check。
# 退出码同 ops_check:0 正常 | 2 有告警但发不出去(OPS_ALERT_EMAIL 未配置或发信失败)
set -uo pipefail

STATE=/opt/gomuseum/ops-check.cpu  # 上次的 /proc/stat 累计值,算这 5 分钟的 CPU
read -r _ u n s i w q sq st _ < /proc/stat
busy=$((u + n + s + q + sq + st))
total=$((busy + i + w))
cpu=""
if read -r pb pt < "$STATE" 2>/dev/null && [ "$total" -gt "$pt" ]; then
    cpu=$((100 * (busy - pb) / (total - pt)))
fi
echo "$busy $total" > "$STATE"
mem=$(free | awk '/^Mem:/ {printf "%d", 100 * ($2 - $7) / $2}')
disk=$(df -P / | awk 'NR == 2 {sub("%", "", $5); print $5}')

# 只取带 urt= 的行(只有 api.gomuseum.app 用 main_rt 格式);grep 没匹配时别让 pipefail 误报
{ tail -n 100000 /var/log/nginx/access.log 2>/dev/null | grep -F ' urt=' || true; } |
    docker exec -i gomuseum_prod_backend python -m scripts.ops_check \
        --cpu "$cpu" --mem "$mem" --disk "$disk" "$@"
code=$?
echo "[$(date -Is)] ops_check exit=$code cpu=$cpu mem=$mem disk=$disk"
exit $code
```

- [ ] **Step 6: 检查脚本**：`bash -n deployment/production/ops-check.sh`，没有输出；本机装了 shellcheck 的话再跑一次 `shellcheck deployment/production/ops-check.sh`，不能有 error。
- [ ] **Step 7: 提交**：`feat(ops): ops_check 容量监控(阶段 0 的 6 项告警 + 三笔账 + 阶段触发提醒)与宿主机 cron 脚本`

### Task 10: ops_report 容量段 + 运维文档 + 登记（§7 报告、§2 扩容总规则）

**Files:**
- Modify: `backend/scripts/ops_check.py`（新增 `render_capacity`）
- Modify: `backend/scripts/ops_report.py`：`build()` 加 `"capacity": collect(db, datetime.now(timezone.utc))`；`render()` 在最后一行 `└─ 收入` 之前打印 `render_capacity(r["capacity"])` 的每一行
- Modify: `backend/app/models/app_event.py`：`EVENTS` 后面新增 `OPS_EVENTS` 元组，把事件表里的 8 个名字各配一行注释。不并进付费漏斗的 `EVENTS`
- Create: `docs/ops/capacity-runbook.md`
- Modify: `deployment/production/env.production.example`：加注释掉的新配置项，并写上默认值
- Modify: `docs/ops/backlog.md`
- Test: `backend/tests/unit/scripts/test_ops_check.py`（追加）

**Interfaces:**
- Consumes: Task 9 的 `collect` 返回值。
- Produces: `render_capacity(m: dict) -> list[str]`，每行以 `├─` 或 `│` 开头，和 ops_report 的风格一致。

- [ ] **Step 1: 写测试**（追加到 `test_ops_check.py`）

```python
def test_render_capacity_lists_every_trigger_metric():
    text = "\n".join(oc.render_capacity(_m()))
    for word in ("名额满", "连接峰值", "TTS", "向量检索", "作品", "生成", "AI 兜底", "账", "IP 额度"):
        assert word in text, word
    assert "26678" in text and "122617" in text  # 作品离 15 万还差 150000 - 27383
```

- [ ] **Step 2: 确认失败**，然后 **Step 3: 实现** `render_capacity`，并在 ops_report 里接上。每个指标一行：现值、阈值，以及越线后进入哪个阶段。账那一行列出今天和本月的生成账、语音账、识别兜底账，以及未知单价的模型。
- [ ] **Step 4: 确认通过**：`poetry run pytest tests/unit/scripts/test_ops_check.py -q --no-cov` PASS；再在本机 SQLite 上手跑 `poetry run python -c "from scripts.ops_report import render"`，确认能 import。
- [ ] **Step 5: 写 `docs/ops/capacity-runbook.md`**，60–100 行，分这几节：
  1. 运行方式：cron、ops-check.sh、ops_check，以及怎么 dry-run。dry-run 命令：`docker exec -i gomuseum_prod_backend python -m scripts.ops_check --dry-run < /dev/null`。
  2. 告警表：照搬 Task 9 的告警表，包括 key、条件、处理办法。
  3. 阶段提醒表：照搬 Task 9 的提醒表，并注明「照 spec §11 做，先写实施计划经用户批准」。
  4. 扩容总规则：spec §2 的 5 条，原文照搬。
  5. 手工配置的现状：nginx 两个限流区、staging 资源上限、prod `max_connections=400`、外部探活，各写一行，说明在哪里改、怎么回滚。
  6. 想提前解除某条告警的限频，删掉对应的 `ops_alert` 行即可，给出 SQL。
- [ ] **Step 6: 改台账 `docs/ops/backlog.md`**：
  - 第五节删掉「nginx 限流阈值」那一行，等 Task 16 做完后挪到「最近关闭」；
  - 第五节新增「弹性扩容阶段 1–5 | 触发条件：ops_check 的阶段提醒邮件，或 ops_report 的容量段越线（spec §11）」；
  - 第三节新增「`ALERT_RECOG_DAILY_USD` 用 7 天真实记账重定（阶段 0 上 prod 后第 7 天；R7）」；
  - 第一节新增「外部探活（UptimeRobot）⏳ 你注册，见 Task 18」。
- [ ] **Step 7: 提交**：`docs(ops): 容量运维文档、ops_report 容量段、新事件登记与台账`

### Task 11: 部署配置入库（§11 ②⑧⑨ 的仓库那一半）

**Files:**
- Modify: `deployment/production/nginx-api.gomuseum.app.conf`
- Create: `deployment/staging/docker-compose.yml`
- Modify: `deployment/production/docker-compose.yml`

- [ ] **Step 1: nginx 模板**
  - 第 17 行的区改成 `rate=50r/s`；
  - 紧接着加一个识别专用区 `limit_req_zone $binary_remote_addr zone=gomuseum_recog:10m rate=2r/s;`；
  - `location /` 里的 `burst=20` 改成 `burst=100`；
  - 在 `location /` 之前新增两个 location：`location = /api/v1/recognize` 和 `location ~ ^/api/v1/museums/[^/]+/recognize$`。两者都写 `limit_req zone=gomuseum_recog burst=50 nodelay;` 和 `limit_req_status 429;`，其余 proxy 那几行和 `proxy_read_timeout 120s` 照抄 `location /`；
  - 文件头注释把「10r/s + burst 20」那段改成新数字，并写明「识别单独限流，它是识别 AI 兜底唯一的量的上限（spec §4.4）；confirm / reject 仍走总区」。
- [ ] **Step 2: staging compose 原样入库**：`scp -i ~/.ssh/deepmeeting_deploy root@38.242.207.219:/opt/gomuseum/staging/docker-compose.yml deployment/staging/docker-compose.yml`（只读取）。提交：`chore(deploy): staging compose 原样入库(VPS /opt/gomuseum/staging)`。
- [ ] **Step 3: staging 加资源上限**：三个服务各加两行，合计 2 核 4G（spec §8）：
  - `gomuseum_backend`：`cpus: 1.5`、`mem_limit: 3g`（10-23 空闲时占 651 MiB）
  - `gomuseum_postgres`：`cpus: 0.4`、`mem_limit: 768m`（空闲 90 MiB）
  - `gomuseum_redis`：`cpus: 0.1`、`mem_limit: 256m`（空闲 7 MiB）

  文件头加注释：「合计 2 核 4G：和 prod 同机，压测别挤占 prod 用户（spec §8）」。
- [ ] **Step 4: prod compose**：`gomuseum_postgres` 加上 `command: ["postgres", "-c", "max_connections=400"]`，注释写「spec §5.1；只能在维护窗口里 `up -d gomuseum_postgres` 生效，见 Task 17」。别的不动。
- [ ] **Step 5: 确认 diff**：`git diff --stat`，确认只改了这 3 个文件；`git diff -- deployment/staging/docker-compose.yml`，确认相对 Step 2 提交的原样版本只多了 6 行资源限制和注释。
- [ ] **Step 6: 提交**：`feat(deploy): nginx 识别单独限流 2r/s、其余放宽到 50r/s;staging 限 2 核 4G;prod postgres max_connections=400(均需手工上线)`

### 整支分支的独立审查（Task 11 之后、Task 12 之前）

- [ ] 按 executing-plans 的 Final Review 做：用 `model=fable` 派一个 reviewer（记忆「独立审查默认用 Fable」），输入是 review package、本计划、spec，以及本计划的 Review Focus 原文。Critical 和 Important 级别的问题一次修完，每条都要先写一个失败的测试，再修到通过；Minor 记进 ledger。
- [ ] 全量：`poetry run pytest -q --no-cov`，和准备阶段的基线对比，不能新增失败。`poetry run black --check app scripts tests && poetry run isort --check-only app scripts tests` 通过。

### Task 12: staging 加资源上限（只动 staging，§11 上线步骤③）

- [ ] **Step 1**：`scp deployment/staging/docker-compose.yml root@38.242.207.219:/opt/gomuseum/staging/docker-compose.yml.new`
- [ ] **Step 2**：`ssh ... 'cd /opt/gomuseum/staging && diff docker-compose.yml docker-compose.yml.new; docker compose -f docker-compose.yml.new config -q && echo CONFIG_OK'`。预期 diff 里只有资源限制和注释，最后打印 `CONFIG_OK`。
- [ ] **Step 3**：`ssh ... 'cd /opt/gomuseum/staging && cp docker-compose.yml docker-compose.yml.bak-$(date +%Y%m%d) && mv docker-compose.yml.new docker-compose.yml && docker compose up -d --wait && docker compose ps'`。这里的项目名是 `gomuseum-staging`，只会重建 staging 的 3 个容器。
- [ ] **Step 4: 验证**：
  - `docker inspect -f '{{.Name}} {{.HostConfig.NanoCpus}} {{.HostConfig.Memory}}' gomuseum_staging_backend gomuseum_staging_postgres gomuseum_staging_redis`，预期三行分别是 `1500000000 3221225472`、`400000000 805306368`、`100000000 268435456`；
  - `curl -fsS https://staging-api.gomuseum.app/api/v1/museums | head -c 80` 有返回；
  - `docker exec gomuseum_staging_backend python scripts/verify_money_path.py --base http://localhost:8000 --slug orsay` 退出码 0；
  - `docker ps` 里 prod 容器的 Up 时长没变（没碰到 prod）。
- [ ] **Step 5**：在 ledger 里记下结果。回滚办法：把 bak 拷回去，再 `up -d`。

### Task 13: 提 PR 合入 staging，在 staging 上验证

- [ ] **Step 1**：`git push -u origin feature/elastic-scaling-spec`。然后 `gh pr create --base staging --head feature/elastic-scaling-spec`，标题「feat: 弹性扩容阶段 0（监控最小版、共用 WiFi 不误伤、大模型超时、并发配置化、补记账）」。正文：
  - 9 项分别做到什么程度；
  - 哪些是手工步骤（Task 12、15–18）；
  - 契约不变；
  - 两处有意放宽（游客登录、nginx）；
  - 设计取舍 R1–R12 各一行。
- [ ] **Step 2**：等 CI 全绿后执行 `gh pr merge <n> --squash`（feature→staging 我可以合）。合完执行 `git push origin --delete feature/elastic-scaling-spec`。本地分支和 worktree 留到最后一个任务再删，后面几步还要用里面的文件。
- [ ] **Step 3**：等 staging 的 CD 跑完（`gh run list --workflow deploy.yml --branch staging --limit 1`），再在 staging 上验证：
  - `docker exec -i gomuseum_staging_backend python -m scripts.ops_check --dry-run --cpu 10 --mem 20 --disk 25 < /dev/null`：打印出采样，`conn_max` 为 100，不报错；
  - 懒生成事件：
    1. 取令牌：`curl -s -X POST https://staging-api.gomuseum.app/api/v1/auth/guest -H 'Content-Type: application/json' -d '{"device_id":"stage0-verify"}'`，拿到 `access_token`；
    2. 在 staging 库里挑一件有图的 stub：`select o.qid, m.slug from museum_objects o join museums m on m.id = o.museum_id where o.content_status = 'stub' and exists (select 1 from object_images i where i.object_id = o.id and i.image_key is not null and i.role not like '%quarantine%') limit 1`；
    3. 带令牌请求 `GET /api/v1/museums/{slug}/objects/{qid}/content?language=fr`；
    4. 等 90 秒后查 staging 的 `app_events`，应该有同一个 `run_id` 的 `lazy_started` 和 `lazy_finished`，且 `ok=true`；
  - 识别记账：带同一个令牌，用 `curl -F image=@<任意一张不在馆藏里的风景照>` 请求 `POST /api/v1/recognize`，走到 AI 兜底后，staging 的 `llm_usage` 里今天多出一行 `recognition@app`；
  - 游客登录限速：用 6 个不同的 `device_id` 连续请求 `/auth/guest`，都不是 429（原来第 6 次就是 429）；
  - `docker exec gomuseum_staging_backend python scripts/llm_cost_report.py --days 1`：Claude 那几行的金额不是 0。

### Task 14: 发 prod（§11 上线步骤①）

- [ ] **Step 1**：确认 prod 上没有长任务（§11 末行）：
  - `ssh ... 'docker top gomuseum_prod_backend'` 只看到 uvicorn；
  - prod 库里正在懒生成的作品数为 0，只读查：`select count(*) from museum_objects where attributes ? 'lazy_lock_at' and (attributes->>'lazy_lock_at')::timestamptz > now() - interval '10 min'`。
- [ ] **Step 2**：`gh pr create --base main --head staging`，写一个发版 PR。正文写清本次带上 prod 的内容，以及哪些手工步骤要随后单独批准（Task 15–17）。⛔ **由用户合并。**
- [ ] **Step 3**：合并后等 prod 的 CD 成功，然后验证：
  - `/api/v1/museums` 返回 200；
  - nginx 日志里部署窗口内的 5xx 数；
  - `docker exec -i gomuseum_prod_backend python -m scripts.ops_check --dry-run < /dev/null`：不报错，并列出现在就会发的告警。把这份清单告诉用户，下一步装 cron 后这些会真的发出去。

### Task 15: ⛔ prod 装 cron（§11 上线步骤④，执行前请用户批准）

- [ ] **Step 1**：请用户批准，说明这一步要做什么：每 5 分钟往 prod 写一条 `ops_sample`，按条件发告警邮件，并附上 Task 14 dry-run 列出的、会立刻发出的告警。
- [ ] **Step 2**：`scp deployment/production/ops-check.sh root@38.242.207.219:/opt/gomuseum/ops-check.sh && ssh ... 'chmod +x /opt/gomuseum/ops-check.sh && env -i PATH=/usr/bin:/bin /opt/gomuseum/ops-check.sh --dry-run'`，预期退出码 0。
- [ ] **Step 3**：先备份再加一行：`ssh ... 'crontab -l > /opt/gomuseum/crontab.bak-$(date +%Y%m%d) && (crontab -l; echo "*/5 * * * * /opt/gomuseum/ops-check.sh >> /var/log/gomuseum-ops-check.log 2>&1") | crontab - && crontab -l'`。
- [ ] **Step 4**：10 分钟后检查：`tail -3 /var/log/gomuseum-ops-check.log` 里有两次 `exit=0`；prod 只读查到最近 15 分钟的 `ops_sample` 不少于 2 条，第二条的 `cpu` 不为空。

### Task 16: ⛔ prod nginx（§11 上线步骤②，执行前请用户批准）

- [ ] **Step 1**：把 VPS 上的 `/etc/nginx/sites-available/api.gomuseum.app` 拉到 scratchpad，照 Task 11 Step 1 的改法改。VPS 上的文件带 certbot 那几行，和仓库模板的结构不同，所以要逐处对着改，不能直接覆盖。把 `diff` 发给用户请求批准。
- [ ] **Step 2**：批准后先备份 `cp …/api.gomuseum.app …/api.gomuseum.app.bak-$(date +%Y%m%d)`，再上传，然后 `nginx -t && systemctl reload nginx`。`nginx -t` 失败就马上把 bak 拷回去，什么都不 reload。
- [ ] **Step 3: 验证**（在 VPS 上执行）：
  - `curl -s -o /dev/null -w '%{http_code}' https://api.gomuseum.app/api/v1/museums` 返回 200；
  - `for i in $(seq 60); do curl -s -o /dev/null -w '%{http_code}\n' -X POST https://api.gomuseum.app/api/v1/recognize; done | sort | uniq -c`：预期约 51 个 422（没带文件，只走到参数校验，不会调用识别），其余是 429，说明识别区 burst 50 生效了；
  - `nginx -T | grep -n gomuseum_recog` 能看到两个 location。
- [ ] **Step 4**：台账里把「nginx 限流阈值」挪到「最近关闭」。

### Task 17: ⛔ prod 数据库 max_connections=400（§11 上线步骤⑥，执行前单独请用户批准）

- [ ] **Step 1: 请批准**：说明这一步要重启 prod 的 postgres，大约 10 秒，期间请求会失败；`pool_pre_ping` 会自动重连，backend 不用重启。附上 Step 2–5 的命令。
- [ ] **Step 2: 确认没有长任务**：同 Task 14 Step 1，另外查 `ops:lazy_running` 为 0 或不存在：`docker exec gomuseum_prod_redis redis-cli get ops:lazy_running`。
- [ ] **Step 3: 备份**（写到宿主机，不写进容器里）：`ssh ... 'f=/opt/gomuseum/backups/gomuseum_pre_maxconn_$(date +%Y%m%d_%H%M%S).sql.gz && docker exec gomuseum_prod_postgres pg_dump -U gomuseum gomuseum | gzip > $f && gunzip -t $f && ls -l $f'`，确认大小和每日备份相近。
- [ ] **Step 4: 改 compose 并当场生效**：
  - `scp deployment/production/docker-compose.yml root@…:/opt/gomuseum/deploy/docker-compose.yml.new`；
  - `ssh ... 'cd /opt/gomuseum/deploy && diff docker-compose.yml docker-compose.yml.new && docker compose -f docker-compose.yml.new config -q'`，预期 diff 只有 `command` 那一行和注释；
  - 再执行 `cp docker-compose.yml docker-compose.yml.bak-$(date +%Y%m%d) && mv docker-compose.yml.new docker-compose.yml && docker compose up -d --wait gomuseum_postgres`。
- [ ] **Step 5: 核实**：
  - `docker exec gomuseum_prod_postgres psql -U gomuseum -d gomuseum -tAc 'show max_connections'` 输出 `400`；
  - `curl -fsS https://api.gomuseum.app/api/v1/museums` 返回 200；
  - `docker logs --since 3m gomuseum_prod_backend 2>&1 | grep -c Traceback`，重启那几秒之后不再增加；
  - `docker ps` 里 backend 的 Up 时长没变；
  - 再跑一次 ops_check dry-run，`conn_max` 为 400。
- [ ] **回滚**：`cp docker-compose.yml.bak-… docker-compose.yml && docker compose up -d --wait gomuseum_postgres`。

### Task 18: 用户注册外部探活（§11 上线步骤⑤）

- [ ] 把下面的设置发给用户，由用户自己注册：
  - UptimeRobot 免费账号，监控类型选 HTTP(s)；
  - URL 填 `https://api.gomuseum.app/api/v1/museums`（它要查库；`/api/health/` 不查库，库挂了也返回正常，§7）；
  - 间隔 5 分钟，告警发到用户邮箱。
- [ ] 用户确认注册好以后，删掉台账里那一行，更新运维文档里外部探活那一行。

### 收尾

- [ ] 记忆 `elastic-scaling-design.md` 更新为「阶段 0 已上线（日期、PR 号）」。下一步是等阶段提醒邮件，并加一句：会话里看到 ops_report 越线时要主动提醒用户。
- [ ] 台账「最近关闭」写上 PR 号。
- [ ] `git worktree remove /Users/hongyang/Projects/GoMuseum-elastic`，再在主仓库执行 `git branch -D feature/elastic-scaling-spec`。删分支是本地 ref 操作，不碰工作区，主仓库里其他会话未提交的改动不受影响。
