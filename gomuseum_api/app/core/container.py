"""
Dependency Injection Container

Implements a lightweight dependency injection container to manage service
dependencies and promote loose coupling following DDD principles.
"""

from typing import Dict, Type, Any, Optional, Callable
from abc import ABC, abstractmethod
import asyncio
from contextlib import asynccontextmanager

from app.core.logging import get_logger

logger = get_logger(__name__)


class DIContainer:
    """Lightweight dependency injection container"""
    
    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._singletons: Dict[str, Any] = {}
        self._factories: Dict[str, Callable] = {}
        self._interfaces: Dict[str, Type] = {}
        
    def register_singleton(self, interface: str, implementation: Any):
        """Register a singleton service"""
        self._singletons[interface] = implementation
        logger.debug(f"Registered singleton: {interface}")
    
    def register_transient(self, interface: str, factory: Callable):
        """Register a transient service factory"""
        self._factories[interface] = factory
        logger.debug(f"Registered transient: {interface}")
    
    def register_interface(self, interface_name: str, interface_type: Type):
        """Register an interface type"""
        self._interfaces[interface_name] = interface_type
        logger.debug(f"Registered interface: {interface_name}")
    
    def get(self, interface: str) -> Any:
        """Get service instance"""
        # Check singletons first
        if interface in self._singletons:
            return self._singletons[interface]
        
        # Check factories
        if interface in self._factories:
            return self._factories[interface]()
        
        # Check regular services
        if interface in self._services:
            return self._services[interface]
        
        raise ValueError(f"Service not registered: {interface}")
    
    def resolve(self, service_type: Type) -> Any:
        """Resolve service by type"""
        type_name = service_type.__name__
        return self.get(type_name)
    
    async def initialize_async_services(self):
        """Initialize services that require async setup"""
        for interface, service in self._singletons.items():
            if hasattr(service, 'initialize') and asyncio.iscoroutinefunction(service.initialize):
                try:
                    await service.initialize()
                    logger.info(f"Initialized async service: {interface}")
                except Exception as e:
                    logger.error(f"Failed to initialize {interface}: {e}")
    
    async def cleanup_services(self):
        """Cleanup services on shutdown"""
        for interface, service in self._singletons.items():
            if hasattr(service, 'cleanup') and asyncio.iscoroutinefunction(service.cleanup):
                try:
                    await service.cleanup()
                    logger.info(f"Cleaned up service: {interface}")
                except Exception as e:
                    logger.error(f"Failed to cleanup {interface}: {e}")


# Global container instance
container = DIContainer()


# Service registration functions
def register_repositories():
    """Register repository implementations"""
    from app.repositories.base import BaseRepository
    from app.repositories.artwork_repository import ArtworkRepository
    from app.repositories.recognition_repository import RecognitionRepository
    
    # Register repository interfaces
    container.register_interface("IArtworkRepository", BaseRepository)
    container.register_interface("IRecognitionRepository", BaseRepository)
    
    # Register repository implementations as singletons
    container.register_singleton("ArtworkRepository", ArtworkRepository())
    container.register_singleton("RecognitionRepository", RecognitionRepository())
    
    logger.info("Repositories registered")


def register_services():
    """Register service implementations"""
    from app.services.recognition_service_refactored import RecognitionService
    from app.services.explanation_service import ExplanationService
    
    # Register services with dependency injection
    def recognition_service_factory():
        artwork_repo = container.get("ArtworkRepository")
        recognition_repo = container.get("RecognitionRepository")
        return RecognitionService(artwork_repo, recognition_repo)
    
    def explanation_service_factory():
        return ExplanationService()
    
    container.register_transient("RecognitionService", recognition_service_factory)
    container.register_transient("ExplanationService", explanation_service_factory)
    
    logger.info("Services registered")


def register_core_services():
    """Register core infrastructure services"""
    from app.core.token_manager import token_manager
    from app.core.security_config import get_key_manager, get_data_encryptor
    from app.core.cache_strategy import cache_manager
    
    # Register core services
    container.register_singleton("TokenManager", token_manager)
    container.register_singleton("KeyManager", get_key_manager())
    container.register_singleton("DataEncryptor", get_data_encryptor())
    container.register_singleton("CacheManager", cache_manager)
    
    logger.info("Core services registered")


async def initialize_container():
    """Initialize the DI container with all services"""
    try:
        register_core_services()
        register_repositories()
        register_services()
        
        # Initialize async services
        await container.initialize_async_services()
        
        logger.info("Dependency injection container initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize DI container: {e}")
        raise


async def cleanup_container():
    """Cleanup the DI container"""
    try:
        await container.cleanup_services()
        logger.info("Dependency injection container cleaned up")
    except Exception as e:
        logger.error(f"Failed to cleanup DI container: {e}")


# Dependency injection decorators for FastAPI
class Inject:
    """Dependency injection for FastAPI endpoints"""
    
    @staticmethod
    def get_service(service_name: str):
        """Get service dependency for FastAPI"""
        def dependency():
            return container.get(service_name)
        return dependency
    
    @staticmethod
    def get_recognition_service():
        """Get recognition service dependency"""
        return container.get("RecognitionService")
    
    @staticmethod
    def get_explanation_service():
        """Get explanation service dependency"""
        return container.get("ExplanationService")
    
    @staticmethod
    def get_token_manager():
        """Get token manager dependency"""
        return container.get("TokenManager")
    
    @staticmethod
    def get_cache_manager():
        """Get cache manager dependency"""
        return container.get("CacheManager")


# FastAPI dependency functions
def get_recognition_service():
    """FastAPI dependency for recognition service"""
    return container.get("RecognitionService")


def get_explanation_service():
    """FastAPI dependency for explanation service"""
    return container.get("ExplanationService")


def get_token_manager():
    """FastAPI dependency for token manager"""
    return container.get("TokenManager")


def get_cache_manager():
    """FastAPI dependency for cache manager"""
    return container.get("CacheManager")


# Context manager for service lifecycle
@asynccontextmanager
async def service_context():
    """Context manager for service lifecycle management"""
    try:
        await initialize_container()
        yield container
    finally:
        await cleanup_container()


# Service locator pattern (discouraged, but provided for legacy support)
class ServiceLocator:
    """Service locator (use dependency injection instead when possible)"""
    
    @staticmethod
    def get_recognition_service():
        """Get recognition service (use DI instead)"""
        return container.get("RecognitionService")
    
    @staticmethod
    def get_explanation_service():
        """Get explanation service (use DI instead)"""
        return container.get("ExplanationService")


# Configuration for testing
def configure_test_container():
    """Configure container for testing with mocks"""
    # Clear existing registrations
    container._services.clear()
    container._singletons.clear()
    container._factories.clear()
    
    # Register test doubles
    from unittest.mock import Mock
    
    container.register_singleton("ArtworkRepository", Mock())
    container.register_singleton("RecognitionRepository", Mock())
    container.register_singleton("TokenManager", Mock())
    
    logger.info("Test container configured")


# Health check for container
def container_health_check() -> Dict[str, Any]:
    """Check container health status"""
    try:
        services_count = len(container._singletons) + len(container._factories)
        
        health_status = {
            "status": "healthy",
            "services_registered": services_count,
            "singletons": list(container._singletons.keys()),
            "factories": list(container._factories.keys())
        }
        
        return health_status
        
    except Exception as e:
        return {
            "status": "unhealthy", 
            "error": str(e)
        }