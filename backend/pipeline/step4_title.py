"""
Step 4: 标题生成 - 为高质量内容生成吸引人的标题
支持断点续传
"""
import json
import logging
import re
import asyncio
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path
from collections import defaultdict

# 导入依赖
from utils.llm_client import LLMClient
from utils.step_aware_llm_client import StepAwareLLMClient, get_step_aware_llm_client
from utils.text_processor import TextProcessor
from utils.checkpoint_manager import CheckpointManager, ProgressTracker
from core.unified_config import get_prompt_files, get_config
from core.step_config import StepType
from core.config import get_project_root

logger = logging.getLogger(__name__)

project_root = get_project_root()
METADATA_DIR = project_root / "data" / "metadata"
PROMPT_FILES = get_prompt_files()

class TitleGenerator:
    """标题生成器（支持断点续传）"""

    def __init__(self, metadata_dir: Optional[Path] = None, prompt_files: Optional[Dict[str, Path]] = None,
                 progress_callback: Optional[Callable[[int, str], None]] = None,
                 enable_checkpoint: bool = True) -> None:
        self.llm_client = LLMClient()
        self.step_aware_llm_client = get_step_aware_llm_client()
        self.text_processor = TextProcessor()
        self.progress_callback = progress_callback
        self.enable_checkpoint = enable_checkpoint

        # 加载提示词
        prompt_files_to_use = prompt_files if prompt_files is not None else PROMPT_FILES
        with open(prompt_files_to_use['title'], 'r', encoding='utf-8') as f:
            self.title_prompt = f.read()

        # 初始化目录结构
        self._init_directories(metadata_dir)

    def _call_llm(self, prompt: str, input_data: Any) -> str:
        """使用步骤感知LLM客户端调用API（支持在ThreadPoolExecutor中运行）"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                
                def run_in_thread():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(
                            self.step_aware_llm_client.call_for_step(
                                StepType.STEP5_TITLE,
                                prompt=prompt,
                                input_data=input_data
                            )
                        )
                    finally:
                        new_loop.close()
                
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_in_thread)
                    return future.result(timeout=300)
            else:
                return loop.run_until_complete(
                    self.step_aware_llm_client.call_for_step(
                        StepType.STEP5_TITLE,
                        prompt=prompt,
                        input_data=input_data
                    )
                )
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(
                    self.step_aware_llm_client.call_for_step(
                        StepType.STEP5_TITLE,
                        prompt=prompt,
                        input_data=input_data
                    )
                )
            finally:
                loop.close()

    def _init_directories(self, metadata_dir: Optional[Path]) -> None:
        """初始化目录结构"""
        # 使用传入的metadata_dir或默认值
        if metadata_dir is None:
            metadata_dir = METADATA_DIR
        self.metadata_dir = metadata_dir
        self.llm_raw_output_dir = self.metadata_dir / "step4_llm_raw_output"

        # 初始化断点管理器
        self.checkpoint_manager = CheckpointManager(
            self.metadata_dir, "step4_title", self.enable_checkpoint
        )
    
    def generate_titles(self, high_score_clips: List[Dict]) -> List[Dict]:
        """
        为高分切片生成标题（按块批量处理，支持断点续传）
        """
        if not high_score_clips:
            return []

        logger.info(f"开始为 {len(high_score_clips)} 个高分片段进行批量标题生成（支持断点续传）...")

        self.llm_raw_output_dir.mkdir(parents=True, exist_ok=True)

        # 按 chunk_index 对所有 clips 进行分组
        clips_by_chunk = defaultdict(list)
        for clip in high_score_clips:
            clips_by_chunk[clip.get('chunk_index', 0)].append(clip)

        # 加载断点
        completed_chunks = self.checkpoint_manager.load_checkpoint()
        all_clips_with_titles = self.checkpoint_manager.load_intermediate_results()

        if completed_chunks:
            logger.info(f"检测到已完成的块: {sorted(completed_chunks)}，将跳过这些块")

        # 过滤出需要处理的块
        pending_chunks = {
            chunk_index: chunk_clips
            for chunk_index, chunk_clips in clips_by_chunk.items()
            if chunk_index not in completed_chunks
        }

        if not pending_chunks:
            logger.info("所有块已完成处理，跳过")
            return all_clips_with_titles

        logger.info(f"待处理块数量: {len(pending_chunks)}/{len(clips_by_chunk)}")

        # 初始化进度跟踪器
        total_chunks = len(clips_by_chunk)
        completed_count = len(completed_chunks)
        tracker = ProgressTracker(total_chunks, self.progress_callback)

        # 恢复初始进度
        if completed_count > 0:
            tracker.set_progress(completed_count, f"已恢复进度 {completed_count}/{total_chunks} 个块")

        # 处理每个待处理的块
        for chunk_index, chunk_clips in pending_chunks.items():
            logger.info(f"处理块 {chunk_index}，其中包含 {len(chunk_clips)} 个片段...")

            try:
                logger.info(f"  > 开始调用API生成标题...")
                input_for_llm = [
                    {
                        "id": clip.get('id'),
                        "title": clip.get('outline'),  # 使用outline字段作为title
                        "content": clip.get('content'),
                        "recommend_reason": clip.get('recommend_reason')
                    } for clip in chunk_clips
                ]

                raw_response = self._call_llm(self.title_prompt, input_for_llm)

                if raw_response:
                    # 保存LLM原始响应用于调试（但不用作缓存）
                    llm_cache_path = self.llm_raw_output_dir / f"chunk_{chunk_index}.txt"
                    with open(llm_cache_path, 'w', encoding='utf-8') as f:
                        f.write(raw_response)
                    logger.info(f"  > LLM原始响应已保存到 {llm_cache_path}")
                    titles_map = self.llm_client.parse_json_response(raw_response)
                else:
                    titles_map = {}

                if not isinstance(titles_map, dict):
                    logger.warning(f"  > LLM返回的标题不是一个字典: {titles_map}，跳过该块。")
                    # 即使失败，也把原始片段加回去，避免数据丢失
                    all_clips_with_titles.extend(chunk_clips)
                    tracker.update(f"处理块 {chunk_index} 失败")
                    continue

                for clip in chunk_clips:
                    clip_id = clip.get('id')
                    generated_title = titles_map.get(clip_id)
                    if generated_title and isinstance(generated_title, str):
                        clip['generated_title'] = generated_title
                        # 安全地获取outline标题用于日志显示
                        outline = clip.get('outline', {})
                        if isinstance(outline, dict):
                            title = outline.get('title', '未知标题')
                        else:
                            title = str(outline)
                        logger.info(f"  > 为片段 {clip_id} ('{title[:20]}...') 生成标题: {generated_title}")
                    else:
                        clip['generated_title'] = clip.get('outline', f"片段_{clip_id}")  # 使用outline作为fallback
                        logger.warning(f"  > 未能为片段 {clip_id} 找到或解析标题，使用原始outline")

                all_clips_with_titles.extend(chunk_clips)

                # 保存断点
                self.checkpoint_manager.save_checkpoint(chunk_index, success=True, item_info={"chunk_file": f"chunk_{chunk_index}.json"})

                # 更新进度
                tracker.update(f"正在处理块 {chunk_index}...")

            except Exception as e:
                logger.error(f"  > 为块 {chunk_index} 生成标题时出错: {e}")
                # 即使出错，也添加原始数据以防丢失
                all_clips_with_titles.extend(chunk_clips)
                tracker.update(f"处理块 {chunk_index} 失败")
                continue

        # 保存中间结果
        self.checkpoint_manager.save_intermediate_results(all_clips_with_titles)

        # 不清理断点，保留用于断点续传
        # 只有在整个流程完全成功后才应该清理断点
        # self.checkpoint_manager.cleanup_checkpoint()

        logger.info("所有高分片段标题生成完成")
        return all_clips_with_titles
        
    def save_clips_with_titles(self, clips_with_titles: List[Dict], output_path: Path):
        """保存带标题的片段数据"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(clips_with_titles, f, ensure_ascii=False, indent=2)
        logger.info(f"带标题的片段数据已保存到: {output_path}")

def run_step4_title(high_score_clips_path: Path, output_path: Optional[Path] = None, metadata_dir: Optional[str] = None, prompt_files: Optional[Dict[str, Path]] = None, progress_callback: Optional[Callable[[int, str], None]] = None, enable_checkpoint: bool = True) -> List[Dict[str, Any]]:
    """
    运行Step 4: 标题生成（支持断点续传）

    Args:
        high_score_clips_path: 高分切片文件路径
        output_path: 输出文件路径，默认为step4_titles.json
        metadata_dir: 元数据目录路径
        prompt_files: 自定义提示词文件
        progress_callback: 进度回调函数 (progress: int, message: str) -> None
        enable_checkpoint: 是否启用断点续传，默认为True

    Returns:
        带标题的切片列表

    Note:
        此步骤只保存step4_titles.json文件，包含带标题的片段数据。
        clips_metadata.json文件将在step5中统一保存，避免重复保存。
    """
    # 加载高分片段
    with open(high_score_clips_path, 'r', encoding='utf-8') as f:
        high_score_clips = json.load(f)

    # 如果高分片段为空，尝试使用所有评分片段作为fallback
    if not high_score_clips:
        logger.warning("高分片段为空，尝试使用所有评分片段作为fallback")
        all_scored_path = Path(metadata_dir) / "step3_all_scored.json"
        if all_scored_path.exists():
            with open(all_scored_path, 'r', encoding='utf-8') as f:
                high_score_clips = json.load(f)
            logger.info(f"从step3_all_scored.json加载了 {len(high_score_clips)} 个片段")
        else:
            logger.error("step3_all_scored.json不存在，无法生成标题")
            return []

    # 创建标题生成器
    if metadata_dir is None:
        metadata_dir = str(METADATA_DIR)
    title_generator = TitleGenerator(metadata_dir=Path(metadata_dir), prompt_files=prompt_files, progress_callback=progress_callback, enable_checkpoint=enable_checkpoint)

    # 生成标题
    clips_with_titles = title_generator.generate_titles(high_score_clips)

    # 确定输出路径
    if metadata_dir is None:
        metadata_dir = str(METADATA_DIR)

    if output_path is None:
        output_path = Path(metadata_dir) / "step4_titles.json"

    # 保存带标题的片段数据到step4_titles.json
    title_generator.save_clips_with_titles(clips_with_titles, output_path)

    # 重要说明：clips_metadata.json将在step5中保存，这里不重复保存
    # 这样可以避免数据重复和保存逻辑混乱

    return clips_with_titles