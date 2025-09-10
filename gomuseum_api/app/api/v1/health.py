from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
import os
import psutil

from app.core.database import get_db, test_connection
from app.core.redis_client import redis_client
from app.core.config import settings

router = APIRouter()

@router.get("/health")
async def health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.app_version,
        "environment": settings.environment
    }

@router.get("/health/detailed")
async def detailed_health_check(db: Session = Depends(get_db)):
    """Detailed health check with database and redis status"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.app_version,
        "environment": settings.environment,
        "checks": {}
    }
    
    # Database health
    try:
        db_healthy = test_connection()
        health_status["checks"]["database"] = {
            "status": "healthy" if db_healthy else "unhealthy",
            "url": settings.database_url.split("@")[-1] if "@" in settings.database_url else "local"
        }
    except Exception as e:
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # Redis health
    try:
        if redis_client.redis:
            await redis_client.redis.ping()
            redis_stats = await redis_client.get_stats()
            health_status["checks"]["redis"] = {
                "status": "healthy",
                "stats": redis_stats
            }
        else:
            health_status["checks"]["redis"] = {
                "status": "disconnected"
            }
    except Exception as e:
        health_status["checks"]["redis"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # System resources
    try:
        memory_info = psutil.virtual_memory()
        disk_info = psutil.disk_usage('/')
        
        health_status["checks"]["system"] = {
            "status": "healthy",
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory": {
                "total": f"{memory_info.total // (1024**3)}GB",
                "available": f"{memory_info.available // (1024**3)}GB",
                "percent": memory_info.percent
            },
            "disk": {
                "total": f"{disk_info.total // (1024**3)}GB",
                "free": f"{disk_info.free // (1024**3)}GB",
                "percent": (disk_info.used / disk_info.total) * 100
            }
        }
    except Exception as e:
        health_status["checks"]["system"] = {
            "status": "error",
            "error": str(e)
        }
    
    # Overall health status
    unhealthy_checks = [
        check for check in health_status["checks"].values() 
        if check.get("status") != "healthy"
    ]
    
    if unhealthy_checks:
        health_status["status"] = "degraded"
        if len(unhealthy_checks) >= 2:
            health_status["status"] = "unhealthy"
    
    return health_status

@router.get("/health/ready")
async def readiness_check(db: Session = Depends(get_db)):
    """Readiness probe for Kubernetes"""
    try:
        # Check critical dependencies
        db_healthy = test_connection()
        
        if not db_healthy:
            raise HTTPException(status_code=503, detail="Database not ready")
        
        return {"status": "ready"}
    
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service not ready: {str(e)}")

@router.get("/health/live")
async def liveness_check():
    """Liveness probe for Kubernetes"""
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}