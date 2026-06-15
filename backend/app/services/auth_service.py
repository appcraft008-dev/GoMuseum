"""Authentication service"""

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import LoginRequest, OAuthRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserResponse


class AuthService:
    """Service for authentication operations"""

    @staticmethod
    def register(db: Session, request: RegisterRequest) -> TokenResponse:
        """Register a new user"""
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == request.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        # Create new user
        user = User(
            email=request.email,
            username=request.username,
            password_hash=hash_password(request.password),
            is_active=True,
            is_verified=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # Generate tokens
        access_token = create_access_token(
            data={"sub": str(user.id), "email": user.email}
        )
        refresh_token = create_refresh_token(
            data={"sub": str(user.id), "email": user.email}
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=UserResponse.model_validate(user),
        )

    @staticmethod
    def login(db: Session, request: LoginRequest) -> TokenResponse:
        """Login user with email and password"""
        # Find user by email
        user = db.query(User).filter(User.email == request.email).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
            )

        # Verify password
        if not user.password_hash or not verify_password(
            request.password, user.password_hash
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
            )

        # Check if user is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive",
            )

        # Update last login
        user.last_login_at = datetime.utcnow()
        db.commit()

        # Generate tokens
        access_token = create_access_token(
            data={"sub": str(user.id), "email": user.email}
        )
        refresh_token = create_refresh_token(
            data={"sub": str(user.id), "email": user.email}
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=UserResponse.model_validate(user),
        )

    @staticmethod
    def refresh_token(db: Session, refresh_token: str) -> TokenResponse:
        """Refresh access token using refresh token"""
        # Decode refresh token
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        # 轮换撤销：已用过的 refresh token 不能再次使用
        from app.core.token_blacklist import token_blacklist

        jti = payload.get("jti")
        if jti and token_blacklist.is_revoked(jti):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been revoked",
            )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )

        # UUID 列在非 PG 后端要求 uuid.UUID 对象（PG 可隐式转换字符串）
        import uuid as _uuid

        try:
            user_id = _uuid.UUID(str(user_id))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )

        # Get user from database
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )

        # Generate new tokens
        access_token = create_access_token(
            data={"sub": str(user.id), "email": user.email}
        )
        new_refresh_token = create_refresh_token(
            data={"sub": str(user.id), "email": user.email}
        )

        # 轮换：旧 refresh token 立即作废（TTL 为其剩余有效期）
        if jti:
            from datetime import datetime as _dt

            exp = payload.get("exp")
            ttl = int(exp - _dt.utcnow().timestamp()) if exp else 0
            token_blacklist.revoke(jti, ttl)

        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            user=UserResponse.model_validate(user),
        )

    @staticmethod
    def get_current_user(db: Session, token: str) -> User:
        """Get current user from access token"""
        # Decode token
        payload = decode_token(token)
        if not payload or payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid access token",
            )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )

        # UUID 列在非 PG 后端要求 uuid.UUID 对象（PG 可隐式转换字符串）
        import uuid as _uuid

        try:
            user_id = _uuid.UUID(str(user_id))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )

        # Get user from database
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )

        return user

    @staticmethod
    def oauth_google(db: Session, request: OAuthRequest) -> TokenResponse:
        """Authenticate with Google OAuth"""
        google_client_id = getattr(settings, "GOOGLE_CLIENT_ID", None)
        if not google_client_id:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="GOOGLE_CLIENT_ID not configured",
            )

        try:
            # Verify the ID token with Google
            idinfo = id_token.verify_oauth2_token(
                request.id_token, google_requests.Request(), google_client_id
            )

            # Extract user info
            google_id = idinfo["sub"]
            email = idinfo["email"]
            username = request.username or idinfo.get("name", email.split("@")[0])

            # Check if user exists
            user = db.query(User).filter(User.google_id == google_id).first()

            if not user:
                # Check if email is already registered
                user = db.query(User).filter(User.email == email).first()
                if user:
                    # Link Google account to existing user
                    user.google_id = google_id
                else:
                    # Create new user
                    user = User(
                        email=email,
                        username=username,
                        google_id=google_id,
                        is_active=True,
                        is_verified=True,  # Email verified by Google
                    )
                    db.add(user)

                db.commit()
                db.refresh(user)

            # Update last login
            user.last_login_at = datetime.utcnow()
            db.commit()

            # Generate tokens
            access_token = create_access_token(
                data={"sub": str(user.id), "email": user.email}
            )
            refresh_token = create_refresh_token(
                data={"sub": str(user.id), "email": user.email}
            )

            return TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                user=UserResponse.model_validate(user),
            )

        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid Google ID token: {str(e)}",
            )

    @staticmethod
    def oauth_apple(db: Session, request: OAuthRequest) -> TokenResponse:
        """Authenticate with Apple Sign In"""
        import jwt
        import requests
        from jwt.algorithms import RSAAlgorithm

        apple_client_id = getattr(settings, "APPLE_CLIENT_ID", None)
        if not apple_client_id:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="APPLE_CLIENT_ID not configured",
            )

        try:
            # 1. Get Apple's public keys
            keys_url = "https://appleid.apple.com/auth/keys"
            keys_response = requests.get(keys_url, timeout=10)
            keys_response.raise_for_status()
            apple_keys = keys_response.json()

            # 2. Decode header to get key id
            unverified_header = jwt.get_unverified_header(request.id_token)
            key_id = unverified_header.get("kid")

            if not key_id:
                raise ValueError("Token header missing 'kid'")

            # 3. Find the correct public key
            public_key = None
            for key in apple_keys["keys"]:
                if key["kid"] == key_id:
                    public_key = RSAAlgorithm.from_jwk(key)
                    break

            if not public_key:
                raise ValueError(f"Public key not found for kid: {key_id}")

            # 4. Verify and decode the token
            decoded = jwt.decode(
                request.id_token,
                public_key,
                algorithms=["RS256"],
                audience=apple_client_id,
                issuer="https://appleid.apple.com",
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_aud": True,
                    "verify_iss": True,
                },
            )

            # 5. Extract user info
            apple_id = decoded["sub"]
            email = decoded.get("email")
            username = request.username or (
                email.split("@")[0] if email else f"user_{apple_id[:8]}"
            )

            # 6. Check if user exists
            user = db.query(User).filter(User.apple_id == apple_id).first()

            if not user:
                if email:
                    # Check if email is already registered
                    user = db.query(User).filter(User.email == email).first()
                    if user:
                        # Link Apple account to existing user
                        user.apple_id = apple_id
                    else:
                        # Create new user with email
                        user = User(
                            email=email,
                            username=username,
                            apple_id=apple_id,
                            is_active=True,
                            is_verified=True,  # Email verified by Apple
                        )
                        db.add(user)
                else:
                    # Create user without email (Apple allows users to hide email)
                    user = User(
                        username=username,
                        apple_id=apple_id,
                        is_active=True,
                        is_verified=False,
                    )
                    db.add(user)

                db.commit()
                db.refresh(user)

            # 7. Update last login
            user.last_login_at = datetime.utcnow()
            db.commit()

            # 8. Generate tokens
            access_token = create_access_token(
                data={"sub": str(user.id), "email": user.email or ""}
            )
            refresh_token = create_refresh_token(
                data={"sub": str(user.id), "email": user.email or ""}
            )

            return TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                user=UserResponse.model_validate(user),
            )

        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Apple ID token has expired",
            )
        except jwt.InvalidTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid Apple ID token: {str(e)}",
            )
        except requests.RequestException as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to fetch Apple public keys: {str(e)}",
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Apple authentication failed: {str(e)}",
            )

    @staticmethod
    def guest_login(db: Session, device_id: Optional[str] = None) -> TokenResponse:
        """Create and login a guest user

        同一 device_id 复用既有游客账号，防止卸载重装刷新免费额度。
        """
        import uuid

        from app.models.user_benefits import UserBenefits

        # 设备已有游客账号则直接复用
        if device_id:
            existing = (
                db.query(UserBenefits)
                .filter(
                    UserBenefits.device_id == device_id,
                    UserBenefits.user_id.isnot(None),
                )
                .first()
            )
            if existing:
                user = (
                    db.query(User)
                    .filter(
                        User.id == uuid.UUID(existing.user_id),
                        User.is_guest.is_(True),
                        User.is_active.is_(True),
                    )
                    .first()
                )
                if user:
                    user.last_login_at = datetime.utcnow()
                    db.commit()
                    access_token = create_access_token(
                        data={
                            "sub": str(user.id),
                            "email": user.email or "",
                            "is_guest": True,
                        }
                    )
                    refresh_token = create_refresh_token(
                        data={"sub": str(user.id), "email": user.email or ""}
                    )
                    return TokenResponse(
                        access_token=access_token,
                        refresh_token=refresh_token,
                        user=UserResponse.model_validate(user),
                    )

        # Generate unique guest username
        guest_username = f"游客_{uuid.uuid4().hex[:8]}"

        # Create guest user
        user = User(
            username=guest_username,
            is_active=True,
            is_verified=False,
            is_guest=True,  # Mark as guest user
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # 绑定设备指纹，新设备初始化默认额度
        db.add(UserBenefits(user_id=str(user.id), device_id=device_id))
        db.commit()

        # Update last login
        user.last_login_at = datetime.utcnow()
        db.commit()

        # Generate tokens
        access_token = create_access_token(
            data={"sub": str(user.id), "email": user.email or "", "is_guest": True}
        )
        refresh_token = create_refresh_token(
            data={"sub": str(user.id), "email": user.email or "", "is_guest": True}
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=UserResponse.model_validate(user),
        )

    @staticmethod
    def export_user_data(db: Session, user: User) -> dict:
        """GDPR 数据导出：返回账号关联的全部个人数据"""
        from app.models.user_benefits import UserBenefits

        benefits = (
            db.query(UserBenefits).filter(UserBenefits.user_id == str(user.id)).all()
        )
        return {
            "user": {
                "id": str(user.id),
                "email": user.email,
                "username": user.username,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "last_login_at": (
                    user.last_login_at.isoformat()
                    if getattr(user, "last_login_at", None)
                    else None
                ),
            },
            "benefits": [
                {
                    "recognition_quota": b.recognition_quota,
                    "total_recognitions_used": b.total_recognitions_used,
                    "is_premium": b.is_premium,
                    "day_pass_active": b.day_pass_active,
                    "created_at": b.created_at.isoformat() if b.created_at else None,
                }
                for b in benefits
            ],
        }

    @staticmethod
    def delete_user_account(db: Session, user: User) -> None:
        """GDPR 删除权 / App Store 账号删除要求：删除账号及关联个人数据"""
        from app.models.user_benefits import UserBenefits

        db.query(UserBenefits).filter(UserBenefits.user_id == str(user.id)).delete(
            synchronize_session=False
        )
        db.delete(user)
        db.commit()
