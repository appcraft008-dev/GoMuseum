"""
Content API Endpoints
Handles AI explanation generation and TTS audio generation
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from app.core.database import SessionLocal
from app.core.exceptions import AIServiceException
from app.services.tts_service import get_tts_service

logger = logging.getLogger(__name__)

router = APIRouter()


_bearer = HTTPBearer(auto_error=False)


def _require_tts_access(
    db, credentials, *, qid: str | None, language: str = "zh", section: str = "guide"
) -> str:
    """TTS 的权益闸。qid 给了就与 /audio 同规则(通票,或识别解锁过的主讲解段);
    没有 qid(ad-hoc 任意文本)则必须通票生效。拒绝一律 402,前端据此弹付费页。"""
    from app.services import entitlement_service as es
    from app.services.auth_service import AuthService

    if credentials is None:
        raise HTTPException(status_code=401, detail={"reason": "auth_required"})
    user_id = str(AuthService.get_current_user(db, credentials.credentials).id)
    if qid is None:
        if es.resolve_state(db, user_id)[0] != es.ACTIVE:
            raise HTTPException(status_code=402, detail={"reason": "pass_required"})
        return user_id
    if (
        es.audio_access(db, user_id, qid, language=language, section=section)
        == "denied"
    ):
        raise HTTPException(status_code=402, detail={"reason": "pass_required"})
    return user_id


# Request/Response Models
class ExplanationRequest(BaseModel):
    """Request model for explanation generation"""

    artwork_name: str = Field(..., description="Name of the artwork")
    artist: str = Field(..., description="Artist name")
    period: str = Field(..., description="Historical period")
    language: str = Field(
        default="en", description="Target language (en, zh, fr, de, es, it)"
    )
    description: Optional[str] = Field(None, description="Optional base description")
    qid: Optional[str] = Field(
        None, description="Wikidata QID；提供时把讲解永久落库到 object_content_section"
    )


class ExplanationResponse(BaseModel):
    """Response model for explanation"""

    title: str
    summary: str
    historical_context: str
    artistic_analysis: str
    cultural_significance: str
    interesting_facts: list[str]
    language: str
    fallback: Optional[bool] = False


class TTSRequest(BaseModel):
    """Request model for TTS generation"""

    text: str = Field(..., description="Text to convert to speech")
    language: str = Field(default="en", description="Language code")
    voice: Optional[str] = Field(None, description="Voice name (optional)")
    speed: float = Field(default=1.0, ge=0.25, le=4.0, description="Speech speed")
    qid: Optional[str] = Field(
        None,
        description="Wikidata QID；与 section_code 同时提供时音频落库并返回 audio_url",
    )
    section_code: Optional[str] = Field(
        None, description="内容段落 code（如 overview）；section 模式必填"
    )


class TTSInfoResponse(BaseModel):
    """Response model for TTS metadata"""

    duration_estimate: float
    voice: str
    language: str
    text_hash: str
    size_bytes: int


@router.post("/explanation", response_model=ExplanationResponse)
async def generate_explanation(request: ExplanationRequest) -> ExplanationResponse:
    """⛔ 已退役(2026-09-20 安全审计)。两个洞叠在一起,任何一个都足以下线它:

    ① **成本洞** —— 完全不鉴权的 LLM 端点。`description` 是请求体里调用方
       完全控制的自由文本、无长度校验,直接拼进 prompt;nginx 放行 15MB 请求体,
       单次请求可撑到模型上下文上限(约 $0.019,正常一次 $0.001)。无限流。
    ② **数据污染洞(更重)** —— 带 `qid` 时会 `persist_explanation` 把结果写进
       `object_content_sections` 并置 `status="published"`,**命中已有行就覆盖**。
       它不走富化管线,于是绕过接地闸/忠实度闸/语言检测闸的**全部**。
       更糟的是 body 一变 `audio_key` 就被置 None(`content_repo.py:39`)——
       **已灌好的音频静默变哑**。合起来:匿名任何人可定点毁掉一件藏品某个语言的
       讲解与音频。

    它也没有现役用途:产品形态已被「`/recognize` 返 qid →
    `/museums/{slug}/objects/{qid}/content`」整条取代,后者带全套质量闸。
    App 唯一的引用在 `history_page.dart` 一条"老后端不返回 slug/qid"的兜底路径上
    (prod 后端从 #483 起一直返回),且那条路**从不传 qid** —— 上面 ② 整条分支
    只有攻击者会走。

    保留路由只为给可能还在调它的老客户端一个明确信号,不是静默 404
    —— 与 `/recognition/recognize` 的退役同款处理。
    """
    raise HTTPException(
        status_code=410,
        detail={
            "reason": "endpoint_retired",
            "use": "GET /api/v1/museums/{slug}/objects/{qid}/content",
        },
    )


@router.post("/tts/generate")
async def generate_tts_audio(
    request: TTSRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    tts_service=Depends(get_tts_service),
):
    """
    Generate TTS audio from text

    ⚠️ **此前完全没有鉴权**,是两个洞叠在一起:
    ① 付费墙旁路 —— section 模式直接返回 audio_url,绕过已加闸的 /audio;
    ② 成本洞 —— ad-hoc 模式接受**任意文本**返回 mp3,等于给全世界提供免费 TTS,
       账单算我们的。
    现在:section 模式走与 /audio 相同的权益闸;ad-hoc 模式需通票生效
    (没有 qid 就无法挂靠"首件免费",只能按付费功能处理)。

    Args:
        request: TTS generation request with text and parameters
        tts_service: TTS service (injected)

    Returns:
        - section 模式（带 qid + section_code）：JSON {audio_url, cached}，音频已落库 R2。
        - ad-hoc 模式（无 qid/section_code）：mp3 流式响应。

    Example:
        ```bash
        curl -X POST "http://localhost:8000/api/v1/content/tts/generate" \\
             -H "Content-Type: application/json" \\
             -d '{
                   "text": "This is a test",
                   "language": "en",
                   "speed": 1.0
                 }' \\
             --output audio.mp3
        ```
    """
    # ⛔ section 模式已退役(2026-09-20 安全审计)。它把 `request.text` —— 调用方
    # 提交的**自由文本**,与 DB 里 `object_content_sections.body` 没有任何关系 ——
    # 合成后经 `persist_section_audio` 写成该件藏品**该语言该段落的官方音频**,
    # 发给所有后续用户。而 `_require_tts_access` 回答的是"你能不能**听**这一段",
    # 不是"你能不能**写**这一段":通票生效(`can_play_audio` 的 `state == ACTIVE`
    # 直接 return True)即可写**全库任意 (qid, language, section)**,
    # 免费用户也能写自己识别过那件的 guide 段。
    #
    # 而且**写入即锁死**:下面原本的 `existing` 分支会直接返回缓存,
    # 于是被污染的音频再也不会被覆盖、也不会被任何正常流程发现。
    #
    # App 从不使用它:`GenerateTtsAudioParams` 只有 text/language/voice/speed,
    # 没有 qid 和 sectionCode —— datasource 里那个 section 分支没有调用方能满足。
    # 正确的音频路径一直是 `/museums/{slug}/objects/{qid}/audio`,那里
    # **不接受客户端 text**,正文由服务端从已发布 section 取。
    #
    # 显式 410 而不是静默落到下面的 ad-hoc 分支:后者返回的是 mp3 流而非 JSON,
    # 悄悄换语义会让万一存在的调用方拿到完全不同形状的响应。
    if request.qid and request.section_code:
        raise HTTPException(
            status_code=410,
            detail={
                "reason": "endpoint_retired",
                "use": "GET /api/v1/museums/{slug}/objects/{qid}/audio",
            },
        )

    # ad-hoc(任意文本)：没有 qid 可挂靠识别解锁,按付费功能处理
    _db = SessionLocal()
    try:
        _require_tts_access(_db, credentials, qid=None)
    finally:
        _db.close()

    logger.info(
        f"Generating TTS audio for text (length: {len(request.text)}) in {request.language}"
    )

    try:
        result = await tts_service.generate_audio(
            text=request.text,
            language=request.language,
            voice=request.voice,
            speed=request.speed,
        )

        logger.info(f"TTS audio generated: {result['size_bytes']} bytes")

        # Return audio as streaming response
        return StreamingResponse(
            iter([result["audio_data"]]),
            media_type=result["content_type"],
            headers={
                "Content-Disposition": f'attachment; filename="audio_{result["text_hash"]}.mp3"',
                "X-Duration-Estimate": str(result["duration_estimate"]),
                "X-Voice": result["voice"],
                "X-Language": result["language"],
            },
        )

    except AIServiceException as e:
        logger.error(f"TTS generation failed: {str(e)}")
        raise HTTPException(
            status_code=500, detail={"error": "TTSGenerationError", "detail": str(e)}
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail={"error": "InternalServerError", "detail": str(e)}
        )


@router.post("/tts/info", response_model=TTSInfoResponse)
async def get_tts_info(
    request: TTSRequest, tts_service=Depends(get_tts_service)
) -> TTSInfoResponse:
    """
    Get TTS metadata without generating audio (for caching checks)

    Args:
        request: TTS request parameters
        tts_service: TTS service (injected)

    Returns:
        TTS metadata including hash and estimated duration
    """
    logger.info(f"Getting TTS info for text in {request.language}")

    try:
        # Generate hash for caching
        text_hash = tts_service.generate_text_hash(
            text=request.text,
            language=request.language,
            voice=request.voice,
            speed=request.speed,
        )

        # Estimate duration
        word_count = len(request.text.split())
        duration_estimate = (word_count / 150) * 60 / request.speed

        # Get voice
        voice_info = tts_service.get_supported_voices(request.language)
        voice = request.voice or voice_info["default_voice"]

        return TTSInfoResponse(
            duration_estimate=duration_estimate,
            voice=voice,
            language=request.language,
            text_hash=text_hash,
            size_bytes=0,  # Unknown until generated
        )

    except Exception as e:
        logger.error(f"Error getting TTS info: {str(e)}")
        raise HTTPException(
            status_code=500, detail={"error": "InternalServerError", "detail": str(e)}
        )


@router.get("/tts/voices/{language}")
async def get_supported_voices(language: str, tts_service=Depends(get_tts_service)):
    """
    Get supported voices for a language

    Args:
        language: Language code (en, zh, fr, de, es, it)
        tts_service: TTS service (injected)

    Returns:
        List of available voices and default voice
    """
    logger.info(f"Getting supported voices for language: {language}")

    try:
        result = tts_service.get_supported_voices(language)
        return result

    except Exception as e:
        logger.error(f"Error getting voices: {str(e)}")
        raise HTTPException(
            status_code=500, detail={"error": "InternalServerError", "detail": str(e)}
        )
