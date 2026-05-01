import React, { useState, useEffect } from 'react'
import {
  Card, Form, Input, Button, Space, Switch, Select,
  Typography, Row, Col, Alert, message, Divider, Popconfirm
} from 'antd'
import {
  SaveOutlined, ReloadOutlined, SettingOutlined,
  VideoCameraOutlined, FileTextOutlined, BugOutlined,
  SafetyOutlined
} from '@ant-design/icons'
import {
  systemConfigApi,
  ProcessingConfig,
  VideoConfig,
  TopicConfig,
  LoggingConfig,
  AdvancedConfig
} from '../services/systemConfigApi'

const { Text, Title } = Typography
const { Option } = Select

interface SystemConfigCardProps {
  category: 'processing' | 'video' | 'topic' | 'logging' | 'advanced'
  title: string
  icon: React.ReactNode
}

const categoryConfig = {
  processing: {
    icon: <SettingOutlined />,
    title: '处理参数',
    description: '控制视频处理流程的核心参数'
  },
  video: {
    icon: <VideoCameraOutlined />,
    title: '视频处理',
    description: '视频编码和处理相关配置'
  },
  topic: {
    icon: <FileTextOutlined />,
    title: '话题提取',
    description: '话题检测和提取的控制参数'
  },
  logging: {
    icon: <BugOutlined />,
    title: '日志配置',
    description: '日志输出的级别和格式'
  },
  advanced: {
    icon: <SafetyOutlined />,
    title: '高级配置',
    description: '代理、加密密钥等高级设置'
  }
}

const SystemConfigCard: React.FC<SystemConfigCardProps> = ({ category }) => {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [configInfo, setConfigInfo] = useState<Record<string, string>>({})

  const config = categoryConfig[category]

  useEffect(() => {
    loadConfig()
    loadConfigInfo()
  }, [category])

  const loadConfig = async () => {
    setLoading(true)
    try {
      let data: Record<string, unknown>
      switch (category) {
        case 'processing':
          data = await systemConfigApi.getProcessingConfig() as unknown as Record<string, unknown>
          break
        case 'video':
          data = await systemConfigApi.getVideoConfig() as unknown as Record<string, unknown>
          break
        case 'topic':
          data = await systemConfigApi.getTopicConfig() as unknown as Record<string, unknown>
          break
        case 'logging':
          data = await systemConfigApi.getLoggingConfig() as unknown as Record<string, unknown>
          break
        case 'advanced':
          data = await systemConfigApi.getAdvancedConfig() as unknown as Record<string, unknown>
          break
      }
      form.setFieldsValue(data)
    } catch (error) {
      console.error(`加载${config.title}配置失败:`, error)
      message.error(`加载${config.title}配置失败`)
    } finally {
      setLoading(false)
    }
  }

  const loadConfigInfo = async () => {
    try {
      const info = await systemConfigApi.getConfigInfo()
      if (info.categories[category]) {
        setConfigInfo(info.categories[category].fields)
      }
    } catch (error) {
      console.error('加载配置说明失败:', error)
    }
  }

  const handleSubmit = async (values: Record<string, unknown>) => {
    setSaving(true)
    try {
      let result
      switch (category) {
        case 'processing':
          result = await systemConfigApi.updateProcessingConfig(values as Partial<ProcessingConfig>)
          break
        case 'video':
          result = await systemConfigApi.updateVideoConfig(values as Partial<VideoConfig>)
          break
        case 'topic':
          result = await systemConfigApi.updateTopicConfig(values as Partial<TopicConfig>)
          break
        case 'logging':
          result = await systemConfigApi.updateLoggingConfig(values as Partial<LoggingConfig>)
          break
        case 'advanced':
          result = await systemConfigApi.updateAdvancedConfig(values as Partial<AdvancedConfig>)
          break
      }
      form.setFieldsValue(result.config)
      message.success(`${config.title}配置已保存`)
    } catch (error) {
      console.error(`保存${config.title}配置失败:`, error)
      message.error(`保存${config.title}配置失败`)
    } finally {
      setSaving(false)
    }
  }

  const handleReset = async () => {
    try {
      await systemConfigApi.resetCategoryConfig(category)
      await loadConfig()
      message.success(`${config.title}配置已重置为默认值`)
    } catch (error) {
      console.error(`重置${config.title}配置失败:`, error)
      message.error(`重置${config.title}配置失败`)
    }
  }

  const renderFormFields = () => {
    switch (category) {
      case 'processing':
        return (
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="chunk_size"
                label="文本分块大小"
                extra={configInfo['chunk_size']}
                rules={[{ required: true, message: '请输入文本分块大小' }]}
              >
                <Input
                  type="number"
                  min={100}
                  max={50000}
                  addonAfter="字符"
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="min_score_threshold"
                label="最小评分阈值"
                extra={configInfo['min_score_threshold']}
                rules={[{ required: true, message: '请输入最小评分阈值' }]}
              >
                <Input
                  type="number"
                  min={0}
                  max={100}
                  step={0.1}
                  addonAfter="分"
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="max_clips_per_collection"
                label="每合集最大切片数"
                extra={configInfo['max_clips_per_collection']}
                rules={[{ required: true, message: '请输入最大切片数' }]}
              >
                <Input
                  type="number"
                  min={1}
                  max={20}
                  addonAfter="个"
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="max_retries"
                label="最大重试次数"
                extra={configInfo['max_retries']}
                rules={[{ required: true, message: '请输入最大重试次数' }]}
              >
                <Input
                  type="number"
                  min={0}
                  max={10}
                  addonAfter="次"
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="api_timeout"
                label="API超时时间"
                extra={configInfo['api_timeout']}
                rules={[{ required: true, message: '请输入API超时时间' }]}
              >
                <Input
                  type="number"
                  min={10}
                  max={3600}
                  addonAfter="秒"
                />
              </Form.Item>
            </Col>
          </Row>
        )

      case 'video':
        return (
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="use_stream_copy"
                label="使用流复制"
                valuePropName="checked"
                extra={configInfo['use_stream_copy']}
              >
                <Switch checkedChildren="开启" unCheckedChildren="关闭" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="use_hardware_accel"
                label="使用硬件加速"
                valuePropName="checked"
                extra={configInfo['use_hardware_accel']}
              >
                <Switch checkedChildren="开启" unCheckedChildren="关闭" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="encoder_preset"
                label="编码预设"
                extra={configInfo['encoder_preset']}
              >
                <Select>
                  <Option value="p1">p1 (最快)</Option>
                  <Option value="p2">p2</Option>
                  <Option value="p3">p3</Option>
                  <Option value="p4">p4</Option>
                  <Option value="p5">p5</Option>
                  <Option value="p6">p6 (平衡)</Option>
                  <Option value="p7">p7 (最慢，质量最好)</Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="crf"
                label="视频质量 (CRF)"
                extra={configInfo['crf']}
                rules={[{ required: true, message: '请输入视频质量值' }]}
              >
                <Input
                  type="number"
                  min={0}
                  max={51}
                  addonAfter="(18-28推荐)"
                />
              </Form.Item>
            </Col>
          </Row>
        )

      case 'topic':
        return (
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="min_topic_duration_minutes"
                label="话题最小时长"
                extra={configInfo['min_topic_duration_minutes']}
                rules={[{ required: true, message: '请输入话题最小时长' }]}
              >
                <Input
                  type="number"
                  min={1}
                  max={60}
                  addonAfter="分钟"
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="max_topic_duration_minutes"
                label="话题最大时长"
                extra={configInfo['max_topic_duration_minutes']}
                rules={[{ required: true, message: '请输入话题最大时长' }]}
              >
                <Input
                  type="number"
                  min={1}
                  max={120}
                  addonAfter="分钟"
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="target_topic_duration_minutes"
                label="话题目标时长"
                extra={configInfo['target_topic_duration_minutes']}
                rules={[{ required: true, message: '请输入话题目标时长' }]}
              >
                <Input
                  type="number"
                  min={1}
                  max={60}
                  addonAfter="分钟"
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="min_topics_per_chunk"
                label="每块最少话题数"
                extra={configInfo['min_topics_per_chunk']}
                rules={[{ required: true, message: '请输入最少话题数' }]}
              >
                <Input
                  type="number"
                  min={1}
                  max={20}
                  addonAfter="个"
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="max_topics_per_chunk"
                label="每块最多话题数"
                extra={configInfo['max_topics_per_chunk']}
                rules={[{ required: true, message: '请输入最多话题数' }]}
              >
                <Input
                  type="number"
                  min={1}
                  max={30}
                  addonAfter="个"
                />
              </Form.Item>
            </Col>
          </Row>
        )

      case 'logging':
        return (
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="log_level"
                label="日志级别"
                extra={configInfo['log_level']}
              >
                <Select>
                  <Option value="DEBUG">DEBUG</Option>
                  <Option value="INFO">INFO</Option>
                  <Option value="WARNING">WARNING</Option>
                  <Option value="ERROR">ERROR</Option>
                  <Option value="CRITICAL">CRITICAL</Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={24}>
              <Form.Item
                name="log_format"
                label="日志格式"
                extra={configInfo['log_format']}
              >
                <Input placeholder="例如: %(asctime)s - %(name)s - %(levelname)s - %(message)s" />
              </Form.Item>
            </Col>
          </Row>
        )

      case 'advanced':
        return (
          <Row gutter={16}>
            <Col span={24}>
              <Form.Item
                name="proxy_url"
                label="代理服务器URL"
                extra={configInfo['proxy_url']}
              >
                <Input placeholder="例如: http://127.0.0.1:7890" />
              </Form.Item>
            </Col>
            <Col span={24}>
              <Form.Item
                name="encryption_key"
                label="加密密钥"
                extra={configInfo['encryption_key']}
              >
                <Input.Password placeholder="输入加密密钥" />
              </Form.Item>
            </Col>
            <Col span={24}>
              <Form.Item
                name="bilibili_cookie"
                label="B站Cookie"
                extra={configInfo['bilibili_cookie']}
              >
                <Input.Password placeholder="输入B站Cookie（用于语音识别）" />
              </Form.Item>
            </Col>
          </Row>
        )
    }
  }

  return (
    <Card
      size="small"
      title={
        <Space>
          {config.icon}
          <span>{config.title}</span>
        </Space>
      }
      extra={
        <Space>
          <Popconfirm
            title={`确定要重置${config.title}配置为默认值吗？`}
            onConfirm={handleReset}
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
      }
      style={{ marginBottom: 16 }}
    >
      <Text type="secondary" style={{ marginBottom: 16, display: 'block' }}>
        {config.description}
      </Text>

      <Form
        form={form}
        layout="vertical"
        onFinish={handleSubmit}
        initialValues={{}}
      >
        {renderFormFields()}

        <Divider />

        <Form.Item>
          <Space>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              htmlType="submit"
              loading={saving}
            >
              保存配置
            </Button>
            <Button
              icon={<ReloadOutlined />}
              onClick={loadConfig}
              loading={loading}
            >
              刷新
            </Button>
          </Space>
        </Form.Item>
      </Form>
    </Card>
  )
}

export default SystemConfigCard
