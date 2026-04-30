"""Step 1: 大纲提取 - 从转写文本中提取结构性大纲"""
import json
import logging
import re
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path

# 导入依赖
from utils.llm_client import LLMClient
from utils.step_aware_llm_client import StepAwareLLMClient
from utils.text_processor import TextProcessor
from utils.checkpoint_manager import CheckpointManager, ProgressTracker
from core.unified_config import get_prompt_files, get_config
from core.step_config import StepType
from core.config import get_project_root

logger = logging.getLogger(__name__)

project_root = get_project_root()
METADATA_DIR = project_root / "data" / "metadata"
PROMPT_FILES = get_prompt_files()

class OutlineExtractor:
    """大纲提取器（支持断点续传）"""

    def __init__(self, metadata_dir: Optional[Path] = None, prompt_files: Optional[Dict[str, Path]] = None,
                 progress_callback: Optional[Callable[[int, str], None]] = None,
                 enable_checkpoint: bool = True) -> None:
        self.llm_client = LLMClient()
        self.step_aware_llm_client = StepAwareLLMClient()
        self.text_processor = TextProcessor()
        self.progress_callback = progress_callback
        self.enable_checkpoint = enable_checkpoint

        # 使用传入的metadata_dir或默认值
        if metadata_dir is None:
            config = get_config()
            metadata_dir = config.paths.output_dir / "metadata"
        self.metadata_dir = metadata_dir

        # 初始化断点管理器
        self.checkpoint_manager = CheckpointManager(
            self.metadata_dir, "step1", enable_checkpoint
        )

        # 使用传入的prompt_files或默认值
        if prompt_files is None:
            prompt_files = get_prompt_files()

        # 加载提示词
        with open(prompt_files['outline'], 'r', encoding='utf-8') as f:
            self.outline_prompt = f.read()

        # 创建用于存放中间文本块的目录
        self.chunks_dir = self.metadata_dir / "step1_chunks"
        self.chunks_dir.mkdir(parents=True, exist_ok=True)
        # 创建用于存放中间SRT块的目录
        self.srt_chunks_dir = self.metadata_dir / "step1_srt_chunks"
        self.srt_chunks_dir.mkdir(parents=True, exist_ok=True)
        # 创建用于存放LLM原始输出的目录
        self.llm_raw_output_dir = self.metadata_dir / "step1_llm_raw_output"
        self.llm_raw_output_dir.mkdir(parents=True, exist_ok=True)

    async def extract_outline(self, srt_path: Path) -> List[Dict]:
        """
        从SRT文件提取视频大纲（支持断点续传）

        Args:
            srt_path: SRT文件路径

        Returns:
            视频大纲列表
        """
        logger.info("开始提取视频大纲...")

        # 1. 解析SRT文件
        try:
            srt_data = self.text_processor.parse_srt(srt_path)
            if not srt_data:
                logger.warning("SRT文件为空或解析失败")
                return []
        except Exception as e:
            logger.error(f"解析SRT文件失败: {e}")
            return []

        # 2. 基于时间智能分块
        chunks = self.text_processor.chunk_srt_data(srt_data, interval_minutes=30)
        logger.info(f"文本已按~30分钟/块切分，共{len(chunks)}个块")

        # 3. 保存文本块和SRT块到中间文件
        chunk_files = self._save_chunks_to_files(chunks)
        self._save_srt_chunks(chunks)

        # 4. 加载断点
        completed_chunks = self.checkpoint_manager.load_checkpoint()
        all_outlines = self.checkpoint_manager.load_intermediate_results()

        if completed_chunks:
            logger.info(f"检测到已完成的块: {sorted(completed_chunks)}，将跳过这些块")

        # 5. 过滤出需要处理的块
        pending_chunks = [
            (i, chunk_file)
            for i, chunk_file in enumerate(chunk_files)
            if i not in completed_chunks
        ]

        if not pending_chunks:
            logger.info("所有块已完成处理，跳过")
            return all_outlines

        logger.info(f"待处理块数量: {len(pending_chunks)}/{len(chunk_files)}")

        # 6. 初始化进度跟踪器
        total_chunks = len(chunk_files)
        completed_count = len(completed_chunks)
        tracker = ProgressTracker(total_chunks, self.progress_callback)

        # 7. 恢复初始进度
        if completed_count > 0:
            tracker.set_progress(completed_count, f"已恢复进度 {completed_count}/{total_chunks} 个块")

        # 8. 处理每个待处理的文本块
        for i, chunk_file in pending_chunks:
            try:
                logger.info(f"处理第{i+1}/{total_chunks}个文本块: {chunk_file.name}")

                # 读取文本块内容
                with open(chunk_file, 'r', encoding='utf-8') as f:
                    chunk_text = f.read()

                # 为每个块调用LLM（带进度回调）
                input_data = {"text": chunk_text}
                response = await self.step_aware_llm_client.call_for_step(
                    StepType.STEP1_OUTLINE,
                    self.outline_prompt,
                    input_data,
                    progress_callback=self.progress_callback
                )

                if response:
                    # 保存原始响应
                    raw_output_file = self.llm_raw_output_dir / f"chunk_{i}_raw_output.txt"
                    with open(raw_output_file, 'w', encoding='utf-8') as f:
                        f.write(response)
                    # 解析响应并附加块索引
                    parsed_outlines = self._parse_outline_response(response, i)
                    all_outlines.extend(parsed_outlines)

                    # 保存断点和中间结果
                    self.checkpoint_manager.save_checkpoint(i, success=True, item_info={"chunk_file": str(chunk_file.name)})
                    self.checkpoint_manager.save_intermediate_results(all_outlines)

                    # 更新进度
                    tracker.update(f"正在处理第 {i+1}/{total_chunks} 个文本块...")

                    logger.info(f"块 {i} 处理完成，生成 {len(parsed_outlines)} 个话题")
                else:
                    logger.warning(f"处理第{i+1}个文本块时返回空响应")
                    # 失败的块不保存断点，下次会重试
                    tracker.update(f"处理第 {i+1} 个文本块失败")

            except Exception as e:
                logger.error(f"处理第{i+1}个文本块失败: {e}")
                tracker.update(f"处理第 {i+1} 个文本块失败")
                continue

        # 9. 合并和去重
        final_outlines = self._merge_outlines(all_outlines)

        logger.info(f"大纲提取完成，共{len(final_outlines)}个话题")

        # 不清理断点，保留用于断点续传
        # 只有在整个流程完全成功后才应该清理断点
        # self.checkpoint_manager.cleanup_checkpoint()

        return final_outlines

    def _save_chunks_to_files(self, chunks: List[Dict]) -> List[Path]:
        """将文本块保存为单独的 .txt 文件"""
        chunk_files = []
        for chunk in chunks:
            chunk_index = chunk['chunk_index']
            text_content = chunk['text']
            file_path = self.chunks_dir / f"chunk_{chunk_index}.txt"

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(text_content)
            chunk_files.append(file_path)

        logger.info(f"所有文本块已保存到: {self.chunks_dir}")
        return chunk_files

    def _save_srt_chunks(self, chunks: List[Dict]):
        """将SRT数据块保存为单独的 .json 文件"""
        for chunk in chunks:
            chunk_index = chunk['chunk_index']
            srt_entries = chunk['srt_entries']
            file_path = self.srt_chunks_dir / f"chunk_{chunk_index}.json"

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(srt_entries, f, ensure_ascii=False, indent=2)

        logger.info(f"所有SRT块已保存到: {self.srt_chunks_dir}")

    def _parse_outline_response(self, response: str, chunk_index: int) -> List[Dict]:
        """
        解析大模型的大纲响应

        Args:
            response: 大模型响应
            chunk_index: 当前处理的块索引

        Returns:
            解析后的大纲结构
        """
        outlines = []
        lines = response.split('\n')
        current_outline = None

        for line in lines:
            line = line.strip()

            if re.match(r'^\d+\.\s*\*\*', line):
                if current_outline:
                    outlines.append(current_outline)

                topic_name = line.split('**')[1] if '**' in line else line.split('.', 1)[1].strip()
                current_outline = {
                    'title': topic_name,
                    'subtopics': [],
                    'chunk_index': chunk_index
                }

            elif line.startswith('-') and current_outline:
                subtopic = line[1:].strip()
                if subtopic and len(subtopic) <= 200:
                    current_outline['subtopics'].append(subtopic)

        if current_outline:
            outlines.append(current_outline)

        return outlines

    def _merge_outlines(self, outlines: List[Dict]) -> List[Dict]:
        """
        合并和去重大纲，保留最先出现的版本
        """
        unique_outlines = {}
        for outline in outlines:
            title = outline['title']
            if title not in unique_outlines:
                unique_outlines[title] = outline
        return list(unique_outlines.values())

    def save_outline(self, outlines: List[Dict], output_path: Optional[Path] = None) -> Path:
        """
        保存大纲到文件
        """
        if output_path is None:
            output_path = self.metadata_dir / "step1_outline.json"

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(outlines, f, ensure_ascii=False, indent=2)

        logger.info(f"大纲已保存到: {output_path}")
        return output_path

    def load_outline(self, input_path: Path) -> List[Dict]:
        """
        从文件加载大纲
        """
        with open(input_path, 'r', encoding='utf-8') as f:
            return json.load(f)

async def run_step1_outline(srt_path: Path, metadata_dir: Optional[Path] = None, output_path: Optional[Path] = None,
                     prompt_files: Optional[Dict[str, Path]] = None, progress_callback: Optional[Callable[[int, str], None]] = None,
                     enable_checkpoint: bool = True) -> List[Dict[str, Any]]:
    """
    运行Step 1: 大纲提取（支持断点续传和进度回调）

    Args:
        srt_path: SRT文件路径
        metadata_dir: 元数据目录
        output_path: 输出文件路径
        prompt_files: 提示词文件字典
        progress_callback: 进度回调函数 (progress: int, message: str) -> None
        enable_checkpoint: 是否启用断点续传，默认为True
    
    Returns:
        大纲列表
    """
    if metadata_dir is None:
        metadata_dir = METADATA_DIR

    extractor = OutlineExtractor(metadata_dir, prompt_files, progress_callback, enable_checkpoint)
    outlines = await extractor.extract_outline(srt_path)

    if output_path is None:
        output_path = metadata_dir / "step1_outline.json"

    extractor.save_outline(outlines, output_path)

    return outlines
