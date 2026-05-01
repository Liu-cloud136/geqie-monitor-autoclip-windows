/**
 * 处理进度页面自定义Hook
 * 提供处理进度页面的状态管理和业务逻辑
 */

import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { message } from 'antd'
import { projectApi } from '../services/api'
import { useProjectStore } from '../store/useProjectStore'
import { useWebSocket, ProgressUpdateMessage, SystemNotificationMessage } from '../hooks/useWebSocket'
import { useSimpleProgressStore } from '../stores/useSimpleProgressStore'

/**
 * 处理状态接口
 */
export interface ProcessingStatus {
  status: 'processing' | 'completed' | 'error'
  current_step: number
  total_steps: number
  step_name: string
  progress: number
  error_message?: string
}

/**
 * 步骤状态类型
 */
export type StepStatus = 'wait' | 'process' | 'finish' | 'error'

/**
 * 处理进度页面的状态和操作
 */
export interface ProcessingProgressState {
  currentProject: any
  status: ProcessingStatus | null
  loading: boolean
  steps: { title: string; description: string }[]
  getStepStatus: (stepIndex: number) => StepStatus
}

/**
 * 处理进度页面自定义Hook
 * @returns 处理进度页面的状态和操作
 */
export const useProcessingProgress = (): ProcessingProgressState => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { currentProject, setCurrentProject } = useProjectStore()
  const [status, setStatus] = useState<ProcessingStatus | null>(null)
  const [loading, setLoading] = useState(true)
  
  // 获取进度数据
  const { updateProgress } = useSimpleProgressStore()
  
  // 使用WebSocket接收实时进度更新
  const [userId] = useState(() => {
    const stored = localStorage.getItem('websocket_user_id')
    if (stored) return stored
    const newId = `user_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
    localStorage.setItem('websocket_user_id', newId)
    return newId
  })
  
  useWebSocket({
    userId,
    projectIds: id ? [id] : [],
    onProgress: (message: ProgressUpdateMessage) => {
      console.log('ProcessingPage收到进度更新:', message)
      updateProgress(
        message.project_id,
        message.stage,
        message.percent,
        message.message,
        message.estimated_remaining
      )
    },
    onNotification: (notification: SystemNotificationMessage) => {
      console.log('ProcessingPage收到系统通知:', notification)
      // 根据通知级别显示不同类型的通知
      if (notification.level === 'error') {
        message.error(notification.message)
      } else if (notification.level === 'warning') {
        message.warning(notification.message)
      } else if (notification.level === 'success') {
        message.success(notification.message)
      } else {
        message.info(notification.message)
      }
    },
    onConnect: () => {
      console.log('ProcessingPage WebSocket已连接')
    },
    onDisconnect: () => {
      console.log('ProcessingPage WebSocket已断开')
    },
    onError: (error) => {
      console.error('ProcessingPage WebSocket错误:', error)
    },
  })

  const steps = [
    { title: '大纲提取', description: '从视频转写文本中提取结构性大纲' },
    { title: '时间定位', description: '基于SRT字幕定位话题时间区间' },
    { title: '内容评分', description: '多维度评估片段质量与传播潜力' },
    { title: '标题生成', description: '为高分片段生成吸引人的标题' },
    { title: '主题聚类', description: '将相关片段聚合为主题推荐' },
    { title: '视频切割', description: '使用FFmpeg生成切片视频' }
  ]

  useEffect(() => {
    if (!id) return
    
    loadProject()
    const interval = setInterval(checkStatus, 2000) // 每2秒检查一次状态
    
    return () => clearInterval(interval)
  }, [id])

  const loadProject = async () => {
    if (!id) return
    
    try {
      const project = await projectApi.getProject(id)
      setCurrentProject(project)
      
      // 如果项目已完成，直接跳转到详情页
      if (project.status === 'completed') {
        navigate(`/project/${id}`)
        return
      }
      
      // 如果项目状态是等待处理，开始处理
      if (project.status === 'pending') {
        await startProcessing()
      }
    } catch (error) {
      message.error('加载项目失败')
      console.error('Load project error:', error)
    } finally {
      setLoading(false)
    }
  }

  const startProcessing = async () => {
    if (!id) return
    
    try {
      await projectApi.startProcessing(id)
      message.success('开始处理项目')
    } catch (error) {
      message.error('启动处理失败')
      console.error('Start processing error:', error)
    }
  }

  const checkStatus = async () => {
    if (!id) return
    
    try {
      const statusData = await projectApi.getProcessingStatus(id)
      setStatus(statusData)
      
      // 如果处理完成，跳转到项目详情页
      if (statusData.status === 'completed') {
        message.success('🎉 视频处理完成！正在跳转到结果页面...')
        setTimeout(() => {
          navigate(`/project/${id}`)
        }, 2000)
      }
      
      // 如果处理失败，显示详细错误信息
      if (statusData.status === 'error') {
        const errorMsg = statusData.error_message || '处理过程中发生未知错误'
        message.error(`处理失败: ${errorMsg}`)
        
        // 提供重试选项
        message.info('您可以返回首页重新上传文件或联系技术支持', 5)
      }
      
    } catch (error: any) {
      console.error('Check status error:', error)
      
      // 根据错误类型提供不同的处理建议
      if (error.response?.status === 404) {
        message.error('项目不存在或已被删除')
        setTimeout(() => navigate('/'), 2000)
      } else if (error.code === 'ECONNABORTED') {
        message.warning('网络连接超时，正在重试...')
      } else {
        message.error('获取处理状态失败，请刷新页面重试')
      }
    }
  }

  const getStepStatus = (stepIndex: number): StepStatus => {
    if (!status) return 'wait'
    
    if (status.status === 'error') {
      return stepIndex < status.current_step ? 'finish' : 'error'
    }
    
    // 如果进度为0且状态不是completed，显示为等待状态
    if (status.progress === 0 && status.status !== 'completed') {
      return 'wait'
    }
    
    if (stepIndex < status.current_step) return 'finish'
    if (stepIndex === status.current_step) return 'process'
    return 'wait'
  }

  return {
    currentProject,
    status,
    loading,
    steps,
    getStepStatus
  }
}
