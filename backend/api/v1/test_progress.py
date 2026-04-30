"""测试进度API端点"""
from fastapi import APIRouter, HTTPException
from services.simple_progress import emit_progress
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/projects/{project_id}/trigger-progress")
async def trigger_progress(project_id: str, stage: str = "TEST", percent: int = 50, message: str = "测试进度"):
    """触发进度更新（用于测试）"""
    try:
        logger.info(f"触发进度更新: {project_id} - {stage} ({percent}%)")
        emit_progress(project_id, stage, message, percent)
        return {"success": True, "project_id": project_id, "stage": stage, "percent": percent}
    except Exception as e:
        logger.error(f"触发进度失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
