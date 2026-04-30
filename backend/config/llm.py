from typing import Optional

from pydantic import BaseModel, Field, field_validator


class LLMConfig(BaseModel):
    """LLM 配置"""
    provider: str = Field(default="dashscope", description="LLM提供商")
    
    # DashScope 配置
    dashscope_api_key: Optional[str] = Field(default="", description="DashScope API密钥")
    dashscope_base_url: str = Field(default="https://dashscope.aliyuncs.com/compatible-mode/v1", description="DashScope API地址")
    
    # OpenAI 配置
    openai_api_key: Optional[str] = Field(default="", description="OpenAI API密钥")
    openai_base_url: str = Field(default="https://api.openai.com/v1", description="OpenAI API地址")
    
    # Gemini 配置
    gemini_api_key: Optional[str] = Field(default="", description="Gemini API密钥")
    
    # SiliconFlow 配置
    siliconflow_api_key: Optional[str] = Field(default="", description="SiliconFlow API密钥")
    siliconflow_base_url: str = Field(default="https://api.siliconflow.cn/v1", description="SiliconFlow API地址")
    
    # 通用配置
    model_name: str = Field(default="qwen-plus", description="模型名称")
    max_tokens: int = Field(default=4096, description="最大token数")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="温度参数")
    top_p: float = Field(default=0.9, ge=0.0, le=1.0, description="top_p参数")
    timeout: int = Field(default=600, ge=1, description="API超时时间（秒）")
    
    # 代理配置
    proxy_url: str = Field(default="", description="代理URL")
    
    @field_validator('max_tokens')
    @classmethod
    def validate_max_tokens(cls, v):
        if v <= 0:
            raise ValueError('max_tokens必须大于0')
        if v > 128000:
            raise ValueError('max_tokens不能超过128000')
        return v
    
    @field_validator('timeout')
    @classmethod
    def validate_timeout(cls, v):
        if v < 30:
            raise ValueError('超时时间不能少于30秒')
        if v > 3600:
            raise ValueError('超时时间不能超过3600秒')
        return v
    
    @field_validator('temperature')
    @classmethod
    def validate_temperature(cls, v):
        if not (0.0 <= v <= 2.0):
            raise ValueError('temperature必须在0.0到2.0之间')
        return v
    
    @field_validator('top_p')
    @classmethod
    def validate_top_p(cls, v):
        if not (0.0 <= v <= 1.0):
            raise ValueError('top_p必须在0.0到1.0之间')
        return v
    
    def get_api_key(self) -> str:
        """获取当前提供商的API密钥"""
        if self.provider == "dashscope":
            return self.dashscope_api_key or ""
        elif self.provider == "openai":
            return self.openai_api_key or ""
        elif self.provider == "gemini":
            return self.gemini_api_key or ""
        elif self.provider == "siliconflow":
            return self.siliconflow_api_key or ""
        return ""
    
    def get_base_url(self) -> str:
        """获取当前提供商的API地址"""
        if self.provider == "dashscope":
            return self.dashscope_base_url
        elif self.provider == "openai":
            return self.openai_base_url
        elif self.provider == "gemini":
            return ""
        elif self.provider == "siliconflow":
            return self.siliconflow_base_url
        return ""
