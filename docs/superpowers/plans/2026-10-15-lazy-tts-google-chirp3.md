# 懒生成 TTS 换成 Google Chirp 3 HD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把懒生成/`/tts/generate` 用的 OpenAI tts-1 换成 Google Chirp 3 HD 流式合成,输出 160 kbps MP3,API 契约与 App 不变。

**Architecture:** `TTSService` 内部换实现:切句(`tts_text.py`)→ 同步 gRPC `streaming_synthesize` 在线程里迭代 PCM → `asyncio.Queue` 桥回事件循环 → `Mp3Encoder`(`tts_mp3.py`,lameenc 160k)边编边吐 → 结尾 `check_audio` 自检。`streaming_audio` / `lazy_audio` / 端点不动。

**Tech Stack:** Python 3.13、FastAPI、`google-cloud-texttospeech`(gRPC)、`lameenc`、pytest(`asyncio_mode = "auto"`)、poetry。

**Spec:** `docs/superpowers/specs/2026-10-15-lazy-tts-google-chirp3-design.md`

## Global Constraints

- 所有命令在 worktree `/Users/hongyang/Projects/GoMuseum-googletts/backend` 下跑;Python 用 `poetry run`。
- 声音/语速表(spec §2.5,逐字照抄):zh `cmn-CN` Laomedeia 1.03;zh-hant `cmn-CN` Despina 1.02;en `en-US` Autonoe 1.05;fr `fr-FR` Callirrhoe 0.90;de `de-DE` Achernar 0.93;es `es-ES` Aoede 0.98;it `it-IT` Autonoe 1.02;pl `pl-PL` Kore 0.97;ja `ja-JP` Aoede 0.99;ko `ko-KR` Erinome 0.98。声音全名 `{locale}-Chirp3-HD-{voice}`。
- 输出:MP3、**160 kbps**、单声道、24 kHz(质量闸按 160k 估时长)。
- 切句阈值:zh/zh-hant 60、ja/ko 95、其余 270 字符;超阈值在 `，；：、,;:` 处切并把切点标点改句号(CJK「。」,其余「.」)。
- 引擎标记常量:`"google-chirp3-hd"`。gRPC deadline 60s;首块前失败重试 1 次。
- 不留 tts-1 回退。`TTSRequest.voice/speed` 字段保留但忽略。
- 禁止 `git add <dir>/`;只 add 具体文件。worktree 里钩子不跑:每次提交前手动 `poetry run black --check` + `poetry run isort --check-only` 改动文件。
- 不往任何 env 加 `GOOGLE_TTS_API_KEY`,直到代码合进对应分支(Settings 拒绝未声明键)。
- 单元测试不连 Google:一律打桩 `_get_client`。

## Review Focus

1. 客户端中途断开:`streaming_audio` 的 detached producer 要把流跑完再落库 —— 桥接器在消费方不再读时不能卡死线程(由 producer 读到底保证;测试 5b 覆盖连续 `asyncio.run`)。
2. 空正文 / 只有标点的正文:`split_sentences` 返回空列表时不应发出空 input,应直接抛 `AIServiceException`(Task 3 测试 `test_empty_text_raises`)。
3. 不支持的语言(如 `pt`):回落 en 声音,不抛错(Task 3 测试 `test_unknown_language_falls_back_to_en`)。
4. QA 音频正文 `question\n\nanswer`:问、答分成两句送(Task 1 测试 `test_qa_newlines_split`)。
5. Google 正常结束但只给了很短的音频:结尾自检抛错、不落库(Task 3 测试 `test_short_audio_fails_self_check`)。

---

### Task 1: 切句器 `split_sentences`

**Files:**
- Create: `backend/app/services/tts_text.py`
- Test: `backend/tests/unit/services/test_tts_text.py`

**Interfaces:**
- Produces: `split_sentences(text: str, language: str) -> list[str]`

- [ ] **Step 1: Write the failing test**

```python
"""切句器:Google 流式会静默吞超长句句尾(spec §2.3),切点必须改句号。"""

import re

from app.services.tts_text import split_sentences

LONG_ZH = (
    "这幅画不仅捕捉了一顿饭，更是思想的聚会——保罗·维尔伦、阿尔图尔·兰波及他们的同时代人"
    "——每个人都沉浸在思考或交谈中，他们的黑色服装与眼前生动的静物形成鲜明对比。"
)


def _letters(s):
    return re.sub(r"[\s。！？.!?，；：、,;:]", "", s)


def test_cjk_sentence_ends():
    assert split_sentences("第一句。第二句！第三句？", "zh") == ["第一句。", "第二句！", "第三句？"]


def test_latin_decimals_and_short_fragments():
    # 1.5 不切;"Is it?" "Yes!" 都 < 12 字符,并成一句
    assert split_sentences("It is 1.5 m wide. Is it? Yes!", "en") == [
        "It is 1.5 m wide.",
        "Is it? Yes!",
    ]


def test_latin_split_on_period_space():
    out = split_sentences("This painting is large. It hangs in the Louvre today.", "en")
    assert out == ["This painting is large.", "It hangs in the Louvre today."]


def test_ellipsis_not_split():
    out = split_sentences("She waited... then the light changed over the river.", "en")
    assert out == ["She waited... then the light changed over the river."]


def test_abbreviation_not_split():
    out = split_sentences("We visit St. Peter's Basilica in the morning light.", "en")
    assert out == ["We visit St. Peter's Basilica in the morning light."]
    out = split_sentences("It belonged to Walter Mme. Vve Jean before the museum bought it.", "es")
    assert len(out) == 1


def test_qa_newlines_split():
    out = split_sentences("What is this painting about?\n\nIt is a painting by Manet.", "en")
    assert out == ["What is this painting about?", "It is a painting by Manet."]


def test_long_zh_sentence_split_with_periods():
    out = split_sentences(LONG_ZH, "zh")
    assert len(out) >= 2
    assert all(len(s) <= 60 for s in out)
    assert all(s.endswith("。") for s in out)
    assert "".join(_letters(s) for s in out) == _letters(LONG_ZH)


def test_ja_threshold_95():
    s = "あ" * 50 + "、" + "い" * 45 + "。"  # 97 字
    out = split_sentences(s, "ja")
    assert len(out) == 2 and all(len(x) <= 95 for x in out) and out[0].endswith("。")


def test_latin_threshold_270():
    s = ("word " * 40).strip() + ", " + ("more " * 20).strip() + "."  # > 270
    out = split_sentences(s, "fr")
    assert all(len(x) <= 270 for x in out) and out[0].endswith(".")


def test_hard_cut_without_commas():
    s = "字" * 130 + "。"
    out = split_sentences(s, "zh")
    assert all(len(x) <= 60 for x in out) and all(x.endswith("。") for x in out)
    assert "".join(_letters(x) for x in out) == "字" * 130


def test_empty_and_blank():
    assert split_sentences("", "en") == []
    assert split_sentences("  \n\n ", "zh") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/unit/services/test_tts_text.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.tts_text'`

- [ ] **Step 3: Write minimal implementation**

```python
"""送 Google TTS 前的切句(spec 2026-10-15 §2.3/§3.1)。

Google 流式合成会**静默吞掉超长句的句尾**(81 字中文句尾 6 字 9/9 次没念,不报错);
只在逗号处切不够 —— Google 按标点把没有句号的 input 拼回一句 —— 切点必须改成句号。
阈值是实测「最长且未被吞」的长度,不是拍的。
"""

import re

_CJK = {"zh", "zh-hant", "ja", "ko"}
_MAX = {"zh": 60, "zh-hant": 60, "ja": 95, "ko": 95}
_DEFAULT_MAX = 270
_MIN_LATIN = 12  # 更短的拉丁碎块多半是缩写断出来的,并入下一句

# 句末:CJK 句末标点后;拉丁 .!? 后跟空白(排除省略号);换行
_SENT_END = re.compile(r"(?<=[。！？])|(?<=[.!?])(?<!\.\.\.)\s+|\n+")
_CLAUSE = re.compile(r"(?<=[，；：、,;:])")
_ABBR_END = re.compile(r"\b[A-Z][a-z]{0,2}\.$")  # St. / Mme. / Dr. / Vve.
_CLAUSE_MARKS = "，；：、,;:"
_END_MARKS = "。！？.!?"


def split_sentences(text: str, language: str) -> list[str]:
    limit = _MAX.get(language, _DEFAULT_MAX)
    cjk = language in _CJK
    stop = "。" if cjk else "."
    raw = [s.strip() for s in _SENT_END.split(text or "") if s and s.strip()]
    if not cjk:
        raw = _merge_fragments(raw)
    out: list[str] = []
    for s in raw:
        out.extend(_split_long(s, limit, stop, cjk))
    return out


def _merge_fragments(parts: list[str]) -> list[str]:
    out: list[str] = []
    carry = ""
    for p in parts:
        cur = f"{carry} {p}".strip() if carry else p
        if len(cur) < _MIN_LATIN or _ABBR_END.search(cur):
            carry = cur
            continue
        out.append(cur)
        carry = ""
    if carry:
        out.append(carry)
    return out


def _split_long(s: str, limit: int, stop: str, cjk: bool) -> list[str]:
    if len(s) <= limit:
        return [s]
    room = limit - 1  # 给 _close 补的句号留一位
    chunks: list[str] = []
    cur = ""
    for p in _CLAUSE.split(s):
        while len(p) > room:  # 一段里没有可切的逗号:硬切
            if cur:
                chunks.append(cur)
                cur = ""
            space = -1 if cjk else p.rfind(" ", 0, room)
            cut = space if space > 0 else room
            chunks.append(p[:cut])
            p = p[cut:]
        if cur and len(cur) + len(p) > room:
            chunks.append(cur)
            cur = ""
        cur += p
    if cur:
        chunks.append(cur)
    return [_close(c, stop) for c in (c.strip() for c in chunks) if c]


def _close(c: str, stop: str) -> str:
    if c[-1] in _CLAUSE_MARKS:
        return c[:-1] + stop
    if c[-1] in _END_MARKS:
        return c
    return c + stop
```

- [ ] **Step 4: Run test to verify it passes**

Run: `poetry run pytest tests/unit/services/test_tts_text.py -q`
Expected: PASS(全部)。

- [ ] **Step 5: Commit**

```bash
poetry run black app/services/tts_text.py tests/unit/services/test_tts_text.py && poetry run isort app/services/tts_text.py tests/unit/services/test_tts_text.py
git add app/services/tts_text.py tests/unit/services/test_tts_text.py
git commit -m "feat(tts): 送 Google 前的切句器(超长句切开并改句号,防静默吞句尾)"
```

---

### Task 2: 依赖 + 160k MP3 编码器

**Files:**
- Modify: `backend/pyproject.toml`、`backend/poetry.lock`(poetry 生成)
- Create: `backend/app/services/tts_mp3.py`
- Test: `backend/tests/unit/services/test_tts_mp3.py`

**Interfaces:**
- Produces: `class Mp3Encoder` with `SAMPLE_RATE = 24000`, `BITRATE_KBPS = 160`, `encode(pcm: bytes) -> bytes`, `flush() -> bytes`(PCM 总量为 0 时抛 `AIServiceException`)。

- [ ] **Step 1: Add dependencies**

Run: `poetry add google-cloud-texttospeech lameenc && poetry lock --check`
Expected: 两个包写进 `pyproject.toml` 的 `dependencies`,`poetry.lock` 更新,`--check` 无报错。
再在 pyproject 里含 `"openai.*",` 的那个 mypy 忽略列表(第 ~151 行)里加两行 `"google.cloud.*",`、`"lameenc",`。

- [ ] **Step 2: Write the failing test**

```python
import math
import struct

import pytest

from app.core.exceptions import AIServiceException
from app.services.enrichment.audio_quality import estimate_duration_sec
from app.services.tts_mp3 import Mp3Encoder


def _sine(seconds: float) -> bytes:
    n = int(Mp3Encoder.SAMPLE_RATE * seconds)
    return b"".join(
        struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / Mp3Encoder.SAMPLE_RATE)))
        for i in range(n)
    )


def _encode(chunks):
    enc = Mp3Encoder()
    out = b"".join(enc.encode(c) for c in chunks)
    return out + enc.flush()


def test_160k_duration_estimate_matches():
    mp3 = _encode([_sine(3.0)])
    assert abs(estimate_duration_sec(mp3) - 3.0) / 3.0 < 0.02


def test_odd_byte_chunks_ok_and_same_length():
    pcm = _sine(2.0)
    whole = _encode([pcm])
    odd = _encode([pcm[i : i + 1001] for i in range(0, len(pcm), 1001)])
    assert abs(len(odd) - len(whole)) / len(whole) < 0.02


def test_flush_without_audio_raises():
    with pytest.raises(AIServiceException):
        Mp3Encoder().flush()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `poetry run pytest tests/unit/services/test_tts_mp3.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.tts_mp3'`

- [ ] **Step 4: Write minimal implementation**

```python
"""PCM(s16le / 24 kHz / mono)→ 160 kbps MP3。

160 不是随便选的:质量闸 `audio_quality.estimate_duration_sec` 按「字节 ÷ 160 kbps」估时长,
低码率落库会让将来 VoxCPM2 替换时被 `deviates_from_existing` 拦下(spec §2.4)。
lameenc 两个坑(已复现):奇数字节 → `Input data must be 16-bit PCM data`;
没 encode 过就 flush → `Not currently encoding`。
"""

from app.core.exceptions import AIServiceException


class Mp3Encoder:
    SAMPLE_RATE = 24000
    BITRATE_KBPS = 160

    def __init__(self):
        import lameenc

        self._enc = lameenc.Encoder()
        self._enc.set_bit_rate(self.BITRATE_KBPS)
        self._enc.set_in_sample_rate(self.SAMPLE_RATE)
        self._enc.set_channels(1)
        self._enc.set_quality(2)
        self._rest = b""
        self.pcm_bytes = 0

    def encode(self, pcm: bytes) -> bytes:
        data = self._rest + pcm
        even = len(data) - len(data) % 2
        self._rest = data[even:]
        if not even:
            return b""
        self.pcm_bytes += even
        return bytes(self._enc.encode(data[:even]))

    def flush(self) -> bytes:
        if not self.pcm_bytes:
            raise AIServiceException("TTS 没有返回音频")
        return bytes(self._enc.flush())
```

- [ ] **Step 5: Run test to verify it passes**

Run: `poetry run pytest tests/unit/services/test_tts_mp3.py -q`
Expected: PASS(3 passed)

- [ ] **Step 6: Commit**

```bash
poetry run black app/services/tts_mp3.py tests/unit/services/test_tts_mp3.py && poetry run isort app/services/tts_mp3.py tests/unit/services/test_tts_mp3.py
git add pyproject.toml poetry.lock app/services/tts_mp3.py tests/unit/services/test_tts_mp3.py
git commit -m "feat(tts): 加 google-cloud-texttospeech/lameenc 依赖与 160k MP3 编码器"
```

---

### Task 3: `TTSService` 换成 Google 流式

**Files:**
- Modify: `backend/app/services/tts_service.py`(整体重写,保留公开方法签名与 `get_tts_service`)
- Modify: `backend/app/core/config.py:55` 附近(OpenAI 段后)加 `GOOGLE_TTS_API_KEY: str = ""`
- Modify: `.env.example`(仓库根,`OPENAI_API_KEY` 行后)加 `GOOGLE_TTS_API_KEY=`
- Rewrite: `backend/tests/unit/services/test_tts_service.py`、`backend/tests/unit/services/test_tts_true_streaming.py`

**Interfaces:**
- Consumes: `split_sentences(text, language)`(Task 1)、`Mp3Encoder`(Task 2)、`check_audio`/`estimate_duration_sec`(`app.services.enrichment.audio_quality`)、`record_llm_usage(channel, model, tokens_in, tokens_out)`。
- Produces:
  - `ENGINE = "google-chirp3-hd"`
  - `VOICES: dict[str, tuple[str, str, float]]`(lang → locale, voice, rate)
  - `voice_name(language: str) -> str`
  - `_get_client()`(测试打桩点)
  - `TTSService.generate_audio_stream(text, language="en", voice=None, speed=1.0) -> AsyncIterator[bytes]`
  - `TTSService.generate_audio(text, language="en", voice=None, speed=1.0) -> dict`(键同旧:`audio_data, content_type, duration_estimate, voice, language, text_hash, size_bytes`)
  - `TTSService.get_supported_voices(language) -> dict`、`TTSService.generate_text_hash(text, language="en", voice=None, speed=1.0) -> str`

- [ ] **Step 1: Write the failing tests** — 用下面内容**整个替换** `tests/unit/services/test_tts_service.py`:

```python
"""Google Chirp 3 HD 流式 TTS(spec 2026-10-15)。gRPC 全部打桩,不连 Google。"""

import asyncio
import math
import struct
import threading

import pytest

import app.services.tts_service as tts_mod
from app.core.exceptions import AIServiceException
from app.services.tts_mp3 import Mp3Encoder
from app.services.tts_service import ENGINE, VOICES, TTSService, voice_name


def _pcm(seconds: float) -> bytes:
    n = int(Mp3Encoder.SAMPLE_RATE * seconds)
    return b"".join(
        struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / 24000))) for i in range(n)
    )


class _Resp:
    def __init__(self, b):
        self.audio_content = b


class _FakeClient:
    """记下发送序列;按 plan 吐 PCM。plan 里放 Exception 表示在那一步抛。"""

    def __init__(self, plans):
        self.plans = list(plans)  # 每次调用一个 plan
        self.sent = []
        self.calls = 0

    def streaming_synthesize(self, requests, timeout=None):
        self.calls += 1
        self.timeout = timeout
        self.sent.append(list(requests))
        plan = self.plans.pop(0)

        def gen():
            for item in plan:
                if isinstance(item, Exception):
                    raise item
                yield _Resp(item)

        return gen()


def _patch(monkeypatch, *plans):
    fake = _FakeClient(plans)
    monkeypatch.setattr(tts_mod, "_get_client", lambda: fake)
    monkeypatch.setattr(tts_mod, "record_llm_usage", lambda *a, **k: None)
    return fake


TEXT_EN = "This painting is large. It hangs in the Louvre today."  # ~3s 合理时长


def test_voices_cover_default_languages():
    from app.services.enrichment.lang_config import DEFAULT_LANGUAGES

    for lang in DEFAULT_LANGUAGES:
        locale, voice, rate = VOICES[lang]
        assert voice and 0.8 <= rate <= 1.1
    assert VOICES["zh-hant"][0] == "cmn-CN"
    assert voice_name("zh") == "cmn-CN-Chirp3-HD-Laomedeia"
    assert voice_name("zh-hant") == "cmn-CN-Chirp3-HD-Despina"


def test_sends_config_then_one_input_per_sentence(monkeypatch):
    fake = _patch(monkeypatch, [_pcm(3.5)])
    asyncio.run(TTSService().generate_audio(TEXT_EN, "en"))
    reqs = fake.sent[0]
    cfg = reqs[0].streaming_config
    assert cfg.voice.name == "en-US-Chirp3-HD-Autonoe"
    assert abs(cfg.streaming_audio_config.speaking_rate - 1.05) < 1e-6
    assert [r.input.text for r in reqs[1:]] == [
        "This painting is large.",
        "It hangs in the Louvre today.",
    ]
    assert fake.timeout == 60


def test_generate_audio_returns_160k_mp3(monkeypatch):
    _patch(monkeypatch, [_pcm(1.5), _pcm(2.0)])
    r = asyncio.run(TTSService().generate_audio(TEXT_EN, "en"))
    assert r["content_type"] == "audio/mpeg"
    assert r["voice"] == "en-US-Chirp3-HD-Autonoe"
    assert abs(r["duration_estimate"] - 3.5) < 0.1


def test_two_asyncio_run_calls_on_same_service(monkeypatch):
    # lazy_audio._synth 每次 asyncio.run 新建 loop —— 不能复用绑定旧 loop 的东西
    _patch(monkeypatch, [_pcm(3.5)], [_pcm(3.5)])
    svc = TTSService()
    asyncio.run(svc.generate_audio(TEXT_EN, "en"))
    asyncio.run(svc.generate_audio(TEXT_EN, "en"))


def test_retry_once_when_failing_before_first_chunk(monkeypatch):
    fake = _patch(monkeypatch, [RuntimeError("unavailable")], [_pcm(3.5)])
    asyncio.run(TTSService().generate_audio(TEXT_EN, "en"))
    assert fake.calls == 2


def test_no_retry_after_first_chunk(monkeypatch):
    fake = _patch(monkeypatch, [_pcm(1.0), RuntimeError("reset")], [_pcm(3.5)])
    with pytest.raises(AIServiceException):
        asyncio.run(TTSService().generate_audio(TEXT_EN, "en"))
    assert fake.calls == 1


def test_short_audio_fails_self_check(monkeypatch):
    _patch(monkeypatch, [_pcm(1.0)])
    with pytest.raises(AIServiceException):
        asyncio.run(TTSService().generate_audio("长句。" * 300, "zh"))


def test_empty_text_raises(monkeypatch):
    fake = _patch(monkeypatch)
    with pytest.raises(AIServiceException):
        asyncio.run(TTSService().generate_audio("  \n ", "en"))
    assert fake.calls == 0


def test_unknown_language_falls_back_to_en(monkeypatch):
    fake = _patch(monkeypatch, [_pcm(3.5)])
    r = asyncio.run(TTSService().generate_audio(TEXT_EN, "pt"))
    assert r["language"] == "en"
    assert fake.sent[0][0].streaming_config.voice.name == "en-US-Chirp3-HD-Autonoe"


@pytest.mark.asyncio
async def test_stream_yields_before_google_finishes(monkeypatch):
    """真流式:Google 还没吐完,客户端已经拿到第一块 MP3。"""
    release = threading.Event()

    class _Blocking(_FakeClient):
        def streaming_synthesize(self, requests, timeout=None):
            list(requests)

            def gen():
                yield _Resp(_pcm(1.0))
                release.wait(5)
                yield _Resp(_pcm(2.5))

            return gen()

    monkeypatch.setattr(tts_mod, "_get_client", lambda: _Blocking([]))
    monkeypatch.setattr(tts_mod, "record_llm_usage", lambda *a, **k: None)
    agen = TTSService().generate_audio_stream(TEXT_EN, "en")
    first = await asyncio.wait_for(agen.__anext__(), timeout=3)
    assert first and not release.is_set()
    release.set()
    rest = [c async for c in agen]
    assert rest


def test_records_usage_with_engine(monkeypatch):
    fake = _FakeClient([[_pcm(3.5)]])
    seen = []
    monkeypatch.setattr(tts_mod, "_get_client", lambda: fake)
    monkeypatch.setattr(tts_mod, "record_llm_usage", lambda *a, **k: seen.append(a))
    asyncio.run(TTSService().generate_audio(TEXT_EN, "en"))
    assert seen == [("tts", ENGINE, len(TEXT_EN), 0)]


def test_supported_voices_shape():
    v = TTSService().get_supported_voices("fr")
    assert v == {
        "language": "fr",
        "default_voice": "fr-FR-Chirp3-HD-Callirrhoe",
        "available_voices": ["fr-FR-Chirp3-HD-Callirrhoe"],
    }
```

并删除 `tests/unit/services/test_tts_true_streaming.py`(它断言 OpenAI `with_streaming_response`,真流式已由上面 `test_stream_yields_before_google_finishes` 接管):`git rm tests/unit/services/test_tts_true_streaming.py`。

- [ ] **Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/unit/services/test_tts_service.py -q`
Expected: FAIL — `ImportError: cannot import name 'ENGINE' from 'app.services.tts_service'`

- [ ] **Step 3: Add the setting**

`backend/app/core/config.py`,在 `OPENAI_TIMEOUT: int = 30` 之后加:

```python
    # Google Cloud TTS(懒生成音频,Chirp 3 HD)
    GOOGLE_TTS_API_KEY: str = ""
```

仓库根 `.env.example`,在 `OPENAI_API_KEY=...` 行后加一行 `GOOGLE_TTS_API_KEY=`。

- [ ] **Step 4: Rewrite `backend/app/services/tts_service.py`**

```python
"""TTS:Google Chirp 3 HD 流式合成(替换 tts-1,spec 2026-10-15)。

只用于懒生成兜底与 /tts/generate;批量音频是 VoxCPM2(离线)。
- 发送:同步 gRPC streaming_synthesize,首个 request 是配置,之后**一句一个 input**
  (REST 整段送中文会随机 400;流式会静默吞超长句句尾 → 切句见 tts_text)。
- 同步客户端 + 线程桥接,不用 grpc.aio:lazy_audio._synth 每次 asyncio.run 新建 loop,
  aio channel 绑定旧 loop 会炸。
- 输出 160 kbps MP3(质量闸按 160k 估时长),结尾跑 check_audio,不过就抛错 → 不落库。
"""

import asyncio
import hashlib
import logging
from typing import AsyncIterator, Callable, Dict, Iterator, Optional

from app.core.config import settings
from app.core.exceptions import AIServiceException
from app.services.enrichment.audio_quality import check_audio, estimate_duration_sec
from app.services.llm_usage import record_llm_usage
from app.services.tts_mp3 import Mp3Encoder
from app.services.tts_text import split_sentences

logger = logging.getLogger(__name__)

ENGINE = "google-chirp3-hd"
_DEADLINE_S = 60

# 语言 → (locale, Chirp 3 HD 声音, speaking_rate)。用户 10-15 逐语言耳选,语速对齐 VoxCPM2 成品。
# zh-hant 用 cmn-CN:Chirp 3 HD 没有 cmn-TW(tts-1 / VoxCPM2 也是普通话读繁体)。
VOICES: Dict[str, tuple] = {
    "zh": ("cmn-CN", "Laomedeia", 1.03),
    "zh-hant": ("cmn-CN", "Despina", 1.02),
    "en": ("en-US", "Autonoe", 1.05),
    "fr": ("fr-FR", "Callirrhoe", 0.90),
    "de": ("de-DE", "Achernar", 0.93),
    "es": ("es-ES", "Aoede", 0.98),
    "it": ("it-IT", "Autonoe", 1.02),
    "pl": ("pl-PL", "Kore", 0.97),
    "ja": ("ja-JP", "Aoede", 0.99),
    "ko": ("ko-KR", "Erinome", 0.98),
}

_client = None


def _get_client():
    """按进程懒建(测试打桩此处)。"""
    global _client
    if _client is None:
        if not settings.GOOGLE_TTS_API_KEY:
            raise AIServiceException("GOOGLE_TTS_API_KEY 未配置")
        from google.cloud import texttospeech

        _client = texttospeech.TextToSpeechClient(
            client_options={"api_key": settings.GOOGLE_TTS_API_KEY}
        )
    return _client


def _lang(language: str) -> str:
    return language if language in VOICES else "en"


def voice_name(language: str) -> str:
    locale, voice, _ = VOICES[_lang(language)]
    return f"{locale}-Chirp3-HD-{voice}"


def _requests(sentences, language: str):
    from google.cloud import texttospeech as tts

    locale, _, rate = VOICES[language]
    yield tts.StreamingSynthesizeRequest(
        streaming_config=tts.StreamingSynthesizeConfig(
            voice=tts.VoiceSelectionParams(
                language_code=locale, name=voice_name(language)
            ),
            streaming_audio_config=tts.StreamingAudioConfig(
                audio_encoding=tts.AudioEncoding.PCM,
                sample_rate_hertz=Mp3Encoder.SAMPLE_RATE,
                speaking_rate=rate,
            ),
        )
    )
    for s in sentences:
        yield tts.StreamingSynthesizeRequest(
            input=tts.StreamingSynthesisInput(text=s)
        )


def _pcm_chunks(sentences, language: str) -> Iterator[bytes]:
    """同步迭代 PCM。首块到达前失败重试 1 次;吐过音频后失败不重试。"""
    for attempt in (1, 2):
        got = False
        try:
            stream = _get_client().streaming_synthesize(
                _requests(sentences, language), timeout=_DEADLINE_S
            )
            for resp in stream:
                if resp.audio_content:
                    got = True
                    yield resp.audio_content
            return
        except AIServiceException:
            raise
        except Exception as e:
            if got or attempt == 2:
                raise AIServiceException(f"Google TTS 失败: {e}") from e
            logger.warning(f"Google TTS 首块前失败,重试一次: {e}")


async def _iterate_in_thread(make_iter: Callable[[], Iterator[bytes]]) -> AsyncIterator[bytes]:
    """在线程里跑同步迭代器,经队列交回事件循环,边收边吐。"""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    done = object()

    def worker():
        try:
            for item in make_iter():
                loop.call_soon_threadsafe(queue.put_nowait, item)
            loop.call_soon_threadsafe(queue.put_nowait, done)
        except BaseException as e:  # 交给消费方抛
            loop.call_soon_threadsafe(queue.put_nowait, e)

    fut = loop.run_in_executor(None, worker)
    while True:
        item = await queue.get()
        if item is done:
            break
        if isinstance(item, BaseException):
            raise item
        yield item
    await fut


class TTSService:
    """Google Chirp 3 HD。`voice` / `speed` 参数保留以兼容调用方与 /tts/generate,但忽略
    (声音按语言固定;倍速在 App 播放端做)。"""

    async def generate_audio_stream(
        self,
        text: str,
        language: str = "en",
        voice: Optional[str] = None,
        speed: float = 1.0,
    ) -> AsyncIterator[bytes]:
        language = _lang(language)
        sentences = split_sentences(text, language)
        if not sentences:
            raise AIServiceException("TTS 正文为空")
        record_llm_usage("tts", ENGINE, len(text), 0)
        enc = Mp3Encoder()
        out = bytearray()
        async for pcm in _iterate_in_thread(lambda: _pcm_chunks(sentences, language)):
            mp3 = enc.encode(pcm)
            if mp3:
                out += mp3
                yield mp3
        tail = enc.flush()
        out += tail
        verdict = check_audio(bytes(out), text=text, language=language)
        if not verdict.ok:
            raise AIServiceException(f"TTS 音频自检不过: {verdict.reason}")
        if tail:
            yield tail

    async def generate_audio(
        self,
        text: str,
        language: str = "en",
        voice: Optional[str] = None,
        speed: float = 1.0,
    ) -> Dict[str, object]:
        language = _lang(language)
        data = b"".join([c async for c in self.generate_audio_stream(text, language)])
        return {
            "audio_data": data,
            "content_type": "audio/mpeg",
            "duration_estimate": estimate_duration_sec(data),
            "voice": voice_name(language),
            "language": language,
            "text_hash": self.generate_text_hash(text, language),
            "size_bytes": len(data),
        }

    def get_supported_voices(self, language: str = "en") -> Dict[str, object]:
        language = _lang(language)
        return {
            "language": language,
            "default_voice": voice_name(language),
            "available_voices": [voice_name(language)],
        }

    def generate_text_hash(
        self,
        text: str,
        language: str = "en",
        voice: Optional[str] = None,
        speed: float = 1.0,
    ) -> str:
        return hashlib.sha256(
            f"{text}:{_lang(language)}:{voice_name(language)}".encode()
        ).hexdigest()[:16]


_tts_service_instance = None


def get_tts_service() -> TTSService:
    global _tts_service_instance
    if _tts_service_instance is None:
        _tts_service_instance = TTSService()
    return _tts_service_instance
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `poetry run pytest tests/unit/services/test_tts_service.py tests/unit/services/test_tts_text.py tests/unit/services/test_tts_mp3.py -q`
Expected: PASS(全部)。
若 `test_short_audio_fails_self_check` 没抛:确认 `check_audio` 对 900 字中文、1s 音频返回 `too_short`(期望 900/280*60≈193s,比例 0.005 < 0.45)。

- [ ] **Step 6: Run the TTS-adjacent suites**

Run: `poetry run pytest tests/integration/test_tts_endpoint.py tests/unit/api/test_retired_cost_holes.py tests/unit/services -q -k "tts or stream or audio or lazy or retired"`
Expected: PASS。`test_tts_endpoint.py` 打桩了 `get_tts_service`,不受影响。

- [ ] **Step 7: Commit**

```bash
poetry run black app/services/tts_service.py app/core/config.py tests/unit/services/test_tts_service.py && poetry run isort app/services/tts_service.py tests/unit/services/test_tts_service.py
git add app/services/tts_service.py app/core/config.py ../.env.example tests/unit/services/test_tts_service.py
git rm -q tests/unit/services/test_tts_true_streaming.py
git commit -m "feat(tts): 懒生成 TTS 换成 Google Chirp 3 HD 流式合成(160k MP3,按句送,结尾自检)"
```

---

### Task 4: 引擎标记 + 成本报表

**Files:**
- Modify: `backend/app/services/content_repo.py:102-113`
- Modify: `backend/scripts/llm_cost_report.py:9-14`
- Test: `backend/tests/unit/services/test_tts_service.py`(追加)

**Interfaces:**
- Consumes: `ENGINE`(Task 3)。
- Produces: `_current_tts_engine() -> "google-chirp3-hd"`。

- [ ] **Step 1: Write the failing test**(追加到 `tests/unit/services/test_tts_service.py` 末尾)

```python
def test_current_engine_marker_is_google():
    from app.services.content_repo import _current_tts_engine

    assert _current_tts_engine() == ENGINE == "google-chirp3-hd"


def test_cost_report_has_google_price():
    import importlib.util
    import pathlib

    p = pathlib.Path(__file__).resolve().parents[3] / "scripts" / "llm_cost_report.py"
    spec = importlib.util.spec_from_file_location("llm_cost_report", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.PRICES["google-chirp3-hd"] == (30.0, 0.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/unit/services/test_tts_service.py -q -k "engine_marker or cost_report"`
Expected: FAIL — `assert 'tts-1' == 'google-chirp3-hd'` 与 `KeyError: 'google-chirp3-hd'`

- [ ] **Step 3: Implement**

`content_repo.py`:注释与函数改为

```python
    # 记录生成引擎:VoxCPM2 队列靠它筛「还有哪些是懒生成引擎录的、待替换」
    row.audio_engine = engine or _current_tts_engine()
```

```python
def _current_tts_engine() -> str:
    """当前懒生成 TTS 引擎标识。别写死在调用方 —— 换引擎时这里跟着变,历史记录才准。"""
    from app.services.tts_service import ENGINE

    return ENGINE
```

`llm_cost_report.py` 的 `PRICES` 加一行(保留 `tts-1` 以便报表能算历史行):

```python
    "google-chirp3-hd": (30.0, 0.0),  # $30/1M chars(每月前 100 万字免费,报表不扣)
```

- [ ] **Step 4: Run tests**

Run: `poetry run pytest tests/unit/services/test_tts_service.py tests/unit/services/test_audio_queue_and_quality.py tests/unit/test_audio_inventory.py -q`
Expected: PASS(audio_queue 测试里的 `engine="tts-1"` 是历史数据夹具,不受影响)

- [ ] **Step 5: Commit**

```bash
poetry run black app/services/content_repo.py scripts/llm_cost_report.py tests/unit/services/test_tts_service.py
git add app/services/content_repo.py scripts/llm_cost_report.py tests/unit/services/test_tts_service.py
git commit -m "feat(tts): 懒生成音频引擎标记改为 google-chirp3-hd,成本报表补价目"
```

---

### Task 5: 文档与台账

**Files:**
- Modify: `docs/architecture/museum-api-contract.md`(「音频批量生产与灌入」节 ③ 之后)
- Modify: `docs/architecture/tts-voice-production-recipe.md`(§六失败方法清单表格末尾)
- Modify: `docs/ops/backlog.md`(删「12 月前换掉 tts-1」行;最近关闭加一条,PR 号合并时补)
- Modify: `backend/app/services/enrichment/audio_queue.py:3` 注释(「tts-1 仍是按需兜底」→ 懒生成引擎)

- [ ] **Step 1: Contract** — 在 ③ 段后加:

```markdown
**③b 懒生成引擎 = Google Chirp 3 HD(2026-10-15 起,替换 tts-1)**
- 任何引擎落库的 MP3 **都必须 160 kbps**(同 ③);Google 只给 32k MP3,所以要 PCM 自己编(`app/services/tts_mp3.py`)。
- 声音/语速表在 `app/services/tts_service.VOICES`(按语言固定;`/tts/generate` 的 `voice`/`speed` 参数保留但忽略,倍速在 App 播放端做)。
- 送 Google 前必须过 `tts_text.split_sentences`:流式合成会静默吞超长句句尾,切点要改成句号。
- `audio_engine = "google-chirp3-hd"` 的音频算「待升级」,VoxCPM2 队列照常替换。
```

- [ ] **Step 2: Recipe** — §六失败方法表格末尾加两行:

```markdown
| Google Chirp 3 HD REST 整段送中文 | ❌ 随机 400「sentences too long」,同一段时好时坏;只能走流式 |
| Google Chirp 3 HD 流式,超长句一个 input | ❌ 不报错但**静默吞句尾**(81 字中文 9/9);逗号处切开也被拼回去 —— 必须把切点改成句号 |
```

- [ ] **Step 3: Backlog** — 删第三节「**12 月前换掉 tts-1**」那一行;「最近关闭」顶部加:

```markdown
- 2026-10-15 **懒生成 TTS 换成 Google Chirp 3 HD**(#PR):tts-1 2027-01-06 停用。对比 tts-1 读音准确度不差、首包更快;10 语声音由用户对照 VoxCPM2 成品逐语言耳选,语速对齐 VoxCPM2;输出 160k 守质量闸;查实 Google 流式静默吞超长句句尾,切句时改句号。spec `docs/superpowers/specs/2026-10-15-lazy-tts-google-chirp3-design.md`
```

- [ ] **Step 4: audio_queue 注释** — 第 3 行改为 `自托管批量生成(VoxCPM2 等)消费这里的输出;懒生成引擎(现为 Google Chirp 3 HD)是按需兜底,其产物算待升级。`

- [ ] **Step 5: Commit**

```bash
poetry run black app/services/enrichment/audio_queue.py
git add ../docs/architecture/museum-api-contract.md ../docs/architecture/tts-voice-production-recipe.md ../docs/ops/backlog.md app/services/enrichment/audio_queue.py
git commit -m "docs: 契约/配方/台账写入懒生成 TTS 换 Google 与 160k、切句约束"
```

---

### Task 6: 全量验证 + PR

- [ ] **Step 1: 全量测试**

Run: `poetry run pytest -q -x -p no:cacheprovider 2>&1 | tail -5`
Expected: 全部 PASS(与 staging 基线相同的 skip 数)。

- [ ] **Step 2: 格式**

Run: `poetry run black --check app tests scripts && poetry run isort --check-only app tests scripts`
Expected: 无改动

- [ ] **Step 3: 真连 Google 冒烟(本机,一次性,不入库)**

用 scratchpad 的实验 key(`ttsab/gkey`)临时导出环境变量跑一次,确认真实 gRPC 下切句、编码、自检全链路通:

```bash
SP=/private/tmp/claude-501/-Users-hongyang-Projects-GoMuseum/e44a5246-76a6-4f1e-9212-505786eba291/scratchpad/ttsab
GOOGLE_TTS_API_KEY="$(cat /private/tmp/claude-501/-Users-hongyang-Projects-GoMuseum/e44a5246-76a6-4f1e-9212-505786eba291/scratchpad/ttsab/gkey)" \
poetry run python -c "
import asyncio
from app.services.tts_service import TTSService
for lang, t in [('zh','这幅画不仅捕捉了一顿饭，更是思想的聚会——保罗·维尔伦、阿尔图尔·兰波及他们的同时代人——每个人都沉浸在思考或交谈中，他们的黑色服装与眼前生动的静物形成鲜明对比。'),('en','This painting is large. It hangs in the Louvre today.')]:
    r = asyncio.run(TTSService().generate_audio(t, lang))
    open(f'$SP/smoke_{lang}.mp3','wb').write(r['audio_data']); print(lang, r['size_bytes'], round(r['duration_estimate'],1))
"
```

Expected: 两行输出、无异常;`ffprobe $SP/smoke_zh.mp3` 显示 160000 bps;用 `~/tts-lab/venv/bin/python` + mlx_whisper 转写 `$SP/smoke_zh.mp3`,含「形成鲜明对比」。

- [ ] **Step 4: 推送并开 PR**

```bash
git push -u origin feature/google-tts-lazy-gen
gh pr create --base staging --title "feat(tts): 懒生成 TTS 换成 Google Chirp 3 HD(替换 2027-01 停用的 tts-1)" --body "<摘要 + spec 链接 + 上线步骤:先合代码,再往 staging env 加 GOOGLE_TTS_API_KEY 并重启>"
```

Expected: CI 绿(ci-status:skipped 视为通过)。合并由用户确认后执行;合并后删分支、删 worktree。

- [ ] **Step 5: 上线后(spec §5,非代码)**
1. 用户新建正式 key(只限 TTS API + IP 38.242.207.219),写进 staging env 并重启;中/英/法各点一段无音频段落实测。
2. 合并后代码对 zh/en/fr 各 ≥10 段 prod 正文生成,读音核对 + 逐句句尾核对,与 tts-1 同口径比较;句尾缺失多于 tts-1 就停。
3. 用户合 main,prod env 加 key 并重启;实验 key 删除。
