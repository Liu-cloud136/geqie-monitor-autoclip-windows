"""
步骤配置 API 路由
支持每个步骤独立配置模型和参数
"""
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import json
from pathlib import Path

from core.step_config import StepConfigManager, StepType, get_step_config_manager

router = APIRouter()

class StepConfigRequest(BaseModel):
    """步骤配置请求模型"""
    enabled: Optional[bool] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None
    timeout: Optional[int] = None
    custom_prompt: Optional[str] = None
    custom_params: Optional[Dict[str, Any]] = None

class StepConfigResponse(BaseModel):
    """步骤配置响应模型"""
    step_type: str
    enabled: bool
    provider: str
    model: str
    temperature: float
    top_p: float
    max_tokens: int
    timeout: int
    custom_prompt: Optional[str] = None
    custom_params: Dict[str, Any]

class StepConfigUpdateRequest(BaseModel):
    """步骤配置更新请求"""
    step_type: str
    config: StepConfigRequest

class StepConfigBatchUpdateRequest(BaseModel):
    """批量更新步骤配置请求"""
    configs: Dict[str, StepConfigRequest]

# 具体路由必须在参数路由之前定义！

@router.get("/")
async def get_all_step_configs():
    """获取所有步骤配置"""
    try:
        config_manager = get_step_config_manager()
        configs = config_manager.get_all_configs()
        
        # 转换为响应格式
        response_configs = {}
        for step_key, config in configs.items():
            response_configs[step_key] = {
                "step_type": config["step_type"],
                "enabled": config["enabled"],
                "provider": config["provider"],
                "model": config["model"],
                "temperature": config["temperature"],
                "top_p": config["top_p"],
                "max_tokens": config["max_tokens"],
                "timeout": config["timeout"],
                "custom_prompt": config["custom_prompt"],
                "custom_params": config["custom_params"]
            }
        
        return {"configs": response_configs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取步骤配置失败: {e}")

@router.get("/step-types")
async def get_step_types():
    """获取所有步骤类型"""
    try:
        step_types = []
        for step_type in StepType:
            # 只有step5_clustering不需要AI配置
            require_ai_config = step_type.value != "step5_clustering"
            step_types.append({
                "value": step_type.value,
                "display_name": _get_step_display_name(step_type.value),
                "description": _get_step_description(step_type.value),
                "require_ai_config": require_ai_config
            })
        
        return {"step_types": step_types}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取步骤类型失败: {e}")

@router.get("/available-providers")
async def get_available_providers():
    """获取可用提供商列表"""
    try:
        from core.llm_providers import ProviderType, LLMProviderFactory
        from core.llm_manager import get_llm_manager
        
        providers = []
        
        # 添加预定义提供商
        for provider_type in ProviderType:
            provider_value = provider_type.value
            providers.append({
                "value": provider_value,
                "display_name": _get_provider_display_name(provider_value),
                "default_base_url": _get_provider_default_base_url(provider_value),
                "default_model": _get_provider_default_model(provider_value),
                "api_format": _get_provider_api_format(provider_value)
            })
        
        # 添加已注册的自定义提供商
        llm_manager = get_llm_manager()
        provider_configs = llm_manager.settings.get("provider_configs", {})
        
        for provider_id, config in provider_configs.items():
            if provider_id.startswith("custom-"):
                # 确保自定义提供商已在 LLMProviderFactory 中注册
                base_url = config.get("base_url", "")
                if base_url:  # 只注册有 base_url 的提供商
                    LLMProviderFactory.add_custom_provider_config(
                        provider_id=provider_id,
                        api_format=config.get("api_format", "openai"),
                        base_url=base_url,
                        default_model=config.get("model", "custom-model")
                    )
                
                providers.append({
                    "value": provider_id,
                    "display_name": f"自定义: {provider_id}",
                    "default_base_url": base_url,
                    "default_model": config.get("model", "custom-model"),
                    "api_format": config.get("api_format", "openai")
                })
        
        return {"providers": providers}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取提供商列表失败: {e}")

@router.get("/available-models/{provider}")
async def get_available_models_for_provider(provider: str):
    """获取指定提供商的可用模型列表"""
    try:
        from core.llm_providers import ProviderType, LLMProviderFactory
        from core.llm_manager import get_llm_manager
        import json
        
        llm_manager = get_llm_manager()
        
        # 检查是否是自定义提供商（以 "custom-" 开头）
        if provider.startswith("custom-"):
            # 自定义提供商
            provider_configs = llm_manager.settings.get("provider_configs", {})
            if provider not in provider_configs:
                raise HTTPException(
                    status_code=404,
                    detail=f"未找到自定义提供商配置: {provider}"
                )
            
            config = provider_configs[provider]
            api_key = config.get("api_key", "")
            base_url = config.get("base_url", "")
            
            if not api_key or not base_url:
                raise HTTPException(
                    status_code=400,
                    detail=f"自定义提供商配置不完整: {provider}"
                )
            
            # 先注册自定义提供商到 LLMProviderFactory
            LLMProviderFactory.add_custom_provider_config(
                provider_id=provider,
                api_format=config.get("api_format", "openai"),
                base_url=base_url,
                default_model=config.get("model", "custom-model")
            )
            
            # 使用 create_provider_from_id 创建提供商实例
            provider_instance = LLMProviderFactory.create_provider_from_id(
                provider_id=provider,
                api_key=api_key,
                model_name=config.get("model", "custom-model"),
                base_url=base_url
            )
            
            # 获取模型列表
            models_list = await provider_instance.get_available_models()
            
            # 更新配置中的模型列表
            config["models"] = [model.id for model in models_list]
            llm_manager.settings["provider_configs"][provider].update(config)
            
            # 保存设置
            settings_file = llm_manager.settings_file
            settings_file.parent.mkdir(parents=True, exist_ok=True)
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(llm_manager.settings, f, ensure_ascii=False, indent=2)
            
            models = [
                {
                    "id": model.id,
                    "display_name": model.display_name,
                    "max_tokens": model.max_tokens,
                    "description": model.description
                }
                for model in models_list
            ]
            
            return {"models": models, "provider": provider}
        else:
            # 预定义提供商
            try:
                provider_type = ProviderType(provider)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"不支持的提供商类型: {provider}"
                )
            
            models = await llm_manager.fetch_provider_models(provider_type=provider_type)
            
            return {"models": models, "provider": provider}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"获取模型列表失败: {str(e)}")

@router.post("/batch-update")
async def batch_update_step_configs(request: StepConfigBatchUpdateRequest):
    """批量更新步骤配置"""
    try:
        config_manager = get_step_config_manager()
        
        for step_type_str, config_request in request.configs.items():
            # 验证步骤类型
            try:
                step_type_enum = StepType(step_type_str)
            except ValueError:
                continue  # 跳过不支持的步骤类型
            
            # 构建更新数据
            config_data = {}
            if config_request.enabled is not None:
                config_data["enabled"] = config_request.enabled
            if config_request.provider is not None:
                config_data["provider"] = config_request.provider
            if config_request.model is not None:
                config_data["model"] = config_request.model
            if config_request.temperature is not None:
                config_data["temperature"] = config_request.temperature
            if config_request.top_p is not None:
                config_data["top_p"] = config_request.top_p
            if config_request.max_tokens is not None:
                config_data["max_tokens"] = config_request.max_tokens
            if config_request.timeout is not None:
                config_data["timeout"] = config_request.timeout
            if config_request.custom_prompt is not None:
                config_data["custom_prompt"] = config_request.custom_prompt
            if config_request.custom_params is not None:
                config_data["custom_params"] = config_request.custom_params
            
            config_manager.update_step_config(step_type_enum, config_data)
        
        return {"message": "批量更新步骤配置成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量更新步骤配置失败: {e}")

@router.post("/reset-all")
async def reset_all_step_configs():
    """重置所有步骤配置为默认值"""
    try:
        config_manager = get_step_config_manager()
        config_manager.reset_all_configs()
        
        return {"message": "所有步骤配置重置成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重置所有步骤配置失败: {e}")

@router.post("/test-response-time/{step_type}")
async def test_step_response_time(step_type: str):
    """测试指定步骤配置的模型响应时间"""
    import time
    import asyncio
    
    try:
        try:
            step_type_enum = StepType(step_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的步骤类型: {step_type}"
            )
        
        config_manager = get_step_config_manager()
        config = config_manager.get_step_config(step_type_enum)
        
        if not config.enabled:
            return {
                "success": False,
                "error": "该步骤已禁用",
                "response_time": None
            }
        
        from core.llm_providers import ProviderType, LLMProviderFactory
        from core.llm_manager import get_llm_manager
        
        llm_manager = get_llm_manager()
        provider_configs = llm_manager.settings.get("provider_configs", {})
        
        provider_key = config.provider
        
        if provider_key not in provider_configs:
            return {
                "success": False,
                "error": f"未找到提供商配置: {provider_key}",
                "response_time": None
            }
        
        provider_config = provider_configs[provider_key]
        api_key = provider_config.get("api_key", "")
        base_url = provider_config.get("base_url", "")
        api_format = provider_config.get("api_format", "openai")
        
        if not api_key:
            return {
                "success": False,
                "error": "未配置 API 密钥",
                "response_time": None
            }
        
        test_prompt = "请回复'测试成功'三个字，不要回复其他内容。"
        
        start_time = time.time()
        
        try:
            if provider_key.startswith("custom-"):
                if provider_key not in LLMProviderFactory._custom_providers:
                    LLMProviderFactory.add_custom_provider_config(
                        provider_id=provider_key,
                        api_format=api_format,
                        base_url=base_url,
                        default_model=config.model
                    )
                
                provider_instance = LLMProviderFactory.create_provider_from_id(
                    provider_id=provider_key,
                    api_key=api_key,
                    model_name=config.model,
                    base_url=base_url,
                    proxy_url=llm_manager.settings.get("proxy_url", ""),
                    timeout=30
                )
            else:
                try:
                    provider_type = ProviderType(provider_key)
                except ValueError:
                    return {
                        "success": False,
                        "error": f"不支持的提供商类型: {provider_key}",
                        "response_time": None
                    }
                
                provider_instance = LLMProviderFactory.create_provider(
                    provider_type, api_key, config.model,
                    base_url=base_url,
                    proxy_url=llm_manager.settings.get("proxy_url", ""),
                    timeout=30
                )
            
            messages = [{"role": "user", "content": test_prompt}]
            
            response = await asyncio.wait_for(
                provider_instance.call(
                    messages,
                    temperature=0.1,
                    max_tokens=50
                ),
                timeout=30
            )
            
            end_time = time.time()
            response_time = round((end_time - start_time) * 1000, 2)
            
            return {
                "success": True,
                "response_time": response_time,
                "model": config.model,
                "provider": config.provider,
                "reply": response.content[:100] if response.content else ""
            }
            
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "请求超时（30秒）",
                "response_time": None
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "response_time": None
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"测试响应时间失败: {e}")

# 参数化路由必须放在具体路由之后！

@router.get("/{step_type}")
async def get_step_config(step_type: str):
    """获取指定步骤配置"""
    try:
        # 验证步骤类型
        try:
            step_type_enum = StepType(step_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的步骤类型: {step_type}"
            )
        
        config_manager = get_step_config_manager()
        config = config_manager.get_step_config(step_type_enum)
        
        return {
            "step_type": config.step_type.value,
            "enabled": config.enabled,
            "provider": config.provider,
            "model": config.model,
            "temperature": config.temperature,
            "top_p": config.top_p,
            "max_tokens": config.max_tokens,
            "timeout": config.timeout,
            "custom_prompt": config.custom_prompt,
            "custom_params": config.custom_params
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取步骤配置失败: {e}")

@router.put("/{step_type}")
async def update_step_config(step_type: str, request: StepConfigRequest):
    """更新指定步骤配置"""
    try:
        # 验证步骤类型
        try:
            step_type_enum = StepType(step_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的步骤类型: {step_type}"
            )
        
        config_manager = get_step_config_manager()
        
        # 构建更新数据
        config_data = {}
        if request.enabled is not None:
            config_data["enabled"] = request.enabled
        if request.provider is not None:
            config_data["provider"] = request.provider
        if request.model is not None:
            config_data["model"] = request.model
        if request.temperature is not None:
            config_data["temperature"] = request.temperature
        if request.top_p is not None:
            config_data["top_p"] = request.top_p
        if request.max_tokens is not None:
            config_data["max_tokens"] = request.max_tokens
        if request.timeout is not None:
            config_data["timeout"] = request.timeout
        if request.custom_prompt is not None:
            config_data["custom_prompt"] = request.custom_prompt
        if request.custom_params is not None:
            config_data["custom_params"] = request.custom_params
        
        config_manager.update_step_config(step_type_enum, config_data)
        
        return {"message": "步骤配置更新成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新步骤配置失败: {e}")

@router.post("/reset/{step_type}")
async def reset_step_config(step_type: str):
    """重置指定步骤配置为默认值"""
    try:
        # 验证步骤类型
        try:
            step_type_enum = StepType(step_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的步骤类型: {step_type}"
            )
        
        config_manager = get_step_config_manager()
        config_manager.reset_step_config(step_type_enum)
        
        return {"message": "步骤配置重置成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重置步骤配置失败: {e}")

# 辅助函数
def _get_provider_display_name(provider_value: str) -> str:
    """获取提供商显示名称"""
    display_names = {
        "dashscope": "阿里通义千问",
        "openai": "OpenAI",
        "gemini": "Google Gemini",
        "siliconflow": "硅基流动",
        "claude": "Anthropic Claude",
        "custom": "自定义提供商"
    }
    return display_names.get(provider_value, provider_value)

def _get_provider_default_base_url(provider_value: str) -> str:
    """获取提供商默认 Base URL"""
    urls = {
        "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "openai": "https://api.openai.com/v1",
        "gemini": "https://generativelanguage.googleapis.com/v1beta",
        "siliconflow": "https://api.siliconflow.cn/v1",
        "claude": "https://api.anthropic.com/v1",
        "custom": ""
    }
    return urls.get(provider_value, "")

def _get_provider_default_model(provider_value: str) -> str:
    """获取提供商默认模型"""
    models = {
        "dashscope": "qwen-plus",
        "openai": "gpt-4",
        "gemini": "gemini-pro",
        "siliconflow": "Qwen/Qwen2.5-7B-Instruct",
        "claude": "claude-3-opus-20240229",
        "custom": ""
    }
    return models.get(provider_value, "")

def _get_provider_api_format(provider_value: str) -> str:
    """获取提供商 API 格式"""
    formats = {
        "dashscope": "openai",
        "openai": "openai",
        "gemini": "gemini",
        "siliconflow": "openai",
        "claude": "anthropic",
        "custom": "openai"
    }
    return formats.get(provider_value, "openai")

def _get_step_display_name(step_value: str) -> str:
    """获取步骤显示名称"""
    display_names = {
        "step1_outline": "大纲提取",
        "step2_timeline": "时间线提取",
        "step3_scoring": "内容评分",
        "step4_recommendation": "视频简介生成",
        "step5_title": "标题生成",
        "step6_clustering": "切片生成"
    }
    return display_names.get(step_value, step_value)

def _get_step_description(step_value: str) -> str:
    """获取步骤描述"""
    descriptions = {
        "step1_outline": "从视频字幕中提取主要话题和结构",
        "step2_timeline": "为每个话题定位具体的时间区间",
        "step3_scoring": "评估每个话题的质量和推荐度",
        "step4_recommendation": "为每个话题生成视频简介",
        "step5_title": "为高质量内容生成吸引人的标题",
        "step6_clustering": "生成最终的视频切片（无需AI配置）"
    }
    return descriptions.get(step_value, "")
