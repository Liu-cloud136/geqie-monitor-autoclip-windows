"""
服务容器 - 使用依赖注入解耦服务层
提供统一的服务实例管理和依赖注入
"""

from dependency_injector import containers, providers
from dependency_injector.wiring import Provide, inject
from sqlalchemy.orm import Session
from typing import Optional
import logging

from core.database import SessionLocal, engine
from core.event_bus import EventBus, get_event_bus
from core.unified_config import get_redis_url, get_database_url
from services.unified_processing_service import UnifiedProcessingService
from services.unified_progress_service import UnifiedProgressService
from services.unified_websocket_service import UnifiedWebSocketService
from services.project_service import ProjectService
from services.task_service import TaskService
from services.clip_service import ClipService
from services.data_sync_service import DataSyncService
from services.task_queue_service import TaskQueueService
from services.task_submission_service import TaskSubmissionService
from services.unified_storage_service import UnifiedStorageService
from repositories.task_repository import TaskRepository

logger = logging.getLogger(__name__)


class ServiceContainer(containers.DeclarativeContainer):
    """服务容器 - 管理所有服务的依赖关系"""

    config = providers.Configuration()

    database_engine = providers.Singleton(
        lambda: engine
    )

    database_session_factory = providers.Factory(
        SessionLocal
    )

    @providers.Singleton
    def event_bus() -> EventBus:
        return get_event_bus()

    @providers.Factory
    def task_repository(db: Session = Provide[database_session_factory]) -> TaskRepository:
        return TaskRepository(db)

    @providers.Singleton
    def progress_service(
        event_bus: EventBus = Provide[event_bus]
    ) -> UnifiedProgressService:
        return UnifiedProgressService(event_bus=event_bus)

    @providers.Singleton
    def websocket_service(
        event_bus: EventBus = Provide[event_bus]
    ) -> UnifiedWebSocketService:
        return UnifiedWebSocketService(event_bus=event_bus)

    @providers.Factory
    def project_service(
        db: Session = Provide[database_session_factory]
    ) -> ProjectService:
        return ProjectService(db)

    @providers.Factory
    def task_service(
        db: Session = Provide[database_session_factory]
    ) -> TaskService:
        return TaskService(db)

    @providers.Factory
    def clip_service(
        db: Session = Provide[database_session_factory]
    ) -> ClipService:
        return ClipService(db)

    @providers.Factory
    def data_sync_service(
        db: Session = Provide[database_session_factory]
    ) -> DataSyncService:
        return DataSyncService(db)

    @providers.Factory
    def task_queue_service(
        db: Session = Provide[database_session_factory],
        event_bus: EventBus = Provide[event_bus]
    ) -> TaskQueueService:
        return TaskQueueService(db, event_bus)

    @providers.Factory
    def task_submission_service(
        db: Session = Provide[database_session_factory],
        event_bus: EventBus = Provide[event_bus]
    ) -> TaskSubmissionService:
        return TaskSubmissionService(db, event_bus)

    @providers.Singleton
    def storage_service() -> UnifiedStorageService:
        return UnifiedStorageService()

    @providers.Factory
    def unified_processing_service(
        db: Session = Provide[database_session_factory],
        task_repository: TaskRepository = Provide[task_repository],
        progress_service: UnifiedProgressService = Provide[progress_service],
        event_bus: EventBus = Provide[event_bus],
        data_sync_service: DataSyncService = Provide[data_sync_service]
    ) -> UnifiedProcessingService:
        return UnifiedProcessingService(
            db=db,
            task_repository=task_repository,
            progress_service=progress_service,
            event_bus=event_bus,
            data_sync_service=data_sync_service
        )


container = ServiceContainer()


def init_container():
    """初始化服务容器"""
    try:
        container.wire(modules=[
            "api.v1.projects",
            "api.v1.tasks",
            "api.v1.clips",
            "services.unified_processing_service",
            "services.unified_progress_service",
            "services.unified_websocket_service",
        ])
        logger.info("服务容器初始化成功")
    except Exception as e:
        logger.error(f"服务容器初始化失败: {e}")
        raise


def get_container() -> ServiceContainer:
    """获取服务容器实例"""
    return container


def shutdown_container():
    """关闭服务容器"""
    try:
        container.unwire()
        logger.info("服务容器已关闭")
    except Exception as e:
        logger.error(f"关闭服务容器失败: {e}")
