"""识别器:一次 GPT-4o-mini 视觉调用 → 候选名(R1:只当查询,绝不当答案展示)
+ 顺带转写取景框内可见文字(墙签白赚);mode=label 纯转写(引导补拍说明牌)。
complete 注入离线可测;异常/坏 JSON 返回空结构不抛(服务层按 no_candidates 处理)。
spec docs/superpowers/specs/2026-07-03-recognition-design.md。"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_EMPTY = {"candidates": [], "label_text": None, "self_confidence": "low"}

_ARTWORK_SYSTEM = (
    "You are a museum artwork recognizer. Look at the photo and try to identify the "
    "artwork. Your guesses are CANDIDATE QUERIES for a catalog search, not final answers "
    "— include up to 3 candidates even if unsure. Also transcribe any visible text in "
    "the frame (wall label, plaque) verbatim. Return STRICT JSON: "
    '{"candidates": [{"title": "...", "artist": "..."}], '
    '"label_text": "verbatim text or null", "self_confidence": "high|medium|low"}. '
    "No commentary."
)

_LABEL_SYSTEM = (
    "You are an OCR assistant. Transcribe ALL visible text in this photo of a museum "
    "wall label verbatim, preserving line breaks. Do NOT guess or add anything that is "
    "not printed. Return STRICT JSON: "
    '{"candidates": [], "label_text": "verbatim text or null", '
    '"self_confidence": "high|medium|low"}. No commentary.'
)


def _default_complete(system: str, user_content) -> str:
    """真实 GPT-4o-mini 视觉调用(30s 超时)。客户端是 AsyncOpenAI——必须 asyncio.run
    (staging 教训:漏 await 时 create() 返回协程,identify 静默空结果)。"""
    import asyncio

    from app.services.content_generation_service import _get_openai_client

    client = _get_openai_client()
    if client is None:
        raise RuntimeError("OpenAI client unavailable")

    async def _run():
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
            timeout=30,
        )
        return resp.choices[0].message.content or ""

    return asyncio.run(_run())


def identify(image_b64: str, mode: str = "artwork", complete=None) -> dict:
    """照片 → {"candidates": [{title, artist}], "label_text", "self_confidence"}。"""
    complete = complete or _default_complete
    system = _LABEL_SYSTEM if mode == "label" else _ARTWORK_SYSTEM
    user_content = [
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
        }
    ]
    try:
        from app.services.enrichment.content_enricher import _parse_json

        data = _parse_json(complete(system, user_content)) or {}
    except Exception:
        logger.exception("vision identify failed (mode=%s)", mode)
        return dict(_EMPTY)
    cands = []
    for c in data.get("candidates") or []:
        if isinstance(c, dict) and c.get("title"):
            cands.append({"title": c["title"], "artist": c.get("artist")})
    return {
        "candidates": cands[:3],
        "label_text": data.get("label_text") or None,
        "self_confidence": data.get("self_confidence") or "low",
    }
