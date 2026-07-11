"""全局识别端点 POST /api/v1/recognize(museum 可选)。

museum 不给 → 全局跨馆识别(service slug=None);给了不存在 → 404;给了且存在 →
馆内语义(与老端点 /museums/{slug}/recognize 完全一致)。老端点内部委托到本文件的
run_recognition,共享身份解析/计费/错误映射,行为零变化。契约加法,不动老端点。
"""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()
_bearer = HTTPBearer(auto_error=False)


def run_recognition(
    db: Session,
    slug: str | None,
    image: UploadFile,
    *,
    language: str,
    mode: str,
    device_id: str | None,
    credentials: HTTPAuthorizationCredentials | None,
) -> dict:
    """共享识别逻辑:身份(Bearer 令牌或 device_id)→ 计费识别 → 402/404 映射。
    slug=None 为全局跨馆;slug 给了但目录无此馆 → out is None → 404。
    计费语义不变:配额用尽在 GPT 调用前抛 QuotaExceededError → 402。"""
    from app.services.recognition.service import QuotaExceededError, recognize_billed

    user_id = None
    if credentials:
        try:
            from app.services.auth_service import AuthService

            user = AuthService.get_current_user(db, credentials.credentials)
            user_id = str(user.id)
        except Exception:
            user_id = None  # 坏/过期令牌按匿名处理,可退 device_id
    if not user_id and not device_id:
        raise HTTPException(status_code=401, detail={"reason": "identity_required"})
    data = image.file.read()
    try:
        out = recognize_billed(
            db,
            slug,
            data,
            user_id=user_id,
            device_id=device_id,
            language=language,
            mode=mode,
        )
    except QuotaExceededError:
        raise HTTPException(status_code=402, detail={"reason": "quota_exceeded"})
    if out is None:
        raise HTTPException(status_code=404, detail=f"museum not found: {slug}")
    return out


@router.post("/recognize")
def recognize_global(
    image: UploadFile = File(...),
    museum: str | None = None,
    language: str = "zh",
    mode: str = "artwork",
    device_id: str | None = None,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> dict:
    """拍照识别(museum 可选:不给=全库跨馆;给了不存在→404;给了存在=馆内)。
    身份=Bearer 令牌或 device_id;计费/分流语义同馆内端点。"""
    return run_recognition(
        db,
        museum,
        image,
        language=language,
        mode=mode,
        device_id=device_id,
        credentials=credentials,
    )
