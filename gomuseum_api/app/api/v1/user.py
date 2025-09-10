from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel, UUID4

from app.core.database import get_db
from app.models.user import User
from app.schemas.user import UserResponse, UserCreate, UserUpdate

router = APIRouter()

def check_and_consume_quota(db: Session, user_id: str) -> bool:
    """Atomically check and consume user quota"""
    try:
        # Use SELECT FOR UPDATE to prevent race conditions
        user = db.query(User).filter(User.id == user_id).with_for_update().first()
        if not user:
            return False
        
        # Check quota atomically
        if user.subscription_type == 'free' and user.free_quota <= 0:
            return False
        
        # Consume quota atomically
        if user.subscription_type == 'free':
            user.free_quota -= 1
        user.total_recognitions += 1
        
        db.commit()
        return True
        
    except Exception as e:
        db.rollback()
        return False

class UserQuotaResponse(BaseModel):
    user_id: str
    free_quota: int
    total_recognitions: int
    subscription_type: str
    has_quota: bool

@router.post("/user", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    """Create a new user"""
    try:
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == user_data.email).first()
        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="User with this email already exists"
            )
        
        # Create new user
        new_user = User(
            email=user_data.email,
            username=user_data.username,
            language=user_data.language or 'zh'
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        return UserResponse.model_validate(new_user)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create user: {str(e)}"
        )

@router.get("/user/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID4,  # Strong UUID validation
    db: Session = Depends(get_db)
):
    """Get user information"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )
        
        return UserResponse.model_validate(user)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get user: {str(e)}"
        )

@router.get("/user/{user_id}/quota", response_model=UserQuotaResponse)
async def get_user_quota(
    user_id: UUID4,
    db: Session = Depends(get_db)
):
    """Get user quota information"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )
        
        return UserQuotaResponse(
            user_id=str(user.id),
            free_quota=user.free_quota,
            total_recognitions=user.total_recognitions,
            subscription_type=user.subscription_type,
            has_quota=user.has_quota()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get quota: {str(e)}"
        )

@router.post("/user/{user_id}/consume-quota")
async def consume_user_quota(
    user_id: UUID4,
    db: Session = Depends(get_db)
):
    """Consume one quota unit"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )
        
        if not user.consume_quota():
            raise HTTPException(
                status_code=400,
                detail="No quota available"
            )
        
        db.commit()
        
        return {
            "success": True,
            "remaining_quota": user.free_quota,
            "total_recognitions": user.total_recognitions
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to consume quota: {str(e)}"
        )

@router.put("/user/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID4,
    user_data: UserUpdate,
    db: Session = Depends(get_db)
):
    """Update user information"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )
        
        # Update fields
        if user_data.username is not None:
            user.username = user_data.username
        if user_data.language is not None:
            user.language = user_data.language
        
        db.commit()
        db.refresh(user)
        
        return UserResponse.model_validate(user)
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update user: {str(e)}"
        )