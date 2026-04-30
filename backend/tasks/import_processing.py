"""
本地导入处理任务
处理视频文件上传后的异步任务：字幕生成、缩略图生成、处理流程启动
"""

import logging
from pathlib import Path
from typing import Optional
from celery import Celery
from core.database import SessionLocal
from services.project_service import ProjectService
from utils.thumbnail_generator import generate_project_thumbnail
from utils.task_submission_utils import submit_video_pipeline_task

logger = logging.getLogger(__name__)

# 获取Celery应用实例
from core.celery_app import celery_app

# 导入优化配置
try:
    from config.import_config import THUMBNAIL_GENERATION_STRATEGY as IMPORT_THUMBNAIL_GENERATION_STRATEGY
except ImportError:
    IMPORT_THUMBNAIL_GENERATION_STRATEGY = 'lazy'  # 默认使用延迟生成

THUMBNAIL_GENERATION_STRATEGY = IMPORT_THUMBNAIL_GENERATION_STRATEGY

@celery_app.task(bind=True)
def process_import_task(self, project_id: str, video_path: str, srt_file_path: Optional[str] = None):
    """
    处理本地导入的异步任务 - 极速优化版本

    Args:
        project_id: 项目ID
        video_path: 视频文件路径
        srt_file_path: 字幕文件路径（可选）
    """
    db = None
    try:
        logger.info(f"开始处理导入任务: {project_id}")

        db = SessionLocal()
        project_service = ProjectService(db)

        project = project_service.get(project_id)
        if not project:
            logger.warning(f"项目 {project_id} 不存在，跳过导入任务")
            return {
                'status': 'skipped',
                'project_id': project_id,
                'message': '项目不存在，跳过导入任务'
            }

        if project.status.value == "completed":
            logger.info(f"项目 {project_id} 已完成，跳过导入任务")
            return {
                'status': 'skipped',
                'project_id': project_id,
                'message': '项目已完成，跳过导入任务'
            }

        if project.status.value == "processing":
            logger.info(f"项目 {project_id} 正在处理中，跳过导入任务")
            return {
                'status': 'skipped',
                'project_id': project_id,
                'message': '项目正在处理中，跳过导入任务'
            }

        if project.status.value == "failed" and not project.video_path:
            logger.warning(f"项目 {project_id} 可能已被删除，跳过导入任务")
            return {
                'status': 'skipped',
                'project_id': project_id,
                'message': '项目可能已被删除，跳过导入任务'
            }

        self.update_state(state='PROGRESS', meta={'progress': 10, 'message': '开始处理...'})

        # 1. 根据配置决定是否立即生成缩略图
        if THUMBNAIL_GENERATION_STRATEGY == 'immediate':
            # 立即生成缩略图（传统模式，速度慢）
            logger.info(f"开始生成项目 {project_id} 缩略图...")
            self.update_state(state='PROGRESS', meta={'progress': 20, 'message': '生成缩略图...'})

            try:
                thumbnail_data = generate_project_thumbnail(project_id, Path(video_path))
                if thumbnail_data:
                    project.thumbnail = thumbnail_data
                    logger.info(f"项目 {project_id} 缩略图生成成功")
                else:
                    logger.warning(f"项目 {project_id} 缩略图生成失败，将使用默认缩略图")
            except Exception as e:
                logger.error(f"生成项目缩略图时发生错误: {e}")
                # 缩略图生成失败不影响后续流程
        else:
            # 跳过缩略图生成（极速模式）- 在后台异步生成
            logger.info(f"使用极速导入模式，跳过缩略图生成（将在后台异步生成）")
            self.update_state(state='PROGRESS', meta={'progress': 20, 'message': '跳过缩略图生成...'})

            # 触发后台缩略图生成任务
            try:
                from tasks.thumbnail_task import generate_thumbnail_background
                thumbnail_task = generate_thumbnail_background.delay(project_id=project_id, video_path=video_path)
                logger.info(f"已触发后台缩略图生成任务: {thumbnail_task.id}")
            except Exception as e:
                logger.error(f"触发后台缩略图生成任务失败: {e}")
                # 缩略图生成失败不影响后续流程

        # 2. 字幕文件处理
        srt_path = srt_file_path
        if not srt_path:
            logger.info(f"项目 {project_id} 没有提供字幕文件，使用AI生成")
            srt_path = None

        # 3. 更新项目状态为处理中并提交所有变更
        logger.info(f"更新项目 {project_id} 状态为处理中...")
        project_service.update_project_status(project_id, "processing")
        db.commit()  # 一次性提交状态更新
        
        # 确保事务提交后的数据对其他进程可见
        # SQLite在WAL模式下可能需要短暂等待确保数据持久化
        import time
        time.sleep(0.1)
        
        self.update_state(state='PROGRESS', meta={'progress': 50, 'message': '启动处理流程...'})

        # 4. 启动处理流程
        try:
            # 重新获取项目，确保状态已更新
            db.refresh(project) if project else None
            project = project_service.get(project_id)
            if not project:
                logger.warning(f"项目 {project_id} 不存在，跳过启动处理流程")
                return {
                    'status': 'skipped',
                    'project_id': project_id,
                    'message': '项目不存在，跳过启动处理流程'
                }
            
            if project.status.value == "completed":
                logger.info(f"项目 {project_id} 已完成，跳过启动处理流程")
                return {
                    'status': 'completed',
                    'project_id': project_id,
                    'message': '项目已完成，跳过启动处理流程'
                }

            logger.info(f"项目 {project_id} 状态验证通过，当前状态: {project.status.value}，准备提交处理任务...")
            
            task_result = submit_video_pipeline_task(
                project_id=project_id,
                input_video_path=video_path,
                input_srt_path=srt_path or "",
                skip_status_check=True
            )

            if task_result['success']:
                logger.info(f"项目 {project_id} 处理任务已启动，Celery任务ID: {task_result['task_id']}")
                self.update_state(state='PROGRESS', meta={'progress': 100, 'message': '处理流程已启动'})
            else:
                logger.error(f"Celery任务提交失败: {task_result['error']}")
                project_service.update_project_status(project_id, "failed")
                db.commit()
                self.update_state(state='FAILURE', meta={'error': task_result['error']})
                return

        except Exception as e:
            logger.error(f"启动项目 {project_id} 处理失败: {str(e)}")
            project_service.update_project_status(project_id, "failed")
            db.commit()
            self.update_state(state='FAILURE', meta={'error': str(e)})
            return

        logger.info(f"导入任务完成: {project_id}")
        return {
            'status': 'completed',
            'project_id': project_id,
            'message': '导入处理完成'
        }

    except Exception as e:
        logger.error(f"导入任务失败: {project_id}, 错误: {e}")

        # 更新项目状态为失败
        try:
            if db is None:
                db = SessionLocal()
            project_service = ProjectService(db)
            project_service.update_project_status(project_id, "failed")
            db.commit()
        except:
            pass

        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise
    finally:
        if db:
            try:
                db.close()
            except:
                pass

