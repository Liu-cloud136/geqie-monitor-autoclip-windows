"""
Step 2: 时间线提取 - 为大纲中的每个话题定位具体时间区间（优化版本）
优化：
1. 支持并发处理多个块，提高处理速度
2. 减少重试次数，快速失败
3. 增加输入大小检查，分批处理
4. 支持断点续传
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

class TimelineExtractor:
    """从大纲和SRT字幕中提取精确时间线（优化版本）"""

    # 限制输入数据大小
    MAX_INPUT_CHARS = 8000  # 单次LLM调用的最大输入字符数
    MAX_OUTLINES_PER_CALL = 10  # 单次LLM调用的最大大纲数量

    def __init__(self, metadata_dir: Optional[Path] = None, prompt_files: Optional[Dict[str, Path]] = None,
                 progress_callback: Optional[Callable[[int, str], None]] = None,
                 enable_checkpoint: bool = True) -> None:
        self.llm_client = LLMClient()
        self.step_aware_llm_client = get_step_aware_llm_client()
        self.text_processor = TextProcessor()
        self.progress_callback = progress_callback
        self.enable_checkpoint = enable_checkpoint

        # 使用传入的metadata_dir或默认值
        if metadata_dir is None:
            metadata_dir = METADATA_DIR
        self.metadata_dir = metadata_dir

        # 初始化断点管理器
        self.checkpoint_manager = CheckpointManager(
            self.metadata_dir, "step2", enable_checkpoint
        )

        # 加载提示词
        prompt_files_to_use = prompt_files if prompt_files is not None else PROMPT_FILES
        with open(prompt_files_to_use['timeline'], 'r', encoding='utf-8') as f:
            self.timeline_prompt = f.read()

        # SRT块的目录
        self.srt_chunks_dir = self.metadata_dir / "step1_srt_chunks"
        self.timeline_chunks_dir = self.metadata_dir / "step2_timeline_chunks"
        self.llm_raw_output_dir = self.metadata_dir / "step2_llm_raw_output"

        # 并发控制：最大同时处理的块数
        self.max_concurrent_chunks = 3

    def _call_llm(self, prompt: str, input_data: Any) -> str:
        """使用步骤感知LLM客户端调用API（支持在ThreadPoolExecutor中运行）"""
        import asyncio
        try:
            # 尝试获取现有的事件循环
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果事件循环正在运行，使用线程池执行
                import concurrent.futures
                
                def run_in_thread():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(
                            self.step_aware_llm_client.call_for_step(
                                StepType.STEP2_TIMELINE,
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
                        StepType.STEP2_TIMELINE,
                        prompt=prompt,
                        input_data=input_data
                    )
                )
        except RuntimeError:
            # 没有事件循环，创建新的
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(
                    self.step_aware_llm_client.call_for_step(
                        StepType.STEP2_TIMELINE,
                        prompt=prompt,
                        input_data=input_data
                    )
                )
            finally:
                loop.close()

    def extract_timeline(self, outlines: List[Dict]) -> List[Dict]:
        """
        提取话题时间区间（优化并发版本，支持断点续传）

        Args:
            outlines: 大纲列表

        Returns:
            时间线数据列表
        """
        logger.info(f"【优化版】开始提取话题时间区间，共 {len(outlines)} 个话题...")

        if not outlines:
            logger.warning("大纲数据为空，无法提取时间线。")
            return []

        if not self.srt_chunks_dir.exists():
            logger.error(f"SRT块目录不存在: {self.srt_chunks_dir}。请先运行Step 1。")
            return []

        # 1. 创建本步骤需要的目录
        self.timeline_chunks_dir.mkdir(parents=True, exist_ok=True)
        self.llm_raw_output_dir.mkdir(parents=True, exist_ok=True)

        # 2. 按 chunk_index 对所有大纲进行分组
        outlines_by_chunk = defaultdict(list)
        for outline in outlines:
            chunk_index = outline.get('chunk_index')
            if chunk_index is not None:
                outlines_by_chunk[chunk_index].append(outline)
            else:
                logger.warning(f"  > 话题 '{outline.get('title', '未知')}' 缺少 chunk_index，将被跳过。")

        # 3. 加载断点
        completed_chunks = self.checkpoint_manager.load_checkpoint()
        all_timeline_data = self.checkpoint_manager.load_intermediate_results()

        if completed_chunks:
            logger.info(f"检测到已完成的块: {sorted(completed_chunks)}，将跳过这些块")

        # 4. 过滤出需要处理的块
        pending_chunks = {
            chunk_index: chunk_outlines
            for chunk_index, chunk_outlines in outlines_by_chunk.items()
            if chunk_index not in completed_chunks
        }

        if not pending_chunks:
            logger.info("所有块已完成处理，跳过")
            return all_timeline_data

        logger.info(f"待处理块数量: {len(pending_chunks)}/{len(outlines_by_chunk)}")

        # 5. 初始化进度跟踪器
        total_chunks = len(outlines_by_chunk)
        completed_count = len(completed_chunks)
        tracker = ProgressTracker(total_chunks, self.progress_callback)

        # 6. 恢复初始进度
        if completed_count > 0:
            tracker.set_progress(completed_count, f"已恢复进度 {completed_count}/{total_chunks} 个块")

        # 7. 使用并发处理多个块
        chunk_count = len(pending_chunks)
        logger.info(f"【优化版】开始并发处理 {chunk_count} 个块，最大并发数: {self.max_concurrent_chunks}")

        try:
            # 检查是否在异步上下文中运行
            try:
                loop = asyncio.get_running_loop()
                # 如果在异步上下文中运行，使用线程池执行
                import concurrent.futures
                
                def run_concurrent_processing():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        # 创建异步任务列表
                        tasks = [
                            self._process_chunk_async(chunk_index, chunk_outlines)
                            for chunk_index, chunk_outlines in pending_chunks.items()
                        ]
                        
                        # 使用 asyncio.gather 并发执行
                        results = new_loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
                        
                        # 处理结果
                        timeline_results = []
                        for i, result in enumerate(results):
                            if isinstance(result, Exception):
                                logger.error(f"块处理异常: {result}")
                            elif result:
                                timeline_results.extend(result)
                        
                        return timeline_results
                    finally:
                        new_loop.close()
                
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_concurrent_processing)
                    all_timeline_data.extend(future.result())
                    
            except RuntimeError:
                # 不在异步上下文中运行，直接创建事件循环
                # 创建新的事件循环来运行异步任务
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    # 创建异步任务列表
                    tasks = [
                        self._process_chunk_async(chunk_index, chunk_outlines)
                        for chunk_index, chunk_outlines in pending_chunks.items()
                    ]

                    # 使用 asyncio.gather 并发执行
                    results = loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))

                    # 处理结果
                    for i, result in enumerate(results):
                        if isinstance(result, Exception):
                            logger.error(f"块处理异常: {result}")
                        elif result:
                            all_timeline_data.extend(result)

                    logger.info(f"【优化版】并发处理完成，成功获取 {len(all_timeline_data)} 个时间段")
                finally:
                    loop.close()
        except Exception as e:
            logger.error(f"并发处理失败: {e}")
            raise

        # 8. 最终排序和ID分配
        if all_timeline_data:
            logger.info("按开始时间对所有话题进行最终排序...")
            try:
                all_timeline_data.sort(key=lambda x: self.text_processor.time_to_seconds(x['start_time']))
                logger.info("排序完成。")

                # 为所有片段按时间顺序分配固定的ID
                logger.info("为所有片段按时间顺序分配固定ID...")
                for i, timeline_item in enumerate(all_timeline_data):
                    timeline_item['id'] = str(i + 1)
                logger.info(f"已为 {len(all_timeline_data)} 个片段分配了固定ID（1-{len(all_timeline_data)}）")

            except Exception as e:
                logger.error(f"对最终结果排序时出错: {e}。返回未排序的结果。")

        # 9. 保存中间结果
        self.checkpoint_manager.save_intermediate_results(all_timeline_data)

        # 10. 不清理断点，保留用于断点续传
        # 只有在整个流程完全成功后才应该清理断点
        # self.checkpoint_manager.cleanup_checkpoint()

        return all_timeline_data

    async def _process_chunk_async(self, chunk_index: int, chunk_outlines: List[Dict]) -> Optional[List[Dict]]:
        """
        异步处理单个块（优化版本）

        Args:
            chunk_index: 块索引
            chunk_outlines: 该块的大纲列表

        Returns:
            该块的时间线数据，失败返回None
        """
        logger.info(f"[并发] 处理块 {chunk_index}，包含 {len(chunk_outlines)} 个话题...")

        try:
            # 加载SRT块文件
            srt_chunk_path = self.srt_chunks_dir / f"chunk_{chunk_index}.json"
            if not srt_chunk_path.exists():
                logger.warning(f"[并发] 块 {chunk_index} 的SRT文件不存在，跳过")
                return None

            with open(srt_chunk_path, 'r', encoding='utf-8') as f:
                srt_chunk_data = json.load(f)

            if not srt_chunk_data:
                logger.warning(f"[并发] 块 {chunk_index} 的SRT数据为空，跳过")
                return None

            # 获取时间范围信息
            chunk_start_time = srt_chunk_data[0]['start_time']
            chunk_end_time = srt_chunk_data[-1]['end_time']

            # 检查输出是否已存在
            chunk_output_path = self.timeline_chunks_dir / f"chunk_{chunk_index}.json"
            if chunk_output_path.exists():
                logger.info(f"[并发] 块 {chunk_index} 已存在输出，跳过处理")
                with open(chunk_output_path, 'r', encoding='utf-8') as f:
                    return json.load(f)

            # 构建用于LLM的SRT文本
            srt_text_for_prompt = ""
            for sub in srt_chunk_data:
                srt_text_for_prompt += f"{sub['index']}\\n{sub['start_time']} --> {sub['end_time']}\\n{sub['text']}\\n\\n"

            # 检查输入大小，如果过大则分批处理
            if len(srt_text_for_prompt) > self.MAX_INPUT_CHARS:
                logger.warning(f"[并发] 块 {chunk_index} 的SRT文本过长({len(srt_text_for_prompt)}字符)，将分批处理")
                return await self._process_chunk_with_srt_batches(
                    chunk_index, chunk_outlines, srt_chunk_data
                )

            # 检查大纲数量，如果过多则分批处理
            if len(chunk_outlines) > self.MAX_OUTLINES_PER_CALL:
                logger.warning(f"[并发] 块 {chunk_index} 的大纲数量过多({len(chunk_outlines)}个)，将分批处理")
                return await self._process_chunk_in_batches(
                    chunk_index, chunk_outlines, srt_text_for_prompt, chunk_start_time, chunk_end_time
                )

            # 为LLM准备输入数据
            llm_input_outlines = [
                {"title": o.get("title"), "subtopics": o.get("subtopics")}
                for o in chunk_outlines
            ]

            input_data = {
                "outline": llm_input_outlines,
                "srt_text": srt_text_for_prompt
            }

            # 调用LLM（减少重试次数）
            max_parse_retries = 1
            parsed_items = None

            for retry_count in range(max_parse_retries + 1):
                try:
                    raw_response = self._call_llm(self.timeline_prompt, input_data)

                    if not raw_response:
                        logger.warning(f"[并发] 块 {chunk_index} LLM响应为空，跳过")
                        break

                    # 保存原始响应
                    cache_file = self.llm_raw_output_dir / f"chunk_{chunk_index}_attempt_{retry_count}.txt"
                    with open(cache_file, 'w', encoding='utf-8') as f:
                        f.write(raw_response)

                    # 解析响应
                    parsed_items = self._parse_and_validate_response(
                        raw_response,
                        chunk_start_time,
                        chunk_end_time,
                        chunk_index
                    )

                    if parsed_items:
                        # 保存结果
                        with open(chunk_output_path, 'w', encoding='utf-8') as f:
                            json.dump(parsed_items, f, ensure_ascii=False, indent=2)
                        logger.info(f"[并发] 块 {chunk_index} 成功解析 {len(parsed_items)} 个时间段")

                        # 保存断点
                        self.checkpoint_manager.save_checkpoint(chunk_index, success=True, item_info={"chunk_file": f"chunk_{chunk_index}.json"})
                        break

                except Exception as e:
                    logger.warning(f"[并发] 块 {chunk_index} 处理失败（尝试 {retry_count + 1}/{max_parse_retries + 1}）: {e}")

            if not parsed_items:
                logger.error(f"[并发] 块 {chunk_index} 所有尝试均失败")
                return None

            return parsed_items

        except Exception as e:
            logger.error(f"[并发] 块 {chunk_index} 处理异常: {e}")
            return None

    async def _process_chunk_in_batches(
        self, chunk_index: int, chunk_outlines: List[Dict],
        srt_text: str, chunk_start_time: str, chunk_end_time: str
    ) -> List[Dict]:
        """分批处理大量的Outline"""
        all_results = []

        # 将大纲分成多批
        batches = [
            chunk_outlines[i:i + self.MAX_OUTLINES_PER_CALL]
            for i in range(0, len(chunk_outlines), self.MAX_OUTLINES_PER_CALL)
        ]

        logger.info(f"[并发] 块 {chunk_index} 分成 {len(batches)} 批处理")

        for batch_idx, batch in enumerate(batches):
            logger.info(f"[并发] 块 {chunk_index} 批 {batch_idx + 1}/{len(batches)}，包含 {len(batch)} 个大纲")

            llm_input_outlines = [
                {"title": o.get("title"), "subtopics": o.get("subtopics")}
                for o in batch
            ]

            input_data = {
                "outline": llm_input_outlines,
                "srt_text": srt_text
            }

            try:
                raw_response = self._call_llm(self.timeline_prompt, input_data)

                if raw_response:
                    parsed_items = self._parse_and_validate_response(
                        raw_response, chunk_start_time, chunk_end_time, chunk_index
                    )
                    if parsed_items:
                        all_results.extend(parsed_items)
                        logger.info(f"[并发] 块 {chunk_index} 批 {batch_idx + 1} 获取 {len(parsed_items)} 个时间段")

            except Exception as e:
                logger.error(f"[并发] 块 {chunk_index} 批 {batch_idx + 1} 处理失败: {e}")

        return all_results

    async def _process_chunk_with_srt_batches(
        self, chunk_index: int, chunk_outlines: List[Dict], srt_chunk_data: List[Dict]
    ) -> List[Dict]:
        """
        当SRT文本过长时，将SRT分成多个批次，每个批次只处理该批次时间范围内的话题
        这样可以提高准确性和效率
        """
        all_results = []
        
        # 计算需要多少批次
        total_chars = sum(len(f"{sub['index']}\\n{sub['start_time']} --> {sub['end_time']}\\n{sub['text']}\\n\\n") 
                          for sub in srt_chunk_data)
        num_batches = (total_chars + self.MAX_INPUT_CHARS - 1) // self.MAX_INPUT_CHARS
        
        logger.info(f"[并发] 块 {chunk_index} 的SRT将分成 {num_batches} 批处理")
        
        # 将SRT数据分成多个批次
        batch_size = (len(srt_chunk_data) + num_batches - 1) // num_batches
        srt_batches = [
            srt_chunk_data[i:i + batch_size]
            for i in range(0, len(srt_chunk_data), batch_size)
        ]
        
        # 为每个批次分配话题
        # 假设话题是按时间顺序排列的，均匀分配到各个批次
        outlines_per_batch = (len(chunk_outlines) + num_batches - 1) // num_batches
        
        for batch_idx, srt_batch in enumerate(srt_batches):
            logger.info(f"[并发] 块 {chunk_index} SRT批 {batch_idx + 1}/{len(srt_batches)}，包含 {len(srt_batch)} 条字幕")
            
            # 获取当前批次应该处理的话题
            start_outline_idx = batch_idx * outlines_per_batch
            end_outline_idx = min(start_outline_idx + outlines_per_batch, len(chunk_outlines))
            current_batch_outlines = chunk_outlines[start_outline_idx:end_outline_idx]
            
            logger.info(f"[并发] 块 {chunk_index} SRT批 {batch_idx + 1} 处理话题 {start_outline_idx + 1}-{end_outline_idx}，共 {len(current_batch_outlines)} 个话题")
            
            # 构建当前批次的SRT文本
            srt_text_for_batch = ""
            for sub in srt_batch:
                srt_text_for_batch += f"{sub['index']}\\n{sub['start_time']} --> {sub['end_time']}\\n{sub['text']}\\n\\n"
            
            # 获取当前批次的时间范围
            batch_start_time = srt_batch[0]['start_time']
            batch_end_time = srt_batch[-1]['end_time']
            
            # 为LLM准备输入数据（只包含当前批次的话题）
            llm_input_outlines = [
                {"title": o.get("title"), "subtopics": o.get("subtopics")}
                for o in current_batch_outlines
            ]
            
            input_data = {
                "outline": llm_input_outlines,
                "srt_text": srt_text_for_batch
            }
            
            try:
                raw_response = self._call_llm(self.timeline_prompt, input_data)
                
                if raw_response:
                    # 为每个批次保存独立的调试文件
                    self._save_debug_response(raw_response, chunk_index, f"batch_{batch_idx + 1}_response")
                    
                    parsed_items = self._parse_and_validate_response(
                        raw_response, batch_start_time, batch_end_time, chunk_index
                    )
                    
                    if parsed_items:
                        all_results.extend(parsed_items)
                        logger.info(f"[并发] 块 {chunk_index} SRT批 {batch_idx + 1} 获取 {len(parsed_items)} 个时间段")
            
            except Exception as e:
                logger.error(f"[并发] 块 {chunk_index} SRT批 {batch_idx + 1} 处理失败: {e}")
        
        logger.info(f"[并发] 块 {chunk_index} 总共获取 {len(all_results)} 个时间段")
        return all_results

    def _parse_and_validate_response(self, response: str, chunk_start: str, chunk_end: str, chunk_index: int) -> List[Dict]:
        """解析并验证LLM响应"""
        validated_items = []

        # 保存原始响应用于调试
        self._save_debug_response(response, chunk_index, "original_response")

        try:
            # 尝试解析JSON
            parsed_response = self.llm_client.parse_json_response(response)

            # 验证JSON结构
            if not self.llm_client._validate_json_structure(parsed_response):
                logger.error(f"  > 块 {chunk_index} JSON结构验证失败")
                self._save_debug_response(str(parsed_response), chunk_index, "invalid_structure")
                return []

            if not isinstance(parsed_response, list):
                logger.warning(f"  > 块 {chunk_index} LLM返回的不是一个列表")
                self._save_debug_response(f"类型: {type(parsed_response)}, 内容: {parsed_response}", chunk_index, "not_list")
                return []

            # 处理每个时间段
            for item in parsed_response:
                validated_item = self._validate_time_range(item, chunk_start, chunk_end, chunk_index)
                if validated_item:
                    validated_items.append(validated_item)

            logger.info(f"块 {chunk_index} 验证通过 {len(validated_items)} 个时间段")
            return validated_items

        except Exception as e:
            logger.error(f"块 {chunk_index} 解析响应失败: {e}")
            return []

    def _validate_time_range(self, item: Dict, chunk_start: str, chunk_end: str, chunk_index: int) -> Optional[Dict]:
        """验证并调整时间范围"""
        try:
            start_time = item.get('start_time', '')
            end_time = item.get('end_time', '')

            if not start_time or not end_time:
                return None

            # 转换时间格式
            start_time = self._convert_time_format(start_time)
            end_time = self._convert_time_format(end_time)

            # 转换为秒数
            start_seconds = self.text_processor.time_to_seconds(start_time)
            end_seconds = self.text_processor.time_to_seconds(end_time)
            chunk_start_seconds = self.text_processor.time_to_seconds(chunk_start)
            chunk_end_seconds = self.text_processor.time_to_seconds(chunk_end)

            # 调整时间范围到块边界
            if start_seconds < chunk_start_seconds:
                start_seconds = chunk_start_seconds
                start_time = chunk_start

            if end_seconds > chunk_end_seconds:
                end_seconds = chunk_end_seconds
                end_time = chunk_end

            # 验证时间范围有效性
            if end_seconds <= start_seconds:
                logger.warning(f"无效的时间范围: {start_time} -> {end_time}，尝试交换")
                # 尝试交换开始和结束时间
                start_seconds, end_seconds = end_seconds, start_seconds
                start_time, end_time = end_time, start_time
                
                # 再次验证
                if end_seconds <= start_seconds:
                    logger.warning(f"交换后仍然无效的时间范围: {start_time} -> {end_time}")
                    return None

            # 构建验证后的项目
            return {
                'title': item.get('title', ''),
                'outline': item.get('title', ''),
                'start_time': start_time,
                'end_time': end_time,
                'description': item.get('description', ''),
                'content': item.get('content', []),
                'chunk_index': chunk_index
            }

        except Exception as e:
            logger.error(f"验证时间范围失败: {e}")
            return None

    def _convert_time_format(self, time_str: str) -> str:
        """
        转换时间格式：SRT格式 -> FFmpeg格式
        """
        if not time_str or time_str == "end":
            return time_str
        return time_str.replace(',', '.')

    def _save_debug_response(self, response: str, chunk_index: int, error_type: str) -> None:
        """保存调试响应到文件"""
        try:
            debug_dir = self.metadata_dir / "debug_responses"
            debug_dir.mkdir(parents=True, exist_ok=True)
            debug_file = debug_dir / f"chunk_{chunk_index}_{error_type}.txt"
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(response)
            logger.info(f"调试响应已保存到: {debug_file}")
        except Exception as e:
            logger.error(f"保存调试响应失败: {e}")

    def save_timeline(self, timeline_data: List[Dict], output_path: Optional[Path] = None) -> Path:
        """
        保存时间区间数据
        """
        if output_path is None:
            output_path = METADATA_DIR / "step2_timeline.json"

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(timeline_data, f, ensure_ascii=False, indent=2)

        logger.info(f"时间数据已保存到: {output_path}")
        return output_path

    def load_timeline(self, input_path: Path) -> List[Dict]:
        """
        从文件加载时间数据
        """
        with open(input_path, 'r', encoding='utf-8') as f:
            return json.load(f)

def run_step2_timeline(outline_path: Path, metadata_dir: Path = None, output_path: Optional[Path] = None,
                      prompt_files: Dict = None, progress_callback: Optional[Callable[[int, str], None]] = None,
                      enable_checkpoint: bool = True) -> List[Dict]:
    """
    运行Step 2: 时间点提取（支持进度回调和断点续传）

    Args:
        outline_path: 大纲文件路径
        metadata_dir: 元数据目录
        output_path: 输出文件路径
        prompt_files: 提示词文件字典
        progress_callback: 进度回调函数 (progress: int, message: str) -> None
        enable_checkpoint: 是否启用断点续传，默认为True
    """
    if metadata_dir is None:
        metadata_dir = METADATA_DIR

    extractor = TimelineExtractor(metadata_dir, prompt_files, progress_callback, enable_checkpoint)

    # 加载大纲
    with open(outline_path, 'r', encoding='utf-8') as f:
        outlines = json.load(f)

    timeline_data = extractor.extract_timeline(outlines)

    # 保存结果
    if output_path is None:
        output_path = metadata_dir / "step2_timeline.json"

    extractor.save_timeline(timeline_data, output_path)

    return timeline_data
