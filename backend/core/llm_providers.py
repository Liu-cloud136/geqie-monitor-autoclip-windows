"""
多模型提供商统一接口 - 重构版
支持 OpenAI 兼容格式、Gemini 原生格式、Claude 等
主要改进：
1. 统一使用 OpenAI 兼容格式作为主要接口
2. 智能模型列表拉取（多路径尝试 + 超时保护）
3. 支持 HTTP 代理
4. 支持流式响应（SSE）
5. 支持多种 API 格式（OpenAI/Gemini/Claude）
"""
import json
import logging
import asyncio
import aiohttp
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, AsyncGenerator, Callable
from enum import Enum
from dataclasses import dataclass
from pathlib import Path
import time

logger = logging.getLogger(__name__)

class ProviderType(Enum):
    """模型提供商类型"""
    DASHSCOPE = "dashscope"      # 阿里通义千问
    OPENAI = "openai"            # OpenAI
    GEMINI = "gemini"            # Google Gemini
    SILICONFLOW = "siliconflow"  # 硅基流动
    CLAUDE = "claude"            # Anthropic Claude
    CUSTOM = "custom"            # 自定义提供商

class APIFormat(Enum):
    """API 格式类型"""
    OPENAI = "openai"      # OpenAI 兼容格式
    GEMINI = "gemini"      # Gemini 原生格式
    ANTHROPIC = "anthropic"  # Anthropic 格式

@dataclass
class ModelInfo:
    """模型信息"""
    id: str
    display_name: str
    provider: ProviderType
    max_tokens: int = 8192
    cost_per_token: Optional[float] = None
    description: Optional[str] = None

@dataclass
class LLMResponse:
    """LLM响应"""
    content: str
    usage: Optional[Dict[str, Any]] = None
    model: Optional[str] = None
    finish_reason: Optional[str] = None
    thinking: Optional[str] = None  # 思维链内容（DeepSeek R1 等）

class LLMProvider(ABC):
    """LLM提供商抽象基类"""
    
    def __init__(self, api_key: str, model_name: str, provider_type: ProviderType = None, **kwargs):
        self.api_key = api_key
        self.model_name = model_name
        self.provider_type = provider_type
        self.kwargs = kwargs
        self.base_url = kwargs.get("base_url", "")
        self.proxy_url = kwargs.get("proxy_url", "")
        self.timeout = kwargs.get("timeout", 600)  # 增加默认超时到10分钟
        self.api_format = kwargs.get("api_format", APIFormat.OPENAI)
    
    @abstractmethod
    async def call(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        """
        调用模型API
        
        Args:
            messages: 消息列表，格式 [{"role": "user", "content": "..."}]
            **kwargs: 其他参数（temperature, max_tokens, top_p等）
            
        Returns:
            LLMResponse: 模型响应
        """
        pass
    
    @abstractmethod
    async def stream_call(self, messages: List[Dict[str, str]], **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式调用模型API
        
        Args:
            messages: 消息列表
            **kwargs: 其他参数
            
        Yields:
            Dict: 流式响应片段，格式 {"text": "...", "thinking": "...", "usage": {...}}
        """
        pass
    
    @abstractmethod
    async def test_connection(self) -> Dict[str, Any]:
        """
        测试API连接
        
        Returns:
            Dict: {"success": bool, "error": str, "message": str, "reply": str}
        """
        pass
    
    @abstractmethod
    async def get_available_models(self, embed_only: bool = False) -> List[ModelInfo]:
        """
        获取可用模型列表
        
        Args:
            embed_only: 是否只获取嵌入模型
            
        Returns:
            List[ModelInfo]: 可用模型列表
        """
        pass
    
    async def _make_request(self, url: str, method: str = "GET", 
                          headers: Optional[Dict] = None,
                          json_data: Optional[Dict] = None,
                          timeout: Optional[float] = None) -> aiohttp.ClientResponse:
        """统一的 HTTP 请求方法，支持代理"""
        timeout = timeout or aiohttp.ClientTimeout(total=self.timeout)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            proxy = self.proxy_url if self.proxy_url else None
            
            if method.upper() == "GET":
                return await session.get(url, headers=headers, proxy=proxy)
            else:
                return await session.post(url, headers=headers, json=json_data, proxy=proxy)

class OpenAICompatProvider(LLMProvider):
    """OpenAI 兼容格式提供商（适用于大多数供应商）"""
    
    def __init__(self, api_key: str, model_name: str = "gpt-3.5-turbo", provider_type: ProviderType = None, **kwargs):
        super().__init__(api_key, model_name, provider_type, **kwargs)
        # 默认 baseUrl 可以通过 kwargs 覆盖
        if not self.base_url:
            self.base_url = kwargs.get("default_base_url", "https://open.bigmodel.cn/api/paas/v4")
        self.base_url = self.base_url.rstrip('/')
    
    async def call(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        """调用 OpenAI 兼容 API"""
        try:
            url = f"{self.base_url}/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # 构建请求参数
            data = {
                "model": self.model_name,
                "messages": messages,
                **kwargs
            }
            
            logger.info(f"调用 `{self.base_url}`，模型: {self.model_name}")
            
            response = await self._make_request(url, "POST", headers, data)
            
            # 处理响应
            try:
                result = await response.json()
            except json.JSONDecodeError as e:
                error_text = await response.text()
                raise Exception(f"API响应解析失败: {error_text}") from e
            
            if response.status != 200:
                error_msg = result.get("error", {}).get("message", "Unknown error")
                request_id = result.get("error", {}).get("request_id", "")
                if request_id:
                    error_msg = f"{error_msg} (request_id: {request_id})"
                raise Exception(f"API错误 ({response.status}): {error_msg}")
            
            if "choices" not in result or len(result["choices"]) == 0:
                raise Exception(f"API响应格式错误: {result}")
            
            choice = result["choices"][0]
            content = choice.get("message", {}).get("content", "")
            finish_reason = choice.get("finish_reason")
            reasoning = choice.get("message", {}).get("reasoning_content")
            
            usage = None
            if "usage" in result:
                usage = {
                    "prompt_tokens": result["usage"].get("prompt_tokens", 0),
                    "completion_tokens": result["usage"].get("completion_tokens", 0),
                    "total_tokens": result["usage"].get("total_tokens", 0)
                }
            
            return LLMResponse(
                content=content,
                usage=usage,
                model=self.model_name,
                finish_reason=finish_reason,
                thinking=reasoning
            )
            
        except Exception as e:
            logger.error(f"OpenAI兼容API调用失败: {str(e)}")
            raise
    
    async def stream_call(self, messages: List[Dict[str, str]], **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        """流式调用 OpenAI 兼容 API"""
        try:
            url = f"{self.base_url}/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": self.model_name,
                "messages": messages,
                "stream": True,
                **kwargs
            }
            
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                proxy = self.proxy_url if self.proxy_url else None
                async with session.post(url, headers=headers, json=data, proxy=proxy) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"流式API错误 ({response.status}): {error_text}")
                    
                    async for line in response.content:
                        line_str = line.decode('utf-8').strip()
                        if not line_str or line_str.startswith(':'):
                            continue
                        
                        if line_str == 'data: [DONE]':
                            yield {"done": True}
                            continue
                        
                        if line_str.startswith('data: '):
                            try:
                                json_str = line_str[6:]  # 去掉 'data: ' 前缀
                                json_data = json.loads(json_str)
                                
                                delta = json_data.get("choices", [{}])[0].get("delta", {})
                                
                                # 思维链（DeepSeek R1）
                                thinking = delta.get("reasoning_content")
                                if thinking:
                                    yield {"thinking": thinking}
                                
                                # 正文内容
                                content = delta.get("content")
                                if content:
                                    yield {"text": content}
                                
                                # usage 信息
                                if "usage" in json_data:
                                    usage = json_data["usage"]
                                    yield {
                                        "usage": {
                                            "prompt_tokens": usage.get("prompt_tokens", 0),
                                            "completion_tokens": usage.get("completion_tokens", 0),
                                            "total_tokens": usage.get("total_tokens", 0)
                                        }
                                    }
                                
                            except json.JSONDecodeError:
                                continue
                                
        except Exception as e:
            logger.error(f"流式调用失败: {str(e)}")
            raise
    
    async def test_connection(self) -> Dict[str, Any]:
        """测试连接"""
        try:
            messages = [{"role": "user", "content": "请回复'连接成功'"}]
            response = await self.call(messages, max_tokens=20)
            
            if "连接成功" in response.content or len(response.content) > 0:
                return {
                    "success": True,
                    "message": "✅ API 连接成功！",
                    "model": self.model_name,
                    "reply": response.content.strip()
                }
            else:
                return {
                    "success": False,
                    "error": "API返回异常内容",
                    "reply": response.content
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_available_models(self, embed_only: bool = False) -> List[ModelInfo]:
        """
        获取可用模型 - 智能拉取（多路径尝试 + 超时保护）
        参考 author 项目：Cherry Studio 的实现方式
        """
        try:
            # 构建候选路径列表（兼容不同的 baseUrl 格式）
            paths_to_try = []
            if self.base_url.endswith('/v1') or self.base_url.endswith('/v1beta'):
                paths_to_try.append(f"{self.base_url}/models")
            else:
                paths_to_try.append(f"{self.base_url}/models")
                paths_to_try.append(f"{self.base_url}/v1/models")
            
            models = []
            last_error = None
            
            for url in paths_to_try:
                try:
                    headers = {
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    }
                    
                    # 15秒超时
                    timeout = aiohttp.ClientTimeout(total=15)
                    async with aiohttp.ClientSession(timeout=timeout) as session:
                        proxy = self.proxy_url if self.proxy_url else None
                        async with session.get(url, headers=headers, proxy=proxy) as response:
                            if response.status != 200:
                                last_error = response
                                continue
                            
                            data = await response.json()
                            raw_models = self._extract_model_array(data)
                            
                            if len(raw_models) > 0:
                                models = raw_models
                                break
                            
                except asyncio.TimeoutError:
                    logger.warning(f"模型拉取超时: {url}")
                    continue
                except Exception as e:
                    logger.warning(f"模型拉取失败 {url}: {str(e)}")
                    last_error = e
                    continue
            
            if len(models) == 0:
                logger.warning(f"未能获取到模型列表，使用默认模型: {self.model_name}")
                return [ModelInfo(
                    id=self.model_name,
                    display_name=self.model_name,
                    provider=self.provider_type,
                    description="默认模型"
                )]
            
            # 如果需要嵌入模型，进行过滤
            if embed_only:
                models = self._filter_embed_models(models)
            
            # 转换为 ModelInfo
            result = []
            for m in models:
                model_id = (m.get("id") or m.get("name", "")).strip()
                if not model_id:
                    continue
                result.append(ModelInfo(
                    id=model_id,
                    display_name=m.get("display_name") or m.get("name") or model_id,
                    provider=self.provider_type,
                    max_tokens=8192,
                    description=m.get("description", "")
                ))
            
            # 按 ID 排序
            result.sort(key=lambda x: x.id)
            return result
            
        except Exception as e:
            logger.error(f"获取模型列表失败: {str(e)}")
            return [ModelInfo(
                id=self.model_name,
                display_name=self.model_name,
                provider=self.provider_type,
                description=f"默认模型（获取列表失败: {str(e)}）"
            )]
    
    def _extract_model_array(self, data: Any) -> List[Dict]:
        """从不同格式的响应中提取模型数组"""
        if isinstance(data, dict):
            if "data" in data and isinstance(data["data"], list):
                return data["data"]
            if "models" in data and isinstance(data["models"], list):
                return data["models"]
            if "results" in data and isinstance(data["results"], list):
                return data["results"]
        elif isinstance(data, list):
            return data
        return []
    
    def _filter_embed_models(self, models: List[Dict]) -> List[Dict]:
        """过滤嵌入模型（参考 Cherry Studio）"""
        EMBED_REGEX = r'(?:^text-|embed|bge[-_]|bce[-_]|e5[-_]|gte[-_]|jina-clip|jina-embed|voyage-|uae[-_]|retrieval|LLM2Vec)'
        RERANK_REGEX = r'(?:rerank|re-rank|re-ranker)'
        
        filtered = []
        for m in models:
            model_id = m.get("id") or m.get("name", "")
            if (EMBED_REGEX in model_id.lower() or
                any(kw in model_id.lower() for kw in ['embed', 'embedding', 'bge', 'e5', 'jina'])):
                if not any(kw in model_id.lower() for kw in ['rerank', 're-rank']):
                    filtered.append(m)
        return filtered if filtered else models



class LLMProviderFactory:
    """LLM提供商工厂"""
    
    _provider_configs = {
        ProviderType.DASHSCOPE: {
            "class": OpenAICompatProvider,
            "default_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "default_model": "qwen-plus"
        },
        ProviderType.OPENAI: {
            "class": OpenAICompatProvider,
            "default_base_url": "https://api.openai.com/v1",
            "default_model": "gpt-4"
        },
        ProviderType.GEMINI: {
            "class": OpenAICompatProvider,
            "default_base_url": "https://generativelanguage.googleapis.com/v1beta",
            "default_model": "gemini-pro"
        },
        ProviderType.SILICONFLOW: {
            "class": OpenAICompatProvider,
            "default_base_url": "https://api.siliconflow.cn/v1",
            "default_model": "Qwen/Qwen2.5-7B-Instruct"
        },
        ProviderType.CLAUDE: {
            "class": OpenAICompatProvider,
            "default_base_url": "https://api.anthropic.com/v1",
            "default_model": "claude-3-opus-20240229"
        },
        ProviderType.CUSTOM: {
            "class": OpenAICompatProvider,
            "default_base_url": "",
            "default_model": "custom-model"
        }
    }
    
    _custom_providers = {}
    
    @classmethod
    def add_custom_provider_config(cls, provider_id: str, api_format: str = "openai",
                                   base_url: str = "", default_model: str = "custom-model"):
        """
        动态添加自定义提供商配置
        
        Args:
            provider_id: 提供商ID（如 "custom-xxx"）
            api_format: API格式（openai/gemini/anthropic）
            base_url: API基础URL
            default_model: 默认模型名称
        """
        cls._custom_providers[provider_id] = {
            "class": OpenAICompatProvider,
            "default_base_url": base_url,
            "default_model": default_model,
            "api_format": api_format
        }
        logger.info(f"已注册自定义提供商: {provider_id}")


    
    @classmethod
    def create_provider(cls, provider_type: ProviderType, api_key: str, 
                      model_name: str, **kwargs) -> LLMProvider:
        """创建提供商实例"""
        config = None
        
        if provider_type not in cls._provider_configs:
            raise ValueError(f"不支持的提供商类型: {provider_type}")
        
        config = cls._provider_configs[provider_type]
        provider_class = config["class"]
        
        # 设置默认 baseUrl
        if "base_url" not in kwargs or not kwargs["base_url"]:
            kwargs["base_url"] = config["default_base_url"]
        
        # 设置默认模型名
        if not model_name:
            model_name = config["default_model"]
        
        return provider_class(api_key, model_name, **kwargs)
    
    @classmethod
    def create_provider_from_id(cls, provider_id: str, api_key: str, 
                               model_name: str, **kwargs) -> LLMProvider:
        """
        通过提供商ID创建提供商实例（支持自定义提供商）
        
        Args:
            provider_id: 提供商ID（可以是 ProviderType 枚举值或自定义ID）
            api_key: API密钥
            model_name: 模型名称
            **kwargs: 其他参数
            
        Returns:
            LLMProvider: 提供商实例
        """
        config = None
        
        # 优先检查自定义提供商
        if provider_id in cls._custom_providers:
            config = cls._custom_providers[provider_id]
        else:
            # 检查预定义提供商
            try:
                provider_type = ProviderType(provider_id)
                if provider_type in cls._provider_configs:
                    config = cls._provider_configs[provider_type]
            except ValueError:
                pass
        
        if not config:
            raise ValueError(f"不支持的提供商ID: {provider_id}")
        
        provider_class = config["class"]
        
        # 设置默认 baseUrl
        if "base_url" not in kwargs or not kwargs["base_url"]:
            kwargs["base_url"] = config["default_base_url"]
        
        # 设置默认模型名
        if not model_name:
            model_name = config["default_model"]
        
        # 设置默认 API 格式（转换为枚举值）
        if "api_format" not in kwargs:
            api_format_str = config.get("api_format", "openai")
            if isinstance(api_format_str, str):
                kwargs["api_format"] = APIFormat(api_format_str)
            else:
                kwargs["api_format"] = api_format_str
        
        return provider_class(api_key, model_name, **kwargs)
    
    @staticmethod
    async def get_all_available_models(api_keys: Dict[ProviderType, str],
                                    provider_configs: Optional[Dict[ProviderType, Dict]] = None,
                                    embed_only: bool = False) -> Dict[ProviderType, List[ModelInfo]]:
        """
        获取所有提供商的可用模型（异步）

        Args:
            api_keys: API密钥字典 {ProviderType: "api_key"}
            provider_configs: 提供商配置字典（可选）
            embed_only: 是否只获取嵌入模型
        """
        models = {}
        provider_configs = provider_configs or {}
        
        # 为每个提供商创建任务
        async def fetch_provider_models(provider_type: ProviderType):
            try:
                api_key = api_keys.get(provider_type, "")
                if not api_key or api_key.strip() == "" or api_key == "dummy_key":
                    return provider_type, []
                
                config = LLMProviderFactory._provider_configs.get(provider_type)
                if not config:
                    return provider_type, []

                # 获取提供商配置
                kwargs = provider_configs.get(provider_type, {})

                # 创建提供商实例
                provider = LLMProviderFactory.create_provider(provider_type, api_key, "", **kwargs)
                
                # 获取模型列表
                models_list = await provider.get_available_models(embed_only=embed_only)
                logger.info(f"成功获取 {provider_type.value} 的模型列表，共 {len(models_list)} 个模型")
                
                return provider_type, models_list
            except Exception as e:
                logger.warning(f"获取 {provider_type.value} 模型列表失败: {str(e)}")
                return provider_type, []
        
        # 并发获取所有提供商的模型
        tasks = [fetch_provider_models(pt) for pt in ProviderType]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"获取模型列表时发生异常: {result}")
                continue
            
            provider_type, models_list = result
            models[provider_type] = models_list
        
        # 确保所有提供商都在结果中
        for provider_type in ProviderType:
            if provider_type not in models:
                models[provider_type] = []
        
        return models
