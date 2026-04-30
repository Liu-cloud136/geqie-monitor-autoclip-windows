"""
文件管理API
提供文件上传、下载和访问功能
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pathlib import Path
import shutil
import uuid

from core.database import get_db
from services.unified_storage_service import UnifiedStorageService
from models.project import Project
from models.clip import Clip


logger = logging.getLogger(__name__)


class FileUploadHandler:
    """流式文件上传处理器"""

    # 使用统一的配置
    try:
        from config.upload_config import UPLOAD_CHUNK_SIZE, MAX_FILE_SIZE
        CHUNK_SIZE = UPLOAD_CHUNK_SIZE
        MAX_FILE_SIZE = MAX_FILE_SIZE
    except ImportError:
        CHUNK_SIZE = 16 * 1024 * 1024  # 16MB chunks - 默认值
        MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB - 默认值

    @staticmethod
    async def save_uploaded_file(
        upload_file: UploadFile,
        target_path: Path
    ) -> dict:
        """
        流式保存上传的文件

        Args:
            upload_file: FastAPI UploadFile 对象
            target_path: 目标文件路径

        Returns:
            dict: 包含文件信息的字典
        """
        file_size = 0
        target_path.parent.mkdir(parents=True, exist_ok=True)

        with open(target_path, "wb") as f:
            while True:
                chunk = await upload_file.read(FileUploadHandler.CHUNK_SIZE)
                if not chunk:
                    break

                file_size += len(chunk)

                # 检查文件大小限制
                if file_size > FileUploadHandler.MAX_FILE_SIZE:
                    f.close()
                    target_path.unlink()  # 删除部分上传的文件
                    raise ValueError(
                        f"文件大小超过限制: "
                        f"{FileUploadHandler.MAX_FILE_SIZE / (1024**3):.1f}GB"
                    )

                f.write(chunk)

        return {
            "path": str(target_path),
            "size": file_size,
            "name": upload_file.filename
        }

router = APIRouter(prefix="/files", tags=["文件管理"])

@router.post("/upload")
async def upload_files(
    files: List[UploadFile] = File(...),
    project_id: str = Query(..., description="项目ID"),
    db: Session = Depends(get_db)
):
    """
    上传文件（优化存储模式）
    
    - 保存文件到文件系统
    - 更新数据库中的文件路径
    - 不存储文件内容到数据库
    """
    try:
        # 验证项目是否存在
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")
        
        # 初始化存储服务
        storage_service = UnifiedStorageService(db, project_id)
        
        uploaded_files = []
        
        for file in files:
            # 生成唯一文件名
            file_id = str(uuid.uuid4())
            file_extension = Path(file.filename).suffix if file.filename else ""
            safe_filename = f"{file_id}{file_extension}"

            # 确定文件类型
            file_type = "raw"  # 默认为原始文件
            if file.filename:
                if file.filename.lower().endswith(('.srt', '.vtt')):
                    file_type = "subtitle"
                elif file.filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
                    file_type = "video"

            # 使用流式上传保存文件
            temp_path = Path(f"/tmp/{safe_filename}")
            try:
                file_info = await FileUploadHandler.save_uploaded_file(file, temp_path)

                # 使用存储服务保存文件
                saved_path = storage_service.save_project_file(temp_path, file_type)

                # 更新项目数据库记录
                if file_type == "video":
                    project.video_path = saved_path
                elif file_type == "subtitle":
                    project.subtitle_path = saved_path

                uploaded_files.append({
                    "original_name": file.filename,
                    "saved_path": saved_path,
                    "file_type": file_type,
                    "file_size": file_info["size"]
                })

            finally:
                # 清理临时文件
                if temp_path.exists():
                    temp_path.unlink()
        
        # 提交数据库更改
        db.commit()
        
        logger.info(f"项目 {project_id} 上传了 {len(uploaded_files)} 个文件")
        
        return {
            "success": True,
            "project_id": project_id,
            "uploaded_files": uploaded_files,
            "message": f"成功上传 {len(uploaded_files)} 个文件"
        }
        
    except ValueError as e:
        logger.error(f"文件大小超过限制: {e}")
        raise HTTPException(status_code=413, detail=str(e))
    except Exception as e:
        logger.error(f"文件上传失败: {e}")
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")

@router.get("/clips/{clip_id}/content")
async def get_clip_content(
    clip_id: str,
    db: Session = Depends(get_db)
):
    """
    获取切片完整内容
    
    - 从数据库获取元数据
    - 从文件系统获取完整数据
    """
    try:
        # 获取切片记录
        clip = db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            raise HTTPException(status_code=404, detail="切片不存在")
        
        # 从文件系统获取完整内容
        from repositories.clip_repository import ClipRepository
        clip_repo = ClipRepository(db)
        content = clip_repo.get_clip_content(clip_id)
        
        if not content:
            raise HTTPException(status_code=404, detail="切片内容不存在")
        
        return {
            "clip_id": clip_id,
            "content": content,
            "metadata": {
                "title": clip.title,
                "duration": clip.duration,
                "score": clip.score,
                "video_path": clip.video_path
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取切片内容失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取切片内容失败: {str(e)}")



@router.get("/clips/{clip_id}/download")
async def download_clip_file(
    clip_id: str,
    db: Session = Depends(get_db)
):
    """
    下载切片文件
    
    - 从数据库获取文件路径
    - 返回文件流
    """
    try:
        # 获取切片记录
        clip = db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            raise HTTPException(status_code=404, detail="切片不存在")
        
        if not clip.video_path:
            raise HTTPException(status_code=404, detail="切片文件不存在")
        
        file_path = Path(clip.video_path)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="切片文件不存在")
        
        return FileResponse(
            path=str(file_path),
            filename=f"clip_{clip_id}.mp4",
            media_type="video/mp4",
            headers={
                "Accept-Ranges": "bytes",  # 支持范围请求，加速下载
                "Cache-Control": "public, max-age=86400",  # 缓存24小时
                "Content-Length": str(file_path.stat().st_size),  # 提供文件大小
                "X-Accel-Buffering": "no"  # 禁用缓冲，直接流式传输
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"下载切片文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"下载切片文件失败: {str(e)}")

@router.get("/projects/{project_id}/files/{filename}")
async def get_project_file(
    project_id: str,
    filename: str,
    db: Session = Depends(get_db)
):
    """
    获取项目原始文件（支持前端播放视频文件）
    
    - 支持按项目ID和文件名获取原始文件
    - 返回文件流，支持在线播放
    """
    try:
        # 验证项目是否存在
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 获取项目原始文件目录
        from core.path_utils import get_project_raw_directory
        raw_dir = get_project_raw_directory(project_id)

        # 尝试查找文件
        file_path = raw_dir / filename
        if not file_path.exists():
            # 尝试使用项目视频路径
            if project.video_path and Path(project.video_path).exists():
                file_path = Path(project.video_path)
            else:
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

@router.get("/projects/{project_id}/clips/{clip_id}")
async def get_project_clip_video(
    project_id: str,
    clip_id: str,
    db: Session = Depends(get_db)
):
    """
    获取项目切片视频（支持前端播放）

    - 支持按项目ID和切片ID获取视频
    - 返回视频文件流，支持在线播放
    """
    try:
        # 验证项目是否存在
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 获取切片记录
        clip = db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            raise HTTPException(status_code=404, detail="切片不存在")

        # 验证切片是否属于该项目
        if clip.project_id != project_id:
            raise HTTPException(status_code=403, detail="切片不属于该项目")

        if not clip.video_path:
            logger.error(f"切片 {clip_id} 的 video_path 为空")
            raise HTTPException(status_code=404, detail="切片文件不存在")

        file_path = Path(clip.video_path)
        logger.info(f"尝试获取切片视频文件: {file_path}, exists: {file_path.exists()}, is_file: {file_path.is_file()}")

        if not file_path.exists():
            logger.error(f"切片视频文件不存在: {file_path}")
            raise HTTPException(status_code=404, detail="切片文件不存在")

        # 返回视频文件，支持在线播放
        return FileResponse(
            path=str(file_path),
            filename=f"clip_{clip_id}.mp4",
            media_type="video/mp4",
            headers={
                "Accept-Ranges": "bytes",  # 支持范围请求，便于视频播放
                "Cache-Control": "public, max-age=86400",  # 缓存24小时
                "Content-Disposition": f'inline; filename="clip_{clip_id}.mp4"',  # 支持在线播放
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取项目切片视频失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取项目切片视频失败: {str(e)}")





@router.get("/projects/{project_id}/storage-info")
async def get_project_storage_info(
    project_id: str,
    db: Session = Depends(get_db)
):
    """
    获取项目存储信息
    
    - 统计文件数量和大小
    - 显示存储使用情况
    """
    try:
        # 验证项目是否存在
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")
        
        # 获取存储信息
        storage_service = UnifiedStorageService(db, project_id)
        storage_info = storage_service.get_project_storage_info()
        
        return {
            "project_id": project_id,
            "storage_info": storage_info,
            "file_paths": {
                "video_path": project.video_path,
                "subtitle_path": project.subtitle_path
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取项目存储信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取项目存储信息失败: {str(e)}")

@router.delete("/projects/{project_id}/cleanup")
async def cleanup_project_files(
    project_id: str,
    keep_days: int = Query(30, description="保留天数"),
    db: Session = Depends(get_db)
):
    """
    清理项目旧文件
    
    - 清理超过指定天数的临时文件
    - 释放存储空间
    """
    try:
        # 验证项目是否存在
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")
        
        # 清理旧文件
        storage_service = UnifiedStorageService(db, project_id)
        storage_service.cleanup_old_files(keep_days)
        
        return {
            "success": True,
            "project_id": project_id,
            "keep_days": keep_days,
            "message": f"项目 {project_id} 旧文件清理完成"
        }
        
    except Exception as e:
        logger.error(f"清理项目文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"清理项目文件失败: {str(e)}")
