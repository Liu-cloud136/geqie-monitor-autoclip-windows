/**
 * 简化的进度条组件 - 基于固定阶段
 */

import React, { useEffect } from 'react'
import { Progress, Card, Typography, Space, Tag } from 'antd'
import { 
  useSimpleProgressStore, 
  getStageDisplayName, 
  getStageColor, 
  isCompleted, 
  isFailed,
  SimpleProgress 
} from '../stores/useSimpleProgressStore'

const { Text } = Typography

interface SimpleProgressBarProps {
  projectId: string
  autoStart?: boolean
  pollingInterval?: number
  showDetails?: boolean
  onProgressUpdate?: (progress: SimpleProgress) => void
}

export const SimpleProgressBar: React.FC<SimpleProgressBarProps> = ({
  projectId,
  autoStart = true,
  pollingInterval = 2000,
  showDetails = true,
  onProgressUpdate
}) => {
  const {
    getProgress
  } = useSimpleProgressStore()

  const progress = getProgress(projectId)
  
  console.log('📊 SimpleProgressBar进度数据:', { projectId, progress })

  // 移除轮询逻辑，改用WebSocket实时更新
  // useSimpleProgressStore.isUsingWebSocket 默认为 true

  // 通知父组件进度更新
  useEffect(() => {
    if (progress && onProgressUpdate) {
      onProgressUpdate(progress)
    }
  }, [progress, onProgressUpdate])

  // 如果没有进度数据，显示等待状态
  if (!progress) {
    return (
      <Card size="small" style={{ margin: '8px 0' }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Text type="secondary">等待开始处理...</Text>
          <Progress 
            percent={0} 
            status="active" 
            strokeColor="#1890ff"
            showInfo={false}
          />
        </Space>
      </Card>
    )
  }

  const { stage, percent, message, ts, estimated_remaining } = progress
  const stageDisplayName = getStageDisplayName(stage)
  const stageColor = getStageColor(stage)
  const completed = isCompleted(stage)
  const failed = isFailed(message)

  // 确定进度条状态
  let progressStatus: 'normal' | 'active' | 'success' | 'exception' = 'normal'
  if (failed) {
    progressStatus = 'exception'
  } else if (completed) {
    progressStatus = 'success'
  } else if (percent > 0) {
    progressStatus = 'active'
  }

  // 格式化预估剩余时间
  const formatEstimatedTime = (seconds?: number): string => {
    if (!seconds || seconds <= 0) return '计算中...'
    if (seconds < 60) return `${seconds}秒`
    if (seconds < 3600) return `${Math.ceil(seconds / 60)}分钟`
    return `${Math.ceil(seconds / 3600)}小时`
  }

  return (
    <Card size="small" style={{ margin: '8px 0' }}>
      <Space direction="vertical" style={{ width: '100%' }}>
        {/* 阶段标签和进度 */}
        <Space align="center" style={{ width: '100%', justifyContent: 'space-between' }}>
          <Space>
            <Tag color={stageColor} style={{ margin: 0 }}>
              {stageDisplayName}
            </Tag>
            {!completed && estimated_remaining && (
              <Tag style={{ margin: 0, fontSize: '11px' }}>
                预计剩余: {formatEstimatedTime(estimated_remaining)}
              </Tag>
            )}
          </Space>
          <Text strong style={{ color: stageColor }}>
            {percent}%
          </Text>
        </Space>

        {/* 进度条 */}
        <Progress
          percent={percent}
          status={progressStatus}
          strokeColor={stageColor}
          showInfo={false}
          size="small"
        />

        {/* 详细信息 */}
        {showDetails && message && (
          <Text type="secondary" style={{ fontSize: '12px' }}>
            {message}
          </Text>
        )}

        {/* 时间戳 */}
        {showDetails && ts > 0 && (
          <Text type="secondary" style={{ fontSize: '11px' }}>
            更新时间: {new Date(ts).toLocaleTimeString()}
          </Text>
        )}
      </Space>
    </Card>
  )
}

// 批量进度显示组件
interface BatchProgressBarProps {
  projectIds: string[]
  autoStart?: boolean
  pollingInterval?: number
  showDetails?: boolean
  onProgressUpdate?: (projectId: string, progress: SimpleProgress) => void
}

export const BatchProgressBar: React.FC<BatchProgressBarProps> = ({
  projectIds,
  autoStart = true,
  pollingInterval = 2000,
  showDetails = true,
  onProgressUpdate
}) => {
  const {
    getAllProgress
  } = useSimpleProgressStore()

  const allProgress = getAllProgress()

  // 移除轮询逻辑，改用WebSocket实时更新

  // 通知父组件进度更新
  useEffect(() => {
    if (onProgressUpdate) {
      projectIds.forEach(projectId => {
        const progress = allProgress[projectId]
        if (progress) {
          onProgressUpdate(projectId, progress)
        }
      })
    }
  }, [allProgress, projectIds, onProgressUpdate])

  return (
    <div>
      {projectIds.map(projectId => (
        <SimpleProgressBar
          key={projectId}
          projectId={projectId}
          autoStart={false} // 批量模式下不自动开始
          showDetails={showDetails}
          onProgressUpdate={(progress) => onProgressUpdate?.(projectId, progress)}
        />
      ))}
    </div>
  )
}
