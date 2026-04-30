"""
大模型客户端 - 使用tenacity实现优雅的重试机制
支持进度心跳和流式响应
"""
import json
import logging
import os
import re
import time
import threading
from typing import Dict, Any, List, Optional, Callable
from collections.abc import Generator
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
from httpx import TimeoutException, ConnectError
import asyncio
import concurrent.futures

from core.unified_config import get_config
from services.exceptions import LLMError, ProcessingError, SystemError
from core.logging_config import get_logger

logger = get_logger(__name__)

class LLMClient:
    """LLM客户端 - 优化的重试机制，支持进度心跳"""

    def __init__(self) -> None:
        config = get_config()
        self.model = config.llm.model_name
        self._llm_manager = None
        self._progress_callback: Optional[Callable[[int, str], None]] = None
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._stop_heartbeat = threading.Event()
    
    @property
    def llm_manager(self):
        """延迟加载 LLM 管理器以避免循环导入"""
        if self._llm_manager is None:
            from core.llm_manager import get_llm_manager
            self._llm_manager = get_llm_manager()
        return self._llm_manager
    
    def call(self, prompt: str, input_data: Any = None) -> str:
        """
        调用大模型API - 使用新的LLM管理器

        Args:
            prompt: 提示词
            input_data: 输入数据

        Returns:
            模型响应文本
        """
        try:
            return self.llm_manager.call(prompt, input_data)
        except TimeoutError as e:
            from services.exceptions import LLMTimeoutError
            timeout_seconds = getattr(self.llm_manager.settings, 'timeout', None)
            provider = getattr(self.llm_manager, 'current_provider', None)
            provider_name = provider.__class__.__name__ if provider else None
            raise LLMTimeoutError(
                message=f"LLM调用超时",
                provider=provider_name,
                timeout_seconds=timeout_seconds,
                cause=e
            )
        except LLMError:
            raise
        except Exception as e:
            from services.exceptions import ProcessingError
            raise ProcessingError(
                message=f"处理失败: {e}",
                step_name="LLM调用",
                cause=e
            )

    async def _call_async(self, prompt: str, input_data: Any = None) -> str:
        """
        异步调用LLM API的核心方法

        Args:
            prompt: 提示词
            input_data: 输入数据

        Returns:
            模型响应文本
        """
        return await self.llm_manager.call(prompt, input_data)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((TimeoutException, ConnectError)),
        reraise=True,
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    async def call_with_retry_async(
        self,
        prompt: str,
        input_data: Any = None,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> str:
        """
        使用tenacity实现优雅的异步重试机制

        Args:
            prompt: 提示词
            input_data: 输入数据
            progress_callback: 进度回调函数

        Returns:
            模型响应文本
        """
        self._progress_callback = progress_callback
        self._start_heartbeat()

        try:
            result = await self._call_async(prompt, input_data)
            return result
        finally:
            self._stop_heartbeat_thread()

    def _start_heartbeat(self):
        """启动心跳线程"""
        if self._progress_callback and not self._heartbeat_thread:
            self._stop_heartbeat.clear()
            self._heartbeat_thread = threading.Thread(
                target=self._heartbeat_worker,
                daemon=True
            )
            self._heartbeat_thread.start()

    def _stop_heartbeat_thread(self):
        """停止心跳线程"""
        if self._heartbeat_thread:
            self._stop_heartbeat.set()
            self._heartbeat_thread.join(timeout=1)
            self._heartbeat_thread = None

    def _heartbeat_worker(self):
        """心跳线程，定期发送进度更新"""
        while not self._stop_heartbeat.is_set():
            self._stop_heartbeat.wait(10)  # 每10秒发送一次心跳
            if not self._stop_heartbeat.is_set() and self._progress_callback:
                try:
                    self._progress_callback(0, "正在调用大模型API处理...")
                except Exception as e:
                    logger.warning(f"心跳回调失败: {e}")

    def _run_async_in_sync_context(
        self,
        async_func: Callable[..., Any],
        *args: Any,
        **kwargs: Any
    ) -> Any:
        """
        在同步上下文中运行异步函数

        Args:
            async_func: 异步函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            异步函数的返回值
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # 事件循环正在运行，使用线程池
            def run_in_new_loop() -> Any:
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(async_func(*args, **kwargs))
                finally:
                    new_loop.close()

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_in_new_loop)
                return future.result(timeout=600)
        else:
            # 没有事件循环或循环未运行，创建新的
            if loop and (loop.is_closed() or not loop.is_running()):
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            elif not loop:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            try:
                return loop.run_until_complete(async_func(*args, **kwargs))
            finally:
                # 不关闭循环，让 Celery 管理
                pass
    
    def call_with_retry(
        self,
        prompt: str,
        input_data: Any = None,
        max_retries: int = 3,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> str:
        """
        带重试机制的API调用（使用优化的异步实现）

        Args:
            prompt: 提示词
            input_data: 输入数据
            max_retries: 最大重试次数（默认3次，使用tenacity自动重试）
            progress_callback: 进度回调函数，参数为 (progress: int, message: str)

        Returns:
            模型响应文本
        """
        async def _call_with_tenacity():
            """在异步环境中使用tenacity重试"""
            return await self.call_with_retry_async(prompt, input_data, progress_callback)

        return self._run_async_in_sync_context(_call_with_tenacity)
    
    def _preprocess_llm_response(self, response: str) -> str:
        """
        预处理LLM响应，移除常见的非JSON内容
        """
        # 移除开头的标题和说明文字
        lines = response.split('\n')
        json_start = -1
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('[') or stripped.startswith('{'):
                json_start = i
                break
        
        if json_start >= 0:
            response = '\n'.join(lines[json_start:])
        
        # 移除末尾的非JSON内容
        if '```' in response:
            # 如果有多个```，取第一个之前的内容
            parts = response.split('```')
            if len(parts) > 1:
                response = parts[0]
        
        return response.strip()
    
    def _auto_fix_response(self, response: str) -> str:
        """
        自动修复常见的响应问题
        """
        # 移除BOM和特殊字符
        response = response.lstrip('\ufeff')
        response = response.strip()
        
        # 修复中文引号
        response = response.replace('"', '\"').replace('"', '\"')
        
        return response
    
    def _validate_json_structure(self, parsed_data: Any) -> bool:
        """
        验证JSON结构的有效性
        """
        try:
            if not isinstance(parsed_data, list):
                logger.error(f"响应不是数组格式，实际类型: {type(parsed_data)}")
                return False
            
            for i, item in enumerate(parsed_data):
                if not isinstance(item, dict):
                    logger.error(f"第{i}个元素不是对象格式，实际类型: {type(item)}")
                    return False
                    
                # 检查基本字段（可根据具体需求调整）
                if 'outline' in item or 'start_time' in item or 'end_time' in item:
                    required_fields = ['outline', 'start_time', 'end_time']
                    for field in required_fields:
                        if field not in item:
                            logger.error(f"第{i}个元素缺少必需字段: {field}")
                            return False
        except Exception as e:
            logger.error(f"验证JSON结构时出错: {e}")
            return False
        
        return True
    
    def parse_json_response(self, response: str) -> Any:
        """
        从可能包含Markdown格式的文本中解析JSON对象。
        该函数具有多层容错机制：
        1. 预处理响应，移除非JSON内容
        2. 优先从Markdown代码块提取。
        3. 如果失败，则尝试直接解析整个响应（在净化后）。
        4. 如果再次失败，则使用通用正则表达式寻找并解析JSON。
        5. 最后尝试修复常见JSON错误后再解析。
        """
        
        def sanitize_string(s: str) -> str:
            """增强的净化函数，移除可能导致JSON解析失败的字符"""
            # 移除BOM标记
            s = s.lstrip('\ufeff')
            # 移除前后空白符
            s = s.strip()
            # 移除可能的控制字符（保留必要的换行和制表符）
            s = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', s)
            return s
        
        def fix_common_json_errors(json_str: str) -> str:
            """修复常见的JSON格式错误"""
            # 记录原始字符串用于调试
            original_str = json_str
            
            # 1. 修复缺少逗号的问题
            json_str = re.sub(r'}\s*{', '},{', json_str)
            json_str = re.sub(r']\s*\[', '],[', json_str)
            
            # 2. 修复对象之间缺少逗号的问题（更精确的模式）
            json_str = re.sub(r'}\s*\n\s*{', '},\n{', json_str)
            
            # 3. 修复多余的逗号
            json_str = re.sub(r',\s*}', '}', json_str)
            json_str = re.sub(r',\s*]', ']', json_str)
            
            # 4. 修复单引号为双引号
            json_str = re.sub(r"'([^']*?)'\s*:", r'"\1":', json_str)
            json_str = re.sub(r":\s*'([^']*?)'", r': "\1"', json_str)
            
            # 5. 修复字段名没有引号的问题
            json_str = re.sub(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'"\1":', json_str)
            
            # 6. 修复可能的换行符问题
            json_str = re.sub(r'\n\s*\n', '\n', json_str)
            
            # 7. 确保数组和对象的正确闭合
            # 统计括号和方括号的数量
            open_braces = json_str.count('{')
            close_braces = json_str.count('}')
            open_brackets = json_str.count('[')
            close_brackets = json_str.count(']')
            
            # 如果括号不匹配，尝试修复
            if open_braces > close_braces:
                json_str += '}' * (open_braces - close_braces)
            if open_brackets > close_brackets:
                json_str += ']' * (open_brackets - close_brackets)
            
            # 记录修复过程
            if json_str != original_str:
                logger.debug(f"JSON修复前: {original_str[:100]}...")
                logger.debug(f"JSON修复后: {json_str[:100]}...")
            
            return json_str

        response = response.strip()
        
        # 0. 预处理响应，移除非JSON内容
        response = self._preprocess_llm_response(response)
        logger.debug(f"预处理后的响应: {response[:200]}...")
        
        # 1. 优先尝试从Markdown代码块中提取
        # 使用findall找到所有代码块，优先选择数组格式（通常是最后的结果）
        all_matches = re.findall(r'```(?:json)?\s*([\s\S]*?)\s*```', response, re.DOTALL)
        
        if all_matches:
            # 尝试解析所有代码块，优先选择数组格式
            list_results = []
            dict_results = []
            
            for match_content in all_matches:
                json_str = sanitize_string(match_content)
                try:
                    parsed = json.loads(json_str)
                    if isinstance(parsed, list):
                        list_results.append(parsed)
                        logger.debug(f"找到数组格式的JSON，包含 {len(parsed)} 个元素")
                    elif isinstance(parsed, dict):
                        dict_results.append(parsed)
                        logger.debug(f"找到字典格式的JSON")
                except json.JSONDecodeError as e:
                    # 尝试修复常见错误后再解析
                    try:
                        fixed_json = fix_common_json_errors(json_str)
                        parsed = json.loads(fixed_json)
                        if isinstance(parsed, list):
                            list_results.append(parsed)
                        elif isinstance(parsed, dict):
                            dict_results.append(parsed)
                    except json.JSONDecodeError:
                        logger.debug(f"某个代码块解析失败，跳过: {str(e)[:100]}")
                        continue
            
            # 优先返回数组格式的结果（大多数步骤需要数组）
            if list_results:
                logger.info(f"使用数组格式的JSON结果（共找到 {len(list_results)} 个数组）")
                return list_results[-1]  # 返回最后一个数组（通常是最终结果）
            elif dict_results:
                logger.info(f"使用字典格式的JSON结果（共找到 {len(dict_results)} 个字典）")
                return dict_results[-1]  # 如果没有数组，返回最后一个字典
            else:
                logger.warning("所有代码块解析失败，尝试解析整个响应")
        
        # 2. 如果没有Markdown，或Markdown解析失败，尝试整个响应
        try:
            sanitized_response = sanitize_string(response)
            return json.loads(sanitized_response)
        except json.JSONDecodeError:
            # 3. 如果整个响应直接解析也失败，做最后一次尝试，用通用正则寻找
            logger.warning("直接解析响应失败，尝试使用通用正则寻找JSON...")
            json_match = re.search(r'\[[\s\S]*\]|\{[\s\S]*\}', response, re.DOTALL)
            if json_match:
                json_str = sanitize_string(json_match.group())
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError as e:
                    # 4. 最后尝试修复常见错误
                    try:
                        fixed_json = fix_common_json_errors(json_str)
                        return json.loads(fixed_json)
                    except json.JSONDecodeError as final_e:
                        logger.error(f"最终尝试解析失败: {final_e}")
                        # 保存原始响应以便调试
                        import tempfile
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                            f.write(response)
                            logger.error(f"原始响应已保存到 {f.name} 以便调试")
                        raise ValueError(f"无法从响应中解析出有效的JSON: {response[:200]}...") from final_e
            
            # 如果连通用正则都找不到，就彻底失败
            raise ValueError(f"无法从响应中解析出有效的JSON: {response[:200]}...")

    def call_with_streaming(
        self,
        prompt: str,
        input_data: Any = None,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> str:
        """
        使用流式模式调用LLM（支持实时进度反馈）

        Args:
            prompt: 提示词
            input_data: 输入数据
            progress_callback: 进度回调函数 (progress: int, message: str) -> None

        Returns:
            模型完整响应文本
        """
        async def _call_streaming():
            """异步流式调用"""
            full_response = []
            async for chunk in self.llm_manager.stream_call(prompt, input_data, progress_callback):
                if isinstance(chunk, dict):
                    content = chunk.get('content', chunk.get('text', ''))
                    if content:
                        full_response.append(content)
            return ''.join(full_response)

        return self._run_async_in_sync_context(_call_streaming)

    def get_current_provider_info(self) -> Dict[str, Any]:
        """获取当前提供商信息"""
        return self.llm_manager.get_current_provider_info()