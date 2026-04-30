"""
步骤配置管理器 - 支持每个步骤独立配置模型和参数
"""
import json
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, field
from pydantic import BaseModel, validator

logger = logging.getLogger(__name__)

class StepType(Enum):
    """步骤类型枚举"""
    STEP1_OUTLINE = "step1_outline"      # 大纲提取
    STEP2_TIMELINE = "step2_timeline"    # 时间线提取
    STEP3_SCORING = "step3_scoring"      # 内容评分
    STEP4_RECOMMENDATION = "step4_recommendation"  # 推荐理由生成
    STEP5_TITLE = "step5_title"          # 标题生成
    STEP6_CLUSTERING = "step6_clustering"  # 切片生成

@dataclass
class StepConfig:
    """步骤配置"""
    step_type: StepType
    enabled: bool = True                  # 是否启用该步骤
    provider: str = "dashscope"          # LLM提供商
    model: str = ""                      # 模型名称
    temperature: float = 1.0             # 温度参数
    top_p: float = 0.95                  # top_p参数
    max_tokens: int = 4096                # 最大token数
    timeout: int = 600                   # 超时时间（秒）
    custom_prompt: Optional[str] = None  # 自定义提示词（可选）
    custom_params: Dict[str, Any] = field(default_factory=dict)  # 自定义参数

class StepConfigManager:
    """步骤配置管理器"""
    
    def __init__(self, config_file: Optional[Path] = None):
        self.config_file = config_file or self._get_default_config_file()
        self.configs: Dict[str, StepConfig] = {}
        self._load_configs()
    
    def _get_default_config_file(self) -> Path:
        """获取默认配置文件路径"""
        current_file = Path(__file__)
        project_root = current_file.parent.parent.parent  # backend/core -> backend -> project_root
        return project_root / "data" / "step_configs.json"
    
    def _load_configs(self):
        """加载配置"""
        default_configs = {
            StepType.STEP1_OUTLINE.value: StepConfig(
                step_type=StepType.STEP1_OUTLINE,
                provider="dashscope",
                model="qwen-plus",
                temperature=1.0,
                top_p=0.95,
                max_tokens=4096,
                timeout=600
            ),
            StepType.STEP2_TIMELINE.value: StepConfig(
                step_type=StepType.STEP2_TIMELINE,
                provider="dashscope",
                model="qwen-plus",
                temperature=1.0,
                top_p=0.95,
                max_tokens=4096,
                timeout=600
            ),
            StepType.STEP3_SCORING.value: StepConfig(
                step_type=StepType.STEP3_SCORING,
                provider="dashscope",
                model="qwen-plus",
                temperature=1.0,
                top_p=0.95,
                max_tokens=4096,
                timeout=600
            ),
            StepType.STEP4_RECOMMENDATION.value: StepConfig(
                step_type=StepType.STEP4_RECOMMENDATION,
                provider="dashscope",
                model="qwen-plus",
                temperature=1.0,
                top_p=0.95,
                max_tokens=4096,
                timeout=600
            ),
            StepType.STEP5_TITLE.value: StepConfig(
                step_type=StepType.STEP5_TITLE,
                provider="dashscope",
                model="qwen-plus",
                temperature=1.0,
                top_p=0.95,
                max_tokens=4096,
                timeout=600
            ),
            StepType.STEP6_CLUSTERING.value: StepConfig(
                step_type=StepType.STEP6_CLUSTERING,
                provider="dashscope",
                model="qwen-plus",
                temperature=1.0,
                top_p=0.95,
                max_tokens=4096,
                timeout=600
            )
        }
        
        # 加载保存的配置
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    saved_configs = json.load(f)
                    
                    # 更新默认配置
                    for step_key, saved_config in saved_configs.items():
                        if step_key in default_configs:
                            default_config = default_configs[step_key]
                            # 更新配置值
                            for key, value in saved_config.items():
                                if hasattr(default_config, key):
                                    setattr(default_config, key, value)
                    
                    self.configs = default_configs
                    print(f"已加载步骤配置文件: {self.config_file}")
            except Exception as e:
                print(f"加载步骤配置失败: {e}")
                self.configs = default_configs
        else:
            self.configs = default_configs
            print(f"使用默认步骤配置，配置文件不存在: {self.config_file}")
    
    def reload_configs(self):
        """重新加载配置"""
        print(f"重新加载步骤配置: {self.config_file}")
        self._load_configs()
    
    def save_configs(self):
        """保存配置"""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
        config_data = {}
        for step_key, config in self.configs.items():
            # 确保我们有一个StepConfig对象
            config_obj = self._ensure_step_config_object(step_key, config)
            
            # 获取步骤类型值
            if isinstance(config_obj.step_type, StepType):
                step_type_value = config_obj.step_type.value
            else:
                step_type_value = str(config_obj.step_type)
            
            config_data[step_key] = {
                "step_type": step_type_value,
                "enabled": config_obj.enabled,
                "provider": config_obj.provider,
                "model": config_obj.model,
                "temperature": config_obj.temperature,
                "top_p": config_obj.top_p,
                "max_tokens": config_obj.max_tokens,
                "timeout": config_obj.timeout,
                "custom_prompt": config_obj.custom_prompt,
                "custom_params": config_obj.custom_params
            }
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存步骤配置失败: {e}")
    
    def get_step_config(self, step_type: StepType) -> StepConfig:
        """获取指定步骤的配置"""
        step_key = step_type.value
        
        # 每次获取配置时都重新加载配置文件，确保使用最新的配置
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    saved_configs = json.load(f)
                    
                    # 更新现有配置
                    for saved_step_key, saved_config in saved_configs.items():
                        if saved_step_key in self.configs:
                            config_obj = self.configs[saved_step_key]
                            # 更新配置值
                            for key, value in saved_config.items():
                                if hasattr(config_obj, key):
                                    setattr(config_obj, key, value)
                        else:
                            # 创建新配置
                            self.configs[saved_step_key] = StepConfig(
                                step_type=saved_step_key,
                                enabled=saved_config.get("enabled", True),
                                provider=saved_config.get("provider", "dashscope"),
                                model=saved_config.get("model", ""),
                                temperature=saved_config.get("temperature", 1.0),
                                top_p=saved_config.get("top_p", 0.95),
                                max_tokens=saved_config.get("max_tokens", 4096),
                                timeout=saved_config.get("timeout", 600),
                                custom_prompt=saved_config.get("custom_prompt"),
                                custom_params=saved_config.get("custom_params", {})
                            )
            except Exception as e:
                logger.warning(f"重新加载配置失败: {e}")
        
        if step_key not in self.configs:
            # 创建默认配置
            self.configs[step_key] = StepConfig(
                step_type=step_type,
                provider="dashscope",
                model="qwen-plus",
                temperature=1.0,
                top_p=0.95,
                max_tokens=4096,
                timeout=600
            )
            self.save_configs()
        
        return self.configs[step_key]
    
    def update_step_config(self, step_type: StepType, config_data: Dict[str, Any]):
        """更新指定步骤的配置"""
        step_key = step_type.value
        config = self.get_step_config(step_type)
        
        # 更新配置值
        for key, value in config_data.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        self.configs[step_key] = config
        self.save_configs()
    
    def get_all_configs(self) -> Dict[str, Dict[str, Any]]:
        """获取所有步骤配置"""
        result = {}
        for step_key, config in self.configs.items():
            # 确保我们有一个StepConfig对象
            config_obj = self._ensure_step_config_object(step_key, config)
            
            # 确保step_type是StepType枚举
            if isinstance(config_obj.step_type, StepType):
                step_type_value = config_obj.step_type.value
            else:
                step_type_value = str(config_obj.step_type)
            
            result[step_key] = {
                "step_type": step_type_value,
                "enabled": config_obj.enabled,
                "provider": config_obj.provider,
                "model": config_obj.model,
                "temperature": config_obj.temperature,
                "top_p": config_obj.top_p,
                "max_tokens": config_obj.max_tokens,
                "timeout": config_obj.timeout,
                "custom_prompt": config_obj.custom_prompt,
                "custom_params": config_obj.custom_params
            }
        return result
    
    def _ensure_step_config_object(self, step_key: str, config: Any) -> StepConfig:
        """确保配置是StepConfig对象"""
        if isinstance(config, StepConfig):
            return config
        
        # 从字典创建StepConfig对象
        config_dict = config if isinstance(config, dict) else {}
        
        # 获取步骤类型
        try:
            step_type = StepType(config_dict.get("step_type", step_key))
        except ValueError:
            # 如果步骤类型无效，使用默认的
            step_type = StepType(step_key) if step_key in [st.value for st in StepType] else StepType.STEP1_OUTLINE
        
        return StepConfig(
            step_type=step_type,
            enabled=config_dict.get("enabled", True),
            provider=config_dict.get("provider", "dashscope"),
            model=config_dict.get("model", ""),
            temperature=config_dict.get("temperature", 1.0),
            top_p=config_dict.get("top_p", 0.95),
            max_tokens=config_dict.get("max_tokens", 4096),
            timeout=config_dict.get("timeout", 600),
            custom_prompt=config_dict.get("custom_prompt"),
            custom_params=config_dict.get("custom_params", {})
        )
    
    def reset_step_config(self, step_type: StepType):
        """重置指定步骤的配置为默认值"""
        step_key = step_type.value
        self.configs[step_key] = StepConfig(
            step_type=step_type,
            provider="dashscope",
            model="qwen-plus",
            temperature=1.0,
            top_p=0.95,
            max_tokens=4096,
            timeout=600
        )
        self.save_configs()
    
    def reset_all_configs(self):
        """重置所有步骤配置为默认值"""
        self.configs = {
            StepType.STEP1_OUTLINE.value: StepConfig(
                step_type=StepType.STEP1_OUTLINE,
                provider="dashscope",
                model="qwen-plus",
                temperature=1.0,
                top_p=0.95,
                max_tokens=4096,
                timeout=600
            ),
            StepType.STEP2_TIMELINE.value: StepConfig(
                step_type=StepType.STEP2_TIMELINE,
                provider="dashscope",
                model="qwen-plus",
                temperature=1.0,
                top_p=0.95,
                max_tokens=4096,
                timeout=600
            ),
            StepType.STEP3_SCORING.value: StepConfig(
                step_type=StepType.STEP3_SCORING,
                provider="dashscope",
                model="qwen-plus",
                temperature=1.0,
                top_p=0.95,
                max_tokens=4096,
                timeout=600
            ),
            StepType.STEP4_RECOMMENDATION.value: StepConfig(
                step_type=StepType.STEP4_RECOMMENDATION,
                provider="dashscope",
                model="qwen-plus",
                temperature=1.0,
                top_p=0.95,
                max_tokens=4096,
                timeout=600
            ),
            StepType.STEP5_TITLE.value: StepConfig(
                step_type=StepType.STEP5_TITLE,
                provider="dashscope",
                model="qwen-plus",
                temperature=1.0,
                top_p=0.95,
                max_tokens=4096,
                timeout=600
            ),
            StepType.STEP6_CLUSTERING.value: StepConfig(
                step_type=StepType.STEP6_CLUSTERING,
                provider="dashscope",
                model="qwen-plus",
                temperature=1.0,
                top_p=0.95,
                max_tokens=4096,
                timeout=600
            )
        }
        self.save_configs()

# 全局步骤配置管理器实例
_step_config_manager: Optional[StepConfigManager] = None

def get_step_config_manager() -> StepConfigManager:
    """获取全局步骤配置管理器实例"""
    global _step_config_manager
    if _step_config_manager is None:
        _step_config_manager = StepConfigManager()
    return _step_config_manager

def reload_step_configs():
    """重新加载步骤配置"""
    global _step_config_manager
    if _step_config_manager is not None:
        _step_config_manager.reload_configs()
        print("步骤配置已重新加载")
    else:
        print("步骤配置管理器未初始化")