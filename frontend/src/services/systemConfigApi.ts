/**
 * 系统配置 API 服务
 */
import api from './api'

export interface ProcessingConfig {
  chunk_size: number
  min_score_threshold: number
  max_clips_per_collection: number
  max_retries: number
  api_timeout: number
}

export interface VideoConfig {
  use_stream_copy: boolean
  use_hardware_accel: boolean
  encoder_preset: string
  crf: number
}

export interface TopicConfig {
  min_topic_duration_minutes: number
  max_topic_duration_minutes: number
  target_topic_duration_minutes: number
  min_topics_per_chunk: number
  max_topics_per_chunk: number
}

export interface LoggingConfig {
  log_level: string
  log_format: string
}

export interface AdvancedConfig {
  proxy_url: string
  encryption_key: string
  bilibili_cookie: string
}

export interface AllSystemConfig {
  processing: ProcessingConfig
  video: VideoConfig
  topic: TopicConfig
  logging: LoggingConfig
  advanced: AdvancedConfig
}

export interface ConfigUpdateRequest {
  [key: string]: unknown
}

export type ConfigCategory = 'processing' | 'video' | 'topic' | 'logging' | 'advanced'

class SystemConfigApi {
  private baseUrl = '/system-config'

  async getAllConfigs(): Promise<AllSystemConfig> {
    const response = await api.get(`${this.baseUrl}/`)
    return response
  }

  async getProcessingConfig(): Promise<ProcessingConfig> {
    const response = await api.get(`${this.baseUrl}/processing`)
    return response
  }

  async updateProcessingConfig(config: Partial<ProcessingConfig>): Promise<{
    message: string
    config: ProcessingConfig
  }> {
    const response = await api.put(`${this.baseUrl}/processing`, config)
    return response
  }

  async getVideoConfig(): Promise<VideoConfig> {
    const response = await api.get(`${this.baseUrl}/video`)
    return response
  }

  async updateVideoConfig(config: Partial<VideoConfig>): Promise<{
    message: string
    config: VideoConfig
  }> {
    const response = await api.put(`${this.baseUrl}/video`, config)
    return response
  }

  async getTopicConfig(): Promise<TopicConfig> {
    const response = await api.get(`${this.baseUrl}/topic`)
    return response
  }

  async updateTopicConfig(config: Partial<TopicConfig>): Promise<{
    message: string
    config: TopicConfig
  }> {
    const response = await api.put(`${this.baseUrl}/topic`, config)
    return response
  }

  async getLoggingConfig(): Promise<LoggingConfig> {
    const response = await api.get(`${this.baseUrl}/logging`)
    return response
  }

  async updateLoggingConfig(config: Partial<LoggingConfig>): Promise<{
    message: string
    config: LoggingConfig
  }> {
    const response = await api.put(`${this.baseUrl}/logging`, config)
    return response
  }

  async getAdvancedConfig(): Promise<AdvancedConfig> {
    const response = await api.get(`${this.baseUrl}/advanced`)
    return response
  }

  async updateAdvancedConfig(config: Partial<AdvancedConfig>): Promise<{
    message: string
    config: AdvancedConfig
  }> {
    const response = await api.put(`${this.baseUrl}/advanced`, config)
    return response
  }

  async resetAllConfigs(): Promise<{
    message: string
    config: AllSystemConfig
  }> {
    const response = await api.post(`${this.baseUrl}/reset-all`)
    return response
  }

  async resetCategoryConfig(category: string): Promise<{
    message: string
    config: Record<string, unknown>
  }> {
    const response = await api.post(`${this.baseUrl}/reset/${category}`)
    return response
  }

  async getConfigInfo(): Promise<{
    categories: Record<string, {
      name: string
      description: string
      fields: Record<string, string>
    }>
  }> {
    const response = await api.get(`${this.baseUrl}/config-info`)
    return response
  }
}

export const systemConfigApi = new SystemConfigApi()
