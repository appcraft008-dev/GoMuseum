"""S5 识别照片反馈上传(加法端点)。

只在用户**勾选同意**后由 App 调用。照片进私有桶(独立凭据,不绑域名),
DB 只存 key 与元数据。开关关/桶未配 → 503(隐私政策上线前的闸)。"""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.models.recognition_event import RecognitionEvent
from app.models.recognition_photo_feedback import (
    KEY_PREFIX,
    TEXT_MAX,
    TRIGGERS,
    RecognitionPhotoFeedback,
)
from app.services.storage import photo_feedback as pf

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer(auto_error=False)


def _server_result(db, phash: str) -> Optional[dict]:
    ev = (
        db.query(RecognitionEvent)
        .filter(RecognitionEvent.phash == phash)
        .order_by(RecognitionEvent.created_at.desc())
        .first()
    )
    if ev is None:
        return None
    return {
        "outcome": ev.outcome,
        "engine": ev.engine,
        "top_qid": ev.top_qid,
        "top_score": ev.top_score,
        "confirmed_qid": ev.confirmed_qid,
        "rejected_qids": ev.rejected_qids,
    }


def _clip(s: Optional[str]) -> Optional[str]:
    s = (s or "").strip()
    return s[:TEXT_MAX] or None


@router.post("/feedback/recognition-photo", status_code=204)
@limiter.limit("60/hour")
def submit_recognition_photo(
    request: Request,
    image: UploadFile = File(...),
    trigger: str = Form(...),
    phash: str = Form(..., max_length=64),
    answer_qid: Optional[str] = Form(None, max_length=32),
    museum_slug: Optional[str] = Form(None, max_length=64),
    language: Optional[str] = Form(None, max_length=8),
    query_text: Optional[str] = Form(None),
    label_text: Optional[str] = Form(None),
    text: Optional[str] = Form(None),
    device_id: Optional[str] = Form(None, max_length=255),
    app_version: Optional[str] = Form(None, max_length=64),
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    if not pf.photo_feedback_available():
        raise HTTPException(status_code=503, detail="photo_feedback_disabled")
    if trigger not in TRIGGERS:
        raise HTTPException(status_code=422, detail="unknown trigger")
    data = image.file.read(settings.PHOTO_FEEDBACK_MAX_BYTES + 1)
    if len(data) > settings.PHOTO_FEEDBACK_MAX_BYTES:
        raise HTTPException(status_code=413, detail="image too large")
    from app.services.image_service import ImageService

    try:
        ImageService.validate_image(data)
    except Exception:
        raise HTTPException(status_code=422, detail="not an image")

    user_id = None
    if credentials is not None:
        try:
            from app.services.auth_service import AuthService

            user_id = str(AuthService.get_current_user(db, credentials.credentials).id)
        except Exception:
            logger.info("recognition-photo: invalid token, storing anonymously")

    key = f"{KEY_PREFIX}{uuid.uuid4()}.jpg"
    try:
        pf.get_photo_feedback_storage().put(key, data, "image/jpeg")
    except Exception:
        # 先写桶再写库:桶失败就不留指向空对象的行;5xx 让 App 静默重试一次
        logger.exception("recognition-photo: private bucket put failed")
        raise HTTPException(status_code=503, detail="storage_unavailable")
    db.add(
        RecognitionPhotoFeedback(
            user_id=user_id,
            device_id=device_id,
            phash=phash,
            museum_slug=museum_slug,
            language=language,
            app_version=app_version,
            engine_model=settings.RECOG_MODEL,
            trigger=trigger,
            answer_qid=answer_qid,
            query_text=_clip(query_text),
            label_text=_clip(label_text),
            server_result=_server_result(db, phash),
            text=_clip(text),
            image_key=key,
        )
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        try:
            pf.get_photo_feedback_storage().delete(key)  # 库写失败:别留孤儿照片
        except Exception:
            logger.exception("recognition-photo: orphan cleanup failed: %s", key)
        raise
