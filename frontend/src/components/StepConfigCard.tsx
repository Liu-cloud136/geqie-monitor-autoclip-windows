import React, { useState, useEffect } from 'react'
import { 
  Card, Form, Input, Button, Space, Select, Switch, Slider, 
  Typography, Row, Col, Alert, message, Divider, Popconfirm, 
  Tooltip, Collapse, Modal, Tag
} from 'antd'
import {
  SaveOutlined,
  ReloadOutlined,
  InfoCircleOutlined,
  EyeOutlined,
  EyeInvisibleOutlined,
  DeleteOutlined,
  CopyOutlined,
  ThunderboltOutlined,
  ClockCircleOutlined
} from '@ant-design/icons'
import { stepConfigApi, StepConfig, StepConfigUpdateRequest } from '../services/stepConfigApi'
import { settingsApi } from '../services/api'

const { Text, Title } = Typography
const { Panel } = Collapse
const { Option } = Select

interface StepConfigCardProps {
  stepType: string
  stepName: string
  stepDescription: string
  config: StepConfig
  onConfigChange: (stepType: string, config: StepConfigUpdateRequest) => void
  onReset: (stepType: string) => void
  onRefreshProviders?: () => void
  providers: Array<{ value: string; display_name: string; default_base_url?: string; default_model?: string; api_format?: string }>
  requireAIConfig?: boolean
}

const StepConfigCard: React.FC<StepConfigCardProps> = ({
  stepType,
  stepName,
  stepDescription,
  config,
  onConfigChange,
  onReset,
  onRefreshProviders,
  providers,
  requireAIConfig = true
}) => {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [models, setModels] = useState<Array<{ id: string; display_name: string }>>([])
  const [refreshingModels, setRefreshingModels] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [showCustomPrompt, setShowCustomPrompt] = useState(false)
  const [showCustomProviderConfig, setShowCustomProviderConfig] = useState(false)
  const [customProviderConfig, setCustomProviderConfig] = useState({
    api_key: '',
    base_url: '',
    models_url: ''
  })
  const [defaultPrompt, setDefaultPrompt] = useState<string>('')
  const [showPromptModal, setShowPromptModal] = useState(false)
  const [customParamsText, setCustomParamsText] = useState<string>('')
  const [testingResponseTime, setTestingResponseTime] = useState(false)
  const [responseTimeResult, setResponseTimeResult] = useState<{
    success: boolean
    response_time: number | null
    model?: string
    provider?: string
    reply?: string
    error?: string
  } | null>(null)

  // 初始化表单
  useEffect(() => {
    form.setFieldsValue({
      enabled: config.enabled,
      provider: config.provider,
      model: config.model,
      temperature: config.temperature,
      top_p: config.top_p,
      max_tokens: config.max_tokens,
      timeout: config.timeout,
      custom_prompt: config.custom_prompt || ''
    })
    // 初始化 custom_params 文本
    if (config.custom_params && Object.keys(config.custom_params).length > 0) {
      setCustomParamsText(JSON.stringify(config.custom_params, null, 2))
    } else {
      setCustomParamsText('')
    }
  }, [config, form])

  // 加载默认提示词
  useEffect(() => {
    const loadDefaultPrompt = async () => {
      if (!requireAIConfig) return
      try {
        const prompt = await stepConfigApi.getStepPrompt(stepType)
        if (prompt) {
          setDefaultPrompt(prompt)
        }
      } catch (error) {
        console.error('加载提示词失败:', error)
      }
    }
    loadDefaultPrompt()
  }, [stepType, requireAIConfig])

  // 当提供商改变时，加载模型列表
  const handleProviderChange = async (provider: string) => {
    if (!provider) return
    
    // 如果是自定义提供商，显示配置界面
    if (provider === 'custom') {
      setShowCustomProviderConfig(true)
      setModels([])
      return
    } else {
      setShowCustomProviderConfig(false)
    }
    
    setRefreshingModels(true)
    try {
      const modelsList = await stepConfigApi.getAvailableModels(provider)
      setModels(modelsList)
      
      // 如果当前模型不在新提供商的模型列表中，选择第一个可用的模型
      if (modelsList.length > 0) {
        const currentModel = form.getFieldValue('model')
        const modelExists = modelsList.some(m => m.id === currentModel)
        if (!modelExists) {
          form.setFieldsValue({ model: modelsList[0].id })
        }
      }
    } catch (error) {
      console.error('加载模型列表失败:', error)
      message.error('加载模型列表失败')
    } finally {
      setRefreshingModels(false)
    }
  }

  // 保存自定义提供商配置
  const handleSaveCustomProvider = async () => {
    const { api_key, base_url, models_url } = customProviderConfig
    
    if (!api_key || !base_url) {
      message.error('请填写 API 密钥和 API 地址')
      return
    }
    
    setLoading(true)
    try {
      // 生成唯一的提供商ID
      const providerId = `custom-${Date.now()}`
      
      // 调用后端API注册自定义提供商
      const result = await settingsApi.registerCustomProvider(
        providerId,
        api_key,
        base_url,
        'openai', // 默认使用 OpenAI 兼容格式
        'custom-model'
      )
      
      if (result.success) {
        message.success(result.message || '自定义提供商配置已保存')
        setShowCustomProviderConfig(false)
        
        // 刷新提供商列表
        if (onRefreshProviders) {
          await onRefreshProviders()
        }
        
        // 设置表单字段
        form.setFieldsValue({ provider: providerId })
        
        // 更新模型列表
        if (result.data && result.data.models && result.data.models.length > 0) {
          setModels(result.data.models)
          // 设置第一个模型为默认模型
          form.setFieldsValue({ model: result.data.models[0].id })
        } else {
          // 如果没有获取到模型列表，尝试刷新获取
          try {
            const modelsList = await stepConfigApi.getAvailableModels(providerId)
            setModels(modelsList)
            if (modelsList.length > 0) {
              form.setFieldsValue({ model: modelsList[0].id })
            } else {
              setModels([{ id: 'custom-model', display_name: '自定义模型' }])
              form.setFieldsValue({ model: 'custom-model' })
            }
          } catch (error) {
            console.error('获取模型列表失败:', error)
            setModels([{ id: 'custom-model', display_name: '自定义模型' }])
            form.setFieldsValue({ model: 'custom-model' })
          }
        }
        
        // 触发表单提交以保存配置
        form.submit()
      } else {
        message.error(result.data?.error || '保存自定义提供商配置失败')
      }
    } catch (error: any) {
      console.error('保存自定义提供商配置失败:', error)
      const errorMsg = error?.response?.data?.detail || error?.message || '保存自定义提供商配置失败'
      message.error(errorMsg)
    } finally {
      setLoading(false)
    }
  }

  // 处理表单提交
  const handleSubmit = (values: any) => {
    // 解析 custom_params
    let customParams: Record<string, unknown> = {}
    if (customParamsText.trim()) {
      try {
        customParams = JSON.parse(customParamsText.trim())
      } catch (e) {
        message.error('自定义参数格式错误，请输入有效的 JSON')
        return
      }
    }
    
    const updateData: StepConfigUpdateRequest = {
      enabled: values.enabled,
      provider: values.provider,
      model: values.model,
      temperature: values.temperature,
      top_p: values.top_p,
      max_tokens: values.max_tokens,
      timeout: values.timeout,
      custom_prompt: values.custom_prompt?.trim() || null,
      custom_params: Object.keys(customParams).length > 0 ? customParams : undefined
    }
    
    onConfigChange(stepType, updateData)
  }

  // 刷新模型列表
  const handleRefreshModels = async () => {
    const provider = form.getFieldValue('provider')
    if (!provider) {
      message.warning('请先选择提供商')
      return
    }
    
    await handleProviderChange(provider)
  }

  // 复制配置
  const handleCopyConfig = () => {
    const configStr = JSON.stringify(config, null, 2)
    navigator.clipboard.writeText(configStr)
    message.success('配置已复制到剪贴板')
  }

  // 测试模型响应时间
  const handleTestResponseTime = async () => {
    setTestingResponseTime(true)
    setResponseTimeResult(null)
    try {
      const result = await stepConfigApi.testResponseTime(stepType)
      setResponseTimeResult(result)
      if (result.success) {
        message.success(`响应时间: ${result.response_time}ms`)
      } else {
        message.error(result.error || '测试失败')
      }
    } catch (error: any) {
      console.error('测试响应时间失败:', error)
      const errorMsg = error?.response?.data?.detail || error?.message || '测试响应时间失败'
      message.error(errorMsg)
      setResponseTimeResult({
        success: false,
        response_time: null,
        error: errorMsg
      })
    } finally {
      setTestingResponseTime(false)
    }
  }

  return (
    <Card
      size="small"
      extra={
        requireAIConfig ? (
          <Space>
            <Button
              type="link"
              icon={<CopyOutlined />}
              onClick={handleCopyConfig}
              size="small"
            >
              复制配置
            </Button>
            <Popconfirm
              title="确定要重置此步骤的配置吗？"
              onConfirm={() => onReset(stepType)}
              okText="确定"
              cancelText="取消"
            >
              <Button
                type="link"
                icon={<ReloadOutlined />}
                danger
                size="small"
              >
                重置
              </Button>
            </Popconfirm>
          </Space>
        ) : null
      }
      style={{ marginBottom: 16 }}
      className="step-config-card"
    >
      <Text type="secondary" style={{ marginBottom: 16, display: 'block' }}>
        {stepDescription}
      </Text>

      <Form
        form={form}
        layout="vertical"
        onFinish={handleSubmit}
        initialValues={config}
      >
        <Row gutter={16}>
          <Col span={24}>
            <Form.Item
              name="enabled"
              label="启用状态"
              valuePropName="checked"
            >
              <Switch
                checkedChildren="启用"
                unCheckedChildren="禁用"
                onChange={(checked) => {
                  form.setFieldsValue({ enabled: checked })
                  form.submit()
                }}
              />
            </Form.Item>
          </Col>
        </Row>

        {requireAIConfig && (
          <>
            <Divider orientation="left" plain>基础配置</Divider>

            <Row gutter={16}>
              <Col span={12}>
                <Form.Item
                  name="provider"
                  label="AI提供商"
                  rules={[{ required: true, message: '请选择AI提供商' }]}
                >
                  <Select
                    placeholder="选择AI提供商"
                    onChange={handleProviderChange}
                    loading={refreshingModels}
                  >
                    {providers.map(provider => (
                      <Option key={provider.value} value={provider.value}>
                        {provider.display_name}
                      </Option>
                    ))}
                  </Select>
                </Form.Item>
              </Col>
              
              <Col span={12}>
                <Form.Item
                  name="model"
                  label="模型"
                  rules={[{ required: true, message: '请选择模型' }]}
                  extra={
                    <Space>
                      <Button
                        type="link"
                        icon={<ReloadOutlined />}
                        onClick={handleRefreshModels}
                        loading={refreshingModels}
                        size="small"
                      >
                        刷新模型
                      </Button>
                    </Space>
                  }
                >
                  <Select
                    placeholder={
                      models.length > 0 
                        ? '选择模型'
                        : '请先选择提供商'
                    }
                    showSearch
                    filterOption={(input, option) => {
                      const optionValue = option?.value as string
                      const model = models.find(m => m.id === optionValue)
                      const displayText = model?.display_name || model?.id || ''
                      return displayText.toLowerCase().includes(input.toLowerCase())
                    }}
                  >
                    {models.map(model => (
                      <Option key={model.id} value={model.id}>
                        {model.display_name || model.id}
                      </Option>
                    ))}
                  </Select>
                </Form.Item>
              </Col>
            </Row>

            {showCustomProviderConfig && (
              <Alert
                message="自定义提供商配置"
                description={
                  <div style={{ marginTop: 16 }}>
                    <Form layout="vertical">
                      <Form.Item
                        label="API 密钥"
                        required
                      >
                        <Input.Password
                          placeholder="输入 API 密钥"
                          value={customProviderConfig.api_key}
                          onChange={(e) => setCustomProviderConfig({
                            ...customProviderConfig,
                            api_key: e.target.value
                          })}
                        />
                      </Form.Item>
                      <Form.Item
                        label="API 地址"
                        required
                        extra="API 的 Base URL，例如: https://api.example.com/v1"
                      >
                        <Input
                          placeholder="输入 API 地址"
                          value={customProviderConfig.base_url}
                          onChange={(e) => setCustomProviderConfig({
                            ...customProviderConfig,
                            base_url: e.target.value
                          })}
                        />
                      </Form.Item>
                      <Form.Item
                        label="模型获取地址"
                        extra="可选，用于获取可用模型列表的 API 地址"
                      >
                        <Input
                          placeholder="输入模型获取地址（可选）"
                          value={customProviderConfig.models_url}
                          onChange={(e) => setCustomProviderConfig({
                            ...customProviderConfig,
                            models_url: e.target.value
                          })}
                        />
                      </Form.Item>
                      <Form.Item>
                        <Space>
                          <Button
                            type="primary"
                            onClick={handleSaveCustomProvider}
                          >
                            保存配置
                          </Button>
                          <Button
                            onClick={() => setShowCustomProviderConfig(false)}
                          >
                            取消
                          </Button>
                        </Space>
                      </Form.Item>
                    </Form>
                  </div>
                }
                type="info"
                showIcon
                style={{ marginBottom: 16 }}
              />
            )}

            <Divider orientation="left" plain>参数配置</Divider>

            <Row gutter={16}>
              <Col span={12}>
                <Form.Item
                  name="temperature"
                  label={
                    <Space>
                      <Text>温度 (Temperature)</Text>
                      <Tooltip title="控制输出的随机性，值越高输出越随机">
                        <InfoCircleOutlined />
                      </Tooltip>
                    </Space>
                  }
                >
                  <Slider
                    min={0}
                    max={2}
                    step={0.1}
                    marks={{
                      0: '0',
                      0.5: '0.5',
                      1.0: '1.0',
                      1.5: '1.5',
                      2.0: '2.0'
                    }}
                    tooltip={{
                      formatter: (value) => value?.toFixed(1)
                    }}
                  />
                </Form.Item>
              </Col>
              
              <Col span={12}>
                <Form.Item
                  name="top_p"
                  label={
                    <Space>
                      <Text>Top P</Text>
                      <Tooltip title="控制采样的随机性，值越小输出越稳定">
                        <InfoCircleOutlined />
                      </Tooltip>
                    </Space>
                  }
                >
                  <Slider
                    min={0}
                    max={1}
                    step={0.05}
                    marks={{
                      0: '0',
                      0.25: '0.25',
                      0.5: '0.5',
                      0.75: '0.75',
                      1.0: '1.0'
                    }}
                    tooltip={{
                      formatter: (value) => value?.toFixed(2)
                    }}
                  />
                </Form.Item>
              </Col>
            </Row>

            <Row gutter={16}>
              <Col span={12}>
                <Form.Item
                  name="max_tokens"
                  label="最大Token数"
                  tooltip="控制生成内容的长度"
                >
                  <Input
                    type="number"
                    min={100}
                    max={32768}
                    step={100}
                    addonAfter="tokens"
                  />
                </Form.Item>
              </Col>
              
              <Col span={12}>
                <Form.Item
                  name="timeout"
                  label="超时时间"
                  tooltip="API调用的超时时间（秒）"
                >
                  <Input
                    type="number"
                    min={10}
                    max={1800}
                    step={10}
                    addonAfter="秒"
                  />
                </Form.Item>
              </Col>
            </Row>

            <Form.Item>
              <Space>
                <Button
                  type="primary"
                  icon={<SaveOutlined />}
                  onClick={() => form.submit()}
                  loading={loading}
                >
                  保存配置
                </Button>
                <Button
                  icon={<ThunderboltOutlined />}
                  onClick={handleTestResponseTime}
                  loading={testingResponseTime}
                >
                  检测响应时间
                </Button>
                <Button
                  type="link"
                  onClick={() => setShowAdvanced(!showAdvanced)}
                >
                  {showAdvanced ? '收起高级选项' : '显示高级选项'}
                </Button>
              </Space>
            </Form.Item>

            {responseTimeResult && (
              <Alert
                message={responseTimeResult.success ? '模型响应测试成功' : '模型响应测试失败'}
                description={
                  responseTimeResult.success ? (
                    <div>
                      <p><ClockCircleOutlined /> 响应时间: <Tag color="green">{responseTimeResult.response_time} ms</Tag></p>
                      <p>模型: {responseTimeResult.model}</p>
                      {responseTimeResult.reply && <p>回复: {responseTimeResult.reply}</p>}
                    </div>
                  ) : (
                    <div>
                      <p>错误: {responseTimeResult.error}</p>
                    </div>
                  )
                }
                type={responseTimeResult.success ? 'success' : 'error'}
                showIcon
                closable
                onClose={() => setResponseTimeResult(null)}
                style={{ marginBottom: 16 }}
              />
            )}

            {showAdvanced && (
              <div style={{ marginTop: 16 }}>
                <Form.Item
                  name="custom_prompt"
                  label={
                    <Space>
                      <Text>自定义提示词</Text>
                      <Tooltip title="可选的，用于覆盖默认提示词。以 PREPEND: 开头则前置，以 APPEND: 开头则追加，否则替换">
                        <InfoCircleOutlined />
                      </Tooltip>
                    </Space>
                  }
                  extra={
                    defaultPrompt && (
                      <Button
                        type="link"
                        size="small"
                        icon={<EyeOutlined />}
                        onClick={() => setShowPromptModal(true)}
                        style={{ padding: 0 }}
                      >
                        查看默认提示词
                      </Button>
                    )
                  }
                >
                  <Input.TextArea
                    rows={4}
                    placeholder="输入自定义提示词，留空则使用默认提示词。以 PREPEND: 开头前置，APPEND: 开头追加，否则替换"
                  />
                </Form.Item>
                
                <Form.Item
                  label={
                    <Space>
                      <Text>自定义参数</Text>
                      <Tooltip title="可选的，JSON格式的额外API参数，如 {&quot;frequency_penalty&quot;: 0.5}">
                        <InfoCircleOutlined />
                      </Tooltip>
                    </Space>
                  }
                >
                  <Input.TextArea
                    rows={3}
                    value={customParamsText}
                    onChange={(e) => setCustomParamsText(e.target.value)}
                    placeholder='JSON格式，例如: {"frequency_penalty": 0.5, "presence_penalty": 0.3}'
                    style={{ fontFamily: 'monospace' }}
                  />
                </Form.Item>
              </div>
            )}
          </>
        )}
      </Form>

      {/* 默认提示词查看模态框 */}
      <Modal
        title="默认提示词"
        open={showPromptModal}
        onCancel={() => setShowPromptModal(false)}
        footer={[
          <Button key="close" onClick={() => setShowPromptModal(false)}>
            关闭
          </Button>,
          <Button 
            key="copy" 
            type="primary" 
            icon={<CopyOutlined />}
            onClick={() => {
              navigator.clipboard.writeText(defaultPrompt)
              message.success('提示词已复制到剪贴板')
            }}
          >
            复制到自定义
          </Button>
        ]}
        width={800}
      >
        <Input.TextArea
          value={defaultPrompt}
          rows={20}
          readOnly
          style={{ fontFamily: 'monospace' }}
        />
      </Modal>
    </Card>
  )
}

export default StepConfigCard