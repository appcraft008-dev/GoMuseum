"""2026-09-20 安全审计退役的端点，以及"它们退役时钱确实没花出去"。

⚠️ **这份文件里的断言口径**：凡涉及花钱的格子，断言的是「花钱那一步**没被调用**」，
不是「状态码是 410」。状态码对证明不了闸站在花费**上游** —— 一个先调 LLM / 先合成
音频、再返回 410 的实现照样全绿，而钱已经付了。

测试本身零成本：桩 + not-called。`tests/conftest.py` 的外网禁连闸（#607）是最后
一道兜底，万一某个桩漏打了也连不出去，会响亮失败而不是静默花钱。
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# POST /content/explanation —— 无鉴权 LLM + 可覆盖已发布内容
# ---------------------------------------------------------------------------

_EXPLANATION_BODY = {
    "artwork_name": "Mona Lisa",
    "artist": "编的",
    "period": "编的",
    "language": "zh",
}


def test_explanation_is_retired_and_never_calls_the_llm(client, monkeypatch):
    """绊线打在 **OpenAI 客户端工厂**上，不是某个具体的生成函数。

    工厂是所有 LLM 路径的共同咽喉（`enrichment/vision`、`content_enricher`、
    `recognition/vision` 全走它），所以这条断言不会因为将来有人换了生成函数的
    名字或实现而悄悄失效 —— 只要这个端点碰了任何 LLM，它就会响。
    """
    import app.services.content_generation_service as cgs

    calls = []

    def _tripwire(*a, **k):
        calls.append(a)
        raise AssertionError("退役端点仍然摸到了 OpenAI 客户端 —— 闸站错位置了")

    monkeypatch.setattr(cgs, "_get_openai_client", _tripwire)

    r = client.post("/api/v1/content/explanation", json=_EXPLANATION_BODY)
    assert r.status_code == 410
    assert calls == []


def test_explanation_with_qid_never_writes_to_db(client, monkeypatch):
    """带 qid 那条分支是整个洞里破坏力最大的一段：它会把结果写成
    `status="published"` 覆盖真实讲解，并把 `audio_key` 置 None 让音频变哑。

    所以这里盯的是**写库函数没被调用**，而不只是响应码。
    """
    import app.services.content_repo as repo

    writes = []
    monkeypatch.setattr(
        repo, "persist_explanation", lambda *a, **k: writes.append(a) or True
    )

    r = client.post(
        "/api/v1/content/explanation", json={**_EXPLANATION_BODY, "qid": "Q12418"}
    )
    assert r.status_code == 410
    assert writes == []


# ---------------------------------------------------------------------------
# POST /content/tts/generate —— section 模式退役，ad-hoc 模式保留
# ---------------------------------------------------------------------------


def test_tts_section_mode_is_retired_and_never_synthesizes(client, monkeypatch):
    """section 模式曾把调用方提交的**自由文本**合成后写成该藏品的官方音频。

    注意这里**不给任何令牌**也期望 410：闸必须在权益检查**之前**就把这条路封死。
    如果实现把 410 放在 `_require_tts_access` 之后，无令牌会先拿到 401 ——
    那说明退役没做在正确的位置。
    """
    import app.services.tts_service as tts

    synth = []
    monkeypatch.setattr(
        tts.TTSService,
        "generate_audio",
        lambda self, *a, **k: synth.append(a) or {},
    )

    r = client.post(
        "/api/v1/content/tts/generate",
        json={
            "text": "这段是我编的，别把它当成官方讲解",
            "language": "zh",
            "qid": "Q12418",
            "section_code": "guide",
        },
    )
    assert r.status_code == 410
    assert synth == []


def test_tts_section_mode_never_persists_audio(client, monkeypatch):
    """写入即锁死：一旦落库，后续请求走 `cached` 分支永不覆盖、也永不被发现。
    所以"没写进去"这件事必须被直接断言。"""
    import app.services.content_repo as repo

    writes = []
    monkeypatch.setattr(
        repo, "persist_section_audio", lambda *a, **k: writes.append(a) or "k"
    )

    r = client.post(
        "/api/v1/content/tts/generate",
        json={
            "text": "x",
            "language": "zh",
            "qid": "Q12418",
            "section_code": "made-up-section",
        },
    )
    assert r.status_code == 410
    assert writes == []


def test_tts_adhoc_mode_still_reaches_its_paywall(client):
    """反向格：删 section 模式不能把 ad-hoc 模式一起弄坏。

    ad-hoc（无 qid）要保留，它的闸是"必须有生效通票"。无令牌 → 401，
    **不是 410** —— 这正是证明"只退役了 section 模式"的那一格。
    只写上面那些的话，把整个端点删掉也会绿。
    """
    r = client.post(
        "/api/v1/content/tts/generate", json={"text": "hello", "language": "en"}
    )
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# recognition.py 的三个无鉴权遗留端点
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/recognition/recent",
        "/api/v1/recognition/stats",
        "/api/v1/recognition/recognize/some-id",
    ],
)
def test_unauthenticated_recognition_leak_routes_are_gone(client, path):
    assert client.get(path).status_code == 404


def test_retired_recognize_still_signals_410_not_404(client):
    """反向格：老识别端点保留 410 信号，不能跟着上面三个一起被删成 404。"""
    r = client.post(
        "/api/v1/recognition/recognize", files={"image": ("a.jpg", b"x", "image/jpeg")}
    )
    assert r.status_code == 410
