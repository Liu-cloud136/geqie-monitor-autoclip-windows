"""
LLM 管理器 - 重构版
借鉴 author 项目设计，主要改进：
1. 支持多种 API 格式（OpenAI 兼容 / Gemini 原生 / Claude）
2. 支持异步调用
3. 支持流式响应
4. 支持代理配置
5. 统一的配置管理
"""
import json
import logging
import os
import asyncio
import hashlib
from typing import Dict, Any, Optional, List, AsyncGenerator, Callable
from pathlib import Path
from dataclasses import asdict
from dotenv import load_dotenv
from functools import lru_cache
from collections import OrderedDict

# 加载环境变量
env_path = Path(__file__).parent.parent.parent.parent / ".env"
load_dotenv(env_path)

from .llm_providers import (
    LLMProvider, LLMProviderFactory, ProviderType, 
    ModelInfo, LLMResponse, APIFormat
)
from services.exceptions import ConfigurationError, LLMError, SystemError

logger = logging.getLogger(__name__)

class LLMManager:
    """LLM管理器"""
    
    def __init__(self, settings_file: Optional[Path] = None):
        self.settings_file = settings_file or self._get_default_settings_file()
        self.current_provider: Optional[LLMProvider] = None
        self.settings = self._load_settings()
        self._initialize_provider()
        
        # 响应缓存 (使用 OrderedDict 实现 LRU 缓存)
        self._response_cache: OrderedDict[str, str] = OrderedDict()
        self._cache_max_size = 100
        self._cache_enabled = True
    
    def _get_default_settings_file(self) -> Path:
        """获取默认设置文件路径"""
        current_file = Path(__file__)
        project_root = current_file.parent.parent.parent  # backend/core -> backend -> project_root
        return project_root / "data" / "settings.json"
    
    def _load_settings(self) -> Dict[str, Any]:
        """加载设置"""
        default_settings = {
            # 当前激活的提供商
            "llm_provider": "dashscope",
            "model_name": "qwen-plus",

            # API 配置（多提供商独立配置）
            "provider_configs": {
                "dashscope": {
                    "api_key": "",
                    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                    "model": "qwen-plus",
                    "models": [],
                    "api_format": "openai"
                },
                "siliconflow": {
                    "api_key": "",
                    "base_url": "https://api.siliconflow.cn/v1",
                    "model": "Qwen/Qwen2.5-7B-Instruct",
                    "models": [],
                    "api_format": "openai"
                },
            },

            # 高级参数
            "temperature": 1.0,
            "top_p": 0.95,
            "max_tokens": 4096,
            "api_timeout": 600,  # 增加到10分钟，支持大批量处理

            # 代理配置
            "proxy_url": "",

            # 旧版兼容字段
            "dashscope_api_key": "",
            "openai_api_key": "",
            "gemini_api_key": "",
            "siliconflow_api_key": "",
            "chunk_size": 5000,
            "min_score_threshold": 80,  # 100分制
        }

        # 从环境变量加载 API 密钥
        if os.getenv("API_DASHSCOPE_API_KEY"):
            default_settings["provider_configs"]["dashscope"]["api_key"] = os.getenv("API_DASHSCOPE_API_KEY")
            default_settings["dashscope_api_key"] = os.getenv("API_DASHSCOPE_API_KEY")
        elif os.getenv("DASHSCOPE_API_KEY"):
            default_settings["provider_configs"]["dashscope"]["api_key"] = os.getenv("DASHSCOPE_API_KEY")
            default_settings["dashscope_api_key"] = os.getenv("DASHSCOPE_API_KEY")

        if os.getenv("SILICONFLOW_API_KEY"):
            default_settings["provider_configs"]["siliconflow"]["api_key"] = os.getenv("SILICONFLOW_API_KEY")
            default_settings["siliconflow_api_key"] = os.getenv("SILICONFLOW_API_KEY")

        # 加载自定义提供商配置
        if os.getenv("CUSTOM_API_KEY"):
            custom_config = {
                "api_key": os.getenv("CUSTOM_API_KEY"),
                "base_url": os.getenv("CUSTOM_BASE_URL", ""),
                "models_url": os.getenv("CUSTOM_MODELS_URL", ""),
                "model": os.getenv("CUSTOM_MODEL_NAME", "custom-model"),
                "api_format": os.getenv("CUSTOM_API_FORMAT", "openai"),
                "models": []
            }
            default_settings["provider_configs"]["custom"] = custom_config

        # 加载保存的设置
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    saved_settings = json.load(f)
                    default_settings.update(saved_settings)
                    
                    # 兼容旧版数据：迁移到 provider_configs
                    self._migrate_legacy_settings(default_settings)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"加载设置文件失败: {e}")
            except Exception as e:
                raise ConfigurationError(f"加载设置文件失败: {e}", cause=e)

        return default_settings
    
    def _migrate_legacy_settings(self, settings: Dict[str, Any]):
        """迁移旧版设置到新格式"""
        # 确保存在 provider_configs
        if "provider_configs" not in settings:
            settings["provider_configs"] = {}
        
        # 迁移 API keys
        legacy_keys = {
            "dashscope_api_key": "dashscope",
            "siliconflow_api_key": "siliconflow",
        }
        
        for legacy_key, provider in legacy_keys.items():
            if legacy_key in settings:
                if provider not in settings["provider_configs"]:
                    settings["provider_configs"][provider] = {}
                
                # 如果旧字段有值且新字段为空，则迁移
                legacy_value = settings[legacy_key]
                if legacy_value and not settings["provider_configs"][provider].get("api_key"):
                    settings["provider_configs"][provider]["api_key"] = legacy_value
                    logger.info(f"迁移 {legacy_key} 到 provider_configs.{provider}")
    
    def _save_settings(self):
        """保存设置"""
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except (IOError, OSError) as e:
            raise ConfigurationError(f"保存设置失败: {e}", cause=e)
    
    def _initialize_provider(self):
        """初始化当前提供商"""
        try:
            provider_key = self.settings.get("llm_provider", "dashscope")

            # 注册自定义提供商
            provider_configs = self.settings.get("provider_configs", {})
            if provider_key in provider_configs:
                config = provider_configs[provider_key]
                if provider_key.startswith("custom-"):
                    LLMProviderFactory.add_custom_provider_config(
                        provider_id=provider_key,
                        api_format=config.get("api_format", "openai"),
                        base_url=config.get("base_url", ""),
                        default_model=config.get("model", "")
                    )

            # 获取提供商配置
            provider_config = provider_configs.get(provider_key, {})

            api_key = provider_config.get("api_key", "")
            model_name = provider_config.get("model", "") or self.settings.get("model_name", "")
            base_url = provider_config.get("base_url", "")
            proxy_url = self.settings.get("proxy_url", "")
            timeout = self.settings.get("api_timeout", 120)
            api_format_str = provider_config.get("api_format", "openai")

            if api_key:
                # 根据提供商类型选择创建方法
                if provider_key.startswith("custom-"):
                    # 自定义提供商使用 create_provider_from_id
                    self.current_provider = LLMProviderFactory.create_provider_from_id(
                        provider_id=provider_key,
                        api_key=api_key,
                        model_name=model_name,
                        base_url=base_url,
                        proxy_url=proxy_url,
                        timeout=timeout,
                        api_format=APIFormat(api_format_str)
                    )
                else:
                    # 预定义提供商使用 create_provider
                    provider_type = ProviderType(provider_key)
                    self.current_provider = LLMProviderFactory.create_provider(
                        provider_type, api_key, model_name,
                        base_url=base_url,
                        proxy_url=proxy_url,
                        timeout=timeout,
                        api_format=APIFormat(api_format_str)
                    )
                logger.info(f"已初始化 {provider_key} 提供商，模型: {model_name}, 超时: {timeout}秒")
            else:
                logger.warning(f"未找到 {provider_key} 的 API 密钥")
                self.current_provider = None

        except (ValueError, KeyError) as e:
            logger.error(f"初始化提供商失败: {e}")
            self.current_provider = None
            raise ConfigurationError(f"初始化提供商失败: {e}", cause=e)
        except Exception as e:
            logger.error(f"初始化提供商失败: {e}")
            self.current_provider = None
            raise SystemError(f"初始化提供商失败: {e}", cause=e)
    
    def _get_api_key_for_provider(self, provider_type: ProviderType) -> str:
        """获取指定提供商的 API 密钥"""
        provider_key = provider_type.value
        provider_configs = self.settings.get("provider_configs", {})
        return provider_configs.get(provider_key, {}).get("api_key", "")
    
    def update_settings(self, new_settings: Dict[str, Any]):
        """更新设置"""
        self.settings.update(new_settings)
        self._save_settings()
        self._initialize_provider()
    
    def set_provider(self, provider_type: ProviderType, api_key: str, model_name: str,
                    base_url: str = "", api_format: str = "openai"):
        """设置提供商（使用 ProviderType 枚举）"""
        self.set_provider_by_id(
            provider_id=provider_type.value,
            api_key=api_key,
            model_name=model_name,
            base_url=base_url,
            api_format=api_format
        )
    
    def set_provider_by_id(self, provider_id: str, api_key: str, model_name: str,
                           base_url: str = "", api_format: str = "openai",
                           timeout: Optional[int] = None):
        """
        通过提供商ID设置提供商（支持自定义提供商）
        
        Args:
            provider_id: 提供商ID（可以是 ProviderType 枚举值或自定义ID如 custom-xxx）
            api_key: API密钥
            model_name: 模型名称
            base_url: 基础URL
            api_format: API格式
            timeout: 超时时间（秒），可选
        """
        try:
            provider_key = provider_id
            
            # 更新设置
            self.settings["llm_provider"] = provider_key
            self.settings["model_name"] = model_name
            
            # 更新提供商配置
            if "provider_configs" not in self.settings:
                self.settings["provider_configs"] = {}
            
            if provider_key not in self.settings["provider_configs"]:
                self.settings["provider_configs"][provider_key] = {}
            
            config = self.settings["provider_configs"][provider_key]
            config["api_key"] = api_key
            config["model"] = model_name
            if base_url:
                config["base_url"] = base_url
            config["api_format"] = api_format
            
            self._save_settings()
            
            # 创建新的提供商实例
            proxy_url = self.settings.get("proxy_url", "")
            # 使用传入的 timeout 或默认值
            actual_timeout = timeout or self.settings.get("api_timeout", 600)
            
            # 根据提供商类型选择创建方法
            if provider_key.startswith("custom-"):
                # 自定义提供商使用 create_provider_from_id
                # 先确保自定义提供商已注册
                if provider_key not in LLMProviderFactory._custom_providers:
                    LLMProviderFactory.add_custom_provider_config(
                        provider_id=provider_key,
                        api_format=api_format,
                        base_url=base_url,
                        default_model=model_name
                    )
                
                self.current_provider = LLMProviderFactory.create_provider_from_id(
                    provider_id=provider_key,
                    api_key=api_key,
                    model_name=model_name,
                    base_url=base_url,
                    proxy_url=proxy_url,
                    timeout=actual_timeout,
                    api_format=APIFormat(api_format)
                )
            else:
                # 预定义提供商使用 create_provider
                provider_type = ProviderType(provider_key)
                self.current_provider = LLMProviderFactory.create_provider(
                    provider_type, api_key, model_name,
                    base_url=base_url,
                    proxy_url=proxy_url,
                    timeout=actual_timeout,
                    api_format=APIFormat(api_format)
                )
            
            logger.info(f"已切换到 {provider_key} 提供商，模型: {model_name}")
            
        except (ValueError, KeyError) as e:
            logger.error(f"设置提供商失败: {e}")
            raise ConfigurationError(f"设置提供商失败: {e}", cause=e)
        except Exception as e:
            logger.error(f"设置提供商失败: {e}")
            raise SystemError(f"设置提供商失败: {e}", cause=e)
    
    def _generate_cache_key(self, prompt: str, input_data: Any = None, **kwargs) -> str:
        """生成缓存键"""
        cache_data = {
            "prompt": prompt,
            "input_data": str(input_data) if input_data else "",
            "model": self.settings.get("model_name", ""),
            "temperature": kwargs.get("temperature", self.settings.get("temperature", 1.0)),
            "top_p": kwargs.get("top_p", self.settings.get("top_p", 0.95)),
            "max_tokens": kwargs.get("max_tokens", self.settings.get("max_tokens", 4096))
        }
        cache_str = json.dumps(cache_data, ensure_ascii=False, sort_keys=True)
        return hashlib.md5(cache_str.encode('utf-8')).hexdigest()
    
    def _get_from_cache(self, cache_key: str) -> Optional[str]:
        """从缓存获取响应"""
        if not self._cache_enabled:
            return None
        return self._response_cache.get(cache_key)
    
    def _set_to_cache(self, cache_key: str, response: str):
        """设置缓存"""
        if not self._cache_enabled:
            return
        
        # 如果缓存已满，删除最旧的条目
        if len(self._response_cache) >= self._cache_max_size:
            self._response_cache.popitem(last=False)
        
        self._response_cache[cache_key] = response
    
    def clear_cache(self):
        """清空缓存"""
        self._response_cache.clear()
        logger.info("LLM 响应缓存已清空")
    
    def set_cache_enabled(self, enabled: bool):
        """启用或禁用缓存"""
        self._cache_enabled = enabled
        logger.info(f"LLM 响应缓存已{'启用' if enabled else '禁用'}")
    
    async def call(self, prompt: str, input_data: Any = None, 
                   use_cache: bool = True,
                   **kwargs) -> str:
        """调用 LLM（异步，支持缓存）"""
        if not self.current_provider:
            raise ValueError("未配置 LLM 提供商，请在设置页面配置 API 密钥")
        
        try:
            # 生成缓存键
            cache_key = self._generate_cache_key(prompt, input_data, **kwargs)
            
            # 尝试从缓存获取
            if use_cache and self._cache_enabled:
                cached_response = self._get_from_cache(cache_key)
                if cached_response is not None:
                    logger.debug(f"从缓存获取响应: {cache_key[:8]}...")
                    return cached_response
            
            # 构建消息
            messages = [{"role": "user", "content": prompt}]
            if input_data:
                import json as json_lib
                if isinstance(input_data, dict):
                    messages[0]["content"] += f"\n\n输入内容：\n{json_lib.dumps(input_data, ensure_ascii=False, indent=2)}"
                else:
                    messages[0]["content"] += f"\n\n输入内容：\n{input_data}"
            
            # 应用默认参数，并从kwargs中移除以避免重复
            temperature = kwargs.pop("temperature", self.settings.get("temperature", 1.0))
            top_p = kwargs.pop("top_p", self.settings.get("top_p", 0.95))
            max_tokens = kwargs.pop("max_tokens", self.settings.get("max_tokens", 4096))
            timeout = kwargs.pop("timeout", None)
            
            # 如果传入了 timeout，更新 provider 的超时设置
            if timeout and self.current_provider:
                self.current_provider.timeout = timeout
            
            response = await self.current_provider.call(
                messages,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                **kwargs
            )
            
            # 缓存响应
            if use_cache and self._cache_enabled:
                self._set_to_cache(cache_key, response.content)
            
            return response.content
        except (TimeoutError, ConnectionError, OSError) as e:
            logger.error(f"LLM 调用失败: {e}")
            raise LLMError(f"LLM调用失败: {e}", cause=e)
        except LLMError:
            raise
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            raise SystemError(f"LLM调用失败: {e}", cause=e)
    
    async def stream_call(self, prompt: str, input_data: Any = None,
                         progress_callback: Optional[Callable[[int, str], None]] = None,
                         **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式调用 LLM（异步，支持进度回调）

        Args:
            prompt: 提示词
            input_data: 输入数据
            progress_callback: 进度回调函数 (progress: int, message: str) -> None
            **kwargs: 其他参数

        Yields:
            流式响应块
        """
        if not self.current_provider:
            raise ValueError("未配置 LLM 提供商，请在设置页面配置 API 密钥")

        try:
            # 构建消息
            messages = [{"role": "user", "content": prompt}]
            if input_data:
                import json as json_lib
                if isinstance(input_data, dict):
                    messages[0]["content"] += f"\n\n输入内容：\n{json_lib.dumps(input_data, ensure_ascii=False, indent=2)}"
                else:
                    messages[0]["content"] += f"\n\n输入内容：\n{input_data}"

            # 应用默认参数，并从kwargs中移除以避免重复
            temperature = kwargs.pop("temperature", self.settings.get("temperature", 1.0))
            top_p = kwargs.pop("top_p", self.settings.get("top_p", 0.95))
            max_tokens = kwargs.pop("max_tokens", self.settings.get("max_tokens", 4096))
            timeout = kwargs.pop("timeout", None)
            
            # 如果传入了 timeout，更新 provider 的超时设置
            if timeout and self.current_provider:
                self.current_provider.timeout = timeout

            # 获取进度回调
            async for chunk in self.current_provider.stream_call(
                messages,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                **kwargs
            ):
                # 如果有进度回调且块包含进度信息
                if progress_callback and isinstance(chunk, dict):
                    progress = chunk.get("progress", None)
                    message = chunk.get("message", "")
                    if progress is not None:
                        progress_callback(progress, message)

                yield chunk
        except (TimeoutError, ConnectionError, OSError) as e:
            logger.error(f"LLM 流式调用失败: {e}")
            raise LLMError(f"LLM流式调用失败: {e}", cause=e)
        except LLMError:
            raise
        except Exception as e:
            logger.error(f"LLM 流式调用失败: {e}")
            raise SystemError(f"LLM流式调用失败: {e}", cause=e)
    
    async def test_provider_connection(self, provider_type: ProviderType, 
                                      api_key: str, model_name: str,
                                      base_url: str = "") -> Dict[str, Any]:
        """测试提供商连接（异步）"""
        try:
            provider = LLMProviderFactory.create_provider(
                provider_type, api_key, model_name,
                base_url=base_url,
                proxy_url=self.settings.get("proxy_url", "")
            )
            return await provider.test_connection()
        except Exception as e:
            logger.error(f"测试 {provider_type.value} 连接失败: {e}")
            return {"success": False, "error": str(e)}
    
    def get_current_provider_info(self) -> Dict[str, Any]:
        """获取当前提供商信息"""
        if not self.current_provider:
            return {"provider": None, "model": None, "available": False}
        
        provider_id = self.settings.get("llm_provider", "dashscope")
        model_name = self.settings.get("model_name", "qwen-plus")
        
        return {
            "provider": provider_id,
            "model": model_name,
            "available": True,
            "display_name": self._get_provider_display_name(provider_id)
        }
    
    def _get_provider_display_name(self, provider_id: str) -> str:
        """获取提供商显示名称"""
        display_names = {
            ProviderType.DASHSCOPE.value: "阿里通义千问",
            ProviderType.SILICONFLOW.value: "硅基流动",
        }

        return display_names.get(provider_id, provider_id)
    
    async def get_all_available_models(self, provider_type: Optional[ProviderType] = None,
                                      embed_only: bool = False) -> Dict[str, List[Dict[str, Any]]]:
        """
        获取所有可用模型（异步）
        
        Args:
            provider_type: 指定提供商类型，如果为 None 则获取当前激活的提供商
            embed_only: 是否只获取嵌入模型
        """
        # 获取 API 密钥字典
        api_keys = {}
        provider_configs = {}
        
        if provider_type:
            # 只获取指定提供商的模型
            key = provider_type.value
            config = self.settings.get("provider_configs", {}).get(key, {})
            api_key = config.get("api_key", "")
            
            if api_key and api_key.strip() and api_key != "dummy_key":
                api_keys[provider_type] = api_key
                provider_configs[provider_type] = {
                    "base_url": config.get("base_url", ""),
                    "proxy_url": self.settings.get("proxy_url", "")
                }
        else:
            # 获取所有配置了 API Key 的提供商
            provider_id = self.settings.get("llm_provider", "dashscope")
            
            # 如果是自定义提供商，跳过（自定义提供商通过其他方式获取模型）
            if provider_id.startswith("custom-"):
                return {}
            
            try:
                current_provider_type = ProviderType(provider_id)
            except ValueError:
                # 不是有效的预定义提供商，返回空
                return {}
            
            key = current_provider_type.value
            config = self.settings.get("provider_configs", {}).get(key, {})
            api_key = config.get("api_key", "")
            
            if api_key and api_key.strip() and api_key != "dummy_key":
                api_keys[current_provider_type] = api_key
                provider_configs[current_provider_type] = {
                    "base_url": config.get("base_url", ""),
                    "proxy_url": self.settings.get("proxy_url", "")
                }
        
        # 获取模型列表
        all_models = await LLMProviderFactory.get_all_available_models(
            api_keys, provider_configs, embed_only=embed_only
        )
        
        # 转换为字典格式
        result = {}
        for provider_type, models in all_models.items():
            provider_name = provider_type.value
            result[provider_name] = [
                {
                    "id": model.id,
                    "display_name": model.display_name,
                    "max_tokens": model.max_tokens,
                    "description": model.description
                }
                for model in models
            ]
        
        return result
    
    async def fetch_provider_models(self, provider_type: ProviderType, 
                                   embed_only: bool = False) -> List[Dict[str, Any]]:
        """
        拉取指定提供商的模型列表（异步）
        
        Args:
            provider_type: 提供商类型
            embed_only: 是否只获取嵌入模型
        """
        try:
            key = provider_type.value
            config = self.settings.get("provider_configs", {}).get(key, {})
            api_key = config.get("api_key", "")
            
            if not api_key or not api_key.strip() or api_key == "dummy_key":
                return []
            
            provider = LLMProviderFactory.create_provider(
                provider_type, api_key, "",
                base_url=config.get("base_url", ""),
                proxy_url=self.settings.get("proxy_url", "")
            )
            
            models = await provider.get_available_models(embed_only=embed_only)
            
            # 更新配置中的模型列表
            config["models"] = [model.id for model in models]
            config["api_key"] = api_key  # 确保存入 API Key
            if provider_type.value not in self.settings["provider_configs"]:
                self.settings["provider_configs"][provider_type.value] = {}
            self.settings["provider_configs"][provider_type.value].update(config)
            self._save_settings()
            
            return [
                {
                    "id": model.id,
                    "display_name": model.display_name,
                    "max_tokens": model.max_tokens,
                    "description": model.description
                }
                for model in models
            ]
        except Exception as e:
            logger.error(f"拉取 {provider_type.value} 模型列表失败: {e}")
            return []
    
    def parse_json_response(self, response: str) -> Any:
        """解析 JSON 响应（保持兼容性）"""
        import re
        import json as json_lib
        
        # 尝试直接解析
        try:
            return json_lib.loads(response)
        except:
            pass
        
        # 尝试提取 JSON 代码块
        pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        match = re.search(pattern, response)
        if match:
            try:
                return json_lib.loads(match.group(1))
            except:
                pass
        
        # 尝试查找 JSON 对象
        pattern = r'\{[\s\S]*\}'
        match = re.search(pattern, response)
        if match:
            try:
                return json_lib.loads(match.group(0))
            except:
                pass
        
        raise ValueError("无法从响应中提取有效的 JSON")

class BatchLLMClient:
    """批量请求合并客户端"""
    
    def __init__(self, llm_manager: LLMManager, batch_size: int = 10, timeout: int = 5):
        self.llm_manager = llm_manager
        self.batch_size = batch_size
        self.timeout = timeout
        self._batch: List[Dict[str, Any]] = []
        self._batch_lock = asyncio.Lock()
        self._request_counter = 0
        self._pending_results: Dict[int, str] = {}
    
    async def add_request(self, prompt: str, input_data: Any = None, **kwargs) -> str:
        """
        添加请求到批次并返回结果
        
        Args:
            prompt: 提示词
            input_data: 输入数据
            **kwargs: 其他参数
            
        Returns:
            模型响应文本（如果已执行），否则返回 None
        """
        async with self._batch_lock:
            # 检查是否有相似的请求可以合并
            for existing_request in self._batch:
                if self._is_similar_request(existing_request, prompt, input_data, kwargs):
                    logger.debug("合并相似请求")
                    return existing_request["result"]
            
            # 如果批次已满，先执行当前批次
            if len(self._batch) >= self.batch_size:
                await self._execute_batch()
            
            # 添加新请求
            request_id = self._request_counter
            self._request_counter += 1
            
            self._batch.append({
                "id": request_id,
                "prompt": prompt,
                "input_data": input_data,
                "kwargs": kwargs,
                "result": None
            })
            
            # 如果达到批次大小，立即执行并返回结果
            if len(self._batch) >= self.batch_size:
                await self._execute_batch()
                return self._pending_results.get(request_id, None)
            
            # 未达到批次大小，返回 None
            return None
    
    async def flush(self) -> List[str]:
        """
        执行当前批次中的所有请求
        
        Returns:
            所有请求的结果列表
        """
        async with self._batch_lock:
            if self._batch:
                await self._execute_batch()
                return [req["result"] for req in self._batch]
            return []
    
    async def _execute_batch(self):
        """执行批次中的所有请求"""
        if not self._batch:
            return
        
        logger.info(f"执行批次请求，共 {len(self._batch)} 个请求")
        
        # 复制批次数据，然后清空批次
        batch_to_execute = self._batch.copy()
        self._batch.clear()
        
        # 并发执行所有请求
        tasks = []
        for request in batch_to_execute:
            task = asyncio.create_task(
                self._execute_single_request(request)
            )
            tasks.append(task)
        
        # 等待所有任务完成
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _execute_single_request(self, request: Dict[str, Any]):
        """执行单个请求"""
        try:
            result = await self.llm_manager.call(
                prompt=request["prompt"],
                input_data=request["input_data"],
                use_cache=True,
                **request["kwargs"]
            )
            request["result"] = result
            self._pending_results[request["id"]] = result
        except Exception as e:
            logger.error(f"请求执行失败: {e}")
            error_msg = str(e)
            request["result"] = error_msg
            self._pending_results[request["id"]] = error_msg
    
    def _is_similar_request(self, existing_request: Dict[str, Any], 
                           prompt: str, input_data: Any, kwargs: Dict[str, Any]) -> bool:
        """
        判断是否为相似请求（可以合并）
        
        Args:
            existing_request: 已存在的请求
            prompt: 新请求的提示词
            input_data: 新请求的输入数据
            kwargs: 新请求的参数
            
        Returns:
            是否相似
        """
        # 如果已有结果，检查提示词和参数是否相同
        if existing_request["result"] is None:
            return False
        
        # 检查提示词是否相同
        if existing_request["prompt"] != prompt:
            return False
        
        # 检查输入数据是否相同
        if str(existing_request["input_data"]) != str(input_data):
            return False
        
        # 检查关键参数是否相同
        for key in ["temperature", "top_p", "max_tokens"]:
            if existing_request["kwargs"].get(key) != kwargs.get(key):
                return False
        
        return True

# 全局 LLM 管理器实例
_llm_manager: Optional[LLMManager] = None

def get_llm_manager() -> LLMManager:
    """获取全局 LLM 管理器实例"""
    global _llm_manager
    if _llm_manager is None:
        _llm_manager = LLMManager()
    return _llm_manager

def initialize_llm_manager(settings_file: Optional[Path] = None) -> LLMManager:
    """初始化 LLM 管理器"""
    global _llm_manager
    _llm_manager = LLMManager(settings_file)
    return _llm_manager
