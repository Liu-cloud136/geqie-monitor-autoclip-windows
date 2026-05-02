/**
 * 项目详情页面
 * 显示项目详情、视频切片列表和时间轴编辑器
 * 
 * 重构说明：
 * - 核心逻辑已拆分到以下模块：
 *   - hooks/useProjectDetail.ts - 项目详情页面的自定义Hook
 *   - components/ClipsTabContent.tsx - 切片列表标签页组件
 *   - components/EditorTabContent.tsx - 时间轴编辑标签页组件
 * - 本文件保持向后兼容，作为统一入口点
 */

import React from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Layout,
  Spin,
  Alert,
  Button,
  Space,
  Typography,
  Tabs,
  Tag
} from 'antd'
import {
  ArrowLeftOutlined,
  UnorderedListOutlined,
  VideoCameraOutlined
} from '@ant-design/icons'

// 导入拆分后的模块
import { useProjectDetail } from '../hooks/useProjectDetail'
import ClipsTabContent from '../components/ClipsTabContent'
import EditorTabContent from '../components/EditorTabContent'
import SelectClipsModal from '../components/SelectClipsModal'

const { Content } = Layout
const { Title, Text } = Typography

/**
 * 项目详情页面组件
 * @returns React组件
 */
const ProjectDetailPage: React.FC = () => {
  const navigate = useNavigate()
  
  // 使用拆分后的自定义Hook
  const {
    currentProject,
    loading,
    error,
    statusLoading,
    sortBy,
    activeTab,
    selectClipsModalVisible,
    selectedClipIdsForAdd,
    currentSession,
    loadProject,
    handleStartProcessing,
    getSortedClips,
    handleOpenSelectClips,
    handleConfirmAddClips,
    setSortBy,
    setActiveTab,
    setSelectClipsModalVisible,
    setSelectedClipIdsForAdd
  } = useProjectDetail()

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
      children: (
        <ClipsTabContent
          currentProject={currentProject}
          sortBy={sortBy}
          setSortBy={setSortBy}
          getSortedClips={getSortedClips}
          handleOpenSelectClips={handleOpenSelectClips}
        />
      ),
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
      children: (
        <EditorTabContent
          currentProject={currentProject}
          handleOpenSelectClips={handleOpenSelectClips}
        />
      ),
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
