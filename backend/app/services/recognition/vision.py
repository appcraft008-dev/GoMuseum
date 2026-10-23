"""识别器:一次 GPT-4o-mini 视觉调用 → 候选名(R1:只当查询,绝不当答案展示)
+ 顺带转写取景框内可见文字(墙签白赚);mode=label 转写 + 摘出墙签上印着的标题/作者
(引导补拍说明牌;匹配只拿摘出的标题当探针,整段几十行逐行模糊太慢)。
complete 注入离线可测;异常/坏 JSON 返回空结构不抛(服务层按 no_candidates 处理)。
spec docs/superpowers/specs/2026-07-03-recognition-design.md。"""

from __future__ import annotations

import io
import logging

logger = logging.getLogger(__name__)

_EMPTY = {"candidates": [], "label_text": None, "self_confidence": "low", "pick": None}


def _shrink(image_bytes: bytes, max_px: int = 1024) -> bytes:
    """GPT 视觉前缩图:手机原图全尺寸 base64 直发 GPT(可达 10MB+)是墙签~60s 慢的主因;
    1024px 对识别/转写足够。任何失败 → log + 原样返回(不阻断识别)。"""
    try:
        from PIL import Image, ImageOps

        img = Image.open(io.BytesIO(image_bytes))
        img = ImageOps.exif_transpose(img).convert("RGB")  # 应用EXIF方向(竖拍横存)
        img.thumbnail((max_px, max_px))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue()
    except Exception:
        logger.exception("_shrink failed, sending original bytes")
        return image_bytes


_ARTWORK_SYSTEM = (
    "You are a museum artwork recognizer. Look at the photo and try to identify the "
    "artwork. Your guesses are CANDIDATE QUERIES for a catalog search, not final answers "
    "— include up to 3 candidates even if unsure. For each candidate, if you know the "
    "artwork's title in its original language (e.g. the French title of a French "
    "painting), give it as original_title; otherwise null. Also transcribe any visible "
    "text in the frame (wall label, plaque) verbatim. Return STRICT JSON: "
    '{"candidates": [{"title": "...", "original_title": "... or null", "artist": "..."}], '
    '"label_text": "verbatim text or null", "self_confidence": "high|medium|low"}. '
    "No commentary."
)

# P1-7(10-12):向量低分时把前 5 名 + 参考缩略图交给 AI 做选择题。评测集 91 张走 AI 的照片:
# 在库答案进候选 5→19、候选含答案比例 15%→40%,库外照片误给候选 25%→37%(用户 10-12 定上)。
_SHORTLIST_EXTRA = (
    " ALSO: a visual similarity search proposed the numbered catalog works below, "
    "each followed by its reference image when available. If the photo clearly shows "
    "one of them (the same artwork, not merely a similar subject or a famous namesake), "
    'set "pick" to its number; otherwise "pick": null. '
    'Add "pick" as a top-level key of the JSON.'
)

_LABEL_SYSTEM = (
    "You are an OCR assistant. Transcribe ALL visible text in this photo of a museum "
    "wall label verbatim, preserving line breaks. Also extract the artwork title(s) "
    "and artist name(s) exactly as printed on the label (main artwork first, at most 3); "
    "if the label prints the same title in two languages, put the original-language one "
    "in original_title. Do NOT guess or add anything that is not printed. "
    "Return STRICT JSON: "
    '{"candidates": [{"title": "as printed", "original_title": "as printed or null", '
    '"artist": "as printed or null"}], '
    '"label_text": "verbatim text or null", '
    '"self_confidence": "high|medium|low"}. No commentary.'
)


def _default_complete(
    system: str, user_content, model: str = "gpt-4o-mini", channel: str | None = None
) -> str:
    """真实视觉调用(30s 超时),按 channel 分发到 OpenAI / Anthropic(见 openai_models.chat)。"""
    from app.services.llm_usage import record_llm_usage
    from app.services.openai_models import chat

    text, real, tin, tout = chat(
        model,
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        channel=channel,
        timeout=30,
    )
    record_llm_usage(channel or "recognition", real, tin, tout)
    return text


def _pick(raw, n: int):
    try:
        i = int(raw)
    except (TypeError, ValueError):
        return None
    return i if 1 <= i <= n else None


def _val(v):
    """模型会照抄提示里的 "... or null",把字符串 "null" 当值返回(prod 30 天文字链 462 次里
    label_text 32 次)。当空处理,否则 App 以为拍了墙签、显示「暂未收录」。"""
    if isinstance(v, str) and v.strip().lower() in ("", "null", "none"):
        return None
    return v or None


def identify(
    image_b64: str, mode: str = "artwork", complete=None, shortlist=None
) -> dict:
    """照片 → {"candidates": [{title, artist}], "label_text", "self_confidence", "pick"}。
    shortlist=[{title, artist, thumb_b64|None}](仅 artwork):pick = 选中的序号(1 起)或 None。"""
    label = mode == "label"
    if complete is None:
        # 墙签用 gpt-4o + 高清:10-07 staging A/B 同一张双语墙签各 5 次,mini 5/5 把说明文字里
        # 提到的另一幅画当主标题,gpt-4o 0/5;单价几乎相同(mini 图片按 33 倍计 token)
        model = "gpt-4o" if label else "gpt-4o-mini"

        def complete(system, user_content):
            # 通路名让墙签/识别兜底能各配各的模型(LLM_CHANNEL_MODELS)
            return _default_complete(
                system,
                user_content,
                model=model,
                channel="label" if label else "recognition",
            )

    shortlist = None if label else shortlist
    system = _LABEL_SYSTEM if label else _ARTWORK_SYSTEM
    image_url = {"url": f"data:image/jpeg;base64,{image_b64}"}
    if label:
        image_url["detail"] = "high"  # 小字多,低清会读错
    user_content = [{"type": "image_url", "image_url": image_url}]
    if shortlist:
        system += _SHORTLIST_EXTRA
        listing = "\n".join(
            f"{i + 1}. {it['title']} — {it.get('artist') or ''}"
            for i, it in enumerate(shortlist)
        )
        user_content.append({"type": "text", "text": "Catalog works:\n" + listing})
        for i, it in enumerate(shortlist):
            if it.get("thumb_b64"):
                user_content += [
                    {"type": "text", "text": f"Reference image of work {i + 1}:"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{it['thumb_b64']}",
                            "detail": "low",
                        },
                    },
                ]
    try:
        from app.services.enrichment.content_enricher import _parse_json

        data = _parse_json(complete(system, user_content)) or {}
    except Exception:
        logger.exception("vision identify failed (mode=%s)", mode)
        return dict(_EMPTY)
    cands = []
    for c in data.get("candidates") or []:
        if isinstance(c, dict) and _val(c.get("title")):
            cands.append(
                {
                    "title": c["title"],
                    "original_title": _val(c.get("original_title")),
                    "artist": _val(c.get("artist")),
                }
            )
    return {
        "candidates": cands[:3],
        "label_text": _val(data.get("label_text")),
        "self_confidence": data.get("self_confidence") or "low",
        "pick": _pick(data.get("pick"), len(shortlist)) if shortlist else None,
    }
