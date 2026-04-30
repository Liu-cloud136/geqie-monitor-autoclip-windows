"""Step 4: 推荐理由生成 - 基于已有的评分生成推荐理由"""
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

class RecommendationGenerator:
    """推荐理由生成器"""

    def __init__(self, prompt_files: Optional[Dict[str, Path]] = None,
                 progress_callback: Optional[Callable[[int, str], None]] = None,
                 max_workers: int = 3,
                 enable_checkpoint: bool = True,
                 metadata_dir: Optional[Path] = None,
                 max_retries: int = 3) -> None:
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
        with open(prompt_files_to_use['recommendation'], 'r', encoding='utf-8') as f:
            self.recommendation_prompt = f.read()
        
        # 创建用于存放LLM原始输出的目录
        self.llm_raw_output_dir = self.metadata_dir / "step4_llm_raw_output"
        self.llm_raw_output_dir.mkdir(parents=True, exist_ok=True)
    
    def _validate_llm_response(self, parsed_list: List[Dict], expected_count: int) -> tuple[bool, List[str]]:
        """
        验证LLM返回的推荐理由结果格式
        
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
            
            if 'recommend_reason' not in result:
                errors.append(f"第 {i+1} 个结果缺少字段: recommend_reason")
            
            # 检查字段值的有效性
            if 'recommend_reason' in result:
                reason = result['recommend_reason']
                if not isinstance(reason, str) or len(reason) > 45:
                    errors.append(f"第 {i+1} 个结果的推荐理由长度超过45字: {len(reason)}字")
        
        is_valid = len(errors) == 0
        return is_valid, errors

    def generate_recommendations(self, scored_clips: List[Dict]) -> List[Dict]:
        """
        为已评分的切片生成推荐理由 (顺序按块批量处理，支持断点续传)
        """
        if not scored_clips:
            logger.warning("已评分数据为空，无法生成推荐理由")
            return []

        logger.info(f"开始为 {len(scored_clips)} 个切片生成推荐理由（顺序模式，断点续传={self.enable_checkpoint}）...")

        # 1. 按 chunk_index 对所有 scored_clips 数据进行分组
        clips_by_chunk = defaultdict(list)
        for item in scored_clips:
            chunk_index = item.get('chunk_index')
            if chunk_index is not None:
                clips_by_chunk[chunk_index].append(item)
            else:
                logger.warning(f"  > 话题 '{item.get('outline', '未知')}' 缺少 chunk_index，将被跳过。")

        all_recommended_clips = []
        total_chunks = len(clips_by_chunk)

        # 2. 如果启用断点续传，加载已完成的进度
        completed_chunks = set()
        if self.enable_checkpoint:
            completed_chunks = self._load_checkpoint()
            if completed_chunks:
                logger.info(f"检测到已完成的块: {sorted(completed_chunks)}，将跳过这些块")

        # 加载已有的推荐理由结果
        if completed_chunks:
            try:
                all_recommended_path = self.metadata_dir / "step4_all_recommended.json"
                if all_recommended_path.exists():
                    with open(all_recommended_path, 'r', encoding='utf-8') as f:
                        all_recommended_clips = json.load(f)
                    logger.info(f"已加载 {len(all_recommended_clips)} 个已生成推荐理由的切片")
            except Exception as e:
                logger.warning(f"加载已有推荐理由结果失败: {e}，将重新开始")
                all_recommended_clips = []

        # 过滤出需要处理的块
        pending_chunks = {
            chunk_index: chunk_items
            for chunk_index, chunk_items in clips_by_chunk.items()
            if chunk_index not in completed_chunks
        }

        if not pending_chunks:
            logger.info("所有块已完成推荐理由生成，跳过处理")
            return all_recommended_clips

        logger.info(f"待处理块数量: {len(pending_chunks)}/{total_chunks}")

        # 3. 顺序处理每个待处理块
        total_completed = len(completed_chunks)
        for chunk_index, chunk_items in pending_chunks.items():
            logger.info(f"开始处理块 {chunk_index}，包含 {len(chunk_items)} 个话题")
            try:
                recommended_chunk_items = self._generate_chunk(chunk_index, chunk_items)

                if recommended_chunk_items:
                    # 合并结果
                    all_recommended_clips.extend(recommended_chunk_items)
                    logger.info(f"块 {chunk_index} 推荐理由生成完成，包含 {len(recommended_chunk_items)} 个话题")

                    # 保存断点
                    if self.enable_checkpoint:
                        self._save_checkpoint(chunk_index)
                        # 立即保存中间结果
                        self._save_intermediate_results(all_recommended_clips)
                else:
                    logger.warning(f"块 {chunk_index} 的LLM评估返回为空")
                    # 即使失败也标记为已完成（避免重试时跳过已完成的成功块）
                    if self.enable_checkpoint:
                        self._save_checkpoint(chunk_index, success=False)

                # 更新进度
                total_completed += 1
                progress = int((total_completed / total_chunks) * 100)
                if self.progress_callback:
                    self.progress_callback(progress, f"已完成 {total_completed}/{total_chunks} 个块的推荐理由生成")

            except Exception as e:
                logger.error(f"处理块 {chunk_index} 生成推荐理由时出错: {str(e)}")
                total_completed += 1
                # 失败的块不保存断点，下次会重试
                continue

        # 4. 按最终得分对所有结果进行排序
        if all_recommended_clips:
            # 去重（如果有重复的）
            unique_clips = {}
            for clip in all_recommended_clips:
                clip_id = clip.get('id')
                if clip_id:
                    unique_clips[clip_id] = clip

            all_recommended_clips = list(unique_clips.values())

            all_recommended_clips.sort(key=lambda x: x.get('final_score', 0), reverse=True)
            # 保持Step 2分配的固定ID，不再重新分配
            logger.info("按评分排序完成，保持原有固定ID不变")

            # 最终按ID排序，确保时间顺序的一致性
            all_recommended_clips.sort(key=lambda x: int(x.get('id', 0)))
            logger.info("按ID排序完成，保持时间顺序")

        logger.info("所有切片推荐理由生成完成")

        # 5. 不清理断点，保留用于断点续传
        # 只有在整个流程完全成功后才应该清理断点

        return all_recommended_clips

    @with_async_concurrency_limit(max_concurrent=5)
    async def _generate_chunk_async(self, chunk_index: int, chunk_items: List[Dict]) -> List[Dict]:
        """
        为单个块的所有话题生成推荐理由（异步版本，带并发控制）
        一次只处理3个话题，防止超时
        """
        logger.info(f"开始处理块 {chunk_index}（异步），其中包含 {len(chunk_items)} 个话题...")
        try:
            # 一次只处理3个话题，分批处理
            batch_size = 3
            all_recommended_items = []
            
            for i in range(0, len(chunk_items), batch_size):
                batch_items = chunk_items[i:i + batch_size]
                logger.info(f"处理块 {chunk_index} 的第 {i//batch_size + 1} 批次，包含 {len(batch_items)} 个话题")
                
                # 使用LLM进行批量评估
                recommended_batch_items = await self._get_llm_evaluation_async(batch_items)
                
                if recommended_batch_items:
                    all_recommended_items.extend(recommended_batch_items)
                    logger.info(f"批次评估成功，返回 {len(recommended_batch_items)} 个结果")
                else:
                    logger.warning(f"批次评估返回为空")

            if all_recommended_items:
                logger.info(f"块 {chunk_index} 的所有批次评估完成，返回 {len(all_recommended_items)} 个结果")
            else:
                logger.warning(f"块 {chunk_index} 的所有批次评估返回为空")

            return all_recommended_items

        except Exception as e:
            logger.error(f"  > 处理块 {chunk_index} 生成推荐理由时出错: {str(e)}")
            # 如果出错，返回原始数据但设置默认推荐理由
            for clip in chunk_items:
                clip['recommend_reason'] = f"推荐理由生成失败: {str(e)[:50]}"
            return chunk_items

    def _generate_chunk(self, chunk_index: int, chunk_items: List[Dict]) -> List[Dict]:
        """
        为单个块的所有话题生成推荐理由（同步包装器）
        """
        try:
            # 直接创建新的事件循环，避免线程安全问题
            def run_in_thread():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(self._generate_chunk_async(chunk_index, chunk_items))
                finally:
                    new_loop.close()
            
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(run_in_thread)
                return future.result(timeout=600)
        except Exception as e:
            logger.error(f"处理块 {chunk_index} 生成推荐理由时出错: {str(e)}")
            # 如果出错，返回原始数据但设置默认推荐理由
            for clip in chunk_items:
                clip['recommend_reason'] = f"推荐理由生成失败: {str(e)[:50]}"
            return chunk_items

    async def _get_llm_evaluation_async(self, clips: List[Dict]) -> List[Dict]:
        """
        使用LLM进行批量评估，为每个clip添加 recommend_reason（异步版本，支持重试）
        """
        # 输入给LLM的数据不需要包含所有字段，只给必要的
        input_for_llm = [
            {
                "outline": clip.get('outline'),
                "content": clip.get('content'),
                "start_time": clip.get('start_time'),
                "end_time": clip.get('end_time'),
                "final_score": clip.get('final_score')
            } for clip in clips
        ]

        parsed_list = None
        last_errors = []
        
        # 尝试调用LLM，最多重试 max_retries 次
        for attempt in range(self.max_retries + 1):
            try:
                # 构建提示词（重试时添加错误提示）
                prompt = self.recommendation_prompt
                if attempt > 0 and last_errors:
                    error_hint = f"\n\n【上次请求的问题】\n" + "\n".join(f"- {err}" for err in last_errors)
                    error_hint += "\n\n请严格按照要求重新输出，确保：\n1. 输出数量与输入数量完全一致\n2. 每个结果都包含 recommend_reason 字段\n3. 输出格式为有效的JSON数组"
                    prompt = self.recommendation_prompt + error_hint
                    logger.warning(f"LLM推荐理由格式错误，第 {attempt} 次重试，错误: {last_errors[:3]}")
                
                # 使用步骤感知的LLM客户端（支持不同步骤使用不同模型）
                response = await self.step_aware_llm_client.call_for_step(
                    StepType.STEP4_RECOMMENDATION,  # 使用推荐理由生成的步骤配置
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
                        logger.info(f"LLM推荐理由重试成功（第 {attempt} 次重试）")
                    break
                else:
                    last_errors = errors
                    logger.warning(f"LLM推荐理由格式验证失败（尝试 {attempt + 1}/{self.max_retries + 1}）: {errors[:3]}")
                    
            except Exception as e:
                error_str = str(e)
                last_errors = [f"LLM调用异常: {error_str[:100]}"]
                logger.error(f"LLM批量评估失败（尝试 {attempt + 1}/{self.max_retries + 1}）: {e}")
                
                # 检查是否为API错误（如模型不可用），如果是则直接返回默认推荐理由，不再重试
                if "API错误" in error_str or "no available channels" in error_str:
                    logger.error("检测到API错误，不再重试，使用默认推荐理由")
                    for clip in clips:
                        clip['recommend_reason'] = f"API调用失败，使用默认推荐理由: {error_str[:50]}"
                    return clips
        
        # 如果所有重试都失败，使用容错处理
        if parsed_list is None or not isinstance(parsed_list, list):
            logger.error("所有LLM重试均失败，使用默认推荐理由")
            for clip in clips:
                clip['recommend_reason'] = "推荐理由生成失败，使用默认推荐理由"
            return clips

        if len(parsed_list) != len(clips):
            logger.error(f"LLM返回的推荐理由结果数量与输入不匹配。输入: {len(clips)}, 输出: {len(parsed_list)}")
            logger.warning(f"使用部分结果，缺失的将设置默认值")

        # 将推荐理由结果合并回原始的clips数据
        for i, original_clip in enumerate(clips):
            if i < len(parsed_list):
                llm_result = parsed_list[i]
                reason = llm_result.get('recommend_reason')

                if reason is None:
                    logger.warning(f"LLM返回的某个结果缺少recommend_reason: {llm_result}")
                    original_clip['recommend_reason'] = "推荐理由生成失败"
                else:
                    original_clip['recommend_reason'] = reason
                    # 安全地获取outline标题用于日志显示
                    outline = original_clip.get('outline', {})
                    if isinstance(outline, dict):
                        title = outline.get('title', '未知标题')
                    else:
                        title = str(outline)
                    logger.info(f"  > 推荐理由生成成功: {title[:20]}...")
            else:
                # LLM没有返回这个clip的结果，设置默认值
                logger.warning(f"LLM未返回第{i+1}个clip的推荐理由结果，使用默认值")
                original_clip['recommend_reason'] = "LLM未返回推荐理由结果"

        return clips

    def _load_checkpoint(self) -> set:
        """加载断点文件，返回已完成的块索引集合"""
        checkpoint_file = self.metadata_dir / "step4_recommendation_checkpoint.json"
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
        checkpoint_file = self.metadata_dir / "step4_recommendation_checkpoint.json"

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

    def _save_intermediate_results(self, all_recommended_clips: List[Dict]):
        """保存中间结果"""
        try:
            all_recommended_path = self.metadata_dir / "step4_all_recommended.json"
            with open(all_recommended_path, 'w', encoding='utf-8') as f:
                json.dump(all_recommended_clips, f, ensure_ascii=False, indent=2)
            logger.debug(f"中间结果已保存，共 {len(all_recommended_clips)} 个切片")
        except Exception as e:
            logger.warning(f"保存中间结果失败: {e}")

    def _cleanup_checkpoint(self):
        """清理断点文件"""
        checkpoint_file = self.metadata_dir / "step4_recommendation_checkpoint.json"
        try:
            if checkpoint_file.exists():
                checkpoint_file.unlink()
                logger.info("断点文件已清理")
        except Exception as e:
            logger.warning(f"清理断点文件失败: {e}")

    def save_recommendations(self, recommended_clips: List[Dict], output_path: Path):
        """保存推荐理由结果"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(recommended_clips, f, ensure_ascii=False, indent=2)
        logger.info(f"推荐理由结果已保存到: {output_path}")

def run_step4_recommendation(scored_clips_path: Path, metadata_dir: Path = None, output_path: Optional[Path] = None,
                           prompt_files: Dict = None, progress_callback: Optional[Callable[[int, str], None]] = None,
                           max_workers: int = 3, enable_checkpoint: bool = True) -> List[Dict]:
    """
    运行Step 4: 推荐理由生成（支持并发处理、断点续传和进度回调）

    Args:
        scored_clips_path: 已评分切片文件路径
        metadata_dir: 元数据目录
        output_path: 输出文件路径
        prompt_files: 自定义提示词文件
        progress_callback: 进度回调函数 (progress: int, message: str) -> None
        max_workers: 并发线程数，默认为3
        enable_checkpoint: 是否启用断点续传，默认为True

    Returns:
        带推荐理由的切片列表
    """
    # 加载已评分数据
    with open(scored_clips_path, 'r', encoding='utf-8') as f:
        scored_clips = json.load(f)

    # 创建推荐理由生成器（启用并发和断点续传）
    generator = RecommendationGenerator(prompt_files, progress_callback, max_workers=max_workers,
                                       enable_checkpoint=enable_checkpoint, metadata_dir=metadata_dir)

    # 生成推荐理由
    recommended_clips = generator.generate_recommendations(scored_clips)

    # 保存结果
    if metadata_dir is None:
        config = get_config()
        metadata_dir = config.paths.output_dir / "metadata"

    # 保存所有带推荐理由的片段
    all_recommended_path = metadata_dir / "step4_all_recommended.json"
    generator.save_recommendations(recommended_clips, all_recommended_path)

    # 保存最终结果
    if output_path is None:
        output_path = metadata_dir / "step4_with_recommendations.json"

    generator.save_recommendations(recommended_clips, output_path)

    return recommended_clips