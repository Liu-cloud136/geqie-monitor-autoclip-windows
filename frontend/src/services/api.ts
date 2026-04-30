import axios, { AxiosError, InternalAxiosRequestConfig, AxiosResponse } from 'axios'
import { Project, Clip } from '../store/useProjectStore'
import { ApiResponse, PaginatedResponse, ApiClient } from '../types/api'

// 格式化时间函数(暂时未使用,保留备用)

// 格式化时间函数
const formatSecondsToTime = (seconds: number) => {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = Math.floor(seconds % 60)
  return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}

// 获取基础URL,用于视频下载等需要完整URL的场景
export const getBaseUrl = (): string => {
  return window.location.origin
}

// 获取后端API地址
export const getBackendUrl = (): string => {
  // 优先使用环境变量
  if (import.meta.env.VITE_BACKEND_URL) {
    return import.meta.env.VITE_BACKEND_URL
  }

  // 默认:使用相对路径(由Vite代理或CloudStudio反向代理处理)
  return ''
}

// 构建完整的API URL
export const getApiUrl = (path: string): string => {
  return `/api/v1${path}`
}

// 创建自定义类型的axios实例
const api = axios.create({
  baseURL: '/api/v1/', // 使用相对路径,由Vite代理或CloudStudio反向代理处理
  timeout: 300000, // 增加到5分钟超时
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
}) as unknown as ApiClient // 响应拦截器会修改返回类型

// 请求拦截器
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    console.log('🌐 API 请求:', config.method?.toUpperCase(), config.baseURL + config.url)
    return config
  },
  (error: unknown) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  (response: AxiosResponse) => {
    console.log('✅ API 响应:', response.config.url, 'Status:', response.status)
    console.log('📦 响应类型:', typeof response.data)
    console.log('📦 响应前100字符:', JSON.stringify(response.data).substring(0, 100))
    return response.data
  },
  (error: unknown) => {
    console.error('❌ API Error:', error)
    const axiosError = error as AxiosError
    if (axiosError.response) {
      console.error('❌ 错误响应:', axiosError.response.status, axiosError.config?.url)
    }
    
    // 特殊处理429错误（系统繁忙）
    if (axiosError.response?.status === 429) {
      const responseData = axiosError.response.data as Record<string, unknown> | undefined
      const message = responseData?.detail || '系统正在处理其他项目，请稍后再试'
      ;(axiosError as unknown as { userMessage?: string }).userMessage = message as string
    }
    // 处理超时错误
    else if (axiosError.code === 'ECONNABORTED' || axiosError.message?.includes('timeout')) {
      ;(axiosError as unknown as { userMessage?: string }).userMessage = '请求超时，项目可能仍在后台处理中，请稍后查看项目状态'
    }
    // 处理网络错误
    else if (axiosError.code === 'NETWORK_ERROR' || !axiosError.response) {
      ;(axiosError as unknown as { userMessage?: string }).userMessage = '网络连接失败，请检查网络连接'
    }
    // 处理服务器错误
    else if (axiosError.response?.status !== undefined && axiosError.response.status >= 500) {
      ;(axiosError as unknown as { userMessage?: string }).userMessage = '服务器内部错误，请稍后重试'
    }
    
    return Promise.reject(error)
  }
)

export interface UploadFilesRequest {
  video_file: File
  danmaku_file?: File
  project_name: string
  danmaku_source_type?: string
}

export interface UploadFilesOptions {
  onUploadProgress?: (progressEvent: import('axios').AxiosProgressEvent) => void
}

export interface ProcessingStatus {
  status: 'processing' | 'completed' | 'error'
  current_step: number
  total_steps: number
  step_name: string
  progress: number
  error_message?: string
}

// 设置相关API
export const settingsApi = {
  // 获取系统配置
  getSettings: (): Promise<ApiResponse<Record<string, unknown>>> => {
    return api.get('settings/')
  },

  // 更新系统配置
  updateSettings: (settings: Record<string, unknown>): Promise<ApiResponse<Record<string, unknown>>> => {
    return api.post('settings/', settings)
  },

  // 测试API密钥
  testApiKey: (
    provider: string,
    apiKey: string,
    modelName: string
  ): Promise<ApiResponse<{ success: boolean; error?: string }>> => {
    return api.post('settings/test-api-key/', {
      provider,
      api_key: apiKey,
      model_name: modelName,
    })
  },

  // 获取所有可用模型
  getAvailableModels: (): Promise<ApiResponse<Record<string, unknown>>> => {
    return api.get('settings/available-models/')
  },

  // 获取当前提供商信息
  getCurrentProvider: (): Promise<ApiResponse<Record<string, unknown>>> => {
    return api.get('settings/current-provider/')
  },

  // 注册自定义提供商
  registerCustomProvider: (
    providerId: string,
    apiKey: string,
    baseUrl: string,
    apiFormat: string = 'openai',
    defaultModel: string = 'custom-model'
  ): Promise<ApiResponse<{
    success: boolean
    message: string
    provider_id: string
    models: Array<{ id: string; display_name: string; description?: string }>
    error?: string
  }>> => {
    return api.post('settings/register-custom-provider/', {
      provider_id: providerId,
      api_key: apiKey,
      base_url: baseUrl,
      api_format: apiFormat,
      default_model: defaultModel,
    })
  },
}

// 项目相关API
export const projectApi = {
  // 获取所有项目
  getProjects: async (): Promise<Project[]> => {
    const data = await api.get('projects/')
    // 响应拦截器已经返回了 response.data
    // 处理分页响应结构，返回items数组
    const projects = data?.items || data || []
    return Array.isArray(projects) ? projects : []
  },

  // 获取单个项目
  getProject: async (id: string): Promise<Project> => {
    const data = await api.get(`projects/${id}`, { params: { include_clips: true } })

    // 如果返回的数据包含 clips，需要转换格式
    if (data.clips && Array.isArray(data.clips)) {
      // 转换秒数为时间字符串格式
      const formatSecondsToTime = (seconds: number) => {
        const hours = Math.floor(seconds / 3600)
        const minutes = Math.floor((seconds % 3600) / 60)
        const secs = Math.floor(seconds % 60)
        return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
      }

      // 转换 clips 数据格式
      data.clips = data.clips.map((clip: Clip) => {
        const metadata = clip.clip_metadata || {}

        return {
          ...clip,
          // 使用 clip_metadata 中的 final_score
          final_score: metadata.final_score || clip.score || 0,
          // 使用 clip_metadata 中的 recommend_reason
          recommend_reason: metadata.recommend_reason || clip.recommendation_reason || '',
          // 使用 clip_metadata 中的 outline
          outline: metadata.outline || '',
          // 使用 clip_metadata 中的 content
          content: metadata.content || [],
          // 将数字秒数转换为时间字符串
          start_time: typeof clip.start_time === 'number'
            ? formatSecondsToTime(clip.start_time)
            : clip.start_time,
          end_time: typeof clip.end_time === 'number'
            ? formatSecondsToTime(clip.end_time)
            : clip.end_time,
          // 确保生成的标题使用正确的字段
          generated_title: metadata.generated_title || clip.title || ''
        }
      })
    }

    return data
  },

  // 上传文件并创建项目
  uploadFiles: async (data: UploadFilesRequest, options?: UploadFilesOptions): Promise<Project> => {
    const formData = new FormData()
    formData.append('video_file', data.video_file)
    formData.append('project_name', data.project_name)
    
    if (data.danmaku_file) {
      formData.append('danmaku_file', data.danmaku_file)
    }
    if (data.danmaku_source_type) {
      formData.append('danmaku_source_type', data.danmaku_source_type)
    }

    const result = await api.post('projects/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: options?.onUploadProgress,
    })
    return result
  },

  // 删除项目
  deleteProject: async (id: string): Promise<void> => {
    await api.delete(`projects/${id}`)
  },

  // 开始处理项目
  startProcessing: async (id: string): Promise<void> => {
    await api.post(`projects/${id}/process`)
  },

  // 重试处理项目
  retryProcessing: async (id: string): Promise<{message: string, project_id: string, task_id: string, celery_task_id: string, status: string, cleaned_files?: number}> => {
    return api.post(`projects/${id}/retry`)
  },

  // 从指定步骤重试处理项目
  retryFromStep: async (id: string, startStep: string, cleanOutput: boolean = true): Promise<{
    message: string
    project_id: string
    task_id: string
    celery_task_id: string
    start_step: string
    status: string
    cleaned_files: number
  }> => {
    return api.post(`projects/${id}/retry-step?start_step=${startStep}&clean_output=${cleanOutput}`)
  },

  // 获取项目步骤状态
  getStepsStatus: async (id: string): Promise<{
    project_id: string
    project_status: string
    steps: Array<{
      step: string
      name: string
      completed: boolean
      file_size: number
      modified_time: number | null
    }>
    clips_count: number
  }> => {
    return api.get(`projects/${id}/steps-status`)
  },

  // 获取处理状态
  getProcessingStatus: async (id: string): Promise<ProcessingStatus> => {
    const data = await api.get(`projects/${id}/status`)
    return data
  },

  // 获取项目日志
  getProjectLogs: async (id: string, lines: number = 50): Promise<{logs: Array<{timestamp: string, module: string, level: string, message: string}>}> => {
    const data = await api.get(`projects/${id}/logs`, { params: { lines } })
    return data
  },

  // 获取项目切片
  getClips: async (projectId: string): Promise<Clip[]> => {
    try {
      // 只从数据库获取数据，不再回退到文件系统
      console.log('🔍 Calling clips API for project:', projectId)
      const data = await api.get(`/clips/?project_id=${projectId}`)
      console.log('📦 Raw API response:', data)
      // 响应拦截器已经返回了 response.data
      const clips = data?.items || data || []
      console.log('📋 Extracted clips:', clips.length, 'clips found')

      // 确保返回的是数组
      if (!Array.isArray(clips)) {
        console.warn('⚠️ Clips response is not an array:', clips)
        return []
      }

      // 转换后端数据格式为前端期望的格式
      const convertedClips = clips.map((clip: Clip) => {
        // 获取metadata中的内容
        const metadata = clip.clip_metadata || {}

        return {
          id: clip.id,
          title: clip.title,
          generated_title: clip.title,
          start_time: formatSecondsToTime(typeof clip.start_time === 'number' ? clip.start_time : parseFloat(clip.start_time as string)),
          end_time: formatSecondsToTime(typeof clip.end_time === 'number' ? clip.end_time : parseFloat(clip.end_time as string)),
          duration: clip.duration || 0,
          final_score: clip.score || 0,
          recommend_reason: metadata.recommend_reason || '',
          outline: metadata.outline || '',
          // 只使用metadata中的content，避免使用description（可能是转写文本）
          content: metadata.content || [],
          chunk_index: metadata.chunk_index || 0,
        }
      })

      console.log('✅ Converted clips:', convertedClips.length, 'clips')
      console.log('📄 First clip sample:', convertedClips[0])
      return convertedClips
    } catch (error) {
      console.error('❌ Failed to get clips:', error)
      return []
    }
  },

  // 重启指定步骤
  restartStep: async (id: string, step: number): Promise<void> => {
    await api.post(`projects/${id}/restart-step`, { step })
  },

  // 更新切片信息
  updateClip: async (projectId: string, clipId: string, updates: Partial<Clip>): Promise<Clip> => {
    const data = await api.patch(`projects/${projectId}/clips/${clipId}`, updates)
    return data
  },

  // 更新切片标题
  updateClipTitle: async (clipId: string, title: string): Promise<Record<string, unknown>> => {
    const data = await api.patch(`/clips/${clipId}/title`, { title })
    return data
  },

  // 生成切片标题
  generateClipTitle: async (clipId: string): Promise<{clip_id: string, generated_title: string, success: boolean}> => {
    const data = await api.post(`/clips/${clipId}/generate-title`)
    return data
  },

  // 下载切片视频
  downloadClip: async (_projectId: string, clipId: string): Promise<Blob> => {
    const data = await api.get(`/files/projects/${_projectId}/clips/${clipId}`, {
      responseType: 'blob'
    })
    return data
  },

  // 导出元数据
  exportMetadata: async (projectId: string): Promise<Blob> => {
    const data = await api.get(`projects/${projectId}/export`, {
      responseType: 'blob'
    })
    return data
  },

  downloadVideo: async (projectId: string, clipId?: string) => {
    let url = `projects/${projectId}/download`
    if (clipId) {
      url += `?clip_id=${clipId}`
    }
    
    try {
      // 对于blob类型的响应，需要直接使用axios而不是经过拦截器
      const response = await axios.get(`${getBaseUrl()}/api/v1${url}`, { 
        responseType: 'blob',
        headers: {
          'Accept': 'application/octet-stream'
        }
      })
      
      // 从响应头获取文件名，如果没有则使用默认名称
      const contentDisposition = response.headers['content-disposition']
      let filename = clipId ? `clip_${clipId}.mp4` : `project_${projectId}.mp4`
      
      if (contentDisposition) {
        // 优先尝试解析 RFC 6266 格式的 filename* 参数
        const filenameStarMatch = contentDisposition.match(/filename\*=UTF-8''([^;]+)/)
        if (filenameStarMatch) {
          filename = decodeURIComponent(filenameStarMatch[1])
        } else {
          // 回退到传统的 filename 参数
          const filenameMatch = contentDisposition.match(/filename="([^"]+)"/)
          if (filenameMatch) {
            filename = filenameMatch[1]
          }
        }
      }
      
      // 创建下载链接
      const blob = new Blob([response.data], { type: 'video/mp4' })
      const downloadUrl = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = downloadUrl
      link.download = filename
      
      // 触发下载
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(downloadUrl)
      
      return response.data
    } catch (error) {
      console.error('下载失败:', error)
      throw error
    }
  },

  // 获取项目文件URL
  getProjectFileUrl: (projectId: string, filename: string): string => {
    return `${api.defaults.baseURL}/projects/${projectId}/files/${filename}`
  },

  // 获取项目视频URL
  getProjectVideoUrl: (projectId: string): string => {
    return `${api.defaults.baseURL}/projects/${projectId}/video`
  },

  // 获取切片视频URL
  getClipVideoUrl: (projectId: string, clipId: string, _clipTitle?: string): string => {
    // 使用files路由获取切片视频
    return getApiUrl(`/files/projects/${projectId}/clips/${clipId}`)
  },

  // 获取切片缩略图URL
  getClipThumbnailUrl: (projectId: string, clipId: string): string => {
    return getApiUrl(`/files/projects/${projectId}/clips/${clipId}/thumbnail`)
  },

  // 生成项目缩略图
  generateThumbnail: async (projectId: string): Promise<{success: boolean, thumbnail: string, message: string}> => {
    return api.post(`projects/${projectId}/generate-thumbnail`)
  }
}

// 系统状态相关API
export const systemApi = {
  // 获取系统状态
  getSystemStatus: (): Promise<{
    current_processing_count: number
    max_concurrent_processing: number
    total_projects: number
    processing_projects: string[]
  }> => {
    return api.get('system/status')
  }
}

// 任务相关API
export const taskApi = {
  // 获取所有任务
  getTasks: async (params?: {
    skip?: number
    limit?: number
    status?: string
    project_id?: string
  }): Promise<ApiResponse<PaginatedResponse<Record<string, unknown>>>> => {
    return api.get('tasks/', { params })
  },

  // 获取项目的任务列表
  getProjectTasks: async (projectId: string): Promise<ApiResponse<PaginatedResponse<Record<string, unknown>>>> => {
    return api.get(`tasks/project/${projectId}`)
  },

  // 获取单个任务详情
  getTask: async (taskId: string): Promise<ApiResponse<Record<string, unknown>>> => {
    return api.get(`tasks/${taskId}`)
  },

  // 删除任务
  deleteTask: async (taskId: string): Promise<ApiResponse<{ message: string }>> => {
    return api.delete(`tasks/${taskId}`)
  },

  // 获取任务状态
  getTaskStatus: async (taskId: string): Promise<ApiResponse<Record<string, unknown>>> => {
    return api.get(`tasks/${taskId}/status`)
  },

  // 重试失败的任务
  retryTask: async (taskId: string): Promise<ApiResponse<{ message: string }>> => {
    return api.post(`tasks/${taskId}/retry`)
  },
}

export default api

export interface DanmakuFileInfo {
  id: string
  file_name: string
  file_path: string
  file_size: number
  source_type: string
  status: string
  danmaku_count: number
  video_duration: number
  project_id: string | null
  analysis_metadata: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface DanmakuHeatPoint {
  start_time: number
  end_time: number
  center_time: number
  danmaku_count: number
  density: number
  heat_score: number
  keywords: string[]
  sentiment_score: number
}

export interface DanmakuScoreBreakdown {
  heat_score: number
  keyword_score: number
  sentiment_score: number
  special_score: number
  total_danmaku_score: number
  heat_contribution: number
  keyword_contribution: number
  sentiment_contribution: number
  special_contribution: number
}

export interface DanmakuScoreResult {
  success: boolean
  danmaku_file_id: string
  time_range: {
    start_time: number
    end_time: number
    duration: number
  }
  scores: DanmakuScoreBreakdown
}

export const danmakuApi = {
  uploadDanmakuFile: async (
    file: File,
    projectId?: string,
    sourceType: string = 'bilibili'
  ): Promise<{
    success: boolean
    danmaku_file_id: string
    file_name: string
    danmaku_count: number
    status: string
    message: string
  }> => {
    const formData = new FormData()
    formData.append('file', file)
    if (projectId) {
      formData.append('project_id', projectId)
    }
    formData.append('source_type', sourceType)

    const result = await api.post('danmaku/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return result
  },

  getDanmakuFileInfo: async (danmakuFileId: string): Promise<DanmakuFileInfo> => {
    const result = await api.get(`danmaku/${danmakuFileId}`)
    return result
  },

  parseDanmakuFile: async (danmakuFileId: string): Promise<{
    success: boolean
    danmaku_file_id: string
    danmaku_count: number
    status: string
    message: string
  }> => {
    const result = await api.post(`danmaku/parse/${danmakuFileId}`)
    return result
  },

  analyzeDanmakuFile: async (
    danmakuFileId: string,
    windowSeconds: number = 10,
    slideSeconds: number = 5
  ): Promise<{
    success: boolean
    danmaku_file_id: string
    status: string
    message: string
    summary: {
      total_danmaku: number
      heat_points_count: number
      top_keywords: Array<{ word: string; count: number }>
      sentiment: { positive: number; negative: number; neutral: number }
      special_danmaku_count: number
    }
  }> => {
    const result = await api.post(`danmaku/analyze/${danmakuFileId}`, null, {
      params: {
        window_seconds: windowSeconds,
        slide_seconds: slideSeconds,
      },
    })
    return result
  },

  getHeatPoints: async (
    danmakuFileId: string,
    limit: number = 20,
    minScore: number = 0
  ): Promise<{
    danmaku_file_id: string
    heat_points: DanmakuHeatPoint[]
  }> => {
    const result = await api.get(`danmaku/${danmakuFileId}/heat-points`, {
      params: {
        limit,
        min_score: minScore,
      },
    })
    return result
  },

  getScoreForTimeRange: async (
    danmakuFileId: string,
    startTime: number,
    endTime: number
  ): Promise<DanmakuScoreResult> => {
    const result = await api.post(`danmaku/score-time-range/${danmakuFileId}`, null, {
      params: {
        start_time: startTime,
        end_time: endTime,
      },
    })
    return result
  },

  getProjectDanmakuFiles: async (projectId: string): Promise<{
    project_id: string
    danmaku_files: Array<{
      id: string
      file_name: string
      status: string
      danmaku_count: number
      created_at: string
    }>
  }> => {
    const result = await api.get(`danmaku/project/${projectId}`)
    return result
  },

  deleteDanmakuFile: async (danmakuFileId: string): Promise<{
    success: boolean
    danmaku_file_id: string
    message: string
  }> => {
    const result = await api.delete(`danmaku/${danmakuFileId}`)
    return result
  },
}

// 切片编辑相关 API
export const clipEditApi = {
  // 创建编辑会话
  createSession: async (
    projectId: string,
    name: string = '未命名编辑'
  ): Promise<{
    success: boolean
    session: Record<string, unknown>
    message?: string
  }> => {
    const result = await api.post('clip-edit/sessions/', {
      name,
      project_id: projectId,
    })
    return result
  },

  // 获取编辑会话
  getSession: async (
    sessionId: string
  ): Promise<{
    success: boolean
    session: Record<string, unknown>
  }> => {
    const result = await api.get(`clip-edit/sessions/${sessionId}`)
    return result
  },

  // 获取项目的所有编辑会话
  getProjectSessions: async (
    projectId: string
  ): Promise<{
    success: boolean
    sessions: Array<Record<string, unknown>>
  }> => {
    const result = await api.get(`clip-edit/projects/${projectId}/sessions/`)
    return result
  },

  // 获取或创建默认编辑会话
  getOrCreateDefaultSession: async (
    projectId: string
  ): Promise<{
    success: boolean
    session: Record<string, unknown>
    is_new: boolean
  }> => {
    const result = await api.post(`clip-edit/projects/${projectId}/default-session/`)
    return result
  },

  // 更新编辑会话
  updateSession: async (
    sessionId: string,
    name?: string
  ): Promise<{
    success: boolean
    session: Record<string, unknown>
  }> => {
    const result = await api.put(`clip-edit/sessions/${sessionId}`, {
      name,
    })
    return result
  },

  // 删除编辑会话
  deleteSession: async (
    sessionId: string
  ): Promise<{
    success: boolean
    message: string
  }> => {
    const result = await api.delete(`clip-edit/sessions/${sessionId}`)
    return result
  },

  // 添加片段到会话
  addSegment: async (
    sessionId: string,
    originalClipId: string,
    startTime?: number,
    endTime?: number,
    segmentOrder?: number
  ): Promise<{
    success: boolean
    segment: Record<string, unknown>
  }> => {
    const result = await api.post(`clip-edit/sessions/${sessionId}/segments/`, {
      original_clip_id: originalClipId,
      start_time: startTime,
      end_time: endTime,
      segment_order: segmentOrder,
    })
    return result
  },

  // 批量添加切片到会话
  addClipsToSession: async (
    sessionId: string,
    clipIds: string[]
  ): Promise<{
    success: boolean
    segments: Array<Record<string, unknown>>
    added_count: number
  }> => {
    const result = await api.post(`clip-edit/sessions/${sessionId}/add-clips/`, {
      clip_ids: clipIds,
    })
    return result
  },

  // 获取会话的所有片段
  getSessionSegments: async (
    sessionId: string
  ): Promise<{
    success: boolean
    segments: Array<Record<string, unknown>>
  }> => {
    const result = await api.get(`clip-edit/sessions/${sessionId}/segments/`)
    return result
  },

  // 更新片段
  updateSegment: async (
    segmentId: string,
    updates: {
      start_time?: number
      end_time?: number
      segment_order?: number
    }
  ): Promise<{
    success: boolean
    segment: Record<string, unknown>
  }> => {
    const result = await api.put(`clip-edit/segments/${segmentId}`, updates)
    return result
  },

  // 删除片段
  deleteSegment: async (
    segmentId: string
  ): Promise<{
    success: boolean
    message: string
  }> => {
    const result = await api.delete(`clip-edit/segments/${segmentId}`)
    return result
  },

  // 重排片段顺序
  reorderSegments: async (
    sessionId: string,
    segmentOrders: Array<{
      segment_id: string
      segment_order: number
    }>
  ): Promise<{
    success: boolean
    segments: Array<Record<string, unknown>>
  }> => {
    const result = await api.post(`clip-edit/sessions/${sessionId}/reorder/`, {
      segment_orders: segmentOrders,
    })
    return result
  },

  // 裁剪片段
  cropSegment: async (
    segmentId: string,
    startTime: number,
    endTime: number
  ): Promise<{
    success: boolean
    segment: Record<string, unknown>
  }> => {
    const result = await api.post(`clip-edit/segments/${segmentId}/crop/`, {
      start_time: startTime,
      end_time: endTime,
    })
    return result
  },

  // 分割片段
  splitSegment: async (
    segmentId: string,
    splitTime: number
  ): Promise<{
    success: boolean
    original_segment: Record<string, unknown>
    new_segment: Record<string, unknown>
  }> => {
    const result = await api.post(`clip-edit/segments/${segmentId}/split/`, {
      split_time: splitTime,
    })
    return result
  },

  // 生成合并视频
  generateVideo: async (
    sessionId: string,
    outputName?: string,
    isAsync: boolean = true
  ): Promise<{
    success: boolean
    status: string
    message: string
    session_id: string
    task_id?: string
    output_path?: string
  }> => {
    const result = await api.post(`clip-edit/sessions/${sessionId}/generate-video/`, {
      output_name: outputName,
      is_async: isAsync,
    })
    return result
  },

  // 获取编辑会话的缩略图 URL
  getSegmentThumbnailUrl: (projectId: string, segmentId: string): string => {
    return getApiUrl(`/files/projects/${projectId}/segments/${segmentId}/thumbnail`)
  },
}