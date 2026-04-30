import React, { useState, useEffect, useMemo } from 'react'
import {
  Layout,
  Typography,
  Select,
  Spin,
  Empty,
  message
} from 'antd'
import { useNavigate } from 'react-router-dom'
import ProjectVirtualGrid from '../components/ProjectVirtualGrid'
import FileUpload from '../components/FileUpload'
import ProjectCard from '../components/ProjectCard'

import { projectApi } from '../services/api'
import { Project, useProjectStore } from '../store/useProjectStore'
import { useProjectPolling } from '../hooks/useProjectPolling'
import { useWebSocket, ProgressUpdateMessage, SystemNotificationMessage } from '../hooks/useWebSocket'
import { useSimpleProgressStore } from '../stores/useSimpleProgressStore'

const { Content } = Layout
const { Title, Text } = Typography
const { Option } = Select

// 虚拟滚动阈值 - 超过此数量使用虚拟滚动
const VIRTUAL_SCROLL_THRESHOLD = 20

const HomePage: React.FC = () => {
  const navigate = useNavigate()
  const { projects, setProjects, deleteProject, loading, setLoading, error } = useProjectStore()
  const [statusFilter, setStatusFilter] = useState<string>('all')

  const [userId] = useState(() => {
    const stored = localStorage.getItem('websocket_user_id')
    if (stored) return stored
    const newId = `user_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
    localStorage.setItem('websocket_user_id', newId)
    return newId
  })

  const { updateProgress } = useSimpleProgressStore()

  const processingProjectIds = useMemo(() => {
    const ids = projects
      .filter(p => p.status === 'processing' || p.status === 'pending')
      .map(p => p.id)
    console.log('📋 处理中的项目ID:', ids, '总项目数:', projects.length)
    return ids
  }, [projects])

  const wsHook = useWebSocket({
    userId,
    projectIds: processingProjectIds,
    onProgress: (message: ProgressUpdateMessage) => {
      console.log('收到进度更新:', message)
      
      // 更新进度数据
      updateProgress(
        message.project_id,
        message.stage,
        message.percent,
        message.message,
        message.estimated_remaining
      )
      
      // 如果任务完成，延迟更新项目状态（避免过早取消订阅）
      if (message.stage === 'DONE' && message.percent === 100) {
        setTimeout(() => {
          setProjects(prevProjects => 
            prevProjects.map(p => 
              p.id === message.project_id 
                ? { ...p, status: 'completed' as const }
                : p
            )
          )
        }, 2000) // 延迟 2 秒更新项目状态
      }
    },
    onNotification: (notification: SystemNotificationMessage) => {
      console.log('收到系统通知:', notification)
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
      console.log('WebSocket已连接')
    },
    onDisconnect: () => {
      console.log('WebSocket已断开')
    },
    onError: (error) => {
      console.error('WebSocket错误:', error)
    },
  })

  // 使用项目轮询Hook
  const { refreshNow } = useProjectPolling({
    onProjectsUpdate: (updatedProjects) => {
      setProjects(updatedProjects || [])
    },
    enabled: true,
    interval: 10000 // 10秒轮询一次
  })

  useEffect(() => {
    loadProjects()
  }, [])

  useEffect(() => {
    if (wsHook) {
      (window as any).__WEBSOCKET__ = wsHook
    }
  }, [wsHook])

  useEffect(() => {
    (window as any).__PROJECT_STORE__ = {
      getState: () => ({ projects, loading, error })
    }
  }, [projects, loading, error])

  useEffect(() => {
    (window as any).__PROGRESS_STORE__ = useSimpleProgressStore
  }, [])

  const loadProjects = async () => {
    setLoading(true)
    try {
      const projects = await projectApi.getProjects()
      setProjects(projects || [])
    } catch (err) {
      message.error('加载项目失败')
      console.error('Load projects error:', err)
      setProjects([])
    } finally {
      setLoading(false)
    }
  }

  const handleDeleteProject = async (id: string) => {
    try {
      await projectApi.deleteProject(id)
      deleteProject(id)
      message.success('项目删除成功')
    } catch (error) {
      message.error('删除项目失败')
      console.error('Delete project error:', error)
    }
  }

  const handleRetryProject = async (projectId: string) => {
    const project = projects.find(p => p.id === projectId)
    if (!project) {
      message.error('项目不存在')
      return
    }
    
    if (project.status === 'pending') {
      try {
        await projectApi.startProcessing(projectId)
        message.success('已开始处理项目')
        
        setTimeout(async () => {
          try {
            await refreshNow()
          } catch (refreshError) {
            console.error('Failed to refresh after starting processing:', refreshError)
          }
        }, 1000)
      } catch (error: unknown) {
        const errorMessage = (error as { userMessage?: string })?.userMessage || '启动处理失败'
        message.error(errorMessage)
        console.error('Start processing error:', error)
      }
    } else {
      try {
        const result = await projectApi.retryProcessing(projectId)
        const cleanedFiles = (result as { cleaned_files?: number })?.cleaned_files || 0
        message.success(`已重新提交任务${cleanedFiles > 0 ? `，已清理 ${cleanedFiles} 个中间文件` : ''}`)
        
        setTimeout(async () => {
          try {
            await refreshNow()
          } catch (refreshError) {
            console.error('Failed to refresh after retry:', refreshError)
          }
        }, 1000)
      } catch (error: unknown) {
        const errorMessage = (error as { userMessage?: string })?.userMessage || '重试失败，请稍后再试'
        message.error(errorMessage)
        console.error('Retry project error:', error)
      }
    }
  }

  const handleStartProcessing = async (projectId: string) => {
    try {
      await projectApi.startProcessing(projectId)
      message.success('项目已开始处理，请稍等片刻查看进度')
      // 立即刷新项目列表以显示最新状态
      setTimeout(async () => {
        try {
          await refreshNow()
        } catch (refreshError) {
          console.error('Failed to refresh after starting processing:', refreshError)
        }
      }, 1000)
    } catch (error: unknown) {
      const errorMessage = (error as { userMessage?: string })?.userMessage || '启动处理失败'
      message.error(errorMessage)
      console.error('Start processing error:', error)
      
      // 如果是超时错误，提示用户项目可能仍在处理
      if ((error as { code?: string; message?: string })?.code === 'ECONNABORTED' || (error as { code?: string; message?: string })?.message?.includes('timeout')) {
        message.info('请求超时，但项目可能已开始处理，请查看项目状态', 5)
        // 延迟刷新项目列表
        setTimeout(async () => {
          try {
            await refreshNow()
          } catch (refreshError) {
            console.error('Failed to refresh after timeout:', refreshError)
          }
        }, 3000)
      }
    }
  }

  const handleProjectCardClick = (project: Project) => {
    // 导入中状态的项目不能点击进入详情页
    if (project.status === 'pending') {
      message.warning('项目正在导入中，请稍后再查看详情')
      return
    }
    
    // 其他状态可以正常进入详情页
    navigate(`/project/${project.id}`)
  }

  const filteredProjects = projects
    .filter(project => {
      const matchesStatus = statusFilter === 'all' || project.status === statusFilter
      return matchesStatus
    })
    .sort((a, b) => {
      // 按创建时间倒序排列，最新的在前面
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    })

  return (
    <Layout style={{
      minHeight: '100vh',
      background: '#f5f5f7'
    }}>
      <Content style={{ padding: '40px 24px', position: 'relative' }}>
        <div style={{ maxWidth: '1600px', margin: '0 auto', position: 'relative', zIndex: 1 }}>
          {/* 文件上传区域 */}
          <div style={{ 
            marginBottom: '48px',
            marginTop: '20px',
            display: 'flex',
            justifyContent: 'center'
          }}>
            <div style={{
              width: '100%',
              maxWidth: '800px',
              background: 'rgba(255, 255, 255, 0.9)',
              backdropFilter: 'blur(20px)',
              borderRadius: '16px',
              border: '1px solid rgba(79, 172, 254, 0.2)',
              padding: '20px',
              boxShadow: '0 8px 32px rgba(0, 0, 0, 0.08), 0 0 0 1px rgba(0, 0, 0, 0.03)'
            }}>
              <FileUpload onUploadSuccess={async (projectId: string) => {
                // 处理完成后刷新项目列表
                await loadProjects()
                message.success('项目创建成功，正在处理中...')
              }} />
            </div>
          </div>

          {/* 项目管理区域 */}
          <div style={{
            background: 'rgba(255, 255, 255, 0.9)',
            backdropFilter: 'blur(20px)',
            borderRadius: '24px',
            border: '1px solid rgba(79, 172, 254, 0.15)',
            padding: '32px',
            marginBottom: '32px',
            boxShadow: '0 8px 32px rgba(0, 0, 0, 0.08), 0 0 0 1px rgba(0, 0, 0, 0.03)'
          }}>
            {/* 项目列表标题区域 */}
            <div style={{ 
              display: 'flex', 
              justifyContent: 'space-between', 
              alignItems: 'center',
              marginBottom: '24px',
              paddingBottom: '16px',
              borderBottom: '1px solid rgba(79, 172, 254, 0.1)'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                <Title
                  level={2}
                  style={{
                    margin: 0,
                    color: '#1a1a1a',
                    fontSize: '24px',
                    fontWeight: 600
                  }}
                >
                  我的项目
                </Title>
                <div style={{
                  padding: '8px 16px',
                  background: 'rgba(79, 172, 254, 0.1)',
                  borderRadius: '20px',
                  border: '1px solid rgba(79, 172, 254, 0.3)',
                  backdropFilter: 'blur(10px)'
                }}>
                  <Text style={{ color: '#4facfe', fontWeight: 600, fontSize: '14px' }}>
                    共 {filteredProjects.length} 个项目
                  </Text>
                </div>
              </div>
              
              {/* 状态筛选移到右侧 */}
              <div style={{ 
                display: 'flex', 
                alignItems: 'center'
              }}>
                <Select
                  placeholder="选择状态"
                  value={statusFilter}
                  onChange={setStatusFilter}
                  style={{
                    minWidth: '140px',
                    height: '36px',
                    borderRadius: '8px',
                    fontSize: '14px'
                  }}
                  styles={{
                    popup: {
                      root: {
                        background: 'rgba(255, 255, 255, 0.95)',
                        border: '1px solid #e0e0e0',
                        borderRadius: '8px',
                        backdropFilter: 'blur(20px)',
                        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.1)'
                      }
                    }
                  }}
                  suffixIcon={
                    <span style={{ 
                      color: '#8c8c8c', 
                      fontSize: '10px',
                      transition: 'all 0.2s ease'
                    }}>
                      ⌄
                    </span>
                  }
                  allowClear
                >
                  <Option value="all">全部状态</Option>
                  <Option value="completed">已完成</Option>
                  <Option value="processing">处理中</Option>
                  <Option value="error">处理失败</Option>
                </Select>
              </div>
            </div>

            {/* 项目列表内容 */}
             <div>
               {loading ? (
                 <div style={{
                   textAlign: 'center',
                   padding: '60px 0',
                   background: '#ffffff',
                   borderRadius: '12px',
                   border: '1px solid #e0e0e0'
                 }}>
                   <Spin size="large" />
                   <div style={{
                     marginTop: '20px',
                     color: '#666666',
                     fontSize: '16px'
                   }}>
                     正在加载项目列表...
                   </div>
                 </div>
               ) : filteredProjects.length === 0 ? (
                 <div style={{
                   textAlign: 'center',
                   padding: '60px 0',
                   background: '#ffffff',
                   borderRadius: '12px',
                   border: '1px solid #e0e0e0'
                 }}>
                   <Empty
                     image={Empty.PRESENTED_IMAGE_SIMPLE}
                     description={
                       <div>
                         <Text type="secondary">
                           {projects.length === 0 ? '还没有项目，请使用上方的导入区域创建第一个项目' : '没有找到匹配的项目'}
                         </Text>
                       </div>
                     }
                   />
                 </div>
               ) : (
                 <div style={{
                   display: 'grid',
                   gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
                   gap: '16px',
                   justifyContent: 'start',
                   padding: '6px 0'
                 }}>
                   {filteredProjects.map((project: Project) => (
                     <div key={project.id} style={{ position: 'relative', zIndex: 1 }}>
                       <ProjectCard 
                         project={project} 
                         onDelete={handleDeleteProject}
                         onRetry={() => handleRetryProject(project.id)}
                         onClick={() => handleProjectCardClick(project)}
                       />
                     </div>
                   ))}
                 </div>
               )}
             </div>
           </div>
         </div>
      </Content>
    </Layout>
  )
}

export default HomePage