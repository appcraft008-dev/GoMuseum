"""User schemas for API validation"""

from datetime import datetime
from typing import Optional

from pydantic import UUID4, BaseModel, EmailStr


class UserBase(BaseModel):
    """Base user schema"""

    email: Optional[EmailStr] = None
    username: Optional[str] = None


class UserCreate(UserBase):
    """Schema for user registration"""

    password: str


class UserUpdate(BaseModel):
    """Schema for user profile update"""

    username: Optional[str] = None
    avatar_url: Optional[str] = None


class UserResponse(UserBase):
    """Schema for user response"""

    id: UUID4
    avatar_url: Optional[str] = None
    is_active: bool
    is_verified: bool
    # 游客标记。**加法字段**,老 App 不认识它、忽略即可。
    #
    # 前端需要它来判断「这个人还能不能去登录页」:游客在服务端是一行真的
    # User(有 token、能过鉴权),客户端此前无从区分,于是路由守卫把游客当成
    # 「已登录」,点「登录后购买」被直接弹回首页 —— 游客永远买不了票。
    # 不能靠 `email == null` 反推:那是拿代理特征猜身份,真相源在这里。
    is_guest: bool = False
    created_at: datetime
    last_login_at: Optional[datetime] = None

    class Config:
        from_attributes = True
