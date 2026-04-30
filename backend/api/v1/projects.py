"""
项目API路由
"""

import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from core.database import get_db
from services.project_service import ProjectService
from services.processing_service import ProcessingService
from services.websocket_notification_service import WebSocketNotificationService
from tasks.processing import process_video_pipeline
from core.websocket_manager import manager as websocket_manager
from schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse, ProjectFilter,
    ProjectType, ProjectStatus
)
from schemas.base import PaginationParams
from pathlib import Path

logger = logging.getLogger(__name__)
router = APIRouter()


def get_project_service(db: Session = Depends(get_db)) -> ProjectService:
    """Dependency to get project service."""
    return ProjectService(db)


def get_processing_service(db: Session = Depends(get_db)) -> ProcessingService:
    """Dependency to get processing service."""
    return ProcessingService(db)

def get_websocket_service():
    """Dependency to get websocket notification service."""
    return WebSocketNotificationService


@router.post("/upload", response_model=ProjectResponse)
async def upload_files(
    video_file: UploadFile = File(...),
    project_name: str = Form(...),
    video_category: Optional[str] = Form(None),
    danmaku_file: Optional[UploadFile] = File(None),
    danmaku_source_type: str = Form("bilibili"),
    project_service: ProjectService = Depends(get_project_service)
):
    """Upload video file to create a new project. AI will automatically generate subtitles using Whisper.
    Optional: upload danmaku file for better clip scoring.
    """
    try:
        # 验证视频文件类型
        if not video_file.filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm')):
            raise HTTPException(status_code=400, detail="Invalid video file format")

        # 验证弹幕文件类型（如果提供）
        danmaku_file_info = None
        if danmaku_file:
            danmaku_ext = Path(danmaku_file.filename).suffix.lower()
            allowed_danmaku_extensions = ['.xml', '.json', '.ass', '.txt']
            if danmaku_ext not in allowed_danmaku_extensions:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid danmaku file format. Allowed: {', '.join(allowed_danmaku_extensions)}"
                )

        # 创建项目数据
        project_data = ProjectCreate(
            name=project_name,
            description=f"Video: {video_file.filename}, Subtitle: AI自动生成",
            project_type=ProjectType.KNOWLEDGE,  # 默认类型
            status=ProjectStatus.PENDING,
            source_url=None,
            source_file=video_file.filename,
            settings={
                "video_category": video_category or "knowledge",
                "video_file": video_file.filename,
                "subtitle_mode": "ai_generated"
            }
        )
        
        # 创建项目
        project = project_service.create_project(project_data)
        
        # 保存文件到项目目录
        project_id = str(project.id)
        from core.path_utils import get_project_raw_directory
        raw_dir = get_project_raw_directory(project_id)
        
        # 保存视频文件（使用流式写入，避免一次性加载到内存）
        video_path = raw_dir / "input.mp4"
        # 使用统一的配置
        try:
            from config.upload_config import UPLOAD_CHUNK_SIZE
            chunk_size = UPLOAD_CHUNK_SIZE
        except ImportError:
            chunk_size = 16 * 1024 * 1024  # 16MB chunks - 默认值
        
        with open(video_path, "wb") as f:
            while chunk := await video_file.read(chunk_size):
                f.write(chunk)

        # 延迟更新项目视频路径，在异步任务中统一提交，减少数据库操作
        project.video_path = str(video_path)
        
        # 处理弹幕文件（如果提供）
        if danmaku_file:
            try:
                from models.danmaku import DanmakuFile, DanmakuFileStatus, DanmakuSourceType
                from utils.danmaku_parser import DanmakuParser, save_danmaku_to_json
                from core.unified_config import get_config
                
                # 获取弹幕存储目录
                config = get_config()
                danmaku_dir = config.paths.data_dir / "danmaku"
                danmaku_dir.mkdir(parents=True, exist_ok=True)
                
                import uuid
                file_id = str(uuid.uuid4())
                safe_filename = f"{file_id}{danmaku_ext}"
                saved_path = danmaku_dir / safe_filename
                
                # 保存弹幕文件
                danmaku_content = await danmaku_file.read()
                saved_path.write_bytes(danmaku_content)
                
                # 解析弹幕来源类型
                try:
                    source_type_enum = DanmakuSourceType(danmaku_source_type.lower())
                except ValueError:
                    source_type_enum = DanmakuSourceType.BILIBILI
                
                # 使用 project_service 中的数据库会话
                db = project_service.db
                
                # 创建弹幕文件记录
                danmaku_file_record = DanmakuFile(
                    file_name=danmaku_file.filename,
                    file_path=str(saved_path),
                    file_size=len(danmaku_content),
                    source_type=source_type_enum,
                    status=DanmakuFileStatus.UPLOADED,
                    project_id=project_id
                )
                
                db.add(danmaku_file_record)
                db.commit()
                db.refresh(danmaku_file_record)
                
                # 尝试解析弹幕文件
                try:
                    danmaku_list, metadata = DanmakuParser.parse(str(saved_path))
                    
                    danmaku_file_record.status = DanmakuFileStatus.PARSED
                    danmaku_file_record.danmaku_count = len(danmaku_list)
                    
                    # 保存解析后的JSON
                    parsed_json_path = danmaku_dir / f"{file_id}_parsed.json"
                    save_danmaku_to_json(danmaku_list, str(parsed_json_path), metadata)
                    
                    # 更新元数据
                    analysis_metadata = {
                        'parsed_file': str(parsed_json_path),
                        'original_file': str(saved_path),
                        'danmaku_count': len(danmaku_list)
                    }
                    danmaku_file_record.analysis_metadata = analysis_metadata
                    
                    # 更新项目的弹幕路径
                    project.danmaku_path = str(saved_path)
                    
                    db.commit()
                    
                    danmaku_file_info = {
                        "danmaku_file_id": danmaku_file_record.id,
                        "file_name": danmaku_file.filename,
                        "danmaku_count": len(danmaku_list),
                        "status": "parsed"
                    }
                    
                    logger.info(f"弹幕文件解析完成: {len(danmaku_list)} 条弹幕")
                    
                except Exception as e:
                    danmaku_file_record.status = DanmakuFileStatus.FAILED
                    danmaku_file_record.error_message = str(e)
                    db.commit()
                    
                    logger.error(f"弹幕文件解析失败: {e}")
                    
                    danmaku_file_info = {
                        "danmaku_file_id": danmaku_file_record.id,
                        "file_name": danmaku_file.filename,
                        "status": "uploaded",
                        "error": str(e)
                    }
                    
            except Exception as e:
                logger.error(f"处理弹幕文件失败: {e}")
                # 弹幕文件处理失败不影响项目创建
        
        # 确保 project.video_path 的修改被提交（如果还没有被提交）
        # 注意：原始代码注释说"延迟更新项目视频路径，在异步任务中统一提交"
        # 但实际上如果没有弹幕文件，就不会有 commit 操作
        # 所以我们需要确保项目的更改被提交
        if not danmaku_file:
            # 没有弹幕文件时，手动提交项目的更改
            db = project_service.db
            db.commit()
        
        # 缩略图生成移到异步任务中，不阻塞上传响应

        # 启动异步处理任务（AI自动生成字幕和缩略图）
        try:
            from tasks.import_processing import process_import_task

            # 提交异步任务，不提供srt_file_path，让AI自动生成
            celery_task = process_import_task.delay(
                project_id=project_id,
                video_path=str(video_path),
                srt_file_path=None  # AI自动生成字幕
            )

            logger.info(f"项目 {project_id} 异步处理任务已启动，Celery任务ID: {celery_task.id}")

        except Exception as e:
            logger.error(f"启动项目 {project_id} 异步处理失败: {str(e)}", exc_info=True)
            # 更新项目状态为失败，让用户知道需要重试
            project_service.update_project_status(project_id, "failed")
            # 即使异步任务启动失败，也要返回项目创建成功
            # 用户可以通过重试按钮重新启动处理
        
        # 返回项目响应
        response_data = {
            "id": str(project.id),
            "name": str(project.name),
            "description": str(project.description) if project.description else None,
            "project_type": ProjectType(project.project_type.value),
            "status": ProjectStatus(project.status.value),
            "source_url": project.project_metadata.get("source_url") if project.project_metadata else None,
            "source_file": str(project.video_path) if project.video_path else None,
            "video_path": str(video_path),  # 添加video_path字段
            "settings": {
                "video_category": video_category or "knowledge",
                "video_file": video_file.filename
            },  # 只包含可序列化的数据
            "created_at": project.created_at,
            "updated_at": project.updated_at,
            "completed_at": project.completed_at,
            "total_clips": 0,
            "total_tasks": 0
        }
        
        # 缩略图将在异步任务中生成
        response_data["thumbnail"] = None
        
        return ProjectResponse(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/", response_model=ProjectResponse)
async def create_project(
    project_data: ProjectCreate,
    project_service: ProjectService = Depends(get_project_service)
):
    """Create a new project."""
    try:
        project = project_service.create_project(project_data)
        # Convert to response (simplified for now)
        return ProjectResponse(
            id=str(project.id),  # Use actual project ID
            name=str(project.name),
            description=str(project.description) if project.description else None,
            project_type=ProjectType(project.project_type.value),
            status=ProjectStatus(project.status.value),
            source_url=project.project_metadata.get("source_url") if project.project_metadata else None,
            source_file=str(project.video_path) if project.video_path else None,
            settings=project.processing_config or {},
            created_at=project.created_at,
            updated_at=project.updated_at,
            completed_at=project.completed_at,
            total_clips=0,
            total_tasks=0
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=ProjectListResponse)
async def get_projects(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    status: Optional[str] = Query(None, description="Filter by status"),
    project_type: Optional[str] = Query(None, description="Filter by project type"),
    search: Optional[str] = Query(None, description="Search in name and description"),
    project_service: ProjectService = Depends(get_project_service)
):
    """Get paginated projects with optional filtering."""
    try:
        pagination = PaginationParams(page=page, size=size)
        
        filters = None
        if status or project_type or search:
            filters = ProjectFilter(
                status=status,
                project_type=project_type,
                search=search
            )
        
        return project_service.get_projects_paginated(pagination, filters)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    include_clips: bool = Query(False, description="是否包含切片数据"),
    project_service: ProjectService = Depends(get_project_service)
):
    """Get a project by ID."""
    try:
        project = project_service.get_project_with_stats(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # 如果需要包含clips数据，则加载它们
        clips_data = None
        
        if include_clips:
            from services.clip_service import ClipService
            from core.database import SessionLocal
            
            # 获取数据库会话
            db = SessionLocal()
            
            clip_service = ClipService(db)
            clips = clip_service.get_multi(filters={"project_id": project_id})
            # 转换为字典格式
            clips_data = [clip.to_dict() if hasattr(clip, 'to_dict') else clip.__dict__ for clip in clips]
            db.close()
        
        # 创建包含clips的响应数据
        response_data = project.model_dump() if hasattr(project, 'model_dump') else project.__dict__
        if clips_data is not None:
            response_data['clips'] = clips_data
        
        # 返回更新后的响应
        return ProjectResponse(**response_data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    project_data: ProjectUpdate,
    project_service: ProjectService = Depends(get_project_service)
):
    """Update a project."""
    try:
        project = project_service.update_project(project_id, project_data)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Convert to response (simplified)
        return ProjectResponse(
            id=str(project_id),  # Keep as string for UUID
            name=project_data.name or "Updated Project",
            description=project_data.description,
            project_type=ProjectType.DEFAULT,  # Use enum
            status=ProjectStatus.PENDING,  # Use enum
            source_url=None,
            source_file=None,
            settings=project_data.settings or {},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            completed_at=None,
            total_clips=0,

            total_tasks=0
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    project_service: ProjectService = Depends(get_project_service)
):
    """Delete a project and all its related files."""
    try:
        success = project_service.delete_project_with_files(project_id)
        if not success:
            raise HTTPException(status_code=404, detail="Project not found")
        return {"message": "Project and all related files deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sync-all-data")
async def sync_all_projects_data(
    db: Session = Depends(get_db)
):
    """同步所有项目的数据到数据库"""
    try:
        from services.data_sync_service import DataSyncService
        from core.config import get_data_directory
        
        data_dir = get_data_directory()
        sync_service = DataSyncService(db)
        
        result = sync_service.sync_all_projects_from_filesystem(data_dir)
        
        return {
            "message": "数据同步完成",
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"数据同步失败: {str(e)}")


@router.post("/{project_id}/sync-data")
async def sync_project_data(
    project_id: str,
    db: Session = Depends(get_db)
):
    """同步指定项目的数据到数据库"""
    try:
        from services.data_sync_service import DataSyncService
        from core.path_utils import get_project_directory
        
        project_dir = get_project_directory(project_id)
        if not project_dir.exists():
            raise HTTPException(status_code=404, detail="项目目录不存在")
        
        sync_service = DataSyncService(db)
        result = sync_service.sync_project_from_filesystem(project_id, project_dir)
        
        if result.get("success"):
            return {
                "message": "项目数据同步成功",
                "result": result
            }
        else:
            raise HTTPException(status_code=500, detail=f"数据同步失败: {result.get('error')}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"数据同步失败: {str(e)}")


@router.post("/{project_id}/process")
async def start_processing(
    project_id: str,
    project_service: ProjectService = Depends(get_project_service),
    processing_service: ProcessingService = Depends(get_processing_service),
    websocket_service: WebSocketNotificationService = Depends(get_websocket_service)
):
    """Start processing a project using Celery task queue."""
    try:
        # 获取项目信息
        project = project_service.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # 检查项目状态
        if project.status.value not in ["pending", "failed"]:
            raise HTTPException(status_code=400, detail="Project is not in pending or failed status")
        
        # 获取视频和SRT文件路径
        video_path = project.video_path
        srt_path = None
        
        # 从processing_config中获取SRT文件路径
        if project.processing_config and "subtitle_path" in project.processing_config:
            srt_path = project.processing_config["subtitle_path"]
        
        # 验证视频文件存在
        if not video_path or not Path(video_path).exists():
            raise HTTPException(status_code=400, detail=f"Video file not found: {video_path}")
        
        # 如果没有SRT文件路径，尝试自动查找
        if not srt_path:
            video_dir = Path(video_path).parent
            srt_file = video_dir / "input.srt"
            if srt_file.exists():
                srt_path = str(srt_file)
            else:
                # SRT文件是可选的，如果没有找到，设置为None
                srt_path = None
        elif not Path(srt_path).exists():
            # 如果指定的SRT文件不存在，尝试自动查找
            video_dir = Path(video_path).parent
            srt_file = video_dir / "input.srt"
            if srt_file.exists():
                srt_path = str(srt_file)
            else:
                srt_path = None
        
        # 更新项目状态为处理中
        project_service.update_project_status(project_id, "processing")
        
        # 发送WebSocket通知：处理开始
        await websocket_service.send_processing_started(
            project_id=project_id,
            message="开始视频处理流程"
        )
        
        # 提交Celery任务
        celery_task = process_video_pipeline.delay(
            project_id=project_id,
            input_video_path=str(video_path),
            input_srt_path=str(srt_path) if srt_path else None
        )
        
        # 创建处理任务记录
        task_result = processing_service._create_processing_task(
            project_id=project_id,
            task_type="VIDEO_PROCESSING"
        )
        
        return {
            "message": "Processing started successfully",
            "project_id": project_id,
            "task_id": task_result.id,
            "celery_task_id": celery_task.id,
            "status": "processing"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        # 发送错误通知
        try:
            await websocket_service.send_processing_error(
                project_id=int(project_id),
                error=str(e),
                step="initialization"
            )
        except:
            pass
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{project_id}/retry")
async def retry_processing(
    project_id: str,
    project_service: ProjectService = Depends(get_project_service),
    processing_service: ProcessingService = Depends(get_processing_service),
    websocket_service: WebSocketNotificationService = Depends(get_websocket_service)
):
    """Retry processing a project from the beginning."""
    try:
        project = project_service.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        if project.status.value not in ["failed", "completed", "processing", "pending"]:
            raise HTTPException(status_code=400, detail="Project is not in failed, completed, processing, or pending status")
        
        from core.celery_app import celery_app
        from models.task import Task, TaskStatus
        
        active_task = project_service.db.query(Task).filter(
            Task.project_id == project_id,
            Task.status.in_([TaskStatus.PENDING, TaskStatus.RUNNING])
        ).order_by(Task.created_at.desc()).first()
        
        if active_task and project.status.value == "processing":
            logger.info(f"项目 {project_id} 有正在运行的任务 {active_task.id}，将停止该任务")
            try:
                if active_task.celery_task_id:
                    celery_app.control.revoke(active_task.celery_task_id, terminate=True)
                    logger.info(f"已撤销 Celery 任务: {active_task.celery_task_id}")
            except Exception as e:
                logger.warning(f"撤销 Celery 任务失败: {e}")
            
            active_task.status = TaskStatus.CANCELLED
            project_service.db.commit()
        
        from core.path_utils import get_project_directory
        project_dir = get_project_directory(project_id)
        
        dirs_to_clean = [
            project_dir / "output",
            project_dir / "temp",
        ]
        
        cleaned_files = []
        for dir_path in dirs_to_clean:
            if dir_path.exists() and dir_path.is_dir():
                import shutil
                for item in dir_path.iterdir():
                    if item.is_file():
                        try:
                            item.unlink()
                            cleaned_files.append(str(item))
                        except Exception as e:
                            logger.warning(f"清理文件失败 {item}: {e}")
        
        if cleaned_files:
            logger.info(f"项目 {project_id} 清理了 {len(cleaned_files)} 个中间文件")
        
        project_service.update_project_status(project_id, "pending")
        
        from core.path_utils import get_project_raw_directory
        raw_dir = get_project_raw_directory(project_id)
        video_path = raw_dir / "input.mp4"
        srt_path = raw_dir / "input.srt"
        
        if not video_path.exists():
            logger.warning(f"视频文件不存在: {video_path}")
            raise HTTPException(
                status_code=400,
                detail="视频文件不存在，请上传本地视频文件"
            )
        
        srt_path_str = str(srt_path) if srt_path.exists() else None
        
        celery_task = process_video_pipeline.delay(
            project_id=project_id,
            input_video_path=str(video_path),
            input_srt_path=srt_path_str
        )
        
        from models.task import TaskType
        task_result = processing_service._create_processing_task(
            project_id=project_id,
            task_type=TaskType.VIDEO_PROCESSING
        )
        
        task_result.celery_task_id = celery_task.id
        processing_service.db.commit()
        
        return {
            "message": "Processing retry started successfully",
            "project_id": project_id,
            "task_id": task_result.id,
            "celery_task_id": celery_task.id,
            "status": "processing",
            "cleaned_files": len(cleaned_files)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重试处理失败: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{project_id}/retry-step")
async def retry_from_step(
    project_id: str,
    start_step: str = Query(..., description="Starting step (step1_outline, step2_timeline, step3_scoring, step4_recommendation, step5_title, step6_clustering)"),
    clean_output: bool = Query(False, description="Whether to clean output files before retry"),
    project_service: ProjectService = Depends(get_project_service),
    processing_service: ProcessingService = Depends(get_processing_service)
):
    """Retry processing from a specific step. Supports completed projects."""
    try:
        project = project_service.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        valid_steps = ["step1_outline", "step2_timeline", "step3_scoring", "step4_recommendation", "step5_title", "step6_clustering"]
        if start_step not in valid_steps:
            raise HTTPException(status_code=400, detail=f"Invalid step. Valid steps are: {', '.join(valid_steps)}")
        
        from services.config_manager import ProcessingStep
        step_mapping = {
            "step1_outline": ProcessingStep.STEP1_OUTLINE,
            "step2_timeline": ProcessingStep.STEP2_TIMELINE,
            "step3_scoring": ProcessingStep.STEP3_SCORING_ONLY,
            "step4_recommendation": ProcessingStep.STEP4_RECOMMENDATION,
            "step5_title": ProcessingStep.STEP5_TITLE,
            "step6_clustering": ProcessingStep.STEP6_CLUSTERING
        }
        
        processing_step = step_mapping[start_step]
        
        from core.path_utils import get_project_directory
        project_dir = get_project_directory(project_id)
        
        cleaned_files = []
        if clean_output:
            step_output_map = {
                "step1_outline": ["step1_outline.json"],
                "step2_timeline": ["step2_timeline.json"],
                "step3_scoring": ["step3_only_high_score_clips.json", "step3_only_all_scored.json", "step3_only_checkpoint.json"],
                "step4_recommendation": ["step4_with_recommendations.json", "step4_all_recommended.json", "step4_recommendation_checkpoint.json"],
                "step5_title": ["step4_titles.json"],
                "step6_clustering": ["step5_video_output.json", "clips"]
            }
            
            files_to_clean = step_output_map.get(start_step, [])
            metadata_dir = project_dir / "metadata"
            output_dir = project_dir / "output"
            
            for file_name in files_to_clean:
                if file_name == "clips":
                    clips_dir = output_dir / "clips"
                    if clips_dir.exists():
                        import shutil
                        for item in clips_dir.iterdir():
                            if item.is_file():
                                try:
                                    item.unlink()
                                    cleaned_files.append(str(item))
                                except Exception as e:
                                    logger.warning(f"清理文件失败 {item}: {e}")
                else:
                    file_path = metadata_dir / file_name
                    if file_path.exists():
                        try:
                            file_path.unlink()
                            cleaned_files.append(str(file_path))
                        except Exception as e:
                            logger.warning(f"清理文件失败 {file_path}: {e}")
            
            if cleaned_files:
                logger.info(f"项目 {project_id} 清理了 {len(cleaned_files)} 个步骤 {start_step} 的输出文件")
        
        from core.path_utils import get_project_raw_directory
        raw_dir = get_project_raw_directory(project_id)
        srt_path = raw_dir / "input.srt"
        
        srt_path_str = str(srt_path) if srt_path.exists() else None
        
        from tasks.processing import process_from_step
        celery_task = process_from_step.delay(
            project_id=project_id,
            start_step=start_step,
            srt_path=srt_path_str
        )
        
        from models.task import TaskType
        task_result = processing_service._create_processing_task(
            project_id=project_id,
            task_type=TaskType.VIDEO_PROCESSING
        )
        
        task_result.celery_task_id = celery_task.id
        task_result.task_metadata = {"start_step": start_step, "clean_output": clean_output}
        processing_service.db.commit()
        
        project_service.update_project_status(project_id, "processing")
        
        return {
            "message": f"Processing retry from {start_step} started successfully",
            "project_id": project_id,
            "task_id": task_result.id,
            "celery_task_id": celery_task.id,
            "start_step": start_step,
            "status": "processing",
            "cleaned_files": len(cleaned_files)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"从指定步骤重试失败: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{project_id}/steps-status")
async def get_steps_status(
    project_id: str,
    project_service: ProjectService = Depends(get_project_service)
):
    """Get the status of each processing step for a project."""
    try:
        project = project_service.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        from core.path_utils import get_project_directory
        project_dir = get_project_directory(project_id)
        metadata_dir = project_dir / "metadata"
        
        steps_info = [
            {"step": "step1_outline", "name": "大纲提取", "file": "step1_outline.json", "dir": "metadata", "required": True},
            {"step": "step2_timeline", "name": "时间定位", "file": "step2_timeline.json", "dir": "metadata", "required": True},
            {"step": "step3_scoring", "name": "内容评分", "file": "step3_only_high_score_clips.json", "dir": "metadata", "required": True},
            {"step": "step4_recommendation", "name": "推荐理由", "file": "step4_with_recommendations.json", "dir": "metadata", "required": False},
            {"step": "step5_title", "name": "标题生成", "file": "step4_titles.json", "dir": "metadata", "required": True},
            {"step": "step6_clustering", "name": "视频切割", "file": "step5_video_output.json", "dir": "output", "required": True}
        ]
        
        steps_status = []
        for i, step_info in enumerate(steps_info):
            step_dir = project_dir / step_info["dir"]
            file_path = step_dir / step_info["file"]
            is_completed = file_path.exists()
            
            if not is_completed and not step_info.get("required", True):
                later_steps_completed = any(
                    project_dir / steps_info[j]["dir"] / steps_info[j]["file"].exists()
                    for j in range(i + 1, len(steps_info))
                )
                if later_steps_completed:
                    is_completed = True
            
            file_size = 0
            modified_time = None
            if is_completed and file_path.exists():
                import os
                file_stat = file_path.stat()
                file_size = file_stat.st_size
                modified_time = file_stat.st_mtime
            
            steps_status.append({
                "step": step_info["step"],
                "name": step_info["name"],
                "completed": is_completed,
                "file_size": file_size,
                "modified_time": modified_time
            })
        
        clips_dir = project_dir / "output" / "clips"
        clips_count = 0
        if clips_dir.exists():
            clips_count = len(list(clips_dir.glob("*.mp4")))
        
        return {
            "project_id": project_id,
            "project_status": project.status.value,
            "steps": steps_status,
            "clips_count": clips_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取步骤状态失败: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{project_id}/resume")
async def resume_processing(
    project_id: str,
    start_step: str = Form(..., description="Step to resume from (step1_outline, step2_timeline, etc.)"),
    project_service: ProjectService = Depends(get_project_service),
    processing_service: object = Depends(get_processing_service)
):
    """Resume processing from a specific step."""
    try:
        # 获取项目信息
        project = project_service.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # 检查项目状态
        if project.status.value not in ["failed", "processing", "pending"]:
            raise HTTPException(status_code=400, detail="Project is not in failed, processing, or pending status")
        
        # 获取SRT文件路径（如果需要）
        srt_path = None
        if start_step == "step1_outline":
            if project.processing_config and "srt_file" in project.processing_config:
                from pathlib import Path
                from core.config import get_project_root
                project_root = get_project_root() / "data" / "projects" / project_id
                srt_path = project_root / "raw" / project.processing_config["srt_file"]
            
            if not srt_path or not srt_path.exists():
                raise HTTPException(status_code=400, detail=f"SRT file not found: {srt_path}")
        
        # 调用处理服务恢复执行
        result = processing_service.resume_processing(project_id, start_step, srt_path)
        
        return {
            "message": f"Processing resumed from {start_step} successfully",
            "project_id": project_id,
            "start_step": start_step,
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{project_id}/status")
async def get_processing_status(
    project_id: str,
    project_service: ProjectService = Depends(get_project_service),
    processing_service: object = Depends(get_processing_service)
):
    """Get processing status of a project."""
    import sys
    print(f"DEBUG ENTRY get_processing_status: project_id = {project_id}", file=sys.stderr, flush=True)
    try:
        print(f"DEBUG: processing_service = {processing_service}, type = {type(processing_service)}", file=sys.stderr, flush=True)

        project = project_service.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        tasks = project.tasks if hasattr(project, 'tasks') else []
        latest_task = None
        if tasks:
            latest_task = max(tasks, key=lambda t: t.created_at) if hasattr(tasks[0], 'created_at') else tasks[0]
        
        if not latest_task:
            return {
                "status": "pending",
                "current_step": 0,
                "total_steps": 6,
                "step_name": "等待开始",
                "progress": 0,
                "error_message": None
            }
        
        from services.simple_progress import get_progress_snapshot, STAGE_NAMES
        
        redis_progress = get_progress_snapshot(project_id)
        
        if redis_progress:
            stage = redis_progress.get("stage", "")
            progress = redis_progress.get("percent", 0)
            message = redis_progress.get("message", "")
            estimated_remaining = redis_progress.get("estimated_remaining")
            
            stage_to_step_map = {
                "INGEST": 0,
                "SUBTITLE": 1,
                "ANALYZE": 2,
                "HIGHLIGHT": 3,
                "EXPORT": 4,
                "DONE": 5
            }
            current_step = stage_to_step_map.get(stage, 0)
            
            step_name = STAGE_NAMES.get(stage, stage)
            
            task_status = latest_task.status.value if hasattr(latest_task.status, 'value') else str(latest_task.status)
            if stage == "DONE" and progress >= 100:
                task_status = "completed"
            elif progress > 0:
                task_status = "processing"
            
            return {
                "status": task_status,
                "current_step": current_step,
                "total_steps": 6,
                "step_name": step_name,
                "progress": progress,
                "message": message,
                "estimated_remaining": estimated_remaining,
                "error_message": latest_task.error_message if hasattr(latest_task, 'error_message') else None
            }
        
        print(f"DEBUG: 调用 get_processing_status, 参数: project_id={project_id}", file=sys.stderr)
        status = processing_service.get_processing_status(project_id)
        print(f"DEBUG: get_processing_status 返回成功", file=sys.stderr)

        return status
    except Exception as e:
        import traceback
        error_msg = f"ERROR in get_processing_status: {e}\n{traceback.format_exc()}"
        print(error_msg, file=sys.stderr)
        logger.error(error_msg)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{project_id}/logs")
async def get_project_logs(
    project_id: str,
    lines: int = Query(50, ge=1, le=1000, description="Number of log lines to return"),
    project_service: ProjectService = Depends(get_project_service)
):
    """Get project logs."""
    try:
        # 模拟日志数据，实际应该从日志服务获取
        return {
            "logs": [
                {
                    "timestamp": "2025-08-01T13:30:00.000Z",
                    "module": "processing",
                    "level": "INFO",
                    "message": "开始处理项目"
                },
                {
                    "timestamp": "2025-08-01T13:30:05.000Z",
                    "module": "processing",
                    "level": "INFO",
                    "message": "Step 1: 提取大纲完成"
                },
                {
                    "timestamp": "2025-08-01T13:30:10.000Z",
                    "module": "processing",
                    "level": "INFO",
                    "message": "Step 2: 时间定位完成"
                },
                {
                    "timestamp": "2025-08-01T13:30:15.000Z",
                    "module": "processing",
                    "level": "INFO",
                    "message": "Step 3: 内容评分进行中..."
                }
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) 


@router.get("/{project_id}/import-status")
async def get_import_status(
    project_id: str,
    project_service: ProjectService = Depends(get_project_service)
):
    """获取项目导入状态"""
    try:
        # 获取项目信息
        project = project_service.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # 检查是否有正在进行的导入任务
        from core.celery_app import celery_app
        
        # 这里可以添加更复杂的任务状态检查逻辑
        # 目前简单返回项目状态
        return {
            "project_id": project_id,
            "status": project.status.value,
            "message": "导入状态正常"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取导入状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取导入状态失败: {str(e)}")


@router.post("/{project_id}/generate-thumbnail")
async def generate_project_thumbnail(
    project_id: str,
    project_service: ProjectService = Depends(get_project_service)
):
    """为项目生成缩略图"""
    try:
        # 获取项目信息
        project = project_service.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # 检查是否有视频文件
        if not project.video_path:
            raise HTTPException(status_code=400, detail="Project has no video file")
        
        # 检查视频文件是否存在
        video_path = Path(project.video_path)
        if not video_path.exists():
            raise HTTPException(status_code=400, detail="Video file not found")
        
        # 生成缩略图
        from utils.thumbnail_generator import generate_project_thumbnail
        thumbnail_data = generate_project_thumbnail(project_id, video_path)
        
        if thumbnail_data:
            # 保存缩略图到数据库
            project.thumbnail = thumbnail_data
            project_service.db.commit()
            
            return {
                "success": True,
                "thumbnail": thumbnail_data,
                "message": "缩略图生成并保存成功"
            }
        else:
            raise HTTPException(status_code=500, detail="缩略图生成失败")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成项目缩略图失败: {e}")
        raise HTTPException(status_code=500, detail=f"生成缩略图失败: {str(e)}")





@router.get("/{project_id}/clips/{clip_id}")
async def get_project_clip(
    project_id: str,
    clip_id: str,
    project_service: ProjectService = Depends(get_project_service)
):
    """Get a specific clip video file for a project."""
    try:
        from pathlib import Path
        import os
        
        # 构建视频文件路径 - 使用正确的项目目录路径
        from core.path_utils import get_project_directory
        project_dir = get_project_directory(project_id)
        clips_dir = project_dir / "output" / "clips"
        
        # 确保路径存在
        if not clips_dir.exists():
            raise HTTPException(status_code=404, detail=f"Clips directory not found: {clips_dir}")
        
        # 查找对应的视频文件
        # 首先尝试通过新格式 clip_{clip_id}.mp4 查找
        video_files = list(clips_dir.glob(f"clip_{clip_id}.mp4"))
        
        # 如果没找到新格式，尝试查找旧格式 {clip_id}_*.mp4
        if not video_files:
            video_files = list(clips_dir.glob(f"{clip_id}_*.mp4"))
        
        # 如果没找到，尝试查找所有mp4文件，然后通过数据库匹配
        if not video_files:
            from models.clip import Clip
            clip = project_service.db.query(Clip).filter(Clip.id == clip_id).first()
            if clip and clip.video_path:
                video_file_path = Path(clip.video_path)
                if video_file_path.exists():
                    video_file = video_file_path
                else:
                    raise HTTPException(status_code=404, detail=f"Clip video file not found for clip_id: {clip_id}")
            else:
                raise HTTPException(status_code=404, detail=f"Clip not found in database: {clip_id}")
        else:
            video_file = video_files[0]
        
        # 检查文件是否存在
        if not video_file.exists():
            raise HTTPException(status_code=404, detail="Clip video file not found")
        
        # 返回文件流
        from fastapi.responses import FileResponse
        return FileResponse(
            path=str(video_file),
            media_type="video/mp4",
            filename=video_file.name
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sync-all")
async def sync_all_projects_from_filesystem(
    db: Session = Depends(get_db)
):
    """从文件系统同步所有项目数据到数据库"""
    try:
        from services.data_sync_service import DataSyncService
        from core.config import get_data_directory
        
        # 获取数据目录
        data_dir = get_data_directory()
        
        # 创建数据同步服务
        sync_service = DataSyncService(db)
        
        # 同步所有项目
        result = sync_service.sync_all_projects_from_filesystem(data_dir)
        
        return {
            "success": result.get("success", False),
            "message": "数据同步完成",
            "synced_projects": result.get("synced_projects", []),
            "failed_projects": result.get("failed_projects", []),
            "total_synced": len(result.get("synced_projects", [])),
            "total_failed": len(result.get("failed_projects", []))
        }
        
    except Exception as e:
        logger.error(f"同步所有项目数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"同步失败: {str(e)}")





@router.post("/sync/{project_id}")
async def sync_project_from_filesystem(
    project_id: str,
    db: Session = Depends(get_db)
):
    """从文件系统同步指定项目数据到数据库"""
    try:
        from services.data_sync_service import DataSyncService
        from core.config import get_data_directory
        
        # 获取数据目录
        data_dir = get_data_directory()
        project_dir = data_dir / "projects" / project_id
        
        if not project_dir.exists():
            raise HTTPException(status_code=404, detail=f"项目目录不存在: {project_id}")
        
        # 创建数据同步服务
        sync_service = DataSyncService(db)
        
        # 同步项目数据
        result = sync_service.sync_project_from_filesystem(project_id, project_dir)
        
        return {
            "success": result.get("success", False),
            "project_id": project_id,
            "clips_synced": result.get("clips_synced", 0),

            "message": f"项目 {project_id} 同步完成"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"同步项目 {project_id} 数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"同步失败: {str(e)}")





@router.get("/{project_id}/files/{filename}")
async def get_project_file(
    project_id: str,
    filename: str,
    db: Session = Depends(get_db),
    project_service: ProjectService = Depends(get_project_service)
):
    """获取项目原始文件（支持前端播放视频文件）"""
    try:
        from fastapi.responses import FileResponse
        from pathlib import Path

        # 验证项目是否存在
        project = project_service.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 获取项目原始文件目录
        from core.path_utils import get_project_raw_directory
        raw_dir = get_project_raw_directory(project_id)

        # 构建可能的文件路径列表，按优先级排序
        possible_paths = []
        
        # 1. 直接使用filename作为完整路径（向后兼容）
        possible_paths.append(raw_dir / filename)
        
        # 2. 如果filename包含子目录，尝试提取文件名并直接在raw目录查找
        # 例如：filename="input/input.mp4"，尝试raw_dir / "input.mp4"
        if '/' in filename or '\\' in filename:
            # 提取最后一部分作为文件名
            clean_filename = Path(filename).name
            possible_paths.append(raw_dir / clean_filename)
        
        # 3. 尝试使用项目视频路径
        if project.video_path:
            possible_paths.append(Path(project.video_path))
        
        # 查找第一个存在的文件
        file_path = None
        for path in possible_paths:
            if path.exists() and path.is_file():
                file_path = path
                logger.info(f"找到文件: {file_path}")
                break
        
        if not file_path:
            logger.error(f"文件不存在，尝试的路径: {[str(p) for p in possible_paths]}")
            raise HTTPException(status_code=404, detail="文件不存在")

        # 根据文件扩展名确定媒体类型
        media_type = "application/octet-stream"
        if filename.lower().endswith('.mp4'):
            media_type = "video/mp4"
        elif filename.lower().endswith('.webm'):
            media_type = "video/webm"
        elif filename.lower().endswith('.avi'):
            media_type = "video/x-msvideo"
        elif filename.lower().endswith('.mov'):
            media_type = "video/quicktime"
        elif filename.lower().endswith('.mkv'):
            media_type = "video/x-matroska"
        elif filename.lower().endswith('.srt'):
            media_type = "text/plain"
        elif filename.lower().endswith('.vtt'):
            media_type = "text/vtt"

        # 返回文件，支持在线播放
        return FileResponse(
            path=str(file_path),
            filename=filename,
            media_type=media_type,
            headers={
                "Accept-Ranges": "bytes",  # 支持范围请求，便于视频播放
                "Cache-Control": "public, max-age=3600"  # 缓存1小时
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取项目文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取项目文件失败: {str(e)}")


@router.get("/{project_id}/download")
async def download_project_file(
    project_id: str,
    clip_id: str = Query(..., description="下载指定切片"),
    db: Session = Depends(get_db),
    project_service: ProjectService = Depends(get_project_service)
):
    """下载项目切片文件"""
    try:
        from fastapi.responses import FileResponse
        from pathlib import Path
        
        # 验证项目是否存在
        project = project_service.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")
        
        # 下载切片视频
        from models.clip import Clip
        clip = db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            raise HTTPException(status_code=404, detail="切片不存在")
        
        if not clip.video_path:
            raise HTTPException(status_code=404, detail="切片视频文件不存在")
        
        file_path = Path(clip.video_path)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="切片视频文件不存在")
        
        # 生成下载文件名
        clip_title = clip.title or f"clip_{clip_id}"
        from utils.video_processor import VideoProcessor
        safe_name = VideoProcessor.sanitize_filename(clip_title)
        filename = f"{safe_name}.mp4"
        
        # 对文件名进行URL编码
        import urllib.parse
        encoded_filename = urllib.parse.quote(filename.encode('utf-8'))
        
        return FileResponse(
            path=str(file_path),
            filename=filename,
            media_type="video/mp4",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"下载文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"下载文件失败: {str(e)}")


