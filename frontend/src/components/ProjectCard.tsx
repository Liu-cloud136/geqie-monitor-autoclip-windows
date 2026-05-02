import React, { useState, useEffect, useRef } from 'react'
import { Card, Tag, Button, Space, Typography, Progress, Popconfirm, App, Tooltip } from 'antd'
import { PlayCircleOutlined, DeleteOutlined, EyeOutlined, ReloadOutlined, LoadingOutlined, CheckCircleOutlined, ExclamationCircleOutlined, SettingOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { Project } from '../store/useProjectStore'
import { projectApi } from '../services/api'
import { UnifiedStatusBar } from './UnifiedStatusBar'
import RetryStepDialog from './RetryStepDialog'
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import timezone from 'dayjs/plugin/timezone'
import utc from 'dayjs/plugin/utc'
import 'dayjs/locale/zh-cn'

dayjs.extend(relativeTime)
dayjs.extend(timezone)
dayjs.extend(utc)
dayjs.locale('zh-cn')

// 添加CSS动画样式
const pulseAnimation = `
  @keyframes pulse {
    0% {
      opacity: 1;
      transform: scale(1);
    }
    50% {
      opacity: 0.5;
      transform: scale(1.1);
    }
    100% {
      opacity: 1;
      transform: scale(1);
    }
  }
`

// 将样式注入到页面
if (typeof document !== 'undefined') {
  const style = document.createElement('style')
  style.textContent = pulseAnimation
  document.head.appendChild(style)
}

const { Text, Title } = Typography
const { Meta } = Card

interface ProjectCardProps {
  project: Project
  onDelete: (id: string) => void
  onRetry?: (id: string) => void
  onClick?: () => void
}

interface LogEntry {
  timestamp: string
  module: string
  level: string
  message: string
}

const ProjectCard: React.FC<ProjectCardProps> = ({ project, onDelete, onRetry, onClick }) => {
  const { message } = App.useApp()
  const navigate = useNavigate()
  const [videoThumbnail, setVideoThumbnail] = useState<string | null>(null)
  const [thumbnailLoading, setThumbnailLoading] = useState(false)
  const [isRetrying, setIsRetrying] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [currentLogIndex, setCurrentLogIndex] = useState(0)
  const [retryStatus, setRetryStatus] = useState<'idle' | 'success' | 'error'>('idle')
  const retryTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastRetryTimeRef = useRef<number>(0)
  const [showRetryDialog, setShowRetryDialog] = useState(false)

  // 缩略图缓存管理
  const thumbnailCacheKey = `thumbnail_${project.id}`
  
  // 生成项目视频缩略图（带缓存）
  useEffect(() => {
    const generateThumbnail = async () => {
      // 优先使用后端提供的缩略图
      if (project.thumbnail) {
        setVideoThumbnail(project.thumbnail)
        console.log(`使用后端提供的缩略图: ${project.id}`)
        return
      }
      
      if (!project.video_path) {
        console.log('项目没有视频路径:', project.id)
        return
      }
      
      // 检查缓存
      const cachedThumbnail = localStorage.getItem(thumbnailCacheKey)
      if (cachedThumbnail) {
        setVideoThumbnail(cachedThumbnail)
        return
      }
      
      setThumbnailLoading(true)
      
      try {
        const video = document.createElement('video')
        video.crossOrigin = 'anonymous'
        video.muted = true
        video.preload = 'metadata'
        
        // 尝试多个可能的视频文件路径
        const possiblePaths = [
          'input/input.mp4',
          'input.mp4',
          project.video_path,
          `${project.video_path}/input.mp4`
        ].filter(Boolean)
        
        let videoLoaded = false
        
        for (const path of possiblePaths) {
          if (videoLoaded) break
          
          try {
            const videoUrl = projectApi.getProjectFileUrl(project.id, path)
            console.log('尝试加载视频:', videoUrl)
            
            await new Promise((resolve, reject) => {
              const timeoutId = setTimeout(() => {
                reject(new Error('视频加载超时'))
              }, 10000) // 10秒超时
              
              video.onloadedmetadata = () => {
                clearTimeout(timeoutId)
                console.log('视频元数据加载成功:', videoUrl)
                video.currentTime = Math.min(5, video.duration / 4) // 取视频1/4处或5秒处的帧
              }
              
              video.onseeked = () => {
                clearTimeout(timeoutId)
                try {
                  const canvas = document.createElement('canvas')
                  const ctx = canvas.getContext('2d')
                  if (!ctx) {
                    reject(new Error('无法获取canvas上下文'))
                    return
                  }
                  
                  // 设置合适的缩略图尺寸
                  const maxWidth = 320
                  const maxHeight = 180
                  const aspectRatio = video.videoWidth / video.videoHeight
                  
                  let width = maxWidth
                  let height = maxHeight
                  
                  if (aspectRatio > maxWidth / maxHeight) {
                    height = maxWidth / aspectRatio
                  } else {
                    width = maxHeight * aspectRatio
                  }
                  
                  canvas.width = width
                  canvas.height = height
                  ctx.drawImage(video, 0, 0, width, height)
                  
                  const thumbnail = canvas.toDataURL('image/jpeg', 0.7)
                  setVideoThumbnail(thumbnail)
                  
                  // 缓存缩略图
                  try {
                    localStorage.setItem(thumbnailCacheKey, thumbnail)
                  } catch (e) {
                    // 如果localStorage空间不足，清理旧缓存
                    const keys = Object.keys(localStorage).filter(key => key.startsWith('thumbnail_'))
                    if (keys.length > 50) { // 保留最多50个缩略图缓存
                      keys.slice(0, 10).forEach(key => localStorage.removeItem(key))
                      localStorage.setItem(thumbnailCacheKey, thumbnail)
                    }
                  }
                  
                  videoLoaded = true
                  resolve(thumbnail)
                } catch (error) {
                  reject(error)
                }
              }
              
              video.onerror = (error) => {
                clearTimeout(timeoutId)
                console.error('视频加载失败:', videoUrl, error)
                reject(error)
              }
              
              video.src = videoUrl
            })
            
            break // 如果成功加载，跳出循环
          } catch (error) {
            console.warn(`路径 ${path} 加载失败:`, error)
            continue // 尝试下一个路径
          }
        }
        
        if (!videoLoaded) {
          console.error('所有视频路径都加载失败')
        }
      } catch (error) {
        console.error('生成缩略图时发生错误:', error)
      } finally {
        setThumbnailLoading(false)
      }
    }
    
    generateThumbnail()
  }, [project.id, project.video_path, thumbnailCacheKey])

  // 获取项目日志（仅在处理中时）
  useEffect(() => {
    if (project.status !== 'processing') {
      setLogs([])
      return
    }

    const fetchLogs = async () => {
      try {
        const response = await projectApi.getProjectLogs(project.id, 20)
        setLogs(response.logs.filter(log => 
          log.message.includes('Step') || 
          log.message.includes('开始') || 
          log.message.includes('完成') ||
          log.message.includes('处理') ||
          log.level === 'ERROR'
        ))
      } catch (error) {
        console.error('获取日志失败:', error)
      }
    }

    // 立即获取一次
    fetchLogs()
    
    // 每3秒更新一次日志
    const logInterval = setInterval(fetchLogs, 3000)
    
    return () => clearInterval(logInterval)
  }, [project.id, project.status])

  // 日志轮播
  useEffect(() => {
    if (logs.length <= 1) return
    
    const interval = setInterval(() => {
      setCurrentLogIndex(prev => (prev + 1) % logs.length)
    }, 2000) // 每2秒切换一条日志
    
    return () => clearInterval(interval)
  }, [logs.length])

  // 清理重试状态定时器
  useEffect(() => {
    return () => {
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current)
      }
    }
  }, [])

  const getStatusColor = (status: Project['status']) => {
    switch (status) {
      case 'completed': return 'success'
      case 'processing': return 'processing'
      case 'error': return 'error'
      case 'pending': return 'default'
      default: return 'default'
    }
  }

  // 检查是否是等待处理状态 - pending状态显示为导入中
  const isImporting = project.status === 'pending'
  
  // 状态标准化处理 - pending状态显示为导入中
  const normalizedStatus = project.status === 'error' ? 'failed' : 
                          isImporting ? 'importing' : project.status
  
  // 调试信息
  console.log('ProjectCard Debug:', {
    projectId: project.id,
    projectStatus: project.status,
    isImporting,
    normalizedStatus,
    processingConfig: project.processing_config,
    downloadProgress: project.processing_config?.download_progress
  })
  
  // 计算进度百分比
  const progressPercent = project.status === 'completed' ? 100 : 
                         project.status === 'failed' ? 0 :
                         isImporting ? (project.processing_config?.download_progress || 20) : // 导入中从 processing_config 获取进度
                         project.current_step && project.total_steps ? 
                         Math.round((project.current_step / project.total_steps) * 100) : 
                         project.status === 'processing' ? 10 : 0

  const handleRetry = async () => {
    if (isRetrying) return
    
    const now = Date.now()
    const timeSinceLastRetry = now - lastRetryTimeRef.current
    const RETRY_COOLDOWN = 3000
    
    if (timeSinceLastRetry < RETRY_COOLDOWN) {
      message.warning(`请等待 ${Math.ceil((RETRY_COOLDOWN - timeSinceLastRetry) / 1000)} 秒后再重试`)
      return
    }
    
    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current)
      retryTimeoutRef.current = null
    }
    
    lastRetryTimeRef.current = now
    setIsRetrying(true)
    setRetryStatus('idle')
    
    try {
      if (onRetry) {
        await onRetry(project.id)
      }
      setRetryStatus('success')
      message.success('任务已成功提交')
      
      retryTimeoutRef.current = setTimeout(() => {
        setRetryStatus('idle')
      }, 2000)
    } catch (error) {
      console.error('重试失败:', error)
      setRetryStatus('error')
      message.error('重试失败，请稍后再试')
      
      retryTimeoutRef.current = setTimeout(() => {
        setRetryStatus('idle')
      }, 3000)
    } finally {
      setIsRetrying(false)
    }
  }

  const handleDelete = async () => {
    if (isDeleting) return
    
    setIsDeleting(true)
    try {
      await onDelete(project.id)
    } catch (error) {
      console.error('删除失败:', error)
      message.error('删除失败，请稍后再试')
    } finally {
      setIsDeleting(false)
    }
  }

  return (
    <Card
      hoverable
      className="project-card"
      style={{
        width: 200,
        height: 240,
        borderRadius: '4px',
        overflow: 'hidden',
        background: 'linear-gradient(145deg, #ffffff 0%, #f5f5f5 100%)',
        border: 'none',
        boxShadow: '0 4px 20px rgba(0, 0, 0, 0.08)',
        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
        cursor: 'pointer',
        marginBottom: '0px'
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = 'translateY(-4px)'
        e.currentTarget.style.boxShadow = '0 8px 30px rgba(79, 172, 254, 0.2)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = 'translateY(0)'
        e.currentTarget.style.boxShadow = '0 4px 20px rgba(0, 0, 0, 0.08)'
      }}
      styles={{
        body: {
          padding: '12px',
          background: 'transparent',
          height: 'calc(100% - 120px)',
          display: 'flex',
          flexDirection: 'column'
        }
      }}
      cover={
        <div 
          style={{ 
            height: 120, 
            position: 'relative',
            background: videoThumbnail 
              ? `url(${videoThumbnail}) center/cover` 
              : 'linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            overflow: 'hidden'
          }}
          onClick={() => {
            // 导入中状态的项目不能点击进入详情页
            if (project.status === 'pending') {
              message.warning('项目正在导入中，请稍后再查看详情')
              return
            }
            
            if (onClick) {
              onClick()
            } else {
              navigate(`/project/${project.id}`)
            }
          }}
        >
          {/* 缩略图加载状态 */}
          {thumbnailLoading && (
            <div style={{ 
              textAlign: 'center',
              color: 'rgba(255, 255, 255, 0.8)'
            }}>
              <LoadingOutlined 
                style={{ 
                  fontSize: '24px', 
                  marginBottom: '4px'
                }} 
              />
              <div style={{ 
                fontSize: '12px',
                fontWeight: 500
              }}>
                生成封面中...
              </div>
            </div>
          )}
          
          {/* 无缩略图时的默认显示 */}
          {!videoThumbnail && !thumbnailLoading && (
            <div style={{ textAlign: 'center' }}>
              <PlayCircleOutlined 
                style={{ 
                  fontSize: '40px', 
                  color: 'rgba(255, 255, 255, 0.9)',
                  marginBottom: '4px',
                  filter: 'drop-shadow(0 2px 8px rgba(0,0,0,0.3))'
                }} 
              />
              <div style={{ 
                color: 'rgba(255, 255, 255, 0.8)', 
                fontSize: '12px',
                fontWeight: 500
              }}>
                点击预览
              </div>
            </div>
          )}
          
          {/* 移除右上角状态指示器 - 可读性差且冗余 */}
        </div>
      }
    >
      <div style={{ padding: '0', flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
        <div>
          {/* 项目名称 - 始终在顶部 */}
          <div style={{ marginBottom: '12px', position: 'relative' }}>
            <Tooltip title={project.name} placement="top">
              <Text
                strong
                style={{
                  fontSize: '13px',
                  color: '#1a1a1a',
                  fontWeight: 600,
                  lineHeight: '16px',
                  display: '-webkit-box',
                  WebkitLineClamp: 2,
                  WebkitBoxOrient: 'vertical',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  cursor: 'help',
                  height: '32px'
                }}
              >
                {project.name}
              </Text>
            </Tooltip>
          </div>
          
          {/* 状态和统计信息 */}
          {(normalizedStatus === 'importing' || normalizedStatus === 'processing' || normalizedStatus === 'failed') ? (
            // 导入中、处理中、失败：显示状态块 + 重试/删除按钮
            <div style={{
              display: 'flex',
              gap: '6px',
              marginBottom: '12px',
              alignItems: 'center'
            }}>
              <div style={{ flex: 2 }}>
                <UnifiedStatusBar
                  projectId={project.id}
                  status={normalizedStatus}
                  downloadProgress={progressPercent}
                  onDownloadProgressUpdate={(progress) => {
                    console.log(`项目 ${project.id} 下载进度更新: ${progress}%`)
                  }}
                />
              </div>

              {/* 重试按钮 */}
              <Tooltip title={
                project.status === 'pending' ? "开始处理" : 
                project.status === 'processing' ? "重新处理（当前任务会停止）" :
                project.status === 'error' ? "重新尝试处理" :
                "重新处理项目"
              }>
                <Button
                  type="text"
                  icon={
                    isRetrying ? <LoadingOutlined /> :
                    retryStatus === 'success' ? <CheckCircleOutlined /> :
                    retryStatus === 'error' ? <ExclamationCircleOutlined /> :
                    <ReloadOutlined />
                  }
                  loading={isRetrying}
                  onClick={(e) => {
                    e.stopPropagation()
                    handleRetry()
                  }}
                  style={{
                    width: '20px',
                    height: '20px',
                    borderRadius: '3px',
                    color: retryStatus === 'success' ? '#52c41a' : 
                           retryStatus === 'error' ? '#ff4d4f' :
                           '#1890ff',
                    border: `1px solid ${
                      retryStatus === 'success' ? 'rgba(82, 196, 26, 0.5)' : 
                      retryStatus === 'error' ? 'rgba(255, 77, 79, 0.5)' :
                      'rgba(24, 144, 255, 0.5)'
                    }`,
                    background: retryStatus === 'success' ? 'rgba(82, 196, 26, 0.1)' : 
                               retryStatus === 'error' ? 'rgba(255, 77, 79, 0.1)' :
                               'rgba(24, 144, 255, 0.1)',
                    padding: 0,
                    minWidth: '20px',
                    fontSize: '10px',
                    transition: 'all 0.3s ease'
                  }}
                />
              </Tooltip>

              {/* 删除按钮 */}
              <Popconfirm
                title="确定要删除这个项目吗？"
                description="删除后无法恢复"
                onConfirm={(e) => {
                  e?.stopPropagation()
                  handleDelete()
                }}
                onCancel={(e) => {
                  e?.stopPropagation()
                }}
                okText="确定"
                cancelText="取消"
                okButtonProps={{ loading: isDeleting }}
              >
                <Button
                  type="text"
                  icon={isDeleting ? <LoadingOutlined /> : <DeleteOutlined />}
                  onClick={(e) => {
                    e.stopPropagation()
                  }}
                  disabled={isDeleting}
                  style={{
                    width: '20px',
                    height: '20px',
                    borderRadius: '3px',
                    color: 'rgba(255, 107, 107, 0.8)',
                    border: '1px solid rgba(255, 107, 107, 0.2)',
                    background: 'rgba(255, 107, 107, 0.05)',
                    padding: 0,
                    minWidth: '20px',
                    fontSize: '10px'
                  }}
                />
              </Popconfirm>
            </div>
          ) : (
            <div style={{ 
              display: 'flex', 
              gap: '6px',
              marginBottom: '12px'
            }}>
              {/* 状态显示 - 占据更多空间 */}
              <div style={{ flex: 2 }}>
                <UnifiedStatusBar
                  projectId={project.id}
                  status={normalizedStatus}
                  downloadProgress={progressPercent}
                  onDownloadProgressUpdate={(progress) => {
                    console.log(`项目 ${project.id} 下载进度更新: ${progress}%`)
                  }}
                />
              </div>
              
              {/* 切片数量 - 减小宽度 */}
              <div style={{
                background: 'rgba(102, 126, 234, 0.15)',
                border: '1px solid rgba(102, 126, 234, 0.3)',
                borderRadius: '3px',
                padding: '3px 4px',
                textAlign: 'center',
                minWidth: '50px',
                flex: 0.8
              }}>
                <div style={{ color: '#667eea', fontSize: '11px', fontWeight: 600, lineHeight: '12px' }}>
                  {project.total_clips || 0}
                </div>
                <div style={{ color: '#999999', fontSize: '8px', lineHeight: '9px' }}>
                  切片
                </div>
              </div>

              {/* 已完成项目的重试按钮 */}
              {project.status === 'completed' && (
                <Tooltip title="重新处理">
                  <Button
                    type="text"
                    icon={<SettingOutlined />}
                    onClick={(e) => {
                      e.stopPropagation()
                      setShowRetryDialog(true)
                    }}
                    style={{
                      width: '20px',
                      height: '20px',
                      borderRadius: '3px',
                      color: '#52c41a',
                      border: '1px solid rgba(82, 196, 26, 0.5)',
                      background: 'rgba(82, 196, 26, 0.1)',
                      padding: 0,
                      minWidth: '20px',
                      fontSize: '10px'
                    }}
                  />
                </Tooltip>
              )}

              {/* 删除按钮 */}
              <Popconfirm
                title="确定要删除这个项目吗？"
                description="删除后无法恢复"
                onConfirm={(e) => {
                  e?.stopPropagation()
                  handleDelete()
                }}
                onCancel={(e) => {
                  e?.stopPropagation()
                }}
                okText="确定"
                cancelText="取消"
                okButtonProps={{ loading: isDeleting }}
              >
                <Button
                  type="text"
                  icon={isDeleting ? <LoadingOutlined /> : <DeleteOutlined />}
                  onClick={(e) => {
                    e.stopPropagation()
                  }}
                  disabled={isDeleting}
                  style={{
                    width: '20px',
                    height: '20px',
                    borderRadius: '3px',
                    color: 'rgba(255, 107, 107, 0.8)',
                    border: '1px solid rgba(255, 107, 107, 0.2)',
                    background: 'rgba(255, 107, 107, 0.05)',
                    padding: 0,
                    minWidth: '20px',
                    fontSize: '10px'
                  }}
                />
              </Popconfirm>
            </div>
          )}

          {/* 详细进度显示已隐藏 - 只在状态块中显示百分比 */}

        </div>
      </div>

      <RetryStepDialog
        visible={showRetryDialog}
        projectId={project.id}
        projectName={project.name}
        projectStatus={project.status}
        onClose={() => setShowRetryDialog(false)}
        onRetry={async (startStep: string, cleanOutput: boolean) => {
          await projectApi.retryFromStep(project.id, startStep, cleanOutput)
        }}
      />
    </Card>
  )
}

export default ProjectCard