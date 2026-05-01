import React, { useState } from 'react'
import {
  Layout, Card, Typography, Tabs, Button, Space, message, Popconfirm, Spin
} from 'antd'
import {
  SaveOutlined, ReloadOutlined, SettingOutlined,
  VideoCameraOutlined, FileTextOutlined, BugOutlined,
  SafetyOutlined
} from '@ant-design/icons'
import SystemConfigCard from '../components/SystemConfigCard'
import { systemConfigApi } from '../services/systemConfigApi'

const { Content } = Layout
const { Title, Text } = Typography

const SystemConfigPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState('processing')
  const [resettingAll, setResettingAll] = useState(false)

  const handleResetAll = async () => {
    setResettingAll(true)
    try {
      await systemConfigApi.resetAllConfigs()
      message.success('所有系统配置已重置为默认值')
    } catch (error) {
      console.error('重置所有配置失败:', error)
      message.error('重置所有配置失败')
    } finally {
      setResettingAll(false)
    }
  }

  const tabItems = [
    {
      key: 'processing',
      label: (
        <Space>
          <SettingOutlined />
          <span>处理参数</span>
        </Space>
      ),
      children: (
        <SystemConfigCard
          category="processing"
          title="处理参数"
          icon={<SettingOutlined />}
        />
      )
    },
    {
      key: 'video',
      label: (
        <Space>
          <VideoCameraOutlined />
          <span>视频处理</span>
        </Space>
      ),
      children: (
        <SystemConfigCard
          category="video"
          title="视频处理"
          icon={<VideoCameraOutlined />}
        />
      )
    },
    {
      key: 'topic',
      label: (
        <Space>
          <FileTextOutlined />
          <span>话题提取</span>
        </Space>
      ),
      children: (
        <SystemConfigCard
          category="topic"
          title="话题提取"
          icon={<FileTextOutlined />}
        />
      )
    },
    {
      key: 'logging',
      label: (
        <Space>
          <BugOutlined />
          <span>日志配置</span>
        </Space>
      ),
      children: (
        <SystemConfigCard
          category="logging"
          title="日志配置"
          icon={<BugOutlined />}
        />
      )
    },
    {
      key: 'advanced',
      label: (
        <Space>
          <SafetyOutlined />
          <span>高级配置</span>
        </Space>
      ),
      children: (
        <SystemConfigCard
          category="advanced"
          title="高级配置"
          icon={<SafetyOutlined />}
        />
      )
    }
  ]

  return (
    <Layout style={{ minHeight: '100vh', background: '#f0f2f5' }}>
      <Content style={{ padding: '24px' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto' }}>
          <Card style={{ marginBottom: 24 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <Title level={3}>
                  <SettingOutlined style={{ marginRight: 8 }} />
                  系统配置
                </Title>
                <Text type="secondary">
                  配置视频处理、话题提取、日志等系统参数
                </Text>
              </div>
              <Space>
                <Popconfirm
                  title="确定要重置所有系统配置为默认值吗？"
                  onConfirm={handleResetAll}
                  okText="确定"
                  cancelText="取消"
                >
                  <Button
                    icon={<ReloadOutlined />}
                    danger
                    loading={resettingAll}
                  >
                    重置所有配置
                  </Button>
                </Popconfirm>
              </Space>
            </div>
          </Card>

          <Card>
            <Tabs
              activeKey={activeTab}
              onChange={setActiveTab}
              type="card"
              size="large"
              items={tabItems}
            />
          </Card>
        </div>
      </Content>
    </Layout>
  )
}

export default SystemConfigPage
