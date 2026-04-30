"""
Step 5: 切片生成 - 生成最终视频切片
支持断点续传
"""
import json
import logging
import re
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path

# 导入依赖
from utils.video_processor import VideoProcessor
from utils.checkpoint_manager import CheckpointManager, ProgressTracker
from utils.thumbnail_generator import ThumbnailGenerator
from core.unified_config import get_config

logger = logging.getLogger(__name__)

class VideoGenerator:
    """视频生成器（支持断点续传）"""

    def __init__(self, clips_dir: Optional[str] = None, metadata_dir: Optional[str] = None,
                 progress_callback: Optional[Callable[[float], None]] = None,
                 enable_checkpoint: bool = True) -> None:
        # 强制使用项目内专属目录，不使用全局目录作为后备
        if not clips_dir:
            raise ValueError("clips_dir 参数是必需的，不能使用全局路径")

        self.clips_dir = Path(clips_dir)
        if metadata_dir is None:
            config = get_config()
            metadata_dir = config.paths.output_dir / "metadata"
        self.metadata_dir = Path(metadata_dir)
        self.progress_callback = progress_callback
        self.enable_checkpoint = enable_checkpoint

        # 确保目录存在
        self.clips_dir.mkdir(parents=True, exist_ok=True)

        # 创建VideoProcessor实例，强制使用项目内路径
        self.video_processor = VideoProcessor(clips_dir=str(self.clips_dir))

        # 创建缩略图生成器实例
        self.thumbnail_generator = ThumbnailGenerator()

        # 初始化断点管理器
        self.checkpoint_manager = CheckpointManager(
            self.metadata_dir, "step5", enable_checkpoint
        )
    
    def generate_clips(self, clips_with_titles: List[Dict], input_video: Path,
                      progress_callback: Optional[Callable[[float], None]] = None,
                      use_stream_copy: bool = True, use_hardware_accel: bool = True) -> List[Path]:
        """
        生成切片视频（优化版本，支持流复制、硬件加速、进度回调和断点续传）

        Args:
            clips_with_titles: 带标题的片段数据
            input_video: 输入视频路径
            progress_callback: 进度回调函数，传入0-100的进度值
            use_stream_copy: 是否使用流复制（默认True，速度最快）
            use_hardware_accel: 是否使用硬件加速（默认True，需要GPU支持）

        Returns:
            生成的切片视频路径列表
        """
        logger.info("开始生成切片视频（优化版本，支持流复制、硬件加速和断点续传）...")

        clips_data = []
        for clip in clips_with_titles:
            clips_data.append({
                'id': clip['id'],
                'title': clip.get('generated_title', f"片段_{clip['id']}"),
                'start_time': clip['start_time'],
                'end_time': clip['end_time']
            })

        completed_clips = self.checkpoint_manager.load_checkpoint()

        if completed_clips:
            logger.info(f"检测到已生成的视频: {sorted(completed_clips)}，将跳过这些视频")

        pending_clips = [
            clip_data for clip_data in clips_data
            if clip_data['id'] not in completed_clips
        ]

        if not pending_clips:
            logger.info("所有视频已生成，跳过处理")

            all_clip_paths = []
            for clip_data in clips_data:
                # 优先使用新格式 clip_{id}.mp4
                clip_path = self.clips_dir / f"clip_{clip_data['id']}.mp4"
                if clip_path.exists():
                    all_clip_paths.append(clip_path)
                else:
                    # 如果新格式不存在，尝试旧格式 {id}_{title}.mp4
                    old_format_files = list(self.clips_dir.glob(f"{clip_data['id']}_*.mp4"))
                    if old_format_files:
                        all_clip_paths.append(old_format_files[0])

            return all_clip_paths

        logger.info(f"待生成视频数量: {len(pending_clips)}/{len(clips_data)}")

        total_clips = len(clips_data)
        completed_count = len(completed_clips)
        tracker = ProgressTracker(total_clips, self.progress_callback)

        if completed_count > 0:
            tracker.set_progress(completed_count, f"已恢复进度 {completed_count}/{total_clips} 个视频")

        successful_clips = self.video_processor.batch_extract_clips(
            input_video,
            pending_clips,
            progress_callback=progress_callback,
            use_stream_copy=use_stream_copy,
            use_hardware_accel=use_hardware_accel
        )

        for clip_data in pending_clips:
            clip_id = clip_data['id']
            clip_path = self.clips_dir / f"clip_{clip_id}.mp4"
            if clip_path.exists():
                self.checkpoint_manager.save_checkpoint(clip_id, success=True, item_info={"clip_file": f"clip_{clip_id}.mp4"})

        all_clip_paths = []
        for clip_data in clips_data:
            # 优先使用新格式 clip_{id}.mp4
            clip_path = self.clips_dir / f"clip_{clip_data['id']}.mp4"
            if clip_path.exists():
                all_clip_paths.append(clip_path)
            else:
                # 如果新格式不存在，尝试旧格式 {id}_{title}.mp4
                old_format_files = list(self.clips_dir.glob(f"{clip_data['id']}_*.mp4"))
                if old_format_files:
                    all_clip_paths.append(old_format_files[0])

        logger.info("开始为切片生成缩略图...")
        thumbnail_count = 0
        skipped_count = 0
        for clip_path in all_clip_paths:
            try:
                thumbnail_path = clip_path.parent / f"{clip_path.stem}_thumbnail.jpg"
                if thumbnail_path.exists():
                    logger.info(f"缩略图已存在，跳过: {thumbnail_path.name}")
                    skipped_count += 1
                    continue

                logger.info(f"正在为切片生成缩略图: {clip_path.name}")
                thumbnail_path = self.thumbnail_generator.generate_thumbnail(
                    video_path=clip_path,
                    width=320,
                    height=180
                )
                if thumbnail_path:
                    thumbnail_count += 1
                    logger.info(f"缩略图生成成功: {thumbnail_path.name}")
                else:
                    logger.warning(f"缩略图生成失败: {clip_path.name}")
            except Exception as e:
                logger.warning(f"为切片 {clip_path} 生成缩略图失败: {e}")

        logger.info(f"缩略图生成完成，共{len(all_clip_paths)}个切片（新生成{thumbnail_count}个，跳过{skipped_count}个）")
        logger.info(f"切片视频生成完成，共{len(all_clip_paths)}个切片")

        # 不清理断点，保留用于断点续传
        # 只有在整个流程完全成功后才应该清理断点
        # self.checkpoint_manager.cleanup_checkpoint()

        return all_clip_paths

    async def generate_clips_async(self, clips_with_titles: List[Dict], input_video: Path,
                                   progress_callback: Optional[Callable[[float], None]] = None,
                                   use_stream_copy: bool = True, use_hardware_accel: bool = True,
                                   max_concurrent: int = 3) -> List[Path]:
        """
        异步生成切片视频（优化版本，支持流复制、硬件加速、进度回调和断点续传）

        Args:
            clips_with_titles: 带标题的片段数据
            input_video: 输入视频路径
            progress_callback: 进度回调函数，传入0-100的进度值
            use_stream_copy: 是否使用流复制（默认True，速度最快）
            use_hardware_accel: 是否使用硬件加速（默认True，需要GPU支持）
            max_concurrent: 最大并发数，默认为3

        Returns:
            生成的切片视频路径列表
        """
        logger.info("开始异步生成切片视频（优化版本，支持流复制、硬件加速和断点续传）...")

        clips_data = []
        for clip in clips_with_titles:
            clips_data.append({
                'id': clip['id'],
                'title': clip.get('generated_title', f"片段_{clip['id']}"),
                'start_time': clip['start_time'],
                'end_time': clip['end_time']
            })

        completed_clips = self.checkpoint_manager.load_checkpoint()

        if completed_clips:
            logger.info(f"检测到已生成的视频: {sorted(completed_clips)}，将跳过这些视频")

        pending_clips = [
            clip_data for clip_data in clips_data
            if clip_data['id'] not in completed_clips
        ]

        if not pending_clips:
            logger.info("所有视频已生成，跳过处理")

            all_clip_paths = []
            for clip_data in clips_data:
                # 优先使用新格式 clip_{id}.mp4
                clip_path = self.clips_dir / f"clip_{clip_data['id']}.mp4"
                if clip_path.exists():
                    all_clip_paths.append(clip_path)
                else:
                    # 如果新格式不存在，尝试旧格式 {id}_{title}.mp4
                    old_format_files = list(self.clips_dir.glob(f"{clip_data['id']}_*.mp4"))
                    if old_format_files:
                        all_clip_paths.append(old_format_files[0])

            return all_clip_paths

        logger.info(f"待生成视频数量: {len(pending_clips)}/{len(clips_data)}")

        total_clips = len(clips_data)
        completed_count = len(completed_clips)
        tracker = ProgressTracker(total_clips, self.progress_callback)

        if completed_count > 0:
            tracker.set_progress(completed_count, f"已恢复进度 {completed_count}/{total_clips} 个视频")

        successful_clips = await self.video_processor.batch_extract_clips_async(
            input_video,
            pending_clips,
            progress_callback=progress_callback,
            use_stream_copy=use_stream_copy,
            use_hardware_accel=use_hardware_accel,
            max_concurrent=max_concurrent
        )

        for clip_data in pending_clips:
            clip_id = clip_data['id']
            clip_path = self.clips_dir / f"clip_{clip_id}.mp4"
            if clip_path.exists():
                self.checkpoint_manager.save_checkpoint(clip_id, success=True, item_info={"clip_file": f"clip_{clip_id}.mp4"})

        all_clip_paths = []
        for clip_data in clips_data:
            # 优先使用新格式 clip_{id}.mp4
            clip_path = self.clips_dir / f"clip_{clip_data['id']}.mp4"
            if clip_path.exists():
                all_clip_paths.append(clip_path)
            else:
                # 如果新格式不存在，尝试旧格式 {id}_{title}.mp4
                old_format_files = list(self.clips_dir.glob(f"{clip_data['id']}_*.mp4"))
                if old_format_files:
                    all_clip_paths.append(old_format_files[0])

        logger.info("开始为切片生成缩略图...")
        thumbnail_count = 0
        skipped_count = 0
        for clip_path in all_clip_paths:
            try:
                thumbnail_path = clip_path.parent / f"{clip_path.stem}_thumbnail.jpg"
                if thumbnail_path.exists():
                    logger.info(f"缩略图已存在，跳过: {thumbnail_path.name}")
                    skipped_count += 1
                    continue

                logger.info(f"正在为切片生成缩略图: {clip_path.name}")
                thumbnail_path = await self.thumbnail_generator.generate_thumbnail_async(
                    video_path=clip_path,
                    width=320,
                    height=180
                )
                if thumbnail_path:
                    thumbnail_count += 1
                    logger.info(f"缩略图生成成功: {thumbnail_path.name}")
                else:
                    logger.warning(f"缩略图生成失败: {clip_path.name}")
            except Exception as e:
                logger.warning(f"为切片 {clip_path} 生成缩略图失败: {e}")

        logger.info(f"缩略图生成完成，共{len(all_clip_paths)}个切片（新生成{thumbnail_count}个，跳过{skipped_count}个）")
        logger.info(f"切片视频生成完成，共{len(all_clip_paths)}个切片")

        self.checkpoint_manager.cleanup_checkpoint()

        return all_clip_paths
    
    def save_clip_metadata(self, clips_with_titles: List[Dict[str, Any]], output_path: Optional[Path] = None) -> Path:
        """
        保存最终的切片元数据到clips_metadata.json
        
        Args:
            clips_with_titles: 带标题的片段数据（来自step4）
            output_path: 输出路径，默认为clips_metadata.json
            
        Returns:
            保存的文件路径
            
        Note:
            此方法保存的是最终的切片元数据，包含视频生成后的完整信息。
            与step4的step4_titles.json不同，这里保存的是用于前端展示的最终数据。
        """
        if output_path is None:
            output_path = self.metadata_dir / "clips_metadata.json"
        
        # 确保目录存在
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 保存数据
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(clips_with_titles, f, ensure_ascii=False, indent=2)
        
        logger.info(f"切片元数据已保存到: {output_path}")
        return output_path

def run_step5_video(clips_with_titles_path: Path,
                   input_video: Path, output_dir: Optional[Path] = None,
                   clips_dir: Optional[str] = None,
                   metadata_dir: Optional[str] = None,
                   progress_callback: Optional[Callable[[float], None]] = None,
                   enable_checkpoint: bool = True,
                   use_stream_copy: bool = True,
                   use_hardware_accel: bool = True) -> Dict[str, Any]:
    """
    运行Step 5: 切片生成（优化版本，支持流复制和硬件加速）

    Args:
        clips_with_titles_path: 带标题的片段文件路径
        input_video: 输入视频路径
        output_dir: 输出目录
        clips_dir: 切片输出目录
        metadata_dir: 元数据目录
        progress_callback: 进度回调函数，传入0-100的进度值
        enable_checkpoint: 是否启用断点续传，默认为True
        use_stream_copy: 是否使用流复制（默认True，速度最快）
        use_hardware_accel: 是否使用硬件加速（默认True，需要GPU支持）

    Returns:
        生成结果信息
    """
    with open(clips_with_titles_path, 'r', encoding='utf-8') as f:
        clips_with_titles = json.load(f)

    generator = VideoGenerator(clips_dir=clips_dir, metadata_dir=metadata_dir, progress_callback=progress_callback, enable_checkpoint=enable_checkpoint)

    successful_clips = generator.generate_clips(
        clips_with_titles,
        input_video,
        progress_callback=progress_callback,
        use_stream_copy=use_stream_copy,
        use_hardware_accel=use_hardware_accel
    )

    if metadata_dir:
        project_metadata_dir = Path(metadata_dir)
        generator.save_clip_metadata(clips_with_titles, project_metadata_dir / "clips_metadata.json")
    else:
        generator.save_clip_metadata(clips_with_titles)

    result = {
        'clips_generated': len(successful_clips),
        'clip_paths': [str(path) for path in successful_clips]
    }

    logger.info(f"视频生成完成: {result['clips_generated']}个切片")

    if output_dir is not None:
        output_path = output_dir / "step5_video_output.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info(f"步骤5结果已保存到: {output_path}")

    return result