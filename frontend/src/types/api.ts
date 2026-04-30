/**
 * API 类型定义
 * 提供类型安全的 API 接口定义
 */

// ============ 通用类型 ============

export interface ApiResponse<T> {
  success: boolean
  data: T
  message?: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface ApiError {
  code?: string
  detail?: string
  message?: string
  userMessage?: string
}

// ============ 项目相关类型 ============

export enum ProjectStatus {
  PENDING = 'pending',
  PROCESSING = 'processing',
  COMPLETED = 'completed',
  FAILED = 'failed'
}

export enum ProjectType {
  DEFAULT = 'default',
  KNOWLEDGE = 'knowledge',
  BUSINESS = 'business',
  OPINION = 'opinion',
  EXPERIENCE = 'experience',
  SPEECH = 'speech',
  CONTENT_REVIEW = 'content_review',
  ENTERTAINMENT = 'entertainment'
}

export interface Project {
  id: string | number
  name: string
  description?: string
  status: ProjectStatus
  project_type: ProjectType
  video_path?: string
  subtitle_path?: string
  video_duration?: number
  thumbnail?: string
  processing_config?: Record<string, any>
  project_metadata?: Record<string, any>
  created_at: string
  updated_at: string
  completed_at?: string
  clips?: Clip[]
  tasks?: Task[]
  clips_count?: number
  is_processing?: boolean
  is_completed?: boolean
  has_error?: boolean
}

export interface CreateProjectRequest {
  name: string
  description?: string
  project_type?: ProjectType
}

export interface UploadFilesRequest {
  video_file: File
  project_name: string
}

export interface ProcessingStatus {
  status: 'processing' | 'completed' | 'error'
  current_step: number
  total_steps: number
  step_name: string
  progress: number
  error_message?: string
}

// ============ 切片相关类型 ============

export enum ClipStatus {
  PENDING = 'pending',
  PROCESSING = 'processing',
  COMPLETED = 'completed',
  FAILED = 'failed'
}

export interface Clip {
  id: string | number
  project_id: string | number
  title: string
  description?: string
  status: ClipStatus
  start_time: number | string
  end_time: number | string
  duration: number
  score?: number
  recommendation_reason?: string
  video_path?: string
  thumbnail_path?: string
  processing_step?: number
  tags?: string[]
  clip_metadata?: ClipMetadata
  created_at: string
  updated_at: string
  is_processing?: boolean
  is_completed?: boolean
  has_error?: boolean

  // 扩展字段（来自 clip_metadata）
  final_score?: number
  recommend_reason?: string
  outline?: string
  content?: ContentItem[]
  chunk_index?: number
  generated_title?: string
}

export interface ClipMetadata {
  final_score?: number
  recommend_reason?: string
  outline?: string
  content?: ContentItem[]
  chunk_index?: number
  generated_title?: string
  metadata_file?: string
}

export interface ContentItem {
  time_range: string
  content: string
}

export interface UpdateClipRequest {
  title?: string
  description?: string
  score?: number
  recommendation_reason?: string
  tags?: string[]
  clip_metadata?: Partial<ClipMetadata>
}

// ============ 任务相关类型 ============

export enum TaskStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled'
}

export enum TaskType {
  VIDEO_PROCESSING = 'video_processing',
  AI_ANALYSIS = 'ai_analysis',
  CLIP_GENERATION = 'clip_generation',
  THUMBNAIL_GENERATION = 'thumbnail_generation'
}

export interface Task {
  id: string | number
  project_id: string | number
  task_type: TaskType
  status: TaskStatus
  progress: number
  current_step?: string
  error_message?: string
  started_at?: string
  completed_at?: string
  created_at: string
  updated_at: string
}

export interface TaskProgress {
  task_id: string | number
  status: TaskStatus
  progress: number
  current_step: string
  total_steps?: number
  current_step_number?: number
  message?: string
  error_message?: string
}

// ============ 设置相关类型 ============

export interface Settings {
  api_provider?: string
  api_dashscope_api_key?: string
  api_model_name?: string
  api_max_tokens?: number
  api_timeout?: number
  processing_chunk_size?: number
  processing_min_score_threshold?: number
  processing_max_retries?: number
  log_level?: string
}

export interface ApiKeyTestRequest {
  provider: string
  api_key: string
  model_name: string
}

export interface ApiKeyTestResponse {
  success: boolean
  error?: string
  message?: string
}

export interface AvailableModelsResponse {
  provider: string
  models: Array<{
    name: string
    display_name: string
    description?: string
    max_tokens?: number
  }>
}

export interface ProviderInfo {
  provider: string
  model_name: string
  is_configured: boolean
  capabilities?: string[]
}

// ============ 系统相关类型 ============

export interface SystemStatus {
  current_processing_count: number
  max_concurrent_processing: number
  total_projects: number
  processing_projects: string[]
}

// ============ 日志相关类型 ============

export interface LogEntry {
  timestamp: string
  module: string
  level: string
  message: string
}

export interface LogsResponse {
  logs: LogEntry[]
  total: number
}

// ============ Axios 类型 ============

// ============ 切片编辑相关类型 ============

export enum EditSessionStatus {
  DRAFT = 'draft',
  PROCESSING = 'processing',
  COMPLETED = 'completed',
  FAILED = 'failed'
}

export enum EditSegmentType {
  ORIGINAL = 'original',
  CROPPED = 'cropped'
}

export interface EditSegment {
  id: string
  session_id: string
  original_clip_id: string | null
  original_clip_title: string | null
  original_clip_thumbnail: string | null
  start_time: number
  end_time: number
  original_start_time: number
  original_end_time: number
  duration: number
  segment_order: number
  segment_type: EditSegmentType
  created_at: string
  updated_at: string
  thumbnail_path?: string
}

export interface ClipEditSession {
  id: string
  name: string
  status: EditSessionStatus
  project_id: string
  output_video_path: string | null
  total_duration: number
  created_at: string
  updated_at: string
  segments: EditSegment[]
}

export interface CreateEditSessionRequest {
  name: string
  project_id: string
}

export interface UpdateEditSessionRequest {
  name?: string
}

export interface AddSegmentRequest {
  original_clip_id: string
  start_time?: number
  end_time?: number
  segment_order?: number
}

export interface AddClipsToSessionRequest {
  clip_ids: string[]
}

export interface ReorderSegmentsRequest {
  segment_orders: Array<{
    segment_id: string
    segment_order: number
  }>
}

export interface CropSegmentRequest {
  start_time: number
  end_time: number
}

export interface SplitSegmentRequest {
  split_time: number
}

export interface GenerateVideoRequest {
  output_name?: string
  is_async?: boolean
}

// ============ Axios 类型 ============
import type { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios'

export interface ApiClient extends AxiosInstance {
  get<T = any>(url: string, config?: AxiosRequestConfig): Promise<T>
  post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T>
  put<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T>
  patch<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T>
  delete<T = any>(url: string, config?: AxiosRequestConfig): Promise<T>
}
