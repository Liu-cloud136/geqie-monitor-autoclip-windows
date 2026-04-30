import React, { useState, useEffect } from 'react'
import { Layout, Card, Button, Typography, Space, Alert, Row, Col, Tabs, message, Popconfirm, Spin } from 'antd'
import {
  SettingOutlined,
  SaveOutlined,
  ReloadOutlined,
  CopyOutlined,
  SyncOutlined,
  CheckCircleOutlined,
  WarningOutlined
} from '@ant-design/icons'
import StepConfigCard from '../components/StepConfigCard'
import { stepConfigApi, StepConfig, StepConfigUpdateRequest, StepTypeInfo } from '../services/stepConfigApi'
import './StepConfigPage.css'

const { Content } = Layout
const { Title, Text } = Typography

const StepConfigPage: React.FC = () => {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [stepConfigs, setStepConfigs] = useState<Record<string, StepConfig>>({})
  const [stepTypes, setStepTypes] = useState<StepTypeInfo[]>([])
  const [providers, setProviders] = useState<Array<{ value: string; display_name: string }>>([])
  const [activeTab, setActiveTab] = useState('step1_outline')

  // 加载数据
  const loadData = async () => {
    setLoading(true)
    try {
      const [configsData, stepTypesData, providersData] = await Promise.all([
        stepConfigApi.getAllStepConfigs(),
        stepConfigApi.getStepTypes(),
        stepConfigApi.getAvailableProviders()
      ])
      
      console.log('Loaded configs:', configsData)
      console.log('Loaded stepTypes:', stepTypesData)
      console.log('Loaded providers:', providersData)
      
      setStepConfigs(configsData || {})
      setStepTypes(stepTypesData || [])
      setProviders(providersData || [])
    } catch (error) {
      console.error('加载数据失败:', error)
      message.error('加载数据失败')
    } finally {
      setLoading(false)
    }
  }

  // 初始化
  useEffect(() => {
    loadData()
  }, [])

  // 处理步骤配置变更
  const handleStepConfigChange = async (stepType: string, config: StepConfigUpdateRequest) => {
    setSaving(true)
    try {
      await stepConfigApi.updateStepConfig(stepType, config)
      
      // 更新本地状态
      setStepConfigs(prev => ({
        ...prev,
        [stepType]: {
          ...prev[stepType],
          ...config
        }
      }))
      
      message.success('配置已保存')
    } catch (error) {
      console.error('保存配置失败:', error)
      message.error('保存配置失败')
    } finally {
      setSaving(false)
    }
  }

  // 重置步骤配置
  const handleResetStep = async (stepType: string) => {
    try {
      await stepConfigApi.resetStepConfig(stepType)
      
      // 重新加载配置
      const newConfig = await stepConfigApi.getStepConfig(stepType)
      setStepConfigs(prev => ({
        ...prev,
        [stepType]: newConfig
      }))
      
      message.success('配置已重置')
    } catch (error) {
      console.error('重置配置失败:', error)
      message.error('重置配置失败')
    }
  }

  // 重置所有配置
  const handleResetAll = async () => {
    try {
      await stepConfigApi.resetAllStepConfigs()
      await loadData()
      message.success('所有配置已重置')
    } catch (error) {
      console.error('重置所有配置失败:', error)
      message.error('重置所有配置失败')
    }
  }

  // 批量保存配置
  const handleSaveAll = async () => {
    setSaving(true)
    try {
      // 这里可以添加批量保存逻辑
      message.success('所有配置已保存')
    } catch (error) {
      console.error('保存所有配置失败:', error)
      message.error('保存所有配置失败')
    } finally {
      setSaving(false)
    }
  }

  // 导出配置
  const handleExportConfig = () => {
    const configStr = JSON.stringify(stepConfigs, null, 2)
    const blob = new Blob([configStr], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `step_configs_${new Date().toISOString().split('T')[0]}.json`
    a.click()
    URL.revokeObjectURL(url)
    message.success('配置已导出')
  }

  // 获取步骤状态统计
  const getStatusStats = () => {
    const enabledSteps = Object.values(stepConfigs).filter(config => config.enabled).length
    const totalSteps = Object.keys(stepConfigs).length
    
    return {
      enabled: enabledSteps,
      total: totalSteps,
      disabled: totalSteps - enabledSteps
    }
  }

  const stats = getStatusStats()

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '100px' }}>
        <Spin size="large" />
        <Text style={{ display: 'block', marginTop: 16 }}>加载步骤配置...</Text>
      </div>
    )
  }

  return (
    <Layout style={{ minHeight: '100vh', background: '#f0f2f5' }}>
      <Content style={{ padding: '24px' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto' }}>
          {/* 标题和操作区域 */}
          <Card style={{ marginBottom: 24 }}>
            <Row justify="space-between" align="middle">
              <Col>
                <Title level={3}>
                  <SettingOutlined /> 步骤配置管理
                </Title>
                <Text type="secondary">
                  为每个处理步骤配置独立的AI模型和参数
                </Text>
              </Col>
              <Col>
                <Space>
                  <Button
                    icon={<CopyOutlined />}
                    onClick={handleExportConfig}
                  >
                    导出配置
                  </Button>
                  <Popconfirm
                    title="确定要重置所有步骤的配置吗？"
                    onConfirm={handleResetAll}
                    okText="确定"
                    cancelText="取消"
                  >
                    <Button
                      icon={<ReloadOutlined />}
                      danger
                    >
                      重置所有
                    </Button>
                  </Popconfirm>
                  <Button
                    type="primary"
                    icon={<SaveOutlined />}
                    onClick={handleSaveAll}
                    loading={saving}
                  >
                    保存所有
                  </Button>
                </Space>
              </Col>
            </Row>
          </Card>

          {/* 状态概览 */}
          <Card style={{ marginBottom: 24 }}>
            <Row gutter={16}>
              <Col span={8}>
                <Card size="small" style={{ textAlign: 'center' }}>
                  <Title level={1} style={{ margin: 0, color: '#52c41a' }}>
                    {stats.enabled}
                  </Title>
                  <Text type="secondary">已启用的步骤</Text>
                </Card>
              </Col>
              <Col span={8}>
                <Card size="small" style={{ textAlign: 'center' }}>
                  <Title level={1} style={{ margin: 0, color: '#faad14' }}>
                    {stats.disabled}
                  </Title>
                  <Text type="secondary">已禁用的步骤</Text>
                </Card>
              </Col>
              <Col span={8}>
                <Card size="small" style={{ textAlign: 'center' }}>
                  <Title level={1} style={{ margin: 0, color: '#1890ff' }}>
                    {stats.total}
                  </Title>
                  <Text type="secondary">总步骤数</Text>
                </Card>
              </Col>
            </Row>
          </Card>

          {/* 步骤配置卡片 */}
          <Card>
            <Tabs
              activeKey={activeTab}
              onChange={setActiveTab}
              type="card"
              size="large"
              items={stepTypes
                .filter(stepType => stepType.value !== 'step6_clustering')
                .map(stepType => {
                const config = stepConfigs[stepType.value]
                if (!config) return null
                
                return {
                  key: stepType.value,
                  label: (
                    <Space>
                      {config.enabled ? (
                        <CheckCircleOutlined style={{ color: '#52c41a' }} />
                      ) : (
                        <WarningOutlined style={{ color: '#faad14' }} />
                      )}
                      {stepType.display_name}
                    </Space>
                  ),
                  children: (
                    <StepConfigCard
                      stepType={stepType.value}
                      stepName={stepType.display_name}
                      stepDescription={stepType.description}
                      config={config}
                      onConfigChange={handleStepConfigChange}
                      onReset={handleResetStep}
                      onRefreshProviders={loadData}
                      providers={providers}
                      requireAIConfig={stepType.require_ai_config !== false}
                    />
                  )
                }
              }).filter(Boolean)}
            />
          </Card>
        </div>
      </Content>
    </Layout>
  )
}

export default StepConfigPage