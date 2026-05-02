import React, { useState, useEffect } from 'react'
import { Modal, List, Button, Checkbox, Space, Typography, Tag, Spin, App, Divider } from 'antd'
import { CheckCircleOutlined, ClockCircleOutlined, PlayCircleOutlined, ReloadOutlined } from '@ant-design/icons'
import { projectApi } from '../services/api'

const { Text } = Typography

interface StepInfo {
  step: string
  name: string
  completed: boolean
  file_size: number
  modified_time: number | null
}

interface StepsStatusResponse {
  project_id: string
  project_status: string
  steps: StepInfo[]
  clips_count: number
}

interface RetryStepDialogProps {
  visible: boolean
  projectId: string
  projectName: string
  projectStatus: string
  onClose: () => void
  onRetry: (startStep: string, cleanOutput: boolean) => Promise<void>
}

const RetryStepDialog: React.FC<RetryStepDialogProps> = ({
  visible,
  projectId,
  projectName,
  projectStatus,
  onClose,
  onRetry
}) => {
  const { message } = App.useApp()
  const [loading, setLoading] = useState(false)
  const [stepsStatus, setStepsStatus] = useState<StepsStatusResponse | null>(null)
  const [selectedStep, setSelectedStep] = useState<string | null>(null)
  const [cleanOutput, setCleanOutput] = useState(true)
  const [retrying, setRetrying] = useState(false)

  useEffect(() => {
    if (visible) {
      loadStepsStatus()
    }
  }, [visible, projectId])

  const loadStepsStatus = async () => {
    setLoading(true)
    try {
      const response = await projectApi.getStepsStatus(projectId)
      setStepsStatus(response)
      
      const completedSteps = response.steps.filter(s => s.completed)
      if (completedSteps.length > 0) {
        const lastCompleted = completedSteps[completedSteps.length - 1]
        setSelectedStep(lastCompleted.step)
      } else {
        setSelectedStep('step1_outline')
      }
    } catch (error) {
      console.error('获取步骤状态失败:', error)
      message.error('获取步骤状态失败')
    } finally {
      setLoading(false)
    }
  }

  const handleRetry = async () => {
    if (!selectedStep) {
      message.warning('请选择要重新处理的步骤')
      return
    }

    setRetrying(true)
    try {
      await onRetry(selectedStep, cleanOutput)
      message.success(`已开始从 ${getStepName(selectedStep)} 重新处理`)
      onClose()
    } catch (error) {
      console.error('重试失败:', error)
      message.error('重试失败，请稍后再试')
    } finally {
      setRetrying(false)
    }
  }

  const getStepName = (step: string): string => {
    const stepInfo = stepsStatus?.steps.find(s => s.step === step)
    return stepInfo?.name || step
  }

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  const getStepIcon = (step: StepInfo, index: number) => {
    if (step.completed) {
      return <CheckCircleOutlined style={{ color: '#52c41a', fontSize: '18px' }} />
    }
    return <ClockCircleOutlined style={{ color: '#d9d9d9', fontSize: '18px' }} />
  }

  const getStepDescription = (step: StepInfo, index: number): string => {
    if (step.completed) {
      let desc = `已完成`
      if (step.file_size > 0) {
        desc += ` · ${formatFileSize(step.file_size)}`
      }
      if (step.modified_time) {
        const date = new Date(step.modified_time * 1000)
        desc += ` · ${date.toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}`
      }
      return desc
    }
    return '未完成'
  }

  const canSelectStep = (step: string, index: number): boolean => {
    if (!stepsStatus) return false
    
    if (projectStatus === 'completed') {
      return true
    }
    
    const stepIndex = stepsStatus.steps.findIndex(s => s.step === step)
    const previousStepsCompleted = stepsStatus.steps.slice(0, stepIndex).every(s => s.completed)
    
    return previousStepsCompleted || step === 'step1_outline'
  }

  return (
    <Modal
      title={
        <Space>
          <ReloadOutlined />
          <span>重新处理项目</span>
        </Space>
      }
      open={visible}
      onCancel={onClose}
      width={520}
      footer={[
        <Button key="cancel" onClick={onClose}>
          取消
        </Button>,
        <Button
          key="retry"
          type="primary"
          icon={<PlayCircleOutlined />}
          loading={retrying}
          onClick={handleRetry}
          disabled={!selectedStep}
        >
          开始处理
        </Button>
      ]}
    >
      <div style={{ marginBottom: '16px' }}>
        <Text strong>项目：</Text>
        <Text>{projectName}</Text>
        <Divider type="vertical" />
        <Tag color={projectStatus === 'completed' ? 'success' : 'default'}>
          {projectStatus === 'completed' ? '已完成' : projectStatus}
        </Tag>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <Spin />
          <div style={{ marginTop: '12px', color: '#666' }}>加载步骤状态...</div>
        </div>
      ) : stepsStatus ? (
        <>
          <div style={{ marginBottom: '12px' }}>
            <Text type="secondary">选择要重新处理的起始步骤：</Text>
          </div>
          
          <List
            dataSource={stepsStatus.steps}
            renderItem={(step, index) => {
              const selectable = canSelectStep(step.step, index)
              const isSelected = selectedStep === step.step
              
              return (
                <List.Item
                  style={{
                    padding: '12px 16px',
                    cursor: selectable ? 'pointer' : 'not-allowed',
                    backgroundColor: isSelected ? '#e6f7ff' : 'transparent',
                    borderRadius: '6px',
                    marginBottom: '4px',
                    border: isSelected ? '1px solid #1890ff' : '1px solid transparent',
                    opacity: selectable ? 1 : 0.5
                  }}
                  onClick={() => {
                    if (selectable) {
                      setSelectedStep(step.step)
                    }
                  }}
                >
                  <List.Item.Meta
                    avatar={getStepIcon(step, index)}
                    title={
                      <Space>
                        <Text strong={isSelected}>{step.name}</Text>
                        {isSelected && <Tag color="blue" style={{ marginLeft: '8px' }}>选中</Tag>}
                      </Space>
                    }
                    description={getStepDescription(step, index)}
                  />
                </List.Item>
              )
            }}
          />

          {stepsStatus.clips_count > 0 && (
            <div style={{ marginTop: '16px', padding: '12px', backgroundColor: '#fafafa', borderRadius: '6px' }}>
              <Text type="secondary">
                当前已生成 <Text strong>{stepsStatus.clips_count}</Text> 个切片
              </Text>
            </div>
          )}

          <div style={{ marginTop: '16px' }}>
            <Checkbox
              checked={cleanOutput}
              onChange={(e) => setCleanOutput(e.target.checked)}
            >
              清理该步骤的输出文件后再处理
            </Checkbox>
            <div style={{ marginTop: '4px', marginLeft: '24px', color: '#999', fontSize: '12px' }}>
              建议勾选，避免旧数据影响新结果
            </div>
          </div>

          <div style={{ marginTop: '16px', padding: '12px', backgroundColor: '#fff7e6', borderRadius: '6px', border: '1px solid #ffd591' }}>
            <Text type="warning" style={{ fontSize: '12px' }}>
              提示：从选中的步骤开始，后续所有步骤都会重新执行
            </Text>
          </div>
        </>
      ) : (
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
          无法获取步骤状态
        </div>
      )}
    </Modal>
  )
}

export default RetryStepDialog
