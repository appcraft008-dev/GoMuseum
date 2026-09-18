"""用户反馈上报(加法端点,2026-09-18)。

一条管道吃两类反馈,靠 `scope` 区分:

- `object` —— 某件藏品的内容/音频有问题。**不可替代**:没有任何外部渠道会告诉你
  「小皇宫 2040 件的繁体讲解念错了」。自带精确坐标,可直接定位 DB 行。
- `app` —— App 整体意见。价值主要在**截流**(用户找不到站内通道就会去 Play 打一星),
  不在信息量。

不拆成两个端点:两类共享几乎全部字段、同一张表、同一套护栏,拆开只是把护栏抄两份。
唯一的分裂点(object 需要坐标)一个校验器就表达完了。
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rate_limit import limiter
from app.models.feedback import ALL_KINDS, SCOPES, TEXT_MAX, Feedback
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter()

# auto_error=False:匿名可写。带了令牌就认人,没带也收 ——
# 最需要反馈的时刻往往正是游客态,要求登录等于把它挡在门外。
security = HTTPBearer(auto_error=False)


class FeedbackIn(BaseModel):
    scope: str
    kind: str
    museum_slug: Optional[str] = None
    qid: Optional[str] = None
    language: Optional[str] = None
    text: Optional[str] = Field(default=None, max_length=TEXT_MAX)
    device_id: Optional[str] = None
    app_version: Optional[str] = None
    platform: Optional[str] = None

    @field_validator("scope")
    @classmethod
    def _scope_known(cls, v: str) -> str:
        if v not in SCOPES:
            raise ValueError(f"scope must be one of {SCOPES}")
        return v

    @field_validator("kind")
    @classmethod
    def _kind_known(cls, v: str) -> str:
        if v not in ALL_KINDS:
            raise ValueError(f"kind must be one of {ALL_KINDS}")
        return v

    @model_validator(mode="after")
    def _object_needs_coordinates(self):
        """藏品级反馈没有坐标就是垃圾数据,宁可拒收。

        少了 language 尤其致命:10 语是 10 份独立内容,不知道语种就不知道改哪一行。
        `scope=app` 不受这条约束 —— 它本来就没有坐标可言。
        """
        if self.scope == "object":
            missing = [
                f for f in ("museum_slug", "qid", "language") if not getattr(self, f)
            ]
            if missing:
                raise ValueError(f"scope=object requires {', '.join(missing)}")
        return self


@router.post("/feedback", status_code=204)
@limiter.limit("60/hour")
def submit_feedback(
    request: Request,
    payload: FeedbackIn,
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """收一条反馈。

    限流 60/hour 而不是 `guest_login` 那种 5/hour:**博物馆共享 WiFi 是真实场景**
    (见 `app_event.py` 里 guest_created 的注释),同一出口 IP 下多人反馈完全正常。
    这个端点写坏了最坏后果是垃圾行(SQL 能批量清),不是账号/资金风险。

    ⚠️ 按 IP 限流要真实客户端 IP 才有意义 —— 见 `app/main.py` 的
    TRUSTED_PROXY_HOSTS(修之前全站共享一个桶)。
    """
    user_id = None
    if credentials is not None:
        try:
            user_id = str(AuthService.get_current_user(db, credentials.credentials).id)
        except Exception:
            # 令牌过期/无效不该让反馈丢掉 —— 当匿名收下就是了。
            logger.info("feedback: ignoring invalid token, storing anonymously")

    db.add(
        Feedback(
            user_id=user_id,
            device_id=payload.device_id,
            scope=payload.scope,
            museum_slug=payload.museum_slug,
            qid=payload.qid,
            language=payload.language,
            kind=payload.kind,
            text=payload.text,
            app_version=payload.app_version,
            platform=payload.platform,
        )
    )
    # 这里**不吞异常**(与 log_event 的纪律相反):用户点了提交,存不下就得让他知道。
    db.commit()
