"""
设置 API 路由 - 重构版
支持多提供商、流式响应、模型拉取等功能
"""
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import os
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent.parent.parent / ".env"
load_dotenv(env_path)

from core.llm_manager import get_llm_manager, ProviderType

router = APIRouter()
logger = logging.getLogger(__name__)

class SettingsRequest(BaseModel):
    """设置请求模型"""
    llm_provider: Optional[str] = None
    model_name: Optional[str] = None
    provider_configs: Optional[Dict[str, Any]] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None
    api_timeout: Optional[int] = None
    proxy_url: Optional[str] = None

class ProviderConfigRequest(BaseModel):
    """提供商配置请求"""
    provider: str
    api_key: str
    model: str
    base_url: Optional[str] = ""
    api_format: Optional[str] = "openai"

class ApiKeyTestRequest(BaseModel):
    """API密钥测试请求"""
    provider: str
    api_key: str
    model_name: str
    base_url: Optional[str] = ""
    api_format: Optional[str] = "openai"

class FetchModelsRequest(BaseModel):
    """拉取模型列表请求"""
    provider: str
    embed_only: Optional[bool] = False

class RegisterCustomProviderRequest(BaseModel):
    """注册自定义提供商请求"""
    provider_id: str  # 例如: "custom-my-provider"
    api_key: str
    base_url: str
    api_format: Optional[str] = "openai"
    default_model: Optional[str] = "custom-model"



def get_settings_file_path() -> Path:
    """获取设置文件路径"""
    try:
        from ...core.path_utils import get_settings_file_path as get_settings_path
        return get_settings_path()
    except ImportError:
        # 回退到手动构造路径
        from pathlib import Path
        current_file = Path(__file__)
        project_root = current_file.parent.parent.parent.parent
        return project_root / "data" / "settings.json"

def load_settings() -> Dict[str, Any]:
    """加载设置"""
    try:
        from ...core.llm_manager import get_llm_manager

        # 使用全局管理器实例
        llm_manager = get_llm_manager()
        return llm_manager.settings
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"导入 LLM 管理器失败: {e}")

def save_settings(settings: Dict[str, Any]):
    """保存设置"""
    settings_file = get_settings_file_path()
    settings_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(settings_file, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存设置失败: {e}")

@router.get("/")
async def get_settings():
    """获取系统设置"""
    try:
        llm_manager = get_llm_manager()
        settings = llm_manager.settings.copy()

        # 隐藏 API Key（可选）
        # for provider in settings.get("provider_configs", {}).values():
        #     if "api_key" in provider and provider["api_key"]:
        #         provider["api_key"] = provider["api_key"][:8] + "..."

        return settings
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"加载设置失败: {e}")

@router.post("/")
async def update_settings(request: SettingsRequest):
    """更新系统设置"""
    try:
        llm_manager = get_llm_manager()
        settings = llm_manager.settings
        
        # 更新基础设置
        if request.llm_provider is not None:
            settings["llm_provider"] = request.llm_provider
        
        if request.model_name is not None:
            settings["model_name"] = request.model_name
            # 同步更新提供商配置中的模型名称
            current_provider = settings.get("llm_provider", "dashscope")
            if "provider_configs" not in settings:
                settings["provider_configs"] = {}
            if current_provider not in settings["provider_configs"]:
                settings["provider_configs"][current_provider] = {}
            settings["provider_configs"][current_provider]["model"] = request.model_name
        
        if request.temperature is not None:
            settings["temperature"] = request.temperature
        
        if request.top_p is not None:
            settings["top_p"] = request.top_p
        
        if request.max_tokens is not None:
            settings["max_tokens"] = request.max_tokens
        
        if request.api_timeout is not None:
            settings["api_timeout"] = request.api_timeout
        
        if request.proxy_url is not None:
            settings["proxy_url"] = request.proxy_url

        # 更新提供商配置
        if request.provider_configs is not None:
            if "provider_configs" not in settings:
                settings["provider_configs"] = {}
            settings["provider_configs"].update(request.provider_configs)
            
            # 如果更新了当前提供商的模型，同步更新 model_name
            current_provider = settings.get("llm_provider", "dashscope")
            if current_provider in request.provider_configs and "model" in request.provider_configs[current_provider]:
                settings["model_name"] = request.provider_configs[current_provider]["model"]
        
        # 保存设置并初始化提供商
        save_settings(settings)
        llm_manager.update_settings(settings)
        
        return {"message": "设置更新成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新设置失败: {e}")

@router.post("/configure-provider/")
async def configure_provider(request: ProviderConfigRequest):
    """配置提供商"""
    try:
        # 验证提供商类型
        try:
            provider_type = ProviderType(request.provider)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的提供商类型: {request.provider}"
            )

        llm_manager = get_llm_manager()

        # 设置提供商
        llm_manager.set_provider(
            provider_type=provider_type,
            api_key=request.api_key,
            model_name=request.model,
            base_url=request.base_url,
            api_format=request.api_format
        )

        return {
            "message": "提供商配置成功",
            "provider": request.provider,
            "model": request.model
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"配置提供商失败: {e}")

@router.post("/test-api-key/")
async def test_api_key(request: ApiKeyTestRequest):
    """测试 API 密钥"""
    try:
        # 验证提供商类型
        try:
            provider_type = ProviderType(request.provider)
        except ValueError:
            return {
                "success": False,
                "error": f"不支持的提供商类型: {request.provider}"
            }

        # 测试连接
        llm_manager = get_llm_manager()
        result = await llm_manager.test_provider_connection(
            provider_type=provider_type,
            api_key=request.api_key,
            model_name=request.model_name,
            base_url=request.base_url
        )

        return result
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/available-models/")
async def get_available_models(provider: Optional[str] = None, embed_only: bool = False):
    """获取所有可用模型"""
    try:
        llm_manager = get_llm_manager()

        # 如果指定了提供商
        if provider:
            try:
                provider_type = ProviderType(provider)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"不支持的提供商类型: {provider}"
                )

            # 拉取指定提供商的模型
            models = await llm_manager.fetch_provider_models(
                provider_type=provider_type,
                embed_only=embed_only
            )

            return {"models": models, "provider": provider}
        else:
            # 获取所有提供商的模型
            all_models = await llm_manager.get_all_available_models(embed_only=embed_only)
            return all_models
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取可用模型失败: {e}")

@router.post("/fetch-models/")
async def fetch_models(request: FetchModelsRequest):
    """拉取指定提供商的模型列表"""
    try:
        # 验证提供商类型
        try:
            provider_type = ProviderType(request.provider)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的提供商类型: {request.provider}"
            )

        llm_manager = get_llm_manager()
        models = await llm_manager.fetch_provider_models(
            provider_type=provider_type,
            embed_only=request.embed_only or False
        )

        return {
            "models": models,
            "provider": request.provider,
            "count": len(models)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"拉取模型列表失败: {e}")

@router.get("/current-provider/")
async def get_current_provider():
    """获取当前提供商信息"""
    try:
        llm_manager = get_llm_manager()
        return llm_manager.get_current_provider_info()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取当前提供商信息失败: {e}")

@router.get("/providers/")
async def get_providers():
    """获取所有支持的提供商列表"""
    try:
        providers = []
        for provider_type in ProviderType:
            providers.append({
                "value": provider_type.value,
                "display_name": _get_provider_display_name(provider_type),
                "default_base_url": _get_provider_default_base_url(provider_type),
                "default_model": _get_provider_default_model(provider_type),
                "api_format": _get_provider_api_format(provider_type)
            })

        return {"providers": providers}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取提供商列表失败: {e}")

@router.post("/register-custom-provider/")
async def register_custom_provider(request: RegisterCustomProviderRequest):
    """注册自定义提供商"""
    try:
        from core.llm_providers import LLMProviderFactory

        # 注册自定义提供商
        LLMProviderFactory.add_custom_provider_config(
            provider_id=request.provider_id,
            api_format=request.api_format,
            base_url=request.base_url,
            default_model=request.default_model
        )

        # 保存到设置文件
        llm_manager = get_llm_manager()
        if "provider_configs" not in llm_manager.settings:
            llm_manager.settings["provider_configs"] = {}

        llm_manager.settings["provider_configs"][request.provider_id] = {
            "api_key": request.api_key,
            "base_url": request.base_url,
            "model": request.default_model,
            "api_format": request.api_format,
            "models": []
        }

        # 保存设置
        save_settings(llm_manager.settings)

        # 尝试获取模型列表
        try:
            from core.llm_providers import ProviderType
            
            # 创建临时提供商实例来获取模型列表
            provider = LLMProviderFactory.create_provider_from_id(
                provider_id=request.provider_id,
                api_key=request.api_key,
                model_name=request.default_model,
                base_url=request.base_url
            )
            
            models = await provider.get_available_models()
            
            # 更新模型列表到设置
            llm_manager.settings["provider_configs"][request.provider_id]["models"] = [
                model.id for model in models
            ]
            save_settings(llm_manager.settings)
            
            return {
                "success": True,
                "message": "自定义提供商注册成功",
                "provider_id": request.provider_id,
                "models": [
                    {
                        "id": model.id,
                        "display_name": model.display_name,
                        "description": model.description
                    }
                    for model in models
                ]
            }
        except Exception as e:
            # 即使获取模型列表失败,提供商也已注册成功
            logger.warning(f"获取模型列表失败: {e}")
            return {
                "success": True,
                "message": "自定义提供商注册成功,但获取模型列表失败",
                "provider_id": request.provider_id,
                "error": str(e),
                "models": []
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"注册自定义提供商失败: {e}")

def _get_provider_display_name(provider_type) -> str:
    """获取提供商显示名称"""
    display_names = {
        "dashscope": "阿里通义千问",
        "openai": "OpenAI",
        "gemini": "Google Gemini",
        "siliconflow": "硅基流动",
        "claude": "Anthropic Claude",
        "custom": "自定义提供商"
    }
    return display_names.get(provider_type.value, provider_type.value)

def _get_provider_default_base_url(provider_type) -> str:
    """获取提供商默认 Base URL"""
    urls = {
        "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "openai": "https://api.openai.com/v1",
        "gemini": "https://generativelanguage.googleapis.com/v1beta",
        "siliconflow": "https://api.siliconflow.cn/v1",
        "claude": "https://api.anthropic.com/v1",
        "custom": ""
    }
    return urls.get(provider_type.value, "")

def _get_provider_default_model(provider_type) -> str:
    """获取提供商默认模型"""
    models = {
        "dashscope": "qwen-plus",
        "openai": "gpt-4",
        "gemini": "gemini-pro",
        "siliconflow": "Qwen/Qwen2.5-7B-Instruct",
        "claude": "claude-3-opus-20240229",
        "custom": ""
    }
    return models.get(provider_type.value, "")

def _get_provider_api_format(provider_type) -> str:
    """获取提供商 API 格式"""
    formats = {
        "dashscope": "openai",
        "openai": "openai",
        "gemini": "gemini",
        "siliconflow": "openai",
        "claude": "anthropic",
        "custom": "openai"
    }
    return formats.get(provider_type.value, "openai")








