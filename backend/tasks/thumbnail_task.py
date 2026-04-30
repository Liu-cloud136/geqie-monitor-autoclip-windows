"""
后台缩略图生成任务
在项目导入后异步生成缩略图，不影响导入速度
"""

import logging
from pathlib import Path
from celery import Celery
from core.database import SessionLocal
from services.project_service import ProjectService
from utils.thumbnail_generator import generate_project_thumbnail

logger = logging.getLogger(__name__)

# 获取Celery应用实例
from core.celery_app import celery_app

@celery_app.task(bind=True)
def generate_thumbnail_background(self, project_id: str, video_path: str):
    """
    后台生成项目缩略图

    Args:
        project_id: 项目ID
        video_path: 视频文件路径
    """
    try:
        logger.info(f"开始后台生成缩略图: {project_id}")

        # 获取数据库会话
        db = SessionLocal()
        project_service = ProjectService(db)

        # 检查项目是否存在
        project = project_service.get(project_id)
        if not project:
            logger.warning(f"项目 {project_id} 不存在，跳过缩略图生成")
            return {
                'status': 'skipped',
                'project_id': project_id,
                'message': '项目不存在'
            }

        # 如果已经有缩略图，跳过
        if project.thumbnail:
            logger.info(f"项目 {project_id} 已有缩略图，跳过生成")
            return {
                'status': 'skipped',
                'project_id': project_id,
                'message': '已有缩略图'
            }

        # 生成缩略图
        try:
            thumbnail_data = generate_project_thumbnail(project_id, Path(video_path))
            if thumbnail_data:
                project.thumbnail = thumbnail_data
                db.commit()
                logger.info(f"项目 {project_id} 缩略图生成并保存成功")
                return {
                    'status': 'completed',
                    'project_id': project_id,
                    'message': '缩略图生成成功'
                }
            else:
                logger.warning(f"项目 {project_id} 缩略图生成失败")
                return {
                    'status': 'failed',
                    'project_id': project_id,
                    'message': '缩略图生成失败'
                }
        except Exception as e:
            logger.error(f"生成项目缩略图时发生错误: {e}")
            return {
                'status': 'failed',
                'project_id': project_id,
                'message': f'缩略图生成错误: {str(e)}'
            }

    except Exception as e:
        logger.error(f"后台缩略图生成任务失败: {project_id}, 错误: {e}")
        return {
            'status': 'failed',
            'project_id': project_id,
            'message': f'任务失败: {str(e)}'
        }
    finally:
        try:
            if 'db' in locals():
                db.close()
        except:
            pass
