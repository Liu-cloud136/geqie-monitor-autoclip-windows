"""
处理API路由
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from core.database import get_db
from services.unified_processing_service import UnifiedProcessingService
from dependency_injector.wiring import inject, Provide
from services.service_container import ServiceContainer

router = APIRouter()


@inject
def get_processing_service(
    db: Session = Depends(get_db),
    processing_service: UnifiedProcessingService = Depends(Provide[ServiceContainer.unified_processing_service])
) -> UnifiedProcessingService:
    """Dependency to get processing service from container."""
    return processing_service


@router.post("/projects/{project_id}/process")
async def process_project(
    project_id: str,
    processing_service: UnifiedProcessingService = Depends(get_processing_service)
) -> Dict[str, Any]:
    """开始处理项目"""
    try:
        result = processing_service.process_project(project_id)
        return {
            "message": "项目处理已开始",
            "project_id": project_id,
            "result": result
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=f"缺少必要文件: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")


@router.get("/projects/{project_id}/processing-status")
async def get_processing_status(
    project_id: str,
    processing_service: UnifiedProcessingService = Depends(get_processing_service)
) -> Dict[str, Any]:
    """获取项目处理状态"""
    try:
        status = processing_service.get_processing_status(project_id)
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取状态失败: {str(e)}")


@router.post("/projects/{project_id}/process/step/{step_number}")
async def process_step(
    project_id: str,
    step_number: int,
    processing_service: UnifiedProcessingService = Depends(get_processing_service)
) -> Dict[str, Any]:
    """处理单个步骤"""
    if step_number < 1 or step_number > 6:
        raise HTTPException(status_code=400, detail="步骤编号必须在1-6之间")
    
    try:
        # 映射步骤编号到ProcessingStep枚举
        step_mapping = {
            1: ProcessingStep.STEP1_OUTLINE,
            2: ProcessingStep.STEP2_TIMELINE,
            3: ProcessingStep.STEP3_SCORING_ONLY,
            4: ProcessingStep.STEP4_RECOMMENDATION,
            5: ProcessingStep.STEP5_TITLE,
            6: ProcessingStep.STEP6_CLUSTERING
        }
        
        step = step_mapping.get(step_number)
        if not step:
            raise HTTPException(status_code=400, detail="无效的步骤编号")
        
        # 执行单个步骤
        result = processing_service.execute_single_step(project_id, step)
        return {
            "message": f"步骤 {step_number} 处理完成",
            "project_id": project_id,
            "step": step_number,
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"步骤处理失败: {str(e)}")