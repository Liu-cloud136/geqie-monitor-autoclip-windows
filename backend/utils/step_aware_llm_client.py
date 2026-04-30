"""
步骤感知的LLM客户端 - 根据步骤类型使用不同的配置
"""
import logging
from typing import Any, Optional, Callable, Dict
from pathlib import Path
import asyncio

from core.step_config import StepType, get_step_config_manager

logger = logging.getLogger(__name__)

class StepAwareLLMClient:
    """
    步骤感知的LLM客户端
    可以根据不同的步骤类型使用不同的AI模型和参数配置
    """
    
    def __init__(self):
        self._llm_manager = None
        self.step_config_manager = get_step_config_manager()
    
    @property
    def llm_manager(self):
        """延迟加载 LLM 管理器以避免循环导入"""
        if self._llm_manager is None:
            from core.llm_manager import get_llm_manager
            self._llm_manager = get_llm_manager()
        return self._llm_manager
    
    def _update_provider_timeout(self, timeout: int):
        """更新当前提供商的超时设置"""
        if self.llm_manager.current_provider:
            self.llm_manager.current_provider.timeout = timeout
            logger.debug(f"已更新提供商超时时间: {timeout}秒")
    
    def _apply_custom_prompt(self, prompt: str, custom_prompt: Optional[str]) -> str:
        """
        应用自定义提示词
        
        Args:
            prompt: 默认提示词
            custom_prompt: 自定义提示词（如果以 "PREPEND:" 开头则前置，以 "APPEND:" 开头则追加，否则替换）
            
        Returns:
            处理后的提示词
        """
        if not custom_prompt:
            return prompt
        
        custom_prompt = custom_prompt.strip()
        
        if custom_prompt.startswith("PREPEND:"):
            # 前置模式
            prepend_text = custom_prompt[8:].strip()
            return f"{prepend_text}\n\n{prompt}"
        elif custom_prompt.startswith("APPEND:"):
            # 追加模式
            append_text = custom_prompt[7:].strip()
            return f"{prompt}\n\n{append_text}"
        else:
            # 替换模式
            return custom_prompt
    
    async def call_for_step(
        self,
        step_type: StepType,
        prompt: str,
        input_data: Any = None,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        **kwargs
    ) -> str:
        """
        为特定步骤调用LLM
        
        Args:
            step_type: 步骤类型
            prompt: 提示词
            input_data: 输入数据
            progress_callback: 进度回调函数
            **kwargs: 额外参数
            
        Returns:
            LLM响应文本
        """
        # 每次调用都重新获取最新的配置
        from core.step_config import get_step_config_manager
        config_manager = get_step_config_manager()
        config = config_manager.get_step_config(step_type)
        
        # 检查步骤是否启用
        if not config.enabled:
            logger.warning(f"步骤 {step_type.value} 已禁用，跳过处理")
            return ""
        
        try:
            # 获取当前的LLM提供商
            current_provider_info = self.llm_manager.get_current_provider_info()
            
            # 如果当前提供商与配置的提供商不同，需要切换
            if current_provider_info.get("provider") != config.provider:
                logger.info(f"为步骤 {step_type.value} 切换提供商: {current_provider_info.get('provider')} -> {config.provider}")
                
                # 获取提供商配置
                provider_configs = self.llm_manager.settings.get("provider_configs", {})
                provider_config = provider_configs.get(config.provider, {})
                
                if not provider_config.get("api_key"):
                    raise ValueError(f"提供商 {config.provider} 未配置API密钥")
                
                # 设置提供商（支持自定义提供商），传递 timeout
                self.llm_manager.set_provider_by_id(
                    provider_id=config.provider,
                    api_key=provider_config["api_key"],
                    model_name=config.model,
                    base_url=provider_config.get("base_url", ""),
                    api_format=provider_config.get("api_format", "openai"),
                    timeout=config.timeout
                )
            else:
                # 相同提供商，只更新模型和超时
                self.llm_manager.settings["model_name"] = config.model
                if self.llm_manager.current_provider:
                    self.llm_manager.current_provider.model_name = config.model
                # 更新超时设置
                self._update_provider_timeout(config.timeout)
            
            # 应用自定义提示词
            final_prompt = self._apply_custom_prompt(prompt, config.custom_prompt)
            if config.custom_prompt:
                logger.debug(f"步骤 {step_type.value} 应用了自定义提示词")
            
            # 合并自定义参数（不覆盖已有参数）
            extra_kwargs = {}
            if config.custom_params:
                extra_kwargs.update(config.custom_params)
            # kwargs 中的参数优先级更高
            extra_kwargs.update(kwargs)
            
            # 调用LLM，传递 timeout 参数和自定义参数
            response = await self.llm_manager.call(
                prompt=final_prompt,
                input_data=input_data,
                temperature=config.temperature,
                top_p=config.top_p,
                max_tokens=config.max_tokens,
                timeout=config.timeout,
                **extra_kwargs
            )
            
            logger.debug(f"步骤 {step_type.value} 调用完成，使用模型: {config.model}, 超时: {config.timeout}秒")
            return response
            
        except Exception as e:
            logger.error(f"步骤 {step_type.value} 调用失败: {e}")
            raise
    
    async def stream_call_for_step(
        self,
        step_type: StepType,
        prompt: str,
        input_data: Any = None,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        **kwargs
    ):
        """
        为特定步骤流式调用LLM
        
        Args:
            step_type: 步骤类型
            prompt: 提示词
            input_data: 输入数据
            progress_callback: 进度回调函数
            **kwargs: 额外参数
            
        Yields:
            流式响应块
        """
        # 每次调用都重新获取最新的配置
        from core.step_config import get_step_config_manager
        config_manager = get_step_config_manager()
        config = config_manager.get_step_config(step_type)
        
        # 检查步骤是否启用
        if not config.enabled:
            logger.warning(f"步骤 {step_type.value} 已禁用，跳过处理")
            yield {"done": True}
            return
        
        try:
            # 获取当前的LLM提供商
            current_provider_info = self.llm_manager.get_current_provider_info()
            
            # 如果当前提供商与配置的提供商不同，需要切换
            if current_provider_info.get("provider") != config.provider:
                logger.info(f"为步骤 {step_type.value} 切换提供商: {current_provider_info.get('provider')} -> {config.provider}")
                
                # 获取提供商配置
                provider_configs = self.llm_manager.settings.get("provider_configs", {})
                provider_config = provider_configs.get(config.provider, {})
                
                if not provider_config.get("api_key"):
                    raise ValueError(f"提供商 {config.provider} 未配置API密钥")
                
                # 设置提供商（支持自定义提供商），传递 timeout
                self.llm_manager.set_provider_by_id(
                    provider_id=config.provider,
                    api_key=provider_config["api_key"],
                    model_name=config.model,
                    base_url=provider_config.get("base_url", ""),
                    api_format=provider_config.get("api_format", "openai"),
                    timeout=config.timeout
                )
            else:
                # 相同提供商，只更新模型和超时
                self.llm_manager.settings["model_name"] = config.model
                if self.llm_manager.current_provider:
                    self.llm_manager.current_provider.model_name = config.model
                # 更新超时设置
                self._update_provider_timeout(config.timeout)
            
            # 应用自定义提示词
            final_prompt = self._apply_custom_prompt(prompt, config.custom_prompt)
            if config.custom_prompt:
                logger.debug(f"步骤 {step_type.value} 应用了自定义提示词")
            
            # 合并自定义参数（不覆盖已有参数）
            extra_kwargs = {}
            if config.custom_params:
                extra_kwargs.update(config.custom_params)
            # kwargs 中的参数优先级更高
            extra_kwargs.update(kwargs)
            
            # 流式调用LLM，传递 timeout 参数和自定义参数
            async for chunk in self.llm_manager.stream_call(
                prompt=final_prompt,
                input_data=input_data,
                temperature=config.temperature,
                top_p=config.top_p,
                max_tokens=config.max_tokens,
                timeout=config.timeout,
                progress_callback=progress_callback,
                **extra_kwargs
            ):
                yield chunk
            
            logger.debug(f"步骤 {step_type.value} 流式调用完成，使用模型: {config.model}, 超时: {config.timeout}秒")
            
        except Exception as e:
            logger.error(f"步骤 {step_type.value} 流式调用失败: {e}")
            raise

# 全局步骤感知LLM客户端实例
_step_aware_llm_client: Optional[StepAwareLLMClient] = None

def get_step_aware_llm_client() -> StepAwareLLMClient:
    """获取全局步骤感知LLM客户端实例"""
    global _step_aware_llm_client
    if _step_aware_llm_client is None:
        _step_aware_llm_client = StepAwareLLMClient()
    return _step_aware_llm_client
