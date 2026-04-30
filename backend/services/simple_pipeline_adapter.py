"""
简化的流水线适配器 - 集成新的进度系统
"""

import logging
import asyncio
import time
from typing import Dict, Any, Optional, Callable
from pathlib import Path

from services.simple_progress import emit_progress, clear_progress
from pipeline.step1_outline import run_step1_outline
from pipeline.step2_timeline import run_step2_timeline
from pipeline.step3_scoring_only import run_step3_scoring_only
from pipeline.step4_recommendation import run_step4_recommendation
from pipeline.step4_title import run_step4_title
from pipeline.step5_video import run_step5_video

logger = logging.getLogger(__name__)


class SimplePipelineAdapter:
    """简化的流水线适配器，使用固定阶段进度系统"""

    def __init__(self, project_id: str, task_id: str):
        self.project_id = project_id
        self.task_id = task_id
        self.start_time = time.time()  # 记录开始时间
        self.current_stage_start_time = time.time()  # 当前阶段开始时间
        self.current_stage = ""

    def _emit_progress(self, stage: str, message: str = "", subpercent: Optional[float] = None):
        """发送进度事件的包装方法，自动包含task_id和预计剩余时间"""
        from services.simple_progress import emit_progress, compute_percent, WEIGHTS, ORDER
        
        # 计算当前进度百分比
        percent = compute_percent(stage, subpercent)
        
        # 计算预计剩余时间
        estimated_remaining = self._calculate_estimated_remaining(percent)
        
        # 更新阶段时间记录
        if stage != self.current_stage:
            self.current_stage = stage
            self.current_stage_start_time = time.time()
        
        emit_progress(self.project_id, stage, message, subpercent, self.task_id, estimated_remaining)
        
        # 强制刷新日志，确保实时输出
        self._flush_logs()
    
    def _flush_logs(self):
        """强制刷新所有日志处理器，确保实时输出"""
        import logging
        for handler in logging.root.handlers:
            if hasattr(handler, 'flush'):
                try:
                    handler.flush()
                except Exception:
                    pass
    
    def _calculate_estimated_remaining(self, current_percent: int) -> Optional[int]:
        """
        计算预计剩余时间（秒）
        
        基于已用时间和当前进度估算剩余时间
        """
        if current_percent <= 0 or current_percent >= 100:
            return None
        
        elapsed = time.time() - self.start_time
        if elapsed <= 0:
            return None
        
        # 基于当前进度和已用时间估算总时间
        # 总时间 = 已用时间 / (当前进度 / 100)
        estimated_total = elapsed / (current_percent / 100)
        estimated_remaining = int(estimated_total - elapsed)
        
        # 确保剩余时间合理（至少1秒，最多2小时）
        if estimated_remaining < 1:
            return 1
        if estimated_remaining > 7200:  # 2小时
            return 7200
        
        return estimated_remaining
        
    async def _generate_subtitle_automatically(self, video_path: str, metadata_dir: Path) -> Path:
        """
        自动生成字幕文件
        
        Args:
            video_path: 视频文件路径
            metadata_dir: 元数据目录
            
        Returns:
            生成的SRT文件路径，如果失败返回None
        """
        try:
            logger.info(f"开始为视频 {video_path} 自动生成字幕")
            
            # 更新进度
            self._emit_progress("SUBTITLE", "正在使用AI生成字幕...", subpercent=25)
            
            # 尝试使用bcut-asr
            try:
                from utils.speech_recognizer import generate_subtitle_for_video
                from pathlib import Path
                
                video_file_path = Path(video_path)
                if not video_file_path.exists():
                    logger.error(f"视频文件不存在: {video_path}")
                    return None
                
                # 使用bcut-asr生成字幕
                logger.info("尝试使用bcut-asr生成字幕")
                output_path = metadata_dir / f"{video_file_path.stem}.srt"
                srt_path = generate_subtitle_for_video(
                    video_file_path,
                    output_path=output_path,
                    method="auto",
                    model="base",
                    language="auto"
                )
                
                if srt_path and srt_path.exists():
                    logger.info(f"bcut-asr生成字幕成功: {srt_path}")
                    self._emit_progress("SUBTITLE", "AI字幕生成完成", subpercent=40)
                    return srt_path
                else:
                    logger.warning("bcut-asr生成字幕失败")
                    
            except Exception as e:
                logger.warning(f"bcut-asr生成字幕失败: {e}")
            
            logger.error("字幕生成失败")
            return None
            
        except Exception as e:
            logger.error(f"自动生成字幕过程中发生错误: {e}")
            return None
        
    async def process_project_sync(self, input_video_path: str, input_srt_path: str) -> Dict[str, Any]:
        """
        同步处理项目 - 使用简化的进度系统，支持断点续传
        
        Args:
            input_video_path: 输入视频路径
            input_srt_path: 输入SRT路径
            
        Returns:
            处理结果
        """
        logger.info(f"开始处理项目: {self.project_id}")
        
        try:
            # 清除之前的进度数据
            clear_progress(self.project_id)
            
            # 创建必要的目录结构 - 使用正确的路径
            from core.path_utils import get_project_directory
            project_dir = get_project_directory(self.project_id)
            metadata_dir = project_dir / "metadata"
            output_dir = project_dir / "output"
            metadata_dir.mkdir(parents=True, exist_ok=True)
            output_dir.mkdir(parents=True, exist_ok=True)
            # 项目内专属输出子目录
            clips_output_dir = output_dir / "clips"
            clips_output_dir.mkdir(parents=True, exist_ok=True)
            
            # 检查各步骤的断点状态
            from utils.checkpoint_manager import CheckpointManager
            step1_checkpoint = CheckpointManager(metadata_dir, "step1")
            step2_checkpoint = CheckpointManager(metadata_dir, "step2")
            step3_checkpoint = CheckpointManager(metadata_dir, "step3")
            step4_checkpoint = CheckpointManager(metadata_dir, "step4_recommendation")
            step4_title_checkpoint = CheckpointManager(metadata_dir, "step4_title")
            step5_checkpoint = CheckpointManager(metadata_dir, "step5")
            
            # 检查各步骤是否已完成
            step1_completed = step1_checkpoint.load_checkpoint()
            step2_completed = step2_checkpoint.load_checkpoint()
            step3_completed = step3_checkpoint.load_checkpoint()
            step4_completed = step4_checkpoint.load_checkpoint()
            step4_title_completed = step4_title_checkpoint.load_checkpoint()
            step5_completed = step5_checkpoint.load_checkpoint()
            
            logger.info(f"各步骤完成状态: step1={len(step1_completed)}, step2={len(step2_completed)}, step3={len(step3_completed)}, step4={len(step4_completed)}, step4_title={len(step4_title_completed)}, step5={len(step5_completed)}")
            self._flush_logs()
            
            # 阶段1: 素材准备
            self._emit_progress("INGEST", "素材准备完成")

            # 阶段2: 字幕处理
            self._emit_progress("SUBTITLE", "开始字幕处理")
            
            # Step 1: 大纲提取（如果未完成）
            if not step1_completed:
                logger.info("执行Step 1: 大纲提取")
                self._flush_logs()
                if input_srt_path and Path(input_srt_path).exists():
                    logger.info(f"使用现有SRT文件: {input_srt_path}")
                    outlines = await run_step1_outline(Path(input_srt_path), metadata_dir=metadata_dir)
                else:
                    logger.warning("没有SRT文件，尝试自动生成字幕")
                    self._flush_logs()
                    srt_path = await self._generate_subtitle_automatically(input_video_path, metadata_dir)

                    if srt_path and srt_path.exists():
                        logger.info(f"自动生成字幕成功: {srt_path}")
                        outlines = await run_step1_outline(srt_path, metadata_dir=metadata_dir)
                    else:
                        logger.warning("自动生成字幕失败，创建空大纲")
                        outlines = []
                        outline_file = metadata_dir / "step1_outline.json"
                        import json
                        with open(outline_file, 'w', encoding='utf-8') as f:
                            json.dump(outlines, f, ensure_ascii=False, indent=2)
                
                # 保存Step 1的断点状态
                step1_checkpoint.save_checkpoint(0, success=True, item_info={"step": "step1_outline", "status": "completed"})
                step1_checkpoint.save_intermediate_results(outlines)
                logger.info("Step 1 断点已保存")
                self._flush_logs()
                self._emit_progress("SUBTITLE", "字幕处理完成", subpercent=50)
            else:
                logger.info("Step 1 已完成，加载大纲结果")
                outlines = step1_checkpoint.load_intermediate_results()
                self._emit_progress("SUBTITLE", "字幕处理完成（已缓存）", subpercent=50)

            # 阶段3: 内容分析
            self._emit_progress("ANALYZE", "开始内容分析")
            
            # Step 2: 时间线提取（如果未完成）
            if not step2_completed and outlines:
                logger.info("执行Step 2: 时间线提取")
                self._flush_logs()
                timeline_data = run_step2_timeline(
                    metadata_dir / "step1_outline.json",
                    metadata_dir=metadata_dir
                )
                self._flush_logs()

                # 保存Step 2的断点状态
                step2_checkpoint.save_checkpoint(0, success=True, item_info={"step": "step2_timeline", "status": "completed"})
                step2_checkpoint.save_intermediate_results(timeline_data)
                logger.info("Step 2 断点已保存")
                self._flush_logs()
                self._emit_progress("ANALYZE", "时间线提取完成", subpercent=50)  # Step 2占ANALYZE阶段的50%
            elif step2_completed:
                logger.info("Step 2 已完成，加载时间线结果")
                timeline_data = step2_checkpoint.load_intermediate_results()
                self._emit_progress("ANALYZE", "时间线提取完成（已缓存）", subpercent=50)  # Step 2占50%
            else:
                logger.warning("没有大纲数据，跳过时间线提取")
                self._flush_logs()
                timeline_file = metadata_dir / "step2_timeline.json"
                scored_file = metadata_dir / "step3_high_score_clips.json"
                import json
                with open(timeline_file, 'w', encoding='utf-8') as f:
                    json.dump([], f, ensure_ascii=False, indent=2)
                with open(scored_file, 'w', encoding='utf-8') as f:
                    json.dump([], f, ensure_ascii=False, indent=2)
                timeline_data = []
                scored_clips = []
                self._emit_progress("ANALYZE", "内容分析完成", subpercent=100)

            # Step 3: 内容评分（如果未完成）
            if not step3_completed and timeline_data:
                logger.info("执行Step 3: 内容评分（并发模式，3个线程同时评分）")
                self._flush_logs()
                scored_clips = run_step3_scoring_only(
                    metadata_dir / "step2_timeline.json",
                    metadata_dir=metadata_dir,
                    progress_callback=lambda p, m: self._emit_progress("ANALYZE", m, subpercent=50 + p/2),  # 将0-100映射到50-100
                    max_workers=3  # 3个并发线程
                )
                self._flush_logs()
                
                # 保存Step 3的断点状态
                step3_checkpoint.save_checkpoint(0, success=True, item_info={"step": "step3_scoring", "status": "completed"})
                step3_checkpoint.save_intermediate_results(scored_clips)
                logger.info("Step 3 断点已保存")
                self._flush_logs()
            elif step3_completed:
                logger.info("Step 3 已完成，加载评分结果")
                scored_clips = step3_checkpoint.load_intermediate_results()
                self._emit_progress("ANALYZE", "内容评分完成（已缓存）", subpercent=100)  # Step 3完成后应该是100%
            else:
                logger.warning("没有时间线数据，跳过内容评分")
                self._flush_logs()
                scored_file = metadata_dir / "step3_only_high_score_clips.json"
                import json
                with open(scored_file, 'w', encoding='utf-8') as f:
                    json.dump([], f, ensure_ascii=False, indent=2)
                scored_clips = []
                self._emit_progress("ANALYZE", "内容分析完成", subpercent=100)
            
            # Step 4: 推荐理由生成（如果未完成）
            if not step4_completed and scored_clips:
                logger.info("执行Step 4: 推荐理由生成")
                self._flush_logs()
                try:
                    recommended_clips = run_step4_recommendation(
                        metadata_dir / "step3_only_high_score_clips.json",
                        metadata_dir=metadata_dir
                    )
                    self._flush_logs()
                    
                    # 保存Step 4的断点状态
                    step4_checkpoint.save_checkpoint(0, success=True, item_info={"step": "step4_recommendation", "status": "completed"})
                    step4_checkpoint.save_intermediate_results(recommended_clips)
                    logger.info("Step 4 断点已保存")
                    self._flush_logs()
                except Exception as e:
                    logger.error(f"Step 4 推荐理由生成失败: {e}")
                    self._flush_logs()
                    # 创建空的推荐理由文件，确保步骤5不会因为找不到文件而失败
                    recommended_file = metadata_dir / "step4_with_recommendations.json"
                    import json
                    with open(recommended_file, 'w', encoding='utf-8') as f:
                        json.dump(scored_clips, f, ensure_ascii=False, indent=2)
                    recommended_clips = scored_clips
                    logger.info("已创建空的推荐理由文件，步骤5将直接使用步骤3的输出")
            elif step4_completed:
                logger.info("Step 4 已完成，加载推荐理由结果")
                recommended_clips = step4_checkpoint.load_intermediate_results()
            else:
                logger.warning("没有评分数据，跳过推荐理由生成")
                self._flush_logs()
                recommended_file = metadata_dir / "step4_with_recommendations.json"
                import json
                with open(recommended_file, 'w', encoding='utf-8') as f:
                    json.dump([], f, ensure_ascii=False, indent=2)
                recommended_clips = []

            # 阶段4: 片段定位
            self._emit_progress("HIGHLIGHT", "开始片段定位")
            
            # Step 5: 标题生成（如果未完成）
            if not step4_title_completed and recommended_clips:
                logger.info("执行Step 5: 标题生成")
                self._flush_logs()
                try:
                    titled_clips = run_step4_title(
                        metadata_dir / "step4_with_recommendations.json",
                        metadata_dir=str(metadata_dir)
                    )
                    self._flush_logs()
                    
                    # 保存Step 5的断点状态
                    step4_title_checkpoint.save_checkpoint(0, success=True, item_info={"step": "step4_title", "status": "completed"})
                    step4_title_checkpoint.save_intermediate_results(titled_clips)
                    logger.info("Step 5 断点已保存")
                    self._flush_logs()
                    self._emit_progress("HIGHLIGHT", "标题生成完成", subpercent=40)
                    self._emit_progress("HIGHLIGHT", "片段定位完成", subpercent=100)
                except Exception as e:
                    logger.error(f"Step 5 标题生成失败: {e}")
                    self._flush_logs()
                    # 如果标题生成失败，直接使用步骤3的输出作为标题
                    titles_file = metadata_dir / "step4_titles.json"
                    import json
                    with open(titles_file, 'w', encoding='utf-8') as f:
                        json.dump(scored_clips, f, ensure_ascii=False, indent=2)
                    titled_clips = scored_clips
                    logger.info("已创建空的标题文件，步骤6将直接使用步骤3的输出")
                    self._emit_progress("HIGHLIGHT", "标题生成失败，使用步骤3数据", subpercent=40)
                    self._emit_progress("HIGHLIGHT", "片段定位完成", subpercent=100)
            elif step4_title_completed:
                logger.info("Step 5 已完成，加载标题结果")
                titled_clips = step4_title_checkpoint.load_intermediate_results()
                self._emit_progress("HIGHLIGHT", "标题生成完成（已缓存）", subpercent=40)
                self._emit_progress("HIGHLIGHT", "片段定位完成", subpercent=100)
            else:
                logger.warning("没有推荐理由数据，跳过标题生成")
                self._flush_logs()
                titles_file = metadata_dir / "step4_titles.json"
                import json
                with open(titles_file, 'w', encoding='utf-8') as f:
                    json.dump([], f, ensure_ascii=False, indent=2)
                titled_clips = []
                self._emit_progress("HIGHLIGHT", "片段定位完成", subpercent=100)

            # 阶段5: 视频导出
            self._emit_progress("EXPORT", "开始视频导出")
            
            # Step 6: 视频切割（如果未完成）
            if not step5_completed and titled_clips:
                logger.info("执行Step 6: 视频切割")
                self._flush_logs()
                video_result = run_step5_video(
                    metadata_dir / "step4_titles.json",
                    input_video_path,
                    output_dir=output_dir,
                    clips_dir=str(clips_output_dir),
                    metadata_dir=str(metadata_dir),
                    use_stream_copy=True,
                    use_hardware_accel=True
                )
                self._flush_logs()
                
                # 保存Step 5的断点状态
                step5_checkpoint.save_checkpoint(0, success=True, item_info={"step": "step5_video", "status": "completed"})
                step5_checkpoint.save_intermediate_results(video_result)
                logger.info("Step 5 断点已保存")
                self._flush_logs()
            elif step5_completed:
                logger.info("Step 6 已完成，加载视频结果")
                video_result = step5_checkpoint.load_intermediate_results()
                self._emit_progress("EXPORT", "视频导出完成（已缓存）", subpercent=100)
            else:
                logger.warning("没有标题数据，跳过视频切割")
                self._flush_logs()
                video_result = {"status": "skipped", "message": "没有内容可处理"}
            self._emit_progress("EXPORT", "视频导出完成", subpercent=100)

            # 阶段6: 处理完成
            self._emit_progress("DONE", "处理完成")
            
            # 清理所有断点文件（只有在整个流程成功后才清理）
            try:
                step1_checkpoint.cleanup_checkpoint()
                step2_checkpoint.cleanup_checkpoint()
                step3_checkpoint.cleanup_checkpoint()
                step4_checkpoint.cleanup_checkpoint()
                step5_checkpoint.cleanup_checkpoint()
                logger.info("所有断点文件已清理")
            except Exception as e:
                logger.warning(f"清理断点文件时出错: {e}")
            
            # 自动同步数据到数据库
            try:
                from services.data_sync_service import DataSyncService
                from core.database import SessionLocal
                
                db = SessionLocal()
                try:
                    sync_service = DataSyncService(db)
                    sync_result = sync_service.sync_project_from_filesystem(self.project_id, project_dir)
                    if sync_result.get("success"):
                        logger.info(f"项目 {self.project_id} 数据同步成功: {sync_result}")
                    else:
                        logger.error(f"项目 {self.project_id} 数据同步失败: {sync_result}")
                finally:
                    db.close()
            except Exception as e:
                logger.error(f"数据同步失败: {e}")
            
            logger.info(f"项目处理完成: {self.project_id}")
            return {
                "status": "succeeded",
                "project_id": self.project_id,
                "task_id": self.task_id,
                "result": {
                    "outlines": outlines,
                    "timeline": timeline_data,
                    "scored_clips": scored_clips,
                    "titled_clips": titled_clips,
                    "video_result": video_result
                }
            }
            
        except Exception as e:
            error_msg = f"流水线处理失败: {str(e)}"
            logger.error(error_msg)
            
            # 发送失败状态
            emit_progress(self.project_id, "DONE", f"处理失败: {error_msg}")
            
            return {
                "status": "failed",
                "project_id": self.project_id,
                "task_id": self.task_id,
                "error": error_msg
            }


def create_simple_pipeline_adapter(project_id: str, task_id: str) -> SimplePipelineAdapter:
    """创建简化的流水线适配器实例"""
    return SimplePipelineAdapter(project_id, task_id)