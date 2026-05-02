/**
 * 统一状态栏组件 - 替换旧的复杂进度系统
 * 支持下载中、处理中、完成等状态的统一显示
 */

import React, { useEffect, useState } from 'react'
import { Progress, Space, Typography, Tag } from 'antd'
import { 
  DownloadOutlined, 
  LoadingOutlined, 
  CheckCircleOutlined, 
  ExclamationCircleOutlined,
  ClockCircleOutlined
} from '@ant-design/icons'
import { useSimpleProgressStore, getStageDisplayName, getStageColor, isCompleted, isFailed } from '../stores/useSimpleProgressStore'

const { Text } = Typography

interface UnifiedStatusBarProps {
  projectId: string
  status: string
  downloadProgress?: number
  onStatusChange?: (status: string) => void
  onDownloadProgressUpdate?: (progress: number) => void
}

export const UnifiedStatusBar: React.FC<UnifiedStatusBarProps> = ({
  projectId,
  status,
  downloadProgress = 0,
  onStatusChange,
  onDownloadProgressUpdate
}) => {
  const progress = useSimpleProgressStore(state => state.byId[projectId])
  const [currentDownloadProgress, setCurrentDownloadProgress] = useState(downloadProgress)

  // 移除轮询逻辑，改用WebSocket实时更新

  // 导入进度轮询
  useEffect(() => {
    if (status === 'importing' && projectId) {
      const pollImportProgress = async () => {
        try {
          console.log(`轮询导入进度: ${projectId}`)
          const response = await fetch(`/api/v1/projects/${projectId}`)
          if (response.ok) {
            const projectData = await response.json()
            console.log('项目数据:', projectData)
            const newProgress = projectData.processing_config?.download_progress || 0
            console.log(`导入进度更新: ${newProgress}%`)
            setCurrentDownloadProgress(newProgress)
            onDownloadProgressUpdate?.(newProgress)
            
            // 如果导入完成（100%），检查是否需要切换到处理状态
            if (newProgress >= 100) {
              console.log('导入完成，切换到处理状态')
              setTimeout(() => {
                onStatusChange?.('processing')
              }, 1000)
            }
          } else {
            // 404 错误表示项目不存在，可以停止轮询
            if (response.status === 404) {
              console.error('项目不存在，停止轮询:', response.status, response.statusText)
              // 不停止轮询，因为项目可能稍后会被创建
            } else {
              console.error('获取项目数据失败:', response.status, response.statusText)
            }
          }
        } catch (error) {
          console.error('获取导入进度失败:', error)
        }
      }

      // 立即获取一次
      pollImportProgress()
      
      // 每2秒轮询一次
      const interval = setInterval(pollImportProgress, 2000)
      
      return () => clearInterval(interval)
    }
  }, [status, projectId, onDownloadProgressUpdate, onStatusChange])

  // 下载进度轮询
  useEffect(() => {
    if (status === 'downloading' && projectId) {
      const pollDownloadProgress = async () => {
        try {
          console.log(`轮询下载进度: ${projectId}`)
          const response = await fetch(`/api/v1/projects/${projectId}`)
          if (response.ok) {
            const projectData = await response.json()
            console.log('项目数据:', projectData)
            const newProgress = projectData.processing_config?.download_progress || 0
            console.log(`下载进度更新: ${newProgress}%`)
            setCurrentDownloadProgress(newProgress)
            onDownloadProgressUpdate?.(newProgress)
            
            // 如果下载完成，检查是否需要切换到处理状态
            if (newProgress >= 100) {
              console.log('下载完成，切换到处理状态')
              setTimeout(() => {
                onStatusChange?.('processing')
              }, 1000)
            }
          } else {
            // 404 错误表示项目不存在，可以停止轮询
            if (response.status === 404) {
              console.error('项目不存在，停止轮询:', response.status, response.statusText)
              // 不停止轮询，因为项目可能稍后会被创建
            } else {
              console.error('获取项目数据失败:', response.status, response.statusText)
            }
          }
        } catch (error) {
          console.error('获取下载进度失败:', error)
        }
      }

      // 立即获取一次
      pollDownloadProgress()
      
      // 每2秒轮询一次
      const interval = setInterval(pollDownloadProgress, 2000)
      
      return () => clearInterval(interval)
    }
  }, [status, projectId, onDownloadProgressUpdate, onStatusChange])

  // 处理状态变化
  useEffect(() => {
    if (progress && onStatusChange) {
      if (isCompleted(progress.stage)) {
        onStatusChange('completed')
      } else if (isFailed(progress.message)) {
        onStatusChange('failed')
      }
    }
  }, [progress, onStatusChange])

  // 导入中状态
  if (status === 'importing') {
    return (
      <div style={{
        background: 'rgba(255, 193, 7, 0.1)',
        border: '1px solid rgba(255, 193, 7, 0.3)',
        borderRadius: '3px',
        padding: '3px 6px',
        textAlign: 'center',
        width: '100%'
      }}>
        <div style={{ 
          color: '#ffc107',
          fontSize: '11px', 
          fontWeight: 600, 
          lineHeight: '12px'
        }}>
          {Math.round(downloadProgress)}%
        </div>
        <div style={{ 
          color: '#999999', 
          fontSize: '8px', 
          lineHeight: '9px'
        }}>
          导入中
        </div>
      </div>
    )
  }

  // 下载中状态
  if (status === 'downloading') {
    return (
      <div style={{
        background: 'rgba(24, 144, 255, 0.1)',
        border: '1px solid rgba(24, 144, 255, 0.3)',
        borderRadius: '3px',
        padding: '3px 6px',
        textAlign: 'center',
        width: '100%'
      }}>
        <div style={{ 
          color: '#1890ff',
          fontSize: '11px', 
          fontWeight: 600, 
          lineHeight: '12px'
        }}>
          {Math.round(currentDownloadProgress)}%
        </div>
        <div style={{ 
          color: '#999999', 
          fontSize: '8px', 
          lineHeight: '9px'
        }}>
          下载中
        </div>
      </div>
    )
  }

  // 处理中状态 - 使用新的简化进度系统
  if (status === 'processing') {
    if (!progress) {
      // 等待进度数据
      return (
      <div style={{
        background: 'rgba(82, 196, 26, 0.1)',
        border: '1px solid rgba(82, 196, 26, 0.3)',
        borderRadius: '3px',
        padding: '3px 6px',
        textAlign: 'center',
        width: '100%'
      }}>
        <div style={{
          color: '#52c41a',
          fontSize: '11px',
          fontWeight: 600,
          lineHeight: '12px'
        }}>
          0%
        </div>
        <div style={{
          color: '#999999',
          fontSize: '8px',
          lineHeight: '9px'
        }}>
          初始化中...
        </div>
      </div>
      )
    }

    const { stage, percent, message, estimated_remaining } = progress
    const stageDisplayName = getStageDisplayName(stage)
    const stageColor = getStageColor(stage)
    const failed = isFailed(message)

    // 格式化预估剩余时间
    const formatEstimatedTime = (seconds?: number): string => {
      if (!seconds || seconds <= 0) return ''
      if (seconds < 60) return `${seconds}s`
      if (seconds < 3600) return `${Math.ceil(seconds / 60)}m`
      return `${Math.ceil(seconds / 3600)}h`
    }

    const estimatedTimeText = formatEstimatedTime(estimated_remaining)

    return (
      <div style={{
        background: failed
          ? 'rgba(255, 77, 79, 0.1)'
          : 'rgba(82, 196, 26, 0.1)',
        border: failed
          ? '1px solid rgba(255, 77, 79, 0.3)'
          : '1px solid rgba(82, 196, 26, 0.3)',
        borderRadius: '3px',
        padding: '3px 6px',
        textAlign: 'center',
        width: '100%'
      }}>
        <div style={{
          color: failed ? '#ff4d4f' : '#52c41a',
          fontSize: '11px',
          fontWeight: 600,
          lineHeight: '12px'
        }}>
          {failed ? '✗ 失败' : `${percent}%`}
        </div>
        <div style={{
          color: '#999999',
          fontSize: '8px',
          lineHeight: '9px',
          minHeight: '9px'
        }}>
          {failed ? '' : (estimatedTimeText ? `约${estimatedTimeText}` : stageDisplayName)}
        </div>
      </div>
    )
  }

  // 已完成状态
  if (status === 'completed') {
    return (
      <div style={{
        background: 'rgba(82, 196, 26, 0.1)',
        border: '1px solid rgba(82, 196, 26, 0.3)',
        borderRadius: '3px',
        padding: '3px 6px',
        textAlign: 'center',
        width: '100%'
      }}>
        <div style={{ 
          color: '#52c41a',
          fontSize: '11px', 
          fontWeight: 600, 
          lineHeight: '12px'
        }}>
          ✓
        </div>
        <div style={{ 
          color: '#999999', 
          fontSize: '8px', 
          lineHeight: '9px'
        }}>
          已完成
        </div>
      </div>
    )
  }

  // 失败状态
  if (status === 'failed') {
    return (
      <div style={{
        background: 'rgba(255, 77, 79, 0.1)',
        border: '1px solid rgba(255, 77, 79, 0.3)',
        borderRadius: '3px',
        padding: '3px 6px',
        textAlign: 'center',
        width: '100%'
      }}>
        <div style={{ 
          color: '#ff4d4f',
          fontSize: '11px', 
          fontWeight: 600, 
          lineHeight: '12px'
        }}>
          ✗ 失败
        </div>
        <div style={{ 
          color: '#999999', 
          fontSize: '8px', 
          lineHeight: '9px',
          minHeight: '9px' // 确保失败状态也有固定高度
        }}>
          处理失败
        </div>
      </div>
    )
  }

  // 等待状态
  return (
    <div style={{
      background: 'rgba(217, 217, 217, 0.1)',
      border: '1px solid rgba(217, 217, 217, 0.3)',
      borderRadius: '3px',
      padding: '3px 6px',
      textAlign: 'center',
      width: '100%'
    }}>
      <div style={{ 
        color: '#d9d9d9',
        fontSize: '11px', 
        fontWeight: 600, 
        lineHeight: '12px'
      }}>
        ○ 等待中
      </div>
      <div style={{ 
        color: '#999999', 
        fontSize: '8px', 
        lineHeight: '9px',
        minHeight: '9px' // 确保等待状态也有固定高度
      }}>
        等待处理
      </div>
    </div>
  )
}

// 简化的进度条组件 - 用于详细进度显示
interface SimpleProgressDisplayProps {
  projectId: string
  status: string
  showDetails?: boolean
}

export const SimpleProgressDisplay: React.FC<SimpleProgressDisplayProps> = ({
  projectId,
  status,
  showDetails = false
}) => {
  const progress = useSimpleProgressStore(state => state.byId[projectId])

  if (status !== 'processing' || !progress || !showDetails) {
    return null
  }

  const { stage, percent, message } = progress
  const stageDisplayName = getStageDisplayName(stage)
  const stageColor = getStageColor(stage)

  return (
    <div style={{ marginTop: '8px' }}>
      <Progress
        percent={percent}
        strokeColor={stageColor}
        showInfo={true}
        size="small"
        format={(percent) => `${percent}%`}
      />
      {message && (
        <Text type="secondary" style={{ fontSize: '11px', display: 'block', marginTop: '4px' }}>
          {message}
        </Text>
      )}
    </div>
  )
}
