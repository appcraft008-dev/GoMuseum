import asyncio
import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional, Callable, List
from enum import Enum
import traceback

from .redis_client import redis_client, get_cache_key
from .logging import get_logger

logger = get_logger(__name__)


class TaskStatus(str, Enum):
    """Task execution status"""
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    """Task priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class Task:
    """Individual task representation"""
    
    def __init__(
        self,
        task_id: str,
        func_name: str,
        args: tuple = (),
        kwargs: dict = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        retry_count: int = 3,
        timeout: Optional[int] = None,
        delay: Optional[int] = None
    ):
        self.task_id = task_id
        self.func_name = func_name
        self.args = args
        self.kwargs = kwargs or {}
        self.priority = priority
        self.retry_count = retry_count
        self.timeout = timeout
        self.delay = delay
        self.status = TaskStatus.PENDING
        self.created_at = datetime.now(timezone.utc)
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.result: Any = None
        self.error: Optional[str] = None
        self.attempts = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary for serialization"""
        return {
            "task_id": self.task_id,
            "func_name": self.func_name,
            "args": self.args,
            "kwargs": self.kwargs,
            "priority": self.priority,
            "retry_count": self.retry_count,
            "timeout": self.timeout,
            "delay": self.delay,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error": self.error,
            "attempts": self.attempts
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """Create task from dictionary"""
        task = cls(
            task_id=data["task_id"],
            func_name=data["func_name"],
            args=tuple(data["args"]),
            kwargs=data["kwargs"],
            priority=TaskPriority(data["priority"]),
            retry_count=data["retry_count"],
            timeout=data["timeout"],
            delay=data["delay"]
        )
        task.status = TaskStatus(data["status"])
        task.created_at = datetime.fromisoformat(data["created_at"])
        task.started_at = datetime.fromisoformat(data["started_at"]) if data["started_at"] else None
        task.completed_at = datetime.fromisoformat(data["completed_at"]) if data["completed_at"] else None
        task.result = data["result"]
        task.error = data["error"]
        task.attempts = data["attempts"]
        return task


class TaskQueue:
    """Async task queue implementation using Redis"""
    
    def __init__(self, queue_name: str = "default"):
        self.queue_name = queue_name
        self.task_registry: Dict[str, Callable] = {}
        self.running = False
        self.workers: List[asyncio.Task] = []
        self.max_workers = 3
    
    def register_task(self, func: Callable, name: Optional[str] = None):
        """Register a task function"""
        task_name = name or f"{func.__module__}.{func.__name__}"
        self.task_registry[task_name] = func
        logger.info(f"Registered task: {task_name}")
        return func
    
    async def enqueue(
        self,
        func_name: str,
        args: tuple = (),
        kwargs: dict = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        retry_count: int = 3,
        timeout: Optional[int] = None,
        delay: Optional[int] = None
    ) -> str:
        """Add task to queue"""
        
        task_id = str(uuid.uuid4())
        task = Task(
            task_id=task_id,
            func_name=func_name,
            args=args,
            kwargs=kwargs or {},
            priority=priority,
            retry_count=retry_count,
            timeout=timeout,
            delay=delay
        )
        
        # Store task data
        await self._store_task(task)
        
        # Add to appropriate queue
        queue_key = get_cache_key("queue", self.queue_name, priority.value)
        
        if delay:
            # Schedule for delayed execution
            scheduled_time = datetime.now(timezone.utc) + timedelta(seconds=delay)
            await redis_client.set(
                get_cache_key("scheduled", task_id),
                json.dumps({
                    "task_id": task_id,
                    "scheduled_time": scheduled_time.isoformat(),
                    "queue_key": queue_key
                }),
                ttl=delay + 3600  # TTL slightly longer than delay
            )
        else:
            # Add to immediate queue
            await redis_client.redis.lpush(queue_key, task_id)
        
        logger.info(f"Task enqueued: {task_id} ({func_name})", extra={"task_id": task_id})
        return task_id
    
    async def _store_task(self, task: Task):
        """Store task data in Redis"""
        task_key = get_cache_key("task", task.task_id)
        await redis_client.set(
            task_key,
            task.to_dict(),
            ttl=86400 * 7  # Keep task data for 7 days
        )
    
    async def _get_task(self, task_id: str) -> Optional[Task]:
        """Retrieve task from Redis"""
        task_key = get_cache_key("task", task_id)
        task_data = await redis_client.get(task_key)
        if task_data:
            return Task.from_dict(task_data)
        return None
    
    async def _update_task(self, task: Task):
        """Update task data in Redis"""
        await self._store_task(task)
    
    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status and result"""
        task = await self._get_task(task_id)
        if task:
            return task.to_dict()
        return None
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task"""
        task = await self._get_task(task_id)
        if task and task.status == TaskStatus.PENDING:
            task.status = TaskStatus.CANCELLED
            await self._update_task(task)
            logger.info(f"Task cancelled: {task_id}")
            return True
        return False
    
    async def start_workers(self, worker_count: Optional[int] = None):
        """Start background workers"""
        if self.running:
            return
        
        self.running = True
        self.max_workers = worker_count or self.max_workers
        
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self.workers.append(worker)
        
        # Start scheduled task processor
        scheduler = asyncio.create_task(self._scheduled_task_processor())
        self.workers.append(scheduler)
        
        logger.info(f"Started {self.max_workers} workers for queue: {self.queue_name}")
    
    async def stop_workers(self):
        """Stop background workers"""
        self.running = False
        
        for worker in self.workers:
            worker.cancel()
        
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()
        
        logger.info(f"Stopped workers for queue: {self.queue_name}")
    
    async def _worker(self, worker_name: str):
        """Background worker that processes tasks"""
        logger.info(f"Worker {worker_name} started")
        
        while self.running:
            try:
                # Check queues by priority
                task_id = None
                for priority in [TaskPriority.CRITICAL, TaskPriority.HIGH, TaskPriority.NORMAL, TaskPriority.LOW]:
                    queue_key = get_cache_key("queue", self.queue_name, priority.value)
                    result = await redis_client.redis.rpop(queue_key)
                    if result:
                        task_id = result.decode('utf-8') if isinstance(result, bytes) else result
                        break
                
                if not task_id:
                    # No tasks available, wait a bit
                    await asyncio.sleep(1)
                    continue
                
                # Process task
                await self._process_task(task_id, worker_name)
                
            except Exception as e:
                logger.error(f"Worker {worker_name} error: {e}", exc_info=True)
                await asyncio.sleep(5)  # Brief pause on error
        
        logger.info(f"Worker {worker_name} stopped")
    
    async def _scheduled_task_processor(self):
        """Process scheduled tasks"""
        while self.running:
            try:
                # Find scheduled tasks that are ready
                pattern = get_cache_key("scheduled", "*")
                
                # This is a simplified approach - in production, use Redis sorted sets
                # for better scheduled task management
                
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logger.error(f"Scheduled task processor error: {e}", exc_info=True)
                await asyncio.sleep(30)
    
    async def _process_task(self, task_id: str, worker_name: str):
        """Process a single task"""
        task = await self._get_task(task_id)
        if not task:
            logger.warning(f"Task not found: {task_id}")
            return
        
        if task.status != TaskStatus.PENDING:
            logger.warning(f"Task not pending: {task_id} (status: {task.status})")
            return
        
        # Update task status
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now(timezone.utc)
        task.attempts += 1
        await self._update_task(task)
        
        logger.info(f"Processing task: {task_id} ({task.func_name}) on {worker_name}")
        
        try:
            # Get task function
            if task.func_name not in self.task_registry:
                raise ValueError(f"Task function not registered: {task.func_name}")
            
            func = self.task_registry[task.func_name]
            
            # Execute task with timeout
            if task.timeout:
                result = await asyncio.wait_for(
                    func(*task.args, **task.kwargs),
                    timeout=task.timeout
                )
            else:
                result = await func(*task.args, **task.kwargs)
            
            # Task completed successfully
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now(timezone.utc)
            task.result = result
            task.error = None
            
            logger.info(f"Task completed: {task_id}")
            
        except Exception as e:
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            logger.error(f"Task failed: {task_id} - {error_msg}")
            
            # Check if we should retry
            if task.attempts < task.retry_count:
                # Retry task
                task.status = TaskStatus.PENDING
                task.error = f"Attempt {task.attempts} failed: {str(e)}"
                
                # Add back to queue with exponential backoff
                delay = min(2 ** task.attempts, 300)  # Max 5 minutes
                await asyncio.sleep(delay)
                
                queue_key = get_cache_key("queue", self.queue_name, task.priority.value)
                await redis_client.redis.lpush(queue_key, task_id)
                
                logger.info(f"Task requeued for retry: {task_id} (attempt {task.attempts}/{task.retry_count})")
            else:
                # Mark as failed
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.now(timezone.utc)
                task.error = error_msg
                
                logger.error(f"Task failed permanently: {task_id}")
        
        await self._update_task(task)
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        stats = {
            "queue_name": self.queue_name,
            "running": self.running,
            "worker_count": len(self.workers),
            "registered_tasks": list(self.task_registry.keys()),
            "queue_sizes": {}
        }
        
        # Get queue sizes for each priority
        for priority in TaskPriority:
            queue_key = get_cache_key("queue", self.queue_name, priority.value)
            size = await redis_client.redis.llen(queue_key) or 0
            stats["queue_sizes"][priority.value] = size
        
        return stats


# Global task queue instance
task_queue = TaskQueue("gomuseum")


# Task decorators
def task(
    priority: TaskPriority = TaskPriority.NORMAL,
    retry_count: int = 3,
    timeout: Optional[int] = None
):
    """Decorator to register a task function"""
    def decorator(func: Callable):
        task_queue.register_task(func)
        
        # Add enqueue method to function
        async def enqueue(*args, **kwargs):
            return await task_queue.enqueue(
                f"{func.__module__}.{func.__name__}",
                args=args,
                kwargs=kwargs,
                priority=priority,
                retry_count=retry_count,
                timeout=timeout
            )
        
        func.enqueue = enqueue
        return func
    
    return decorator


# Example task functions
@task(priority=TaskPriority.LOW)
async def cleanup_expired_cache():
    """Clean up expired cache entries"""
    logger.info("Running cache cleanup")
    # Implementation here
    return "Cache cleanup completed"


@task(priority=TaskPriority.NORMAL)
async def process_recognition_result(user_id: str, image_hash: str, result: dict):
    """Process recognition result in background"""
    logger.info(f"Processing recognition result for user {user_id}")
    
    # Save to database, send notifications, etc.
    await asyncio.sleep(2)  # Simulate processing
    
    return f"Processed recognition for {user_id}"


@task(priority=TaskPriority.HIGH, retry_count=5)
async def send_notification(user_id: str, message: str, channel: str = "email"):
    """Send notification to user"""
    logger.info(f"Sending notification to user {user_id} via {channel}")
    
    # Implementation for sending notifications
    await asyncio.sleep(1)  # Simulate sending
    
    return f"Notification sent to {user_id}"


# Task queue management functions
async def start_task_workers():
    """Start background task workers"""
    await task_queue.start_workers()


async def stop_task_workers():
    """Stop background task workers"""
    await task_queue.stop_workers()


async def get_task_status(task_id: str) -> Optional[Dict[str, Any]]:
    """Get task status"""
    return await task_queue.get_task_status(task_id)


async def cancel_task(task_id: str) -> bool:
    """Cancel a task"""
    return await task_queue.cancel_task(task_id)


async def get_queue_stats() -> Dict[str, Any]:
    """Get queue statistics"""
    return await task_queue.get_queue_stats()