/**
 * 步骤配置 API 服务
 */
import api from './api'

// 步骤配置接口
export interface StepConfig {
  step_type: string
  enabled: boolean
  provider: string
  model: string
  temperature: number
  top_p: number
  max_tokens: number
  timeout: number
  custom_prompt?: string
  custom_params: Record<string, unknown>
}

export interface StepConfigUpdateRequest {
  enabled?: boolean
  provider?: string
  model?: string
  temperature?: number
  top_p?: number
  max_tokens?: number
  timeout?: number
  custom_prompt?: string
  custom_params?: Record<string, unknown>
}

export interface StepConfigBatchUpdateRequest {
  [stepType: string]: StepConfigUpdateRequest
}

export interface StepTypeInfo {
  value: string
  display_name: string
  description: string
  require_ai_config?: boolean
}

export interface ProviderInfo {
  value: string
  display_name: string
  default_base_url?: string
  default_model?: string
  api_format?: string
}

export interface ModelInfo {
  id: string
  display_name: string
  max_tokens: number
  description?: string
}

class StepConfigApi {
  private baseUrl = '/step-config'

  /**
   * 获取所有步骤配置
   */
  async getAllStepConfigs(): Promise<Record<string, StepConfig>> {
    const response = await api.get(`${this.baseUrl}/`)
    console.log('getAllStepConfigs 原始响应:', response)
    return response.configs || {}
  }

  /**
   * 获取指定步骤配置
   */
  async getStepConfig(stepType: string): Promise<StepConfig> {
    const response = await api.get(`${this.baseUrl}/${stepType}`)
    console.log('getStepConfig 原始响应:', response)
    return response
  }

  /**
   * 更新指定步骤配置
   */
  async updateStepConfig(stepType: string, config: StepConfigUpdateRequest): Promise<void> {
    await api.put(`${this.baseUrl}/${stepType}`, config)
  }

  /**
   * 批量更新步骤配置
   */
  async batchUpdateStepConfigs(configs: StepConfigBatchUpdateRequest): Promise<void> {
    await api.post(`${this.baseUrl}/batch-update`, { configs })
  }

  /**
   * 重置指定步骤配置
   */
  async resetStepConfig(stepType: string): Promise<void> {
    await api.post(`${this.baseUrl}/reset/${stepType}`)
  }

  /**
   * 重置所有步骤配置
   */
  async resetAllStepConfigs(): Promise<void> {
    await api.post(`${this.baseUrl}/reset-all`)
  }

  /**
   * 获取所有步骤类型
   */
  async getStepTypes(): Promise<StepTypeInfo[]> {
    const response = await api.get(`${this.baseUrl}/step-types`)
    console.log('getStepTypes 原始响应:', response)
    return response.step_types || []
  }

  /**
   * 获取可用提供商列表
   */
  async getAvailableProviders(): Promise<ProviderInfo[]> {
    const response = await api.get(`${this.baseUrl}/available-providers`)
    console.log('getAvailableProviders 原始响应:', response)
    return response.providers || []
  }

  /**
   * 获取指定提供商的可用模型
   */
  async getAvailableModels(provider: string): Promise<ModelInfo[]> {
    const response = await api.get(`${this.baseUrl}/available-models/${provider}`)
    console.log('getAvailableModels 原始响应:', response)
    return response.models || []
  }

  /**
   * 获取指定步骤的提示词内容
   */
  async getStepPrompt(stepType: string): Promise<string | null> {
    const response = await api.get(`/prompt/${stepType}`)
    return response.prompt || null
  }

  /**
   * 测试步骤配置的模型响应时间
   */
  async testResponseTime(stepType: string): Promise<{
    success: boolean
    response_time: number | null
    model?: string
    provider?: string
    reply?: string
    error?: string
  }> {
    const response = await api.post(`${this.baseUrl}/test-response-time/${stepType}`)
    return response
  }
}

export const stepConfigApi = new StepConfigApi()