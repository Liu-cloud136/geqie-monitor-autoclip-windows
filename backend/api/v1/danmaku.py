"""
弹幕文件管理 API
提供弹幕文件上传、解析、分析功能
"""

import logging
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pathlib import Path
import json

from core.database import get_db
from models.project import Project
from models.danmaku import DanmakuFile, DanmakuFileStatus, DanmakuSourceType
from utils.danmaku_parser import DanmakuParser, save_danmaku_to_json
from utils.danmaku_analyzer import DanmakuAnalyzer, save_analysis_result, load_analysis_result
from core.unified_config import get_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/danmaku", tags=["弹幕管理"])


def get_danmaku_storage_path() -> Path:
    """获取弹幕文件存储目录"""
    config = get_config()
    danmaku_dir = config.paths.data_dir / "danmaku"
    danmaku_dir.mkdir(parents=True, exist_ok=True)
    return danmaku_dir


@router.post("/upload")
async def upload_danmaku_file(
    file: UploadFile = File(..., description="弹幕文件"),
    project_id: Optional[str] = Query(None, description="关联项目ID（可选）"),
    source_type: str = Query("bilibili", description="弹幕来源类型: bilibili, youtube, douyu, huya, custom"),
    db: Session = Depends(get_db)
):
    """
    上传弹幕文件
    
    - 支持 XML（B站）、JSON、ASS 格式
    - 自动解析弹幕内容
    - 可选关联到项目
    """
    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail="文件名不能为空")
        
        file_ext = Path(file.filename).suffix.lower()
        allowed_extensions = ['.xml', '.json', '.ass', '.txt']
        
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"不支持的文件格式。支持的格式: {', '.join(allowed_extensions)}"
            )
        
        project = None
        if project_id:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise HTTPException(status_code=404, detail="项目不存在")
        
        storage_dir = get_danmaku_storage_path()
        file_id = str(uuid.uuid4())
        safe_filename = f"{file_id}{file_ext}"
        saved_path = storage_dir / safe_filename
        
        file_content = await file.read()
        saved_path.write_bytes(file_content)
        
        try:
            source_type_enum = DanmakuSourceType(source_type.lower())
        except ValueError:
            source_type_enum = DanmakuSourceType.BILIBILI
        
        danmaku_file = DanmakuFile(
            file_name=file.filename,
            file_path=str(saved_path),
            file_size=len(file_content),
            source_type=source_type_enum,
            status=DanmakuFileStatus.UPLOADED,
            project_id=project_id
        )
        
        db.add(danmaku_file)
        db.commit()
        db.refresh(danmaku_file)
        
        logger.info(f"弹幕文件已上传: {file.filename} -> {saved_path}")
        
        try:
            danmaku_list, metadata = DanmakuParser.parse(str(saved_path))
            
            danmaku_file.status = DanmakuFileStatus.PARSED
            danmaku_file.danmaku_count = len(danmaku_list)
            
            if project and project.video_duration:
                danmaku_file.video_duration = project.video_duration
            
            parsed_json_path = storage_dir / f"{file_id}_parsed.json"
            save_danmaku_to_json(danmaku_list, str(parsed_json_path), metadata)
            
            analysis_metadata = {
                'parsed_file': str(parsed_json_path),
                'original_file': str(saved_path),
                'danmaku_count': len(danmaku_list)
            }
            danmaku_file.analysis_metadata = analysis_metadata
            
            db.commit()
            
            logger.info(f"弹幕文件解析完成: {len(danmaku_list)} 条弹幕")
            
            return {
                "success": True,
                "danmaku_file_id": danmaku_file.id,
                "file_name": file.filename,
                "danmaku_count": len(danmaku_list),
                "status": "parsed",
                "message": f"弹幕文件上传成功，共解析 {len(danmaku_list)} 条弹幕"
            }
            
        except Exception as e:
            danmaku_file.status = DanmakuFileStatus.FAILED
            danmaku_file.error_message = str(e)
            db.commit()
            
            logger.error(f"弹幕文件解析失败: {e}")
            
            return {
                "success": True,
                "danmaku_file_id": danmaku_file.id,
                "file_name": file.filename,
                "status": "uploaded",
                "message": f"文件已上传，但解析失败: {str(e)}。您可以稍后手动触发解析。"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"上传弹幕文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@router.post("/parse/{danmaku_file_id}")
async def parse_danmaku_file(
    danmaku_file_id: str,
    db: Session = Depends(get_db)
):
    """
    手动触发弹幕文件解析
    """
    try:
        danmaku_file = db.query(DanmakuFile).filter(DanmakuFile.id == danmaku_file_id).first()
        if not danmaku_file:
            raise HTTPException(status_code=404, detail="弹幕文件不存在")
        
        if danmaku_file.status == DanmakuFileStatus.PARSED or danmaku_file.status == DanmakuFileStatus.ANALYZED:
            return {
                "success": True,
                "danmaku_file_id": danmaku_file_id,
                "status": danmaku_file.status.value,
                "danmaku_count": danmaku_file.danmaku_count,
                "message": "弹幕文件已经解析过了"
            }
        
        danmaku_file.status = DanmakuFileStatus.PARSING
        db.commit()
        
        try:
            danmaku_list, metadata = DanmakuParser.parse(danmaku_file.file_path)
            
            danmaku_file.status = DanmakuFileStatus.PARSED
            danmaku_file.danmaku_count = len(danmaku_list)
            
            storage_dir = get_danmaku_storage_path()
            file_id = Path(danmaku_file.file_path).stem
            parsed_json_path = storage_dir / f"{file_id}_parsed.json"
            save_danmaku_to_json(danmaku_list, str(parsed_json_path), metadata)
            
            if danmaku_file.analysis_metadata is None:
                danmaku_file.analysis_metadata = {}
            danmaku_file.analysis_metadata['parsed_file'] = str(parsed_json_path)
            
            db.commit()
            
            return {
                "success": True,
                "danmaku_file_id": danmaku_file_id,
                "danmaku_count": len(danmaku_list),
                "status": "parsed",
                "message": f"解析成功，共 {len(danmaku_list)} 条弹幕"
            }
            
        except Exception as e:
            danmaku_file.status = DanmakuFileStatus.FAILED
            danmaku_file.error_message = str(e)
            db.commit()
            
            raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"解析弹幕文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")


@router.post("/analyze/{danmaku_file_id}")
async def analyze_danmaku_file(
    danmaku_file_id: str,
    window_seconds: float = Query(10.0, description="滑动窗口大小（秒）"),
    slide_seconds: float = Query(5.0, description="滑动步长（秒）"),
    db: Session = Depends(get_db)
):
    """
    分析弹幕文件，生成热度图、关键词、情感分析等
    
    分析结果包括：
    - 弹幕热度点（高弹幕密度时间段）
    - 关键词统计
    - 情感分析
    - 特殊弹幕识别（高能预警、前方高能等）
    """
    try:
        danmaku_file = db.query(DanmakuFile).filter(DanmakuFile.id == danmaku_file_id).first()
        if not danmaku_file:
            raise HTTPException(status_code=404, detail="弹幕文件不存在")
        
        if danmaku_file.status != DanmakuFileStatus.PARSED and danmaku_file.status != DanmakuFileStatus.ANALYZED:
            raise HTTPException(status_code=400, detail="弹幕文件尚未解析，请先解析")
        
        if danmaku_file.status == DanmakuFileStatus.ANALYZED:
            return {
                "success": True,
                "danmaku_file_id": danmaku_file_id,
                "status": "analyzed",
                "message": "弹幕文件已经分析过了",
                "heat_points_count": len(danmaku_file.analysis_metadata.get('heat_points', [])) if danmaku_file.analysis_metadata else 0
            }
        
        danmaku_file.status = DanmakuFileStatus.ANALYZING
        db.commit()
        
        try:
            storage_dir = get_danmaku_storage_path()
            file_id = Path(danmaku_file.file_path).stem
            parsed_json_path = storage_dir / f"{file_id}_parsed.json"
            
            if not parsed_json_path.exists():
                if danmaku_file.analysis_metadata and 'parsed_file' in danmaku_file.analysis_metadata:
                    parsed_json_path = Path(danmaku_file.analysis_metadata['parsed_file'])
                else:
                    raise HTTPException(status_code=404, detail="解析后的弹幕文件不存在")
            
            with open(parsed_json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            from utils.danmaku_parser import Danmaku
            danmaku_list = []
            for item in data.get('danmaku', []):
                danmaku = Danmaku(**item)
                danmaku_list.append(danmaku)
            
            analyzer = DanmakuAnalyzer(window_seconds=window_seconds, slide_seconds=slide_seconds)
            
            video_duration = danmaku_file.video_duration
            if not video_duration and danmaku_list:
                video_duration = max(d.timestamp for d in danmaku_list) + 10.0
            
            analysis_result = analyzer.analyze(danmaku_list, video_duration)
            
            analysis_json_path = storage_dir / f"{file_id}_analysis.json"
            save_analysis_result(analysis_result, str(analysis_json_path))
            
            heat_points_summary = []
            for hp in analysis_result.heat_points[:20]:
                heat_points_summary.append({
                    'start_time': hp.start_time,
                    'end_time': hp.end_time,
                    'center_time': hp.center_time,
                    'danmaku_count': hp.danmaku_count,
                    'density': hp.density,
                    'heat_score': hp.heat_score,
                    'keywords': hp.keywords[:5]
                })
            
            if danmaku_file.analysis_metadata is None:
                danmaku_file.analysis_metadata = {}
            
            danmaku_file.analysis_metadata.update({
                'analysis_file': str(analysis_json_path),
                'window_seconds': window_seconds,
                'slide_seconds': slide_seconds,
                'heat_points': heat_points_summary,
                'overall_keywords': [{'word': k, 'count': c} for k, c in analysis_result.overall_keywords[:20]],
                'overall_sentiment': analysis_result.overall_sentiment,
                'special_danmaku_count': len(analysis_result.special_danmaku_summary)
            })
            
            danmaku_file.status = DanmakuFileStatus.ANALYZED
            db.commit()
            
            logger.info(f"弹幕分析完成: {danmaku_file_id}")
            
            return {
                "success": True,
                "danmaku_file_id": danmaku_file_id,
                "status": "analyzed",
                "message": "弹幕分析完成",
                "summary": {
                    "total_danmaku": analysis_result.total_danmaku_count,
                    "heat_points_count": len(analysis_result.heat_points),
                    "top_keywords": [{'word': k, 'count': c} for k, c in analysis_result.overall_keywords[:10]],
                    "sentiment": analysis_result.overall_sentiment,
                    "special_danmaku_count": len(analysis_result.special_danmaku_summary)
                }
            }
            
        except Exception as e:
            danmaku_file.status = DanmakuFileStatus.FAILED
            danmaku_file.error_message = str(e)
            db.commit()
            
            raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"分析弹幕文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@router.get("/{danmaku_file_id}")
async def get_danmaku_file_info(
    danmaku_file_id: str,
    db: Session = Depends(get_db)
):
    """获取弹幕文件信息"""
    try:
        danmaku_file = db.query(DanmakuFile).filter(DanmakuFile.id == danmaku_file_id).first()
        if not danmaku_file:
            raise HTTPException(status_code=404, detail="弹幕文件不存在")
        
        return {
            "id": danmaku_file.id,
            "file_name": danmaku_file.file_name,
            "file_path": danmaku_file.file_path,
            "file_size": danmaku_file.file_size,
            "source_type": danmaku_file.source_type.value,
            "status": danmaku_file.status.value,
            "danmaku_count": danmaku_file.danmaku_count,
            "video_duration": danmaku_file.video_duration,
            "project_id": danmaku_file.project_id,
            "analysis_metadata": danmaku_file.analysis_metadata,
            "created_at": danmaku_file.created_at.isoformat() if danmaku_file.created_at else None,
            "updated_at": danmaku_file.updated_at.isoformat() if danmaku_file.updated_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取弹幕文件信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.get("/{danmaku_file_id}/heat-points")
async def get_heat_points(
    danmaku_file_id: str,
    limit: int = Query(20, description="返回数量限制", ge=1, le=100),
    min_score: float = Query(0.0, description="最小热度分数", ge=0.0, le=100.0),
    db: Session = Depends(get_db)
):
    """获取弹幕热度点"""
    try:
        danmaku_file = db.query(DanmakuFile).filter(DanmakuFile.id == danmaku_file_id).first()
        if not danmaku_file:
            raise HTTPException(status_code=404, detail="弹幕文件不存在")
        
        if danmaku_file.status != DanmakuFileStatus.ANALYZED:
            raise HTTPException(status_code=400, detail="弹幕文件尚未分析")
        
        if not danmaku_file.analysis_metadata or 'analysis_file' not in danmaku_file.analysis_metadata:
            raise HTTPException(status_code=404, detail="分析结果不存在")
        
        analysis_result = load_analysis_result(danmaku_file.analysis_metadata['analysis_file'])
        
        filtered_heat_points = [
            hp for hp in analysis_result.heat_points 
            if hp.heat_score >= min_score
        ][:limit]
        
        return {
            "danmaku_file_id": danmaku_file_id,
            "heat_points": [
                {
                    'start_time': hp.start_time,
                    'end_time': hp.end_time,
                    'center_time': hp.center_time,
                    'danmaku_count': hp.danmaku_count,
                    'density': hp.density,
                    'heat_score': hp.heat_score,
                    'keywords': hp.keywords,
                    'sentiment_score': hp.sentiment_score
                }
                for hp in filtered_heat_points
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取热度点失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.post("/score-time-range/{danmaku_file_id}")
async def get_score_for_time_range(
    danmaku_file_id: str,
    start_time: float = Query(..., description="开始时间（秒）", ge=0.0),
    end_time: float = Query(..., description="结束时间（秒）", ge=0.0),
    db: Session = Depends(get_db)
):
    """
    获取指定时间范围的弹幕评分
    
    用于将弹幕评分集成到切片评分机制中
    """
    try:
        if end_time <= start_time:
            raise HTTPException(status_code=400, detail="结束时间必须大于开始时间")
        
        danmaku_file = db.query(DanmakuFile).filter(DanmakuFile.id == danmaku_file_id).first()
        if not danmaku_file:
            raise HTTPException(status_code=404, detail="弹幕文件不存在")
        
        if danmaku_file.status != DanmakuFileStatus.ANALYZED:
            return {
                "success": False,
                "message": "弹幕文件尚未分析",
                "scores": {
                    'heat_score': 0.0,
                    'keyword_score': 0.0,
                    'sentiment_score': 0.0,
                    'special_score': 0.0,
                    'total_danmaku_score': 0.0
                }
            }
        
        if not danmaku_file.analysis_metadata or 'analysis_file' not in danmaku_file.analysis_metadata:
            return {
                "success": False,
                "message": "分析结果不存在",
                "scores": {
                    'heat_score': 0.0,
                    'keyword_score': 0.0,
                    'sentiment_score': 0.0,
                    'special_score': 0.0,
                    'total_danmaku_score': 0.0
                }
            }
        
        analysis_result = load_analysis_result(danmaku_file.analysis_metadata['analysis_file'])
        
        analyzer = DanmakuAnalyzer()
        scores = analyzer.get_score_for_time_range(start_time, end_time, analysis_result)
        
        return {
            "success": True,
            "danmaku_file_id": danmaku_file_id,
            "time_range": {
                "start_time": start_time,
                "end_time": end_time,
                "duration": end_time - start_time
            },
            "scores": scores
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取时间范围评分失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.get("/project/{project_id}")
async def get_project_danmaku_files(
    project_id: str,
    db: Session = Depends(get_db)
):
    """获取项目关联的弹幕文件列表"""
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")
        
        danmaku_files = db.query(DanmakuFile).filter(
            DanmakuFile.project_id == project_id
        ).order_by(DanmakuFile.created_at.desc()).all()
        
        return {
            "project_id": project_id,
            "danmaku_files": [
                {
                    "id": df.id,
                    "file_name": df.file_name,
                    "status": df.status.value,
                    "danmaku_count": df.danmaku_count,
                    "created_at": df.created_at.isoformat() if df.created_at else None
                }
                for df in danmaku_files
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取项目弹幕文件列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.delete("/{danmaku_file_id}")
async def delete_danmaku_file(
    danmaku_file_id: str,
    db: Session = Depends(get_db)
):
    """删除弹幕文件"""
    try:
        danmaku_file = db.query(DanmakuFile).filter(DanmakuFile.id == danmaku_file_id).first()
        if not danmaku_file:
            raise HTTPException(status_code=404, detail="弹幕文件不存在")
        
        try:
            file_path = Path(danmaku_file.file_path)
            if file_path.exists():
                file_path.unlink()
            
            if danmaku_file.analysis_metadata:
                if 'parsed_file' in danmaku_file.analysis_metadata:
                    parsed_path = Path(danmaku_file.analysis_metadata['parsed_file'])
                    if parsed_path.exists():
                        parsed_path.unlink()
                
                if 'analysis_file' in danmaku_file.analysis_metadata:
                    analysis_path = Path(danmaku_file.analysis_metadata['analysis_file'])
                    if analysis_path.exists():
                        analysis_path.unlink()
        
        except Exception as e:
            logger.warning(f"删除弹幕文件时清理文件失败: {e}")
        
        db.delete(danmaku_file)
        db.commit()
        
        logger.info(f"弹幕文件已删除: {danmaku_file_id}")
        
        return {
            "success": True,
            "danmaku_file_id": danmaku_file_id,
            "message": "弹幕文件已删除"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除弹幕文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")
