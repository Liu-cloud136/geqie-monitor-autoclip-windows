import React, { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Layout,
  Card,
  Typography,
  Button,
  Space,
  Alert,
  Spin,
  Empty,
  message,
  Radio,
  Tabs,
  Tag,
} from 'antd'
import {
  ArrowLeftOutlined,
  PlayCircleOutlined,
  VideoCameraOutlined,
  UnorderedListOutlined,
} from '@ant-design/icons'
import { useProjectStore, Clip } from '../store/useProjectStore'
import { projectApi, clipEditApi } from '../services/api'
import { useClipEditStore } from '../stores/useClipEditStore'
import ClipVirtualGrid from '../components/ClipVirtualGrid'
import ClipCard from '../components/ClipCard'
import TimelineEditor from '../components/TimelineEditor'
import SelectClipsModal from '../components/SelectClipsModal'
import { EditSegment } from '../types/api'

const { Content } = Layout
const { Title, Text } = Typography

const VIRTUAL_SCROLL_THRESHOLD = 30

const ProjectDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const {
    currentProject,
    loading,
    error,
    setCurrentProject
  } = useProjectStore()

  // 编辑状态
  const {
    currentSession,
    setSession,
    setSegments,
    addSegment,
  } = useClipEditStore()

  const [statusLoading, setStatusLoading] = useState(false)
  const [sortBy, setSortBy] = useState<'time' | 'score'>('score')
  const [activeTab, setActiveTab] = useState<'clips' | 'editor'>('clips')
  const [selectClipsModalVisible, setSelectClipsModalVisible] = useState(false)
  const [selectedClipIdsForAdd, setSelectedClipIdsForAdd] = useState<string[]>([])

  useEffect(() => {
    if (id) {
      if (!currentProject || currentProject.id !== id) {
        loadProject()
      }
      loadProcessingStatus()
    }
  }, [id])

  const loadProject = async () => {
    if (!id) return
    try {
      console.log('🔄 开始加载项目:', id)
      const project = await projectApi.getProject(id)
      console.log('📦 完整项目数据:', project)
      console.log('🎬 Loaded project with clips:', project.clips?.length || 0, 'clips')
      setCurrentProject(project)

      const { projects } = useProjectStore.getState()
      const updatedProjects = projects.map(p =>
        p.id === id ? project : p
      )
      useProjectStore.setState({ projects: updatedProjects })
    } catch (error) {
      console.error('Failed to load project:', error)
      message.error('加载项目失败')
    }
  }

  const loadProcessingStatus = async () => {
    if (!id) return
    setStatusLoading(true)
    try {
      await projectApi.getProcessingStatus(id)
    } catch (error) {
      console.error('Failed to load processing status:', error)
    } finally {
      setStatusLoading(false)
    }
  }

  const handleStartProcessing = async () => {
    if (!id) return
    try {
      await projectApi.startProcessing(id)
      message.success('开始处理')
      loadProcessingStatus()
    } catch (error) {
      console.error('Failed to start processing:', error)
      message.error('启动处理失败')
    }
  }

  const getSortedClips = useCallback(() => {
    if (!currentProject?.clips) return []
    const clips = [...currentProject.clips]
    
    if (sortBy === 'score') {
      return clips.sort((a, b) => b.final_score - a.final_score)
    } else {
      return clips.sort((a, b) => {
        const getTimeInSeconds = (timeStr: string | number) => {
          if (typeof timeStr === 'number') {
            return timeStr
          }
          const parts = timeStr.split(':')
          const hours = parseInt(parts[0])
          const minutes = parseInt(parts[1])
          const seconds = parseFloat(parts[2].replace(',', '.'))
          return hours * 3600 + minutes * 60 + seconds
        }
        
        const aTime = getTimeInSeconds(a.start_time)
        const bTime = getTimeInSeconds(b.start_time)
        return aTime - bTime
      })
    }
  }, [currentProject, sortBy])

  // 打开选择切片模态框
  const handleOpenSelectClips = useCallback(() => {
    const existingIds = currentSession?.segments?.map(s => String(s.original_clip_id)) || []
    setSelectedClipIdsForAdd(existingIds)
    setSelectClipsModalVisible(true)
  }, [currentSession])

  // 确认添加选择的切片到时间轴
  const handleConfirmAddClips = useCallback(async (clipIds: string[]) => {
    if (!currentSession || !id) return

    const existingIds = new Set(currentSession.segments.map(s => String(s.original_clip_id)))
    const newIds = clipIds.filter(clipId => !existingIds.has(clipId))

    if (newIds.length === 0) {
      message.info('这些切片已在时间轴中')
      return
    }

    try {
      const result = await clipEditApi.addClipsToSession(currentSession.id, newIds)
      if (result.success) {
        message.success(`已添加 ${result.added_count} 个切片到时间轴`)
        // 重新加载会话数据
        const sessionResult = await clipEditApi.getSession(currentSession.id)
        if (sessionResult.success) {
          setSession(sessionResult.session as any)
        }
        // 切换到编辑标签
        setActiveTab('editor')
      }
    } catch (error) {
      message.error('添加切片失败')
    }
  }, [currentSession, id, setSession])

  if (loading) {
    return (
      <Content style={{ padding: '24px', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
        <Spin size="large" />
      </Content>
    )
  }

  if (error || !currentProject) {
    return (
      <Content style={{ padding: '24px', background: '#ffffff' }}>
        <Alert
          message="加载失败"
          description={error || '项目不存在'}
          type="error"
          action={
            <Button size="small" onClick={() => navigate('/')}>
              返回首页
            </Button>
          }
        />
      </Content>
    )
  }

  // 渲染切片列表标签页内容
  const renderClipsTab = () => {
    if (currentProject.status !== 'completed') {
      return (
        <div>
          {currentProject.clips && currentProject.clips.length > 0 ? (
            <Card style={{ marginTop: '16px', borderRadius: '16px', border: '1px solid #e0e0e0' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
                <div>
                  <Title level={4} style={{ margin: 0, fontWeight: 600 }}>已生成的片段（预览）</Title>
                  <Text type="secondary" style={{ fontSize: '14px' }}>
                    正在处理中... 已生成 {currentProject.clips?.length || 0} 个片段
                  </Text>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <Text style={{ fontSize: '13px', color: '#666666', fontWeight: 500 }}>排序</Text>
                  <Radio.Group
                    value={sortBy}
                    onChange={(e) => setSortBy(e.target.value)}
                    size="small"
                    buttonStyle="solid"
                  >
                    <Radio.Button value="time" style={{ height: '28px', lineHeight: '26px' }}>时间</Radio.Button>
                    <Radio.Button value="score" style={{ height: '28px', lineHeight: '26px' }}>评分</Radio.Button>
                  </Radio.Group>
                </div>
              </div>

              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
                  gap: '20px',
                  padding: '8px 0'
                }}
              >
                {getSortedClips().map((clip) => (
                  <ClipCard
                    key={clip.id}
                    clip={clip}
                    projectId={currentProject.id}
                  />
                ))}
              </div>

              <div style={{ marginTop: '16px', textAlign: 'center', padding: '12px', background: '#fffbe6', borderRadius: '8px' }}>
                <Text style={{ color: '#faad14', fontSize: '14px' }}>
                  ℹ️ 更多片段正在处理中，完成后将自动更新...
                </Text>
              </div>
            </Card>
          ) : (
            <Card style={{ marginTop: '16px', borderRadius: '16px' }}>
              <Empty
                image={<PlayCircleOutlined style={{ fontSize: '64px', color: '#d9d9d9' }} />}
                description={
                  <div>
                    <Text>项目还未完成处理</Text>
                    <br />
                    <Text type="secondary">处理完成后可查看视频片段</Text>
                  </div>
                }
              />
            </Card>
          )}
        </div>
      )
    }

    // 已完成状态的切片列表
    return (
      <Card
        className="clip-list-card"
        style={{
          borderRadius: '16px',
          border: '1px solid #e0e0e0',
        }}
        styles={{
          body: {
            padding: '24px'
          }
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px' }}>
          <div>
            <Title level={4} style={{ margin: 0, color: '#1a1a1a', fontWeight: 600 }}>视频片段</Title>
            <Text type="secondary" style={{ color: '#666666', fontSize: '14px' }}>
              AI 已为您生成了 {currentProject.clips?.length || 0} 个精彩片段
            </Text>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <Button
              type="primary"
              icon={<VideoCameraOutlined />}
              onClick={handleOpenSelectClips}
              style={{
                background: 'linear-gradient(45deg, #52c41a, #73d13d)',
                border: 'none',
              }}
            >
              添加到时间轴
            </Button>

            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <Text style={{ fontSize: '13px', color: '#666666', fontWeight: 500 }}>排序</Text>
              <Radio.Group
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                size="small"
                buttonStyle="solid"
              >
                <Radio.Button
                   value="time"
                   style={{
                     fontSize: '13px',
                     height: '32px',
                     lineHeight: '30px',
                     padding: '0 16px',
                     background: sortBy === 'time' ? 'linear-gradient(45deg, #1890ff, #36cfc9)' : '#ffffff',
                     border: sortBy === 'time' ? '1px solid #1890ff' : '1px solid #d0d0d0',
                     color: sortBy === 'time' ? '#ffffff' : '#666666',
                     borderRadius: '6px 0 0 6px',
                     fontWeight: sortBy === 'time' ? 600 : 400,
                     boxShadow: sortBy === 'time' ? '0 2px 8px rgba(24, 144, 255, 0.3)' : 'none',
                     transition: 'all 0.2s ease'
                   }}
                 >
                   时间
                 </Radio.Button>
                 <Radio.Button
                   value="score"
                   style={{
                     fontSize: '13px',
                     height: '32px',
                     lineHeight: '30px',
                     padding: '0 16px',
                     background: sortBy === 'score' ? 'linear-gradient(45deg, #1890ff, #36cfc9)' : '#ffffff',
                     border: sortBy === 'score' ? '1px solid #1890ff' : '1px solid #d0d0d0',
                     borderLeft: 'none',
                     color: sortBy === 'score' ? '#ffffff' : '#666666',
                     borderRadius: '0 6px 6px 0',
                     fontWeight: sortBy === 'score' ? 600 : 400,
                     boxShadow: sortBy === 'score' ? '0 2px 8px rgba(24, 144, 255, 0.3)' : 'none',
                     transition: 'all 0.2s ease'
                   }}
                 >
                   评分
                 </Radio.Button>
              </Radio.Group>
            </div>
          </div>
        </div>

        {currentProject.clips && currentProject.clips.length > 0 ? (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
              gap: '20px',
              padding: '8px 0'
            }}
          >
            {getSortedClips().map((clip) => (
              <ClipCard
                key={clip.id}
                clip={clip}
                projectId={currentProject.id}
              />
            ))}
          </div>
        ) : (
          <div style={{
            padding: '60px 0',
            textAlign: 'center',
            background: 'rgba(255,255,255,0.02)',
            borderRadius: '12px',
            border: '1px dashed #404040'
          }}>
            <Empty
              description={
                <Text style={{ color: '#888', fontSize: '14px' }}>暂无视频片段</Text>
              }
              image={<PlayCircleOutlined style={{ fontSize: '48px', color: '#555' }} />}
            />
          </div>
        )}
      </Card>
    )
  }

  // 渲染时间轴编辑标签页内容
  const renderEditorTab = () => {
    if (currentProject.status !== 'completed') {
      return (
        <Card style={{ marginTop: '16px', borderRadius: '16px' }}>
          <Empty
            description={
              <div>
                <Text>项目还未完成处理</Text>
                <br />
                <Text type="secondary">处理完成后可使用时间轴编辑功能</Text>
              </div>
            }
            image={<VideoCameraOutlined style={{ fontSize: '64px', color: '#d9d9d9' }} />}
          />
        </Card>
      )
    }

    return (
      <div style={{ marginTop: '16px' }}>
        <TimelineEditor
          projectId={currentProject.id}
          onAddClips={handleOpenSelectClips}
        />
      </div>
    )
  }

  // 定义标签页
  const tabItems = [
    {
      key: 'clips',
      label: (
        <span>
          <UnorderedListOutlined style={{ marginRight: '6px' }} />
          切片列表
          {currentProject.clips && currentProject.clips.length > 0 && (
            <Tag color="blue" style={{ marginLeft: '8px' }}>
              {currentProject.clips.length}
            </Tag>
          )}
        </span>
      ),
      children: renderClipsTab(),
    },
  ]

  // 只有项目完成时才显示时间轴编辑标签
  if (currentProject.status === 'completed') {
    tabItems.push({
      key: 'editor',
      label: (
        <span>
          <VideoCameraOutlined style={{ marginRight: '6px' }} />
          时间轴编辑
          {currentSession && currentSession.segments.length > 0 && (
            <Tag color="green" style={{ marginLeft: '8px' }}>
              {currentSession.segments.length}
            </Tag>
          )}
        </span>
      ),
      children: renderEditorTab(),
    })
  }

  return (
    <>
      <Content style={{ padding: '24px', background: '#ffffff' }}>
        {/* 项目头部 */}
        <div style={{ marginBottom: '24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <Button 
              type="link" 
              icon={<ArrowLeftOutlined />} 
              onClick={() => navigate('/')}
              style={{ padding: 0, marginBottom: '8px' }}
            >
              返回项目列表
            </Button>
            <Title level={2} style={{ margin: 0 }}>
              {currentProject.name}
            </Title>
          </div>
          
          <Space>
            {currentProject.status === 'pending' && (
              <Button
                type="primary"
                onClick={handleStartProcessing}
                loading={statusLoading}
              >
                开始处理
              </Button>
            )}
            <Button
              onClick={() => {
                console.log('🔄 手动刷新项目数据')
                loadProject()
              }}
            >
              刷新
            </Button>
            <Button
              type="primary"
              onClick={() => {
                navigate(`/project/${currentProject.id}/ai`)
              }}
              style={{
                backgroundColor: '#1890ff',
                borderColor: '#1890ff',
                fontWeight: 'bold',
                marginLeft: '10px'
              }}
            >
              AI 响应详情
            </Button>
          </Space>
        </div>

        {/* 标签页内容 */}
        <Tabs
          activeKey={activeTab}
          onChange={(key) => setActiveTab(key as 'clips' | 'editor')}
          items={tabItems}
          size="large"
          style={{
            '--ant-tabs-tab-active-color': '#1890ff',
          } as React.CSSProperties}
        />

        {/* 选择切片模态框 */}
        <SelectClipsModal
          visible={selectClipsModalVisible}
          clips={currentProject.clips || []}
          projectId={currentProject.id}
          selectedClipIds={selectedClipIdsForAdd}
          onCancel={() => setSelectClipsModalVisible(false)}
          onConfirm={handleConfirmAddClips}
        />
      </Content>
    </>
  )
}

export default ProjectDetailPage
