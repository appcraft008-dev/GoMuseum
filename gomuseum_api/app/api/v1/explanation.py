from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel

from app.core.database import get_db
from app.schemas.explanation import ExplanationRequest, ExplanationResponse
from app.services.explanation_service import ExplanationService

router = APIRouter()

explanation_service = ExplanationService()

class ExplanationRequestModel(BaseModel):
    artwork_id: str
    language: str = "zh"
    user_id: Optional[str] = None
    style: str = "standard"  # standard, detailed, simple

@router.post("/artwork/{artwork_id}/explanation", response_model=ExplanationResponse)
async def generate_explanation(
    artwork_id: str,
    request: ExplanationRequestModel,
    db: Session = Depends(get_db)
):
    """
    Generate AI explanation for an artwork
    
    This endpoint generates detailed explanations using GPT-4,
    with caching and multiple language support.
    """
    try:
        # Validate artwork exists
        # TODO: Check if artwork exists in database
        
        explanation_result = await explanation_service.generate_explanation(
            artwork_id=artwork_id,
            language=request.language,
            style=request.style,
            db=db
        )
        
        return ExplanationResponse(**explanation_result)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate explanation: {str(e)}"
        )

@router.get("/artwork/{artwork_id}/explanation")
async def get_cached_explanation(
    artwork_id: str,
    language: str = "zh",
    db: Session = Depends(get_db)
):
    """Get cached explanation if available"""
    try:
        cached_explanation = await explanation_service.get_cached_explanation(
            artwork_id=artwork_id,
            language=language
        )
        
        if not cached_explanation:
            raise HTTPException(
                status_code=404,
                detail="No cached explanation found"
            )
            
        return cached_explanation
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get explanation: {str(e)}"
        )

@router.post("/artwork/{artwork_id}/chat")
async def chat_with_artwork(
    artwork_id: str,
    question: str,
    language: str = "zh",
    user_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    AI chat about specific artwork
    
    This endpoint allows users to ask questions about an artwork
    and get AI-generated responses based on the artwork's context.
    """
    try:
        if not question.strip():
            raise HTTPException(
                status_code=400,
                detail="Question cannot be empty"
            )
        
        chat_response = await explanation_service.chat_with_artwork(
            artwork_id=artwork_id,
            question=question,
            language=language,
            db=db
        )
        
        return chat_response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Chat failed: {str(e)}"
        )