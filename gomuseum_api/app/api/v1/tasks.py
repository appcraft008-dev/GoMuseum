from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, UUID4
from typing import Optional, Dict, Any
from datetime import datetime

from app.core.auth import require_auth, require_enterprise
from app.core.tasks import (
    get_task_status, cancel_task, get_queue_stats, 
    TaskPriority, cleanup_expired_cache, send_notification
)
from app.core.logging import get_logger
from app.schemas.common import success_response

router = APIRouter()
logger = get_logger(__name__)


class TaskResponse(BaseModel):
    task_id: str
    status: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    attempts: int


class CreateTaskRequest(BaseModel):
    task_type: str
    priority: TaskPriority = TaskPriority.NORMAL
    delay: Optional[int] = None
    parameters: Optional[Dict[str, Any]] = None


@router.get("/tasks/{task_id}")
async def get_task(
    task_id: UUID4,
    current_user: dict = Depends(require_auth)
) -> TaskResponse:
    """Get task status and result"""
    
    task_data = await get_task_status(str(task_id))
    
    if not task_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "task_not_found", "message": "Task not found"}
        )
    
    # Convert datetime strings back to datetime objects for response model
    for field in ["created_at", "started_at", "completed_at"]:
        if task_data.get(field):
            task_data[field] = datetime.fromisoformat(task_data[field])
    
    return TaskResponse(**task_data)


@router.delete("/tasks/{task_id}")
async def cancel_task_endpoint(
    task_id: UUID4,
    current_user: dict = Depends(require_auth)
):
    """Cancel a pending task"""
    
    success = await cancel_task(str(task_id))
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "task_not_found", "message": "Task not found or cannot be cancelled"}
        )
    
    logger.info(f"Task cancelled: {task_id} by user {current_user['id']}")
    
    return success_response({"message": "Task cancelled successfully"})


@router.get("/tasks/queue/stats")
async def get_queue_statistics(
    current_user: dict = Depends(require_enterprise)  # Only enterprise users can see queue stats
):
    """Get task queue statistics"""
    
    stats = await get_queue_stats()
    return success_response(stats)


@router.post("/tasks/cleanup-cache")
async def trigger_cache_cleanup(
    current_user: dict = Depends(require_enterprise)  # Only enterprise users can trigger maintenance
):
    """Trigger cache cleanup task"""
    
    task_id = await cleanup_expired_cache.enqueue()
    
    logger.info(f"Cache cleanup task triggered: {task_id} by user {current_user['id']}")
    
    return success_response({
        "message": "Cache cleanup task queued",
        "task_id": task_id
    })


@router.post("/tasks/send-notification")
async def trigger_notification(
    request: CreateTaskRequest,
    current_user: dict = Depends(require_auth)
):
    """Send notification to user (demo task)"""
    
    if request.task_type != "send_notification":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_task_type", "message": "Only send_notification tasks are allowed"}
        )
    
    params = request.parameters or {}
    message = params.get("message", "Test notification")
    channel = params.get("channel", "email")
    
    # Send notification to current user
    task_id = await send_notification.enqueue(
        current_user["id"], 
        message,
        channel
    )
    
    logger.info(f"Notification task queued: {task_id} for user {current_user['id']}")
    
    return success_response({
        "message": "Notification task queued",
        "task_id": task_id
    })


@router.get("/tasks")
async def list_user_tasks(
    current_user: dict = Depends(require_auth),
    limit: int = 20,
    offset: int = 0
):
    """List user's tasks (would need implementation to filter by user)"""
    
    # This would require storing user association with tasks
    # For now, return empty list
    
    return success_response({
        "tasks": [],
        "total": 0,
        "limit": limit,
        "offset": offset
    })