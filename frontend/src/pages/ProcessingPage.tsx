/**
 * 处理进度页面
 * 显示视频处理的进度状态
 * 
 * 重构说明：
 * - 核心逻辑已拆分到以下模块：
 *   - hooks/useProcessingProgress.ts - 处理进度页面的自定义Hook
 * - 本文件保持向后兼容，作为统一入口点
 */

import React from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Layout,
  Card,
  Progress,
  Steps,
  Typography,
  Button,
  Alert,
  Space,
  Spin,
} from 'antd'
import { ArrowLeftOutlined } from '@ant-design/icons'

// 导入拆分后的模块
import { useProcessingProgress } from '../hooks/useProcessingProgress'

const { Content } = Layout
const { Title, Text } = Typography
const { Step } = Steps

/**
 * 处理进度页面组件
 * @returns React组件
 */
const ProcessingPage: React.FC = () => {
  const navigate = useNavigate()
  
  // 使用拆分后的自定义Hook
  const {
    currentProject,
    status,
    loading,
    steps,
    getStepStatus,
    getStepIcon
  } = useProcessingProgress()

  if (loading) {
    return (
      <Content style={{ padding: '24px', display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '400px' }}>
        <Spin size="large" tip="加载中..." />
      </Content>
    )
  }

  return (
    <Content style={{ padding: '24px', maxWidth: '1000px', margin: '0 auto' }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Title level={2}>视频处理进度</Title>
          <Button 
            icon={<ArrowLeftOutlined />} 
            onClick={() => navigate('/')}
          >
            返回首页
          </Button>
        </div>

        {currentProject && (
          <Card>
            <Title level={4}>{currentProject.name}</Title>
            <Text type="secondary">项目ID: {currentProject.id}</Text>
          </Card>
        )}

        {status?.status === 'error' && (
          <Alert
            message="处理失败"
            description={
              <div>
                <p>{status.error_message || '处理过程中发生未知错误'}</p>
                <p style={{ marginTop: '8px', fontSize: '12px', color: '#666' }}>
                  可能的原因：文件格式不支持、文件损坏、网络问题或服务器错误
                </p>
              </div>
            }
            type="error"
            showIcon
            action={
              <Space>
                <Button size="small" onClick={() => window.location.reload()}>
                  刷新页面
                </Button>
                <Button size="small" onClick={() => navigate('/')}>
                  返回首页
                </Button>
              </Space>
            }
          />
        )}

        {status && status.status === 'processing' && (
          <Card title="处理进度">
            <Space direction="vertical" size="large" style={{ width: '100%' }}>
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <Text strong>总体进度</Text>
                  <Text>{Math.round(status.progress)}%</Text>
                </div>
                <Progress
                  percent={status.progress}
                  // @ts-ignore
                  status={status.status === 'completed' ? 'success' : 'active'}
                  strokeColor={{
                    '0%': '#108ee9',
                    '100%': '#87d068',
                  }}
                />
              </div>

              <div>
                <Text strong>当前步骤: </Text>
                <Text>{status.step_name}</Text>
              </div>

              <Steps
                direction="vertical"
                current={status.current_step}
                // @ts-ignore
                status={status.status === 'error' ? 'error' : 'process'}
              >
                {steps.map((step, index) => (
                  <Step
                    key={index}
                    title={step.title}
                    description={step.description}
                    status={getStepStatus(index)}
                    icon={getStepIcon(index)}
                  />
                ))}
              </Steps>
            </Space>
          </Card>
        )}

        {status?.status === 'completed' && (
          <Alert
            message="处理完成"
            description="视频已成功处理完成，正在跳转到项目详情页..."
            type="success"
            showIcon
          />
        )}
      </Space>
    </Content>
  )
}

export default ProcessingPage
