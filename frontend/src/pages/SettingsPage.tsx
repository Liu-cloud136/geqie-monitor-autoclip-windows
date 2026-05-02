import React, { useState, useEffect } from 'react'
import {
  Layout, Card, Typography, Tabs, Button, Space, message,
  Row, Col, Tag, Divider, Spin, Alert, Form
} from 'antd'
import {
  SettingOutlined,
  RobotOutlined,
  ControlOutlined,
  CodeSandboxOutlined
} from '@ant-design/icons'
import StepConfigPage from './StepConfigPage'
import SystemConfigPage from './SystemConfigPage'
import { settingsApi } from '../services/api'

const { Content } = Layout
const { Title, Text } = Typography

interface LLMProviderSettings {
  provider?: string
  display_name?: string
  model?: string
  [key: string]: unknown
}

const SettingsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState('llm')

  const tabItems = [
    {
      key: 'llm',
      label: (
        <Space>
          <RobotOutlined />
          <span>LLM配置</span>
        </Space>
      ),
      children: (
        <LLMConfigSection />
      )
    },
    {
      key: 'steps',
      label: (
        <Space>
          <CodeSandboxOutlined />
          <span>步骤配置</span>
          <Tag color="blue">每个步骤独立</Tag>
        </Space>
      ),
      children: (
        <StepConfigPage />
      )
    },
    {
      key: 'system',
      label: (
        <Space>
          <ControlOutlined />
          <span>系统配置</span>
        </Space>
      ),
      children: (
        <SystemConfigPage />
      )
    }
  ]

  return (
    <Layout style={{ minHeight: '100vh', background: '#f0f2f5' }}>
      <Content style={{ padding: '24px' }}>
        <div style={{ maxWidth: 1400, margin: '0 auto' }}>
          <Card style={{ marginBottom: 24 }}>
            <Row justify="space-between" align="middle">
              <Col>
                <Title level={3}>
                  <SettingOutlined style={{ marginRight: 8 }} />
                  设置中心
                </Title>
                <Text type="secondary">
                  配置LLM模型、处理步骤和系统参数
                </Text>
              </Col>
              <Col>
                <Space>
                  <ConfigStatus />
                </Space>
              </Col>
            </Row>
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

const ConfigStatus: React.FC = () => {
  const [loading, setLoading] = useState(false)

  const handleCheckConfig = async () => {
    setLoading(true)
    try {
      const settings = (await settingsApi.getCurrentProvider()) as unknown as LLMProviderSettings
      if (settings && settings.provider) {
        message.success(`当前配置: ${settings.display_name || settings.provider} - ${settings.model || '默认模型'}`)
      } else {
        message.warning('尚未配置LLM提供商')
      }
    } catch (error) {
      console.error('检查配置失败:', error)
      message.error('检查配置失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Button
      icon={<RobotOutlined />}
      onClick={handleCheckConfig}
      loading={loading}
    >
      检查当前配置
    </Button>
  )
}

const LLMConfigSection: React.FC = () => {
  const [loading, setLoading] = useState(false)
  const [settings, setSettings] = useState<Record<string, unknown> | null>(null)
  const [form] = Form.useForm()

  useEffect(() => {
    loadSettings()
  }, [])

  const loadSettings = async () => {
    setLoading(true)
    try {
      const data = (await settingsApi.getSettings()) as unknown as Record<string, unknown>
      setSettings(data)
      form.setFieldsValue(data)
    } catch (error) {
      console.error('加载设置失败:', error)
      message.error('加载设置失败')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '40px' }}>
        <Spin size="large" />
        <div style={{ marginTop: 16 }}>加载LLM配置...</div>
      </div>
    )
  }

  return (
    <div>
      <Alert
        message="LLM配置说明"
        description={
          <div>
            <p>LLM配置用于控制AI模型的调用参数。您可以在这里配置：</p>
            <ul>
              <li>默认的LLM提供商和模型</li>
              <li>API密钥和连接参数</li>
              <li>温度、Top P等生成参数</li>
            </ul>
            <p>注意：每个处理步骤也可以独立配置LLM参数（在"步骤配置"标签页中）。</p>
          </div>
        }
        type="info"
        showIcon
        style={{ marginBottom: 24 }}
      />

      <Card size="small">
        <div style={{ textAlign: 'center', padding: '20px' }}>
          <Text type="secondary">
            LLM配置已整合到步骤配置中。请点击上方的"步骤配置"标签页，
            在每个步骤的配置卡片中设置LLM提供商和模型参数。
          </Text>
          <Divider />
          <Button
            type="primary"
            icon={<CodeSandboxOutlined />}
            onClick={() => {
              const tab = document.querySelector('[data-node-key="steps"]')
              if (tab) {
                (tab as HTMLElement).click()
              }
            }}
          >
            前往步骤配置
          </Button>
        </div>
      </Card>
    </div>
  )
}

export default SettingsPage
