"""Step 3: 单独评分步骤 - 只进行评分，不生成推荐理由"""
import json
import logging
import re
import asyncio
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from utils.llm_client import LLMClient
from utils.step_aware_llm_client import StepAwareLLMClient, get_step_aware_llm_client
from utils.text_processor import TextProcessor
from core.unified_config import get_prompt_files, get_config, get_processing_config
from core.step_config import StepType
from services.concurrency_manager import with_async_concurrency_limit

logger = logging.getLogger(__name__)

class ClipScorerOnly:
    """单独内容评分器"""

    def __init__(self, prompt_files: Optional[Dict[str, Path]] = None,
                 progress_callback: Optional[Callable[[int, str], None]] = None,
                 max_workers: int = 3,
                 enable_checkpoint: bool = True,
                 metadata_dir: Optional[Path] = None,
                 max_retries: int = 2) -> None:
        self.llm_client = LLMClient()
        self.step_aware_llm_client = get_step_aware_llm_client()
        self.text_processor = TextProcessor()
        self.progress_callback = progress_callback
        self.max_workers = max_workers  # 并发线程数
        self.enable_checkpoint = enable_checkpoint  # 是否启用断点续传
        self.max_retries = max_retries  # 最大重试次数
        if metadata_dir is None:
            config = get_config()
            metadata_dir = config.paths.output_dir / "metadata"
        self.metadata_dir = Path(metadata_dir)

        # 加载提示词
        prompt_files_to_use = prompt_files if prompt_files is not None else get_prompt_files()
        with open(prompt_files_to_use['scoring'], 'r', encoding='utf-8') as f:
            self.scoring_prompt = f.read()
        
        # 创建用于存放LLM原始输出的目录
        self.llm_raw_output_dir = self.metadata_dir / "step3_only_llm_raw_output"
        self.llm_raw_output_dir.mkdir(parents=True, exist_ok=True)
    
    def _validate_llm_response(self, parsed_list: List[Dict], expected_count: int) -> tuple[bool, List[str]]:
        """
        验证LLM返回的评分结果格式
        
        Returns:
            (is_valid, error_messages)
        """
        errors = []
        
        # 检查数量
        if len(parsed_list) != expected_count:
            errors.append(f"数量不匹配：期望 {expected_count} 个结果，实际返回 {len(parsed_list)} 个")
        
        # 检查每个结果的字段完整性
        for i, result in enumerate(parsed_list):
            if not isinstance(result, dict):
                errors.append(f"第 {i+1} 个结果不是字典格式")
                continue
            
            if 'final_score' not in result:
                errors.append(f"第 {i+1} 个结果缺少字段: final_score")
            
            # 检查字段值的有效性
            if 'final_score' in result:
                try:
                    score = float(result['final_score'])
                    if not (0 <= score <= 100):
                        errors.append(f"第 {i+1} 个结果的分数超出范围: {score}")
                except (ValueError, TypeError):
                    errors.append(f"第 {i+1} 个结果的分数格式错误: {result['final_score']}")
        
        is_valid = len(errors) == 0
        return is_valid, errors

    def score_clips(self, timeline_data: List[Dict]) -> List[Dict]:
        """
        为切片评分 (新版：并发按块批量处理，支持断点续传)
        """
        if not timeline_data:
            logger.warning("时间线数据为空，无法评分")
            return []

        logger.info(f"开始为 {len(timeline_data)} 个切片进行单独批量评分（并发模式，线程数={self.max_workers}, 断点续传={self.enable_checkpoint}）...")

        # 1. 按 chunk_index 对所有 timeline 数据进行分组
        timeline_by_chunk = defaultdict(list)
        for item in timeline_data:
            chunk_index = item.get('chunk_index')
            if chunk_index is not None:
                timeline_by_chunk[chunk_index].append(item)
            else:
                logger.warning(f"  > 话题 '{item.get('outline', '未知')}' 缺少 chunk_index，将被跳过。")

        all_scored_clips = []
        total_chunks = len(timeline_by_chunk)

        # 2. 如果启用断点续传，加载已完成的进度
        completed_chunks = set()
        if self.enable_checkpoint:
            completed_chunks = self._load_checkpoint()
            if completed_chunks:
                logger.info(f"检测到已完成的块: {sorted(completed_chunks)}，将跳过这些块")

        # 加载已有的评分结果
        if completed_chunks:
            try:
                all_scored_path = self.metadata_dir / "step3_only_all_scored.json"
                if all_scored_path.exists():
                    with open(all_scored_path, 'r', encoding='utf-8') as f:
                        all_scored_clips = json.load(f)
                    logger.info(f"已加载 {len(all_scored_clips)} 个已评分的切片")
            except Exception as e:
                logger.warning(f"加载已有评分结果失败: {e}，将重新开始")
                all_scored_clips = []

        # 过滤出需要处理的块
        pending_chunks = {
            chunk_index: chunk_items
            for chunk_index, chunk_items in timeline_by_chunk.items()
            if chunk_index not in completed_chunks
        }

        if not pending_chunks:
            logger.info("所有块已完成评分，跳过处理")
            return all_scored_clips

        logger.info(f"待处理块数量: {len(pending_chunks)}/{total_chunks}")

        # 3. 并发处理每个待处理块
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有待处理任务
            future_to_chunk = {
                executor.submit(self._score_chunk, chunk_index, chunk_items): chunk_index
                for chunk_index, chunk_items in pending_chunks.items()
            }

            # 等待所有任务完成
            total_completed = len(completed_chunks)
            for future in as_completed(future_to_chunk, timeout=600):  # 添加10分钟超时
                chunk_index = future_to_chunk[future]
                try:
                    scored_chunk_items = future.result(timeout=600)  # 添加10分钟超时

                    if scored_chunk_items:
                        # 合并结果
                        all_scored_clips.extend(scored_chunk_items)
                        logger.info(f"块 {chunk_index} 评分完成，包含 {len(scored_chunk_items)} 个话题")

                        # 保存断点
                        if self.enable_checkpoint:
                            self._save_checkpoint(chunk_index)
                            # 立即保存中间结果
                            self._save_intermediate_results(all_scored_clips)
                    else:
                        logger.warning(f"块 {chunk_index} 的LLM评估返回为空")
                        # 即使失败也标记为已完成（避免重试时跳过已完成的成功块）
                        if self.enable_checkpoint:
                            self._save_checkpoint(chunk_index, success=False)

                    # 更新进度
                    total_completed += 1
                    progress = int((total_completed / total_chunks) * 100)
                    if self.progress_callback:
                        self.progress_callback(progress, f"已完成 {total_completed}/{total_chunks} 个块的评分")

                except Exception as e:
                    logger.error(f"处理块 {chunk_index} 进行评分时出错: {str(e)}")
                    total_completed += 1
                    # 失败的块不保存断点，下次会重试
                    continue

        # 4. 按最终得分对所有结果进行排序
        if all_scored_clips:
            # 去重（如果有重复的）
            unique_clips = {}
            for clip in all_scored_clips:
                clip_id = clip.get('id')
                if clip_id:
                    unique_clips[clip_id] = clip

            all_scored_clips = list(unique_clips.values())

            all_scored_clips.sort(key=lambda x: x.get('final_score', 0), reverse=True)
            # 保持Step 2分配的固定ID，不再重新分配
            logger.info("按评分排序完成，保持原有固定ID不变")

            # 最终按ID排序，确保时间顺序的一致性
            all_scored_clips.sort(key=lambda x: int(x.get('id', 0)))
            logger.info("按ID排序完成，保持时间顺序")

        logger.info("所有切片评分完成")

        # 5. 不清理断点，保留用于断点续传
        # 只有在整个流程完全成功后才应该清理断点

        return all_scored_clips

    @with_async_concurrency_limit(max_concurrent=5)
    async def _score_chunk_async(self, chunk_index: int, chunk_items: List[Dict]) -> List[Dict]:
        """
        为单个块的所有话题评分（异步版本，带并发控制）
        一次只处理3个话题，防止超时
        """
        logger.info(f"开始处理块 {chunk_index}（异步），其中包含 {len(chunk_items)} 个话题...")
        try:
            # 一次只处理3个话题，分批处理
            batch_size = 3
            all_scored_items = []
            
            for i in range(0, len(chunk_items), batch_size):
                batch_items = chunk_items[i:i + batch_size]
                logger.info(f"处理块 {chunk_index} 的第 {i//batch_size + 1} 批次，包含 {len(batch_items)} 个话题")
                
                # 使用LLM进行批量评估
                scored_batch_items = await self._get_llm_evaluation_async(batch_items)
                
                if scored_batch_items:
                    all_scored_items.extend(scored_batch_items)
                    logger.info(f"批次评估成功，返回 {len(scored_batch_items)} 个结果")
                else:
                    logger.warning(f"批次评估返回为空")

            if all_scored_items:
                logger.info(f"块 {chunk_index} 的所有批次评估完成，返回 {len(all_scored_items)} 个结果")
            else:
                logger.warning(f"块 {chunk_index} 的所有批次评估返回为空")

            return all_scored_items

        except Exception as e:
            logger.error(f"  > 处理块 {chunk_index} 进行评分时出错: {str(e)}")
            # 如果出错，返回原始数据但设置默认分数（50分）
            # 这样至少有一些片段可以通过阈值筛选
            for clip in chunk_items:
                clip['final_score'] = 50  # 使用中等分数而不是0
            return chunk_items

    def _score_chunk(self, chunk_index: int, chunk_items: List[Dict]) -> List[Dict]:
        """
        为单个块的所有话题评分（同步包装器）
        """
        try:
            # 直接创建新的事件循环，避免线程安全问题
            def run_in_thread():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(self._score_chunk_async(chunk_index, chunk_items))
                finally:
                    new_loop.close()
            
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(run_in_thread)
                return future.result(timeout=600)
        except Exception as e:
            logger.error(f"处理块 {chunk_index} 进行评分时出错: {str(e)}")
            # 如果出错，返回原始数据但设置默认分数（50分）
            for clip in chunk_items:
                clip['final_score'] = 50  # 使用中等分数而不是0
            return chunk_items

    async def _get_llm_evaluation_async(self, clips: List[Dict]) -> List[Dict]:
        """
        使用LLM进行批量评估，为每个clip添加 final_score（异步版本，支持重试）
        """
        # 输入给LLM的数据不需要包含所有字段，只给必要的
        input_for_llm = [
            {
                "outline": clip.get('outline'),
                "content": clip.get('content'),
                "start_time": clip.get('start_time'),
                "end_time": clip.get('end_time'),
            } for clip in clips
        ]

        parsed_list = None
        last_errors = []
        
        # 尝试调用LLM，最多重试 max_retries 次
        for attempt in range(self.max_retries + 1):
            try:
                # 构建提示词（重试时添加错误提示）
                prompt = self.scoring_prompt
                if attempt > 0 and last_errors:
                    error_hint = f"\n\n【上次请求的问题】\n" + "\n".join(f"- {err}" for err in last_errors)
                    error_hint += "\n\n请严格按照要求重新输出，确保：\n1. 输出数量与输入数量完全一致\n2. 每个结果都包含 final_score 字段\n3. 输出格式为有效的JSON数组"
                    prompt = self.scoring_prompt + error_hint
                    logger.warning(f"LLM评分格式错误，第 {attempt} 次重试，错误: {last_errors[:3]}")
                
                # 使用步骤感知的LLM客户端（支持不同步骤使用不同模型）
                response = await self.step_aware_llm_client.call_for_step(
                    StepType.STEP3_SCORING,
                    prompt=prompt,
                    input_data=input_for_llm
                )
                
                # 保存原始响应
                raw_output_file = self.llm_raw_output_dir / f"batch_{attempt}_raw_output.txt"
                with open(raw_output_file, 'w', encoding='utf-8') as f:
                    f.write(response)

                parsed_list = self.llm_client.parse_json_response(response)

                if not isinstance(parsed_list, list):
                    last_errors = [f"返回结果不是列表格式，而是 {type(parsed_list).__name__}"]
                    continue

                # 验证格式
                is_valid, errors = self._validate_llm_response(parsed_list, len(clips))
                
                if is_valid:
                    # 格式正确，跳出重试循环
                    if attempt > 0:
                        logger.info(f"LLM评分重试成功（第 {attempt} 次重试）")
                    break
                else:
                    last_errors = errors
                    logger.warning(f"LLM评分格式验证失败（尝试 {attempt + 1}/{self.max_retries + 1}）: {errors[:3]}")
                    
            except Exception as e:
                error_str = str(e)
                last_errors = [f"LLM调用异常: {error_str[:100]}"]
                logger.error(f"LLM批量评估失败（尝试 {attempt + 1}/{self.max_retries + 1}）: {e}")
                
                # 检查是否为API错误（如模型不可用），如果是则直接返回默认分数，不再重试
                if "API错误" in error_str or "no available channels" in error_str:
                    logger.error("检测到API错误，不再重试，使用默认分数")
                    for clip in clips:
                        clip['final_score'] = 50
                    return clips
        
        # 如果所有重试都失败，使用容错处理
        if parsed_list is None or not isinstance(parsed_list, list):
            logger.error("所有LLM重试均失败，使用默认分数")
            for clip in clips:
                clip['final_score'] = 50
            return clips

        if len(parsed_list) != len(clips):
            logger.error(f"LLM返回的评分结果数量与输入不匹配。输入: {len(clips)}, 输出: {len(parsed_list)}")
            logger.warning(f"使用部分结果，缺失的将设置默认值")

        # 将评分结果合并回原始的clips数据
        for i, original_clip in enumerate(clips):
            if i < len(parsed_list):
                llm_result = parsed_list[i]
                score = llm_result.get('final_score')

                if score is None:
                    logger.warning(f"LLM返回的某个结果缺少score: {llm_result}")
                    original_clip['final_score'] = 0
                else:
                    # 评分现在是0-100的整数
                    original_clip['final_score'] = int(round(float(score)))
                    # 安全地获取outline标题用于日志显示
                    outline = original_clip.get('outline', {})
                    if isinstance(outline, dict):
                        title = outline.get('title', '未知标题')
                    else:
                        title = str(outline)
                    logger.info(f"  > 评分成功: {title[:20]}... [分数: {score}]")
            else:
                # LLM没有返回这个clip的结果，设置默认值
                logger.warning(f"LLM未返回第{i+1}个clip的评分结果，使用默认值")
                original_clip['final_score'] = 0

        return clips

    def _load_checkpoint(self) -> set:
        """加载断点文件，返回已完成的块索引集合"""
        checkpoint_file = self.metadata_dir / "step3_only_checkpoint.json"
        if not checkpoint_file.exists():
            return set()

        try:
            with open(checkpoint_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                completed = set(data.get('completed_chunks', []))
                logger.info(f"从断点文件加载了 {len(completed)} 个已完成的块")
                return completed
        except Exception as e:
            logger.warning(f"加载断点文件失败: {e}，将重新开始")
            return set()

    def _save_checkpoint(self, chunk_index: int, success: bool = True):
        """保存断点文件"""
        checkpoint_file = self.metadata_dir / "step3_only_checkpoint.json"

        try:
            # 加载现有数据
            completed_chunks = set()
            if checkpoint_file.exists():
                with open(checkpoint_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    completed_chunks = set(data.get('completed_chunks', []))

            # 添加新的完成块
            if success:
                completed_chunks.add(chunk_index)
            else:
                # 失败的块不添加，下次会重试
                pass

            # 保存
            data = {
                'completed_chunks': sorted(list(completed_chunks)),
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'last_chunk': chunk_index
            }

            with open(checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.debug(f"断点已保存: 块 {chunk_index}")

        except Exception as e:
            logger.warning(f"保存断点文件失败: {e}")

    def _save_intermediate_results(self, all_scored_clips: List[Dict]):
        """保存中间结果"""
        try:
            all_scored_path = self.metadata_dir / "step3_only_all_scored.json"
            with open(all_scored_path, 'w', encoding='utf-8') as f:
                json.dump(all_scored_clips, f, ensure_ascii=False, indent=2)
            logger.debug(f"中间结果已保存，共 {len(all_scored_clips)} 个切片")
        except Exception as e:
            logger.warning(f"保存中间结果失败: {e}")

    def _cleanup_checkpoint(self):
        """清理断点文件"""
        checkpoint_file = self.metadata_dir / "step3_only_checkpoint.json"
        try:
            if checkpoint_file.exists():
                checkpoint_file.unlink()
                logger.info("断点文件已清理")
        except Exception as e:
            logger.warning(f"清理断点文件失败: {e}")

    def save_scores(self, scored_clips: List[Dict], output_path: Path):
        """保存评分结果"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(scored_clips, f, ensure_ascii=False, indent=2)
        logger.info(f"评分结果已保存到: {output_path}")

def run_step3_scoring_only(timeline_path: Path, metadata_dir: Path = None, output_path: Optional[Path] = None,
                           prompt_files: Dict = None, progress_callback: Optional[Callable[[int, str], None]] = None,
                           max_workers: int = 3, enable_checkpoint: bool = True) -> List[Dict]:
    """
    运行Step 3: 单独内容评分（支持并发处理、断点续传和进度回调）

    Args:
        timeline_path: 时间线文件路径
        metadata_dir: 元数据目录
        output_path: 输出文件路径
        prompt_files: 自定义提示词文件
        progress_callback: 进度回调函数 (progress: int, message: str) -> None
        max_workers: 并发线程数，默认为3
        enable_checkpoint: 是否启用断点续传，默认为True

    Returns:
        高分切片列表
    """
    # 加载时间线数据
    with open(timeline_path, 'r', encoding='utf-8') as f:
        timeline_data = json.load(f)

    # 创建评分器（启用并发和断点续传）
    scorer = ClipScorerOnly(prompt_files, progress_callback, max_workers=max_workers,
                           enable_checkpoint=enable_checkpoint, metadata_dir=metadata_dir)

    # 评分
    scored_clips = scorer.score_clips(timeline_data)

    # 筛选高分切片
    processing_config = get_processing_config()
    high_score_clips = [clip for clip in scored_clips if clip['final_score'] >= processing_config.min_score_threshold]

    # 保存结果
    if metadata_dir is None:
        config = get_config()
        metadata_dir = config.paths.output_dir / "metadata"

    # 保存所有评分后的片段（用于调试和分析）
    all_scored_path = metadata_dir / "step3_only_all_scored.json"
    scorer.save_scores(scored_clips, all_scored_path)

    # 保存筛选后的高分片段（用于后续步骤）
    if output_path is None:
        output_path = metadata_dir / "step3_only_high_score_clips.json"

    scorer.save_scores(high_score_clips, output_path)

    return high_score_clips