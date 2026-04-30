"""
切片缩略图 API 端点
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pathlib import Path

from core.database import get_db
from models.clip import Clip


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["文件管理"])


@router.get("/projects/{project_id}/clips/{clip_id}/thumbnail")
async def get_project_clip_thumbnail(
    project_id: str,
    clip_id: str,
    db: Session = Depends(get_db)
):
    """
    获取项目切片缩略图

    - 支持按项目ID和切片ID获取缩略图
    - 如果缩略图不存在，返回404
    """
    try:
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

        video_path = Path(clip.video_path)
        # 缩略图文件名规则：{video_name}_thumbnail.jpg
        thumbnail_path = video_path.parent / f"{video_path.stem}_thumbnail.jpg"

        if not thumbnail_path.exists():
            logger.warning(f"切片缩略图不存在: {thumbnail_path}")
            raise HTTPException(status_code=404, detail="切片缩略图不存在")

        # 返回缩略图文件
        return FileResponse(
            path=str(thumbnail_path),
            filename=f"clip_{clip_id}_thumbnail.jpg",
            media_type="image/jpeg",
            headers={
                "Cache-Control": "public, max-age=86400"  # 缓存24小时
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取项目切片缩略图失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取项目切片缩略图失败: {str(e)}")
