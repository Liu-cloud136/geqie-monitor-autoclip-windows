import React, { useState, useCallback, useRef, useEffect, useMemo } from 'react'
import {
  Card,
  Button,
  Tooltip,
  Popconfirm,
  InputNumber,
  Space,
  Typography,
  Empty,
  message,
  Modal,
  Input,
  Spin,
  Progress,
  Alert,
  Divider,
} from 'antd'
import {
  DeleteOutlined,
  ScissorOutlined,
  PlusOutlined,
  PlayCircleOutlined,
  LoadingOutlined,
  DragOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined,
  VideoCameraOutlined,
  EditOutlined,
  SaveOutlined,
  InboxOutlined,
  ColumnHeightOutlined,
} from '@ant-design/icons'
import {
  EditSegment,
  ClipEditSession,
  EditSessionStatus,
  EditSegmentType,
} from '../types/api'
import { clipEditApi, projectApi } from '../services/api'
import { useClipEditStore } from '../stores/useClipEditStore'
import { formatSecondsToTime, parseTimeToSeconds } from '../utils/time'

const { Title, Text } = Typography

// ==================== 类型定义 ====================

interface TimelineEditorProps {
  projectId: string
  onAddClips?: () => void
}

interface TimelineSegment extends EditSegment {
  timelineStart: number
  timelineEnd: number
}

interface DragState {
  isDragging: boolean
  type: 'reorder' | 'left' | 'right' | 'move' | null
  segmentId: string | null
  startX: number
  startLeft: number
  startWidth: number
  initialStart: number
  initialEnd: number
}

// ==================== 时间轴刻度组件 ====================

const TimelineRuler: React.FC<{
  totalDuration: number
  pixelsPerSecond: number
}> = ({ totalDuration, pixelsPerSecond }) => {
  const ticks = useMemo(() => {
    const result: Array<{ time: number; isMajor: boolean; label: string }> = []
    const interval = totalDuration <= 60 ? 10 : totalDuration <= 300 ? 30 : 60
    
    for (let t = 0; t <= totalDuration; t += interval) {
      result.push({
        time: t,
        isMajor: t % (interval * 2) === 0,
        label: formatSecondsToTime(t),
      })
    }
    return result
  }, [totalDuration])

  return (
    <div
      className="timeline-ruler"
      style={{
        height: '40px',
        position: 'relative',
        borderBottom: '1px solid #d9d9d9',
        background: 'linear-gradient(180deg, #fafafa 0%, #f0f0f0 100%)',
        overflow: 'hidden',
      }}
    >
      {ticks.map((tick) => (
        <div
          key={tick.time}
          style={{
            position: 'absolute',
            left: `${tick.time * pixelsPerSecond}px`,
            bottom: 0,
            height: tick.isMajor ? '16px' : '8px',
            width: '1px',
            background: '#999',
          }}
        />
      ))}
      {ticks.filter((t) => t.isMajor).map((tick) => (
        <Text
          key={`label-${tick.time}`}
          style={{
            position: 'absolute',
            left: `${tick.time * pixelsPerSecond + 4}px`,
            top: '4px',
            fontSize: '11px',
            color: '#666',
            fontWeight: 500,
          }}
        >
          {tick.label}
        </Text>
      ))}
    </div>
  )
}

// ==================== 时间轴片段组件 ====================

const TimelineSegmentComponent: React.FC<{
  segment: TimelineSegment
  isSelected: boolean
  pixelsPerSecond: number
  onSelect: (id: string) => void
  onDelete: (id: string) => void
  onDragStart: (type: 'reorder' | 'left' | 'right' | 'move', segmentId: string, x: number) => void
  onCrop: (segmentId: string) => void
  onSplit: (segmentId: string) => void
  onMoveUp: (segmentId: string) => void
  onMoveDown: (segmentId: string) => void
  projectId: string
}> = ({
  segment,
  isSelected,
  pixelsPerSecond,
  onSelect,
  onDelete,
  onDragStart,
  onCrop,
  onSplit,
  onMoveUp,
  onMoveDown,
  projectId,
}) => {
  const segmentWidth = Math.max(80, segment.duration * pixelsPerSecond)
  const segmentLeft = segment.timelineStart * pixelsPerSecond

  const colors = {
    original: {
      bg: 'linear-gradient(135deg, #1890ff 0%, #36cfc9 100%)',
      border: '#1890ff',
    },
    cropped: {
      bg: 'linear-gradient(135deg, #faad14 0%, #ffc53d 100%)',
      border: '#faad14',
    },
  }

  const color = segment.segment_type === EditSegmentType.CROPPED ? colors.cropped : colors.original

  return (
    <div
      style={{
        position: 'absolute',
        left: `${segmentLeft}px`,
        top: '8px',
        width: `${segmentWidth}px`,
        height: '56px',
        background: color.bg,
        borderRadius: '8px',
        border: isSelected ? '3px solid #ff4d4f' : `2px solid ${color.border}`,
        boxShadow: isSelected
          ? '0 4px 12px rgba(255, 77, 79, 0.4)'
          : '0 2px 8px rgba(0, 0, 0, 0.15)',
        cursor: 'pointer',
        transition: 'box-shadow 0.2s, transform 0.1s',
        transform: isSelected ? 'translateY(-2px)' : 'translateY(0)',
      }}
      onClick={(e) => {
        if (!e.defaultPrevented) {
          onSelect(segment.id)
        }
      }}
      onMouseDown={(e) => {
        e.preventDefault()
        e.stopPropagation()
        onDragStart('move', segment.id, e.clientX)
      }}
    >
      {/* 左侧拖拽手柄（调整开始时间） */}
      <div
        style={{
          position: 'absolute',
          left: '-6px',
          top: '50%',
          transform: 'translateY(-50%)',
          width: '12px',
          height: '40px',
          background: 'rgba(255, 255, 255, 0.9)',
          borderRadius: '6px',
          border: '1px solid rgba(0, 0, 0, 0.15)',
          cursor: 'ew-resize',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 1px 3px rgba(0, 0, 0, 0.2)',
          zIndex: 10,
        }}
        onMouseDown={(e) => {
          e.preventDefault()
          e.stopPropagation()
          onDragStart('left', segment.id, e.clientX)
        }}
      >
        <ColumnHeightOutlined style={{ fontSize: '10px', color: '#888' }} />
      </div>

      {/* 右侧拖拽手柄（调整结束时间） */}
      <div
        style={{
          position: 'absolute',
          right: '-6px',
          top: '50%',
          transform: 'translateY(-50%)',
          width: '12px',
          height: '40px',
          background: 'rgba(255, 255, 255, 0.9)',
          borderRadius: '6px',
          border: '1px solid rgba(0, 0, 0, 0.15)',
          cursor: 'ew-resize',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 1px 3px rgba(0, 0, 0, 0.2)',
          zIndex: 10,
        }}
        onMouseDown={(e) => {
          e.preventDefault()
          e.stopPropagation()
          onDragStart('right', segment.id, e.clientX)
        }}
      >
        <ColumnHeightOutlined style={{ fontSize: '10px', color: '#888' }} />
      </div>

      {/* 重排序拖拽手柄 */}
      <div
        style={{
          position: 'absolute',
          left: '12px',
          top: '50%',
          transform: 'translateY(-50%)',
          padding: '4px 6px',
          cursor: 'grab',
          borderRadius: '4px',
          background: 'rgba(255, 255, 255, 0.2)',
        }}
        onMouseDown={(e) => {
          e.preventDefault()
          e.stopPropagation()
          onDragStart('reorder', segment.id, e.clientX)
        }}
      >
        <DragOutlined style={{ fontSize: '14px', color: '#fff' }} />
      </div>

      {/* 片段内容 */}
      <div
        style={{
          marginLeft: '48px',
          marginRight: '12px',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          overflow: 'hidden',
        }}
      >
        <Text
          style={{
            color: '#fff',
            fontSize: '12px',
            fontWeight: 600,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            textShadow: '0 1px 2px rgba(0,0,0,0.3)',
          }}
        >
          {segment.original_clip_title || `片段 ${segment.segment_order + 1}`}
        </Text>
        <Text
          style={{
            color: 'rgba(255,255,255,0.9)',
            fontSize: '11px',
            textShadow: '0 1px 2px rgba(0,0,0,0.3)',
          }}
        >
          {formatSecondsToTime(segment.duration)} · {segment.segment_type === EditSegmentType.CROPPED ? '已裁剪' : '原始'}
        </Text>
      </div>

      {/* 操作按钮 */}
      {isSelected && (
        <div
          style={{
            position: 'absolute',
            right: '20px',
            top: '-36px',
            display: 'flex',
            gap: '4px',
            background: '#fff',
            padding: '4px',
            borderRadius: '8px',
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
            zIndex: 20,
          }}
        >
          <Tooltip title="上移">
            <Button
              size="small"
              icon={<ArrowUpOutlined />}
              onClick={(e) => {
                e.stopPropagation()
                onMoveUp(segment.id)
              }}
            />
          </Tooltip>
          <Tooltip title="下移">
            <Button
              size="small"
              icon={<ArrowDownOutlined />}
              onClick={(e) => {
                e.stopPropagation()
                onMoveDown(segment.id)
              }}
            />
          </Tooltip>
          <Tooltip title="精确裁剪">
            <Button
              size="small"
              icon={<EditOutlined />}
              onClick={(e) => {
                e.stopPropagation()
                onCrop(segment.id)
              }}
            />
          </Tooltip>
          <Tooltip title="分割片段">
            <Button
              size="small"
              icon={<ScissorOutlined />}
              onClick={(e) => {
                e.stopPropagation()
                onSplit(segment.id)
              }}
            />
          </Tooltip>
          <Popconfirm
            title="确定删除此片段？"
            onConfirm={(e) => {
              e?.stopPropagation()
              onDelete(segment.id)
            }}
            okText="确定"
            cancelText="取消"
          >
            <Button
              size="small"
              danger
              icon={<DeleteOutlined />}
              onClick={(e) => e.stopPropagation()}
            />
          </Popconfirm>
        </div>
      )}
    </div>
  )
}

// ==================== 精确时间调整模态框 ====================

const TimeAdjustModal: React.FC<{
  visible: boolean
  segment: EditSegment | null
  onCancel: () => void
  onConfirm: (segmentId: string, startTime: number, endTime: number) => void
}> = ({ visible, segment, onCancel, onConfirm }) => {
  const [startTime, setStartTime] = useState<number>(0)
  const [endTime, setEndTime] = useState<number>(0)

  useEffect(() => {
    if (segment) {
      setStartTime(segment.start_time)
      setEndTime(segment.end_time)
    }
  }, [segment, visible])

  if (!segment) return null

  const handleConfirm = () => {
    if (startTime >= endTime) {
      message.error('开始时间必须小于结束时间')
      return
    }
    if (startTime < segment.original_start_time || endTime > segment.original_end_time) {
      message.error('时间范围不能超出原始片段范围')
      return
    }
    onConfirm(segment.id, startTime, endTime)
    onCancel()
  }

  const step = 0.001 // 毫秒级精度

  return (
    <Modal
      title="精确调整时间"
      open={visible}
      onCancel={onCancel}
      onOk={handleConfirm}
      okText="应用"
      cancelText="取消"
      width={520}
    >
      <div style={{ padding: '8px 0' }}>
        <Alert
          message={`原始范围: ${formatSecondsToTime(segment.original_start_time)} - ${formatSecondsToTime(segment.original_end_time)}`}
          type="info"
          showIcon
          style={{ marginBottom: '16px' }}
        />

        <Space direction="vertical" style={{ width: '100%' }} size="large">
          <div>
            <Text style={{ marginBottom: '8px', display: 'block', fontWeight: 500 }}>
              开始时间 (秒)
            </Text>
            <Space.Compact style={{ width: '100%' }}>
              <InputNumber
                style={{ width: '100%' }}
                value={startTime}
                onChange={(v) => setStartTime(v ?? 0)}
                min={segment.original_start_time}
                max={endTime - 0.001}
                step={step}
                precision={3}
                addonAfter={formatSecondsToTime(startTime)}
              />
            </Space.Compact>
          </div>

          <div>
            <Text style={{ marginBottom: '8px', display: 'block', fontWeight: 500 }}>
              结束时间 (秒)
            </Text>
            <Space.Compact style={{ width: '100%' }}>
              <InputNumber
                style={{ width: '100%' }}
                value={endTime}
                onChange={(v) => setEndTime(v ?? 0)}
                min={startTime + 0.001}
                max={segment.original_end_time}
                step={step}
                precision={3}
                addonAfter={formatSecondsToTime(endTime)}
              />
            </Space.Compact>
          </div>

          <Divider style={{ margin: '8px 0' }} />

          <div style={{ background: '#f5f5f5', padding: '12px', borderRadius: '8px' }}>
            <Space style={{ width: '100%', justifyContent: 'space-between' }}>
              <Text type="secondary">当前时长:</Text>
              <Text strong style={{ fontSize: '16px' }}>
                {formatSecondsToTime(endTime - startTime)}
              </Text>
            </Space>
            <Space style={{ width: '100%', justifyContent: 'space-between', marginTop: '8px' }}>
              <Text type="secondary">原始时长:</Text>
              <Text type="secondary">
                {formatSecondsToTime(segment.original_end_time - segment.original_start_time)}
              </Text>
            </Space>
          </div>
        </Space>
      </div>
    </Modal>
  )
}

// ==================== 分割片段模态框 ====================

const SplitModal: React.FC<{
  visible: boolean
  segment: EditSegment | null
  onCancel: () => void
  onConfirm: (segmentId: string, splitTime: number) => void
}> = ({ visible, segment, onCancel, onConfirm }) => {
  const [splitTime, setSplitTime] = useState<number>(0)

  useEffect(() => {
    if (segment) {
      setSplitTime((segment.start_time + segment.end_time) / 2)
    }
  }, [segment, visible])

  if (!segment) return null

  const handleConfirm = () => {
    if (splitTime <= segment.start_time || splitTime >= segment.end_time) {
      message.error('分割时间必须在片段时间范围内')
      return
    }
    onConfirm(segment.id, splitTime)
    onCancel()
  }

  return (
    <Modal
      title="分割片段"
      open={visible}
      onCancel={onCancel}
      onOk={handleConfirm}
      okText="分割"
      cancelText="取消"
      width={480}
    >
      <div style={{ padding: '8px 0' }}>
        <Alert
          message={`当前片段范围: ${formatSecondsToTime(segment.start_time)} - ${formatSecondsToTime(segment.end_time)}`}
          type="info"
          showIcon
          style={{ marginBottom: '16px' }}
        />

        <div>
          <Text style={{ marginBottom: '8px', display: 'block', fontWeight: 500 }}>
            分割时间点 (秒)
          </Text>
          <Space.Compact style={{ width: '100%' }}>
            <InputNumber
              style={{ width: '100%' }}
              value={splitTime}
              onChange={(v) => setSplitTime(v ?? 0)}
              min={segment.start_time + 0.001}
              max={segment.end_time - 0.001}
              step={0.001}
              precision={3}
              addonAfter={formatSecondsToTime(splitTime)}
            />
          </Space.Compact>
        </div>

        <div style={{ marginTop: '16px', background: '#f5f5f5', padding: '12px', borderRadius: '8px' }}>
          <Space direction="vertical" style={{ width: '100%' }}>
            <Space style={{ width: '100%', justifyContent: 'space-between' }}>
              <Text type="secondary">片段 1:</Text>
              <Text>
                {formatSecondsToTime(segment.start_time)} - {formatSecondsToTime(splitTime)}
              </Text>
            </Space>
            <Space style={{ width: '100%', justifyContent: 'space-between' }}>
              <Text type="secondary">片段 2:</Text>
              <Text>
                {formatSecondsToTime(splitTime)} - {formatSecondsToTime(segment.end_time)}
              </Text>
            </Space>
          </Space>
        </div>
      </div>
    </Modal>
  )
}

// ==================== 主组件：时间轴编辑器 ====================

const TimelineEditor: React.FC<TimelineEditorProps> = ({ projectId, onAddClips }) => {
  const {
    currentSession,
    isLoading,
    selectedSegmentId,
    isGenerating,
    generationProgress,
    setSession,
    setLoading,
    selectSegment,
    setGenerating,
    setGenerationProgress,
    setSegments,
    removeSegment,
    updateSegment,
    reorderSegments,
    addSegment,
  } = useClipEditStore()

  const timelineRef = useRef<HTMLDivElement>(null)
  const [dragState, setDragState] = useState<DragState>({
    isDragging: false,
    type: null,
    segmentId: null,
    startX: 0,
    startLeft: 0,
    startWidth: 0,
    initialStart: 0,
    initialEnd: 0,
  })

  const [timeAdjustModalVisible, setTimeAdjustModalVisible] = useState(false)
  const [splitModalVisible, setSplitModalVisible] = useState(false)
  const [currentEditSegment, setCurrentEditSegment] = useState<EditSegment | null>(null)

  // 计算时间轴参数
  const totalDuration = useMemo(() => {
    if (!currentSession || currentSession.segments.length === 0) return 60
    return Math.max(
      60,
      currentSession.total_duration + 10
    )
  }, [currentSession])

  const pixelsPerSecond = useMemo(() => {
    // 根据总时长动态调整每秒钟的像素数
    if (totalDuration <= 60) return 8
    if (totalDuration <= 300) return 4
    if (totalDuration <= 600) return 2
    return 1
  }, [totalDuration])

  // 计算每个片段在时间轴上的位置
  const timelineSegments = useMemo((): TimelineSegment[] => {
    if (!currentSession) return []
    
    let currentTime = 0
    return currentSession.segments
      .sort((a, b) => a.segment_order - b.segment_order)
      .map((segment) => {
        const timelineSegment: TimelineSegment = {
          ...segment,
          timelineStart: currentTime,
          timelineEnd: currentTime + segment.duration,
        }
        currentTime += segment.duration
        return timelineSegment
      })
  }, [currentSession])

  // 加载或创建默认编辑会话
  useEffect(() => {
    const loadDefaultSession = async () => {
      if (!projectId) return
      setLoading(true)
      try {
        const result = await clipEditApi.getOrCreateDefaultSession(projectId)
        if (result.success) {
          setSession(result.session as unknown as ClipEditSession)
        }
      } catch (error) {
        console.error('Failed to load edit session:', error)
      } finally {
        setLoading(false)
      }
    }
    loadDefaultSession()
  }, [projectId, setSession, setLoading])

  // 处理拖拽开始
  const handleDragStart = useCallback(
    (type: 'reorder' | 'left' | 'right' | 'move', segmentId: string, x: number) => {
      const segment = timelineSegments.find((s) => s.id === segmentId)
      if (!segment) return

      selectSegment(segmentId)
      
      setDragState({
        isDragging: true,
        type,
        segmentId,
        startX: x,
        startLeft: segment.timelineStart * pixelsPerSecond,
        startWidth: segment.duration * pixelsPerSecond,
        initialStart: segment.start_time,
        initialEnd: segment.end_time,
      })
    },
    [timelineSegments, pixelsPerSecond, selectSegment]
  )

  // 处理拖拽移动
  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!dragState.isDragging || !dragState.segmentId) return

      const deltaX = e.clientX - dragState.startX
      const deltaSeconds = deltaX / pixelsPerSecond

      const segment = currentSession?.segments.find((s) => s.id === dragState.segmentId)
      if (!segment) return

      if (dragState.type === 'left') {
        // 调整开始时间
        let newStartTime = dragState.initialStart + deltaSeconds
        newStartTime = Math.max(segment.original_start_time, Math.min(newStartTime, dragState.initialEnd - 0.1))
        updateSegment(segment.id, { start_time: newStartTime, duration: dragState.initialEnd - newStartTime })
      } else if (dragState.type === 'right') {
        // 调整结束时间
        let newEndTime = dragState.initialEnd + deltaSeconds
        newEndTime = Math.min(segment.original_end_time, Math.max(newEndTime, dragState.initialStart + 0.1))
        updateSegment(segment.id, { end_time: newEndTime, duration: newEndTime - dragState.initialStart })
      }
    },
    [dragState, pixelsPerSecond, currentSession, updateSegment]
  )

  // 处理拖拽结束
  const handleMouseUp = useCallback(async () => {
    if (!dragState.isDragging) return

    // 保存更改到后端
    if (dragState.segmentId && (dragState.type === 'left' || dragState.type === 'right')) {
      const segment = currentSession?.segments.find((s) => s.id === dragState.segmentId)
      if (segment) {
        try {
          await clipEditApi.cropSegment(segment.id, segment.start_time, segment.end_time)
          message.success('时间范围已更新')
        } catch (error) {
          message.error('更新失败')
        }
      }
    }

    setDragState({
      isDragging: false,
      type: null,
      segmentId: null,
      startX: 0,
      startLeft: 0,
      startWidth: 0,
      initialStart: 0,
      initialEnd: 0,
    })
  }, [dragState, currentSession])

  // 添加全局事件监听
  useEffect(() => {
    if (dragState.isDragging) {
      window.addEventListener('mousemove', handleMouseMove)
      window.addEventListener('mouseup', handleMouseUp)
      return () => {
        window.removeEventListener('mousemove', handleMouseMove)
        window.removeEventListener('mouseup', handleMouseUp)
      }
    }
  }, [dragState.isDragging, handleMouseMove, handleMouseUp])

  // 删除片段
  const handleDeleteSegment = async (segmentId: string) => {
    try {
      await clipEditApi.deleteSegment(segmentId)
      removeSegment(segmentId)
      message.success('已删除片段')
    } catch (error) {
      message.error('删除失败')
    }
  }

  // 上移/下移片段
  const handleMoveSegment = async (segmentId: string, direction: 'up' | 'down') => {
    if (!currentSession) return

    const segments = [...currentSession.segments].sort((a, b) => a.segment_order - b.segment_order)
    const currentIndex = segments.findIndex((s) => s.id === segmentId)

    if (direction === 'up' && currentIndex <= 0) return
    if (direction === 'down' && currentIndex >= segments.length - 1) return

    const newIndex = direction === 'up' ? currentIndex - 1 : currentIndex + 1
    const swapSegment = segments[newIndex]

    // 更新本地状态
    const segmentOrders = segments.map((s, i) => {
      if (s.id === segmentId) return { segment_id: s.id, segment_order: newIndex }
      if (s.id === swapSegment.id) return { segment_id: s.id, segment_order: currentIndex }
      return { segment_id: s.id, segment_order: i }
    })

    reorderSegments(segmentOrders)

    // 保存到后端
    try {
      await clipEditApi.reorderSegments(currentSession.id, segmentOrders)
    } catch (error) {
      message.error('排序失败')
      // 回滚？
    }
  }

  // 打开精确裁剪模态框
  const handleOpenCropModal = (segmentId: string) => {
    const segment = currentSession?.segments.find((s) => s.id === segmentId)
    if (segment) {
      setCurrentEditSegment(segment)
      setTimeAdjustModalVisible(true)
    }
  }

  // 确认裁剪
  const handleConfirmCrop = async (segmentId: string, startTime: number, endTime: number) => {
    try {
      const result = await clipEditApi.cropSegment(segmentId, startTime, endTime)
      if (result.success) {
        updateSegment(segmentId, {
          start_time: startTime,
          end_time: endTime,
          duration: endTime - startTime,
          segment_type: EditSegmentType.CROPPED,
        })
        message.success('已裁剪片段')
      }
    } catch (error) {
      message.error('裁剪失败')
    }
  }

  // 打开分割模态框
  const handleOpenSplitModal = (segmentId: string) => {
    const segment = currentSession?.segments.find((s) => s.id === segmentId)
    if (segment) {
      setCurrentEditSegment(segment)
      setSplitModalVisible(true)
    }
  }

  // 确认分割
  const handleConfirmSplit = async (segmentId: string, splitTime: number) => {
    try {
      const result = await clipEditApi.splitSegment(segmentId, splitTime)
      if (result.success) {
        // 重新加载片段
        const segmentsResult = await clipEditApi.getSessionSegments(currentSession!.id)
        if (segmentsResult.success) {
          setSegments(segmentsResult.segments as unknown as EditSegment[])
        }
        message.success('已分割片段')
      }
    } catch (error) {
      message.error('分割失败')
    }
  }

  // 生成合并视频
  const handleGenerateVideo = async () => {
    if (!currentSession) return
    if (currentSession.segments.length === 0) {
      message.warning('请先添加至少一个片段')
      return
    }

    setGenerating(true)
    setGenerationProgress(0)

    try {
      const result = await clipEditApi.generateVideo(
        currentSession.id,
        `${currentSession.name}_merged`,
        true
      )

      if (result.success) {
        message.success('视频生成任务已启动，请稍候...')
        // TODO: 可以添加轮询来检查任务状态
      } else {
        message.error(result.message || '生成失败')
      }
    } catch (error) {
      message.error('生成失败')
    } finally {
      setGenerating(false)
    }
  }

  if (isLoading) {
    return (
      <Card style={{ borderRadius: '16px' }}>
        <div style={{ textAlign: 'center', padding: '40px' }}>
          <Spin size="large" />
          <div style={{ marginTop: '16px' }}>
            <Text type="secondary">加载编辑会话...</Text>
          </div>
        </div>
      </Card>
    )
  }

  return (
    <Card
      style={{ borderRadius: '16px', border: '1px solid #e0e0e0' }}
      styles={{
        body: { padding: '20px' },
      }}
    >
      {/* 头部 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <div>
          <Title level={4} style={{ margin: 0, fontWeight: 600 }}>
            <VideoCameraOutlined style={{ marginRight: '8px' }} />
            时间轴编辑
          </Title>
          <Text type="secondary" style={{ fontSize: '13px' }}>
            {currentSession?.segments.length || 0} 个片段 · 总时长 {formatSecondsToTime(currentSession?.total_duration || 0)}
          </Text>
        </div>
        <Space>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={onAddClips}
            style={{
              background: 'linear-gradient(45deg, #1890ff, #36cfc9)',
              border: 'none',
            }}
          >
            添加切片
          </Button>
          <Button
            type="primary"
            icon={isGenerating ? <LoadingOutlined /> : <PlayCircleOutlined />}
            onClick={handleGenerateVideo}
            loading={isGenerating}
            disabled={!currentSession || currentSession.segments.length === 0}
            style={{
              background: 'linear-gradient(45deg, #52c41a, #73d13d)',
              border: 'none',
            }}
          >
            {isGenerating ? '生成中...' : '生成视频'}
          </Button>
        </Space>
      </div>

      {/* 生成进度 */}
      {isGenerating && (
        <div style={{ marginBottom: '16px' }}>
          <Progress percent={generationProgress} status="active" />
        </div>
      )}

      {/* 时间轴区域 */}
      {currentSession && currentSession.segments.length > 0 ? (
        <div
          style={{
            background: '#fafafa',
            borderRadius: '12px',
            border: '1px solid #e0e0e0',
            overflow: 'hidden',
          }}
        >
          {/* 时间轴刻度 */}
          <TimelineRuler totalDuration={totalDuration} pixelsPerSecond={pixelsPerSecond} />

          {/* 时间轴轨道 */}
          <div
            ref={timelineRef}
            style={{
              position: 'relative',
              height: '80px',
              minWidth: `${Math.max(600, totalDuration * pixelsPerSecond)}px`,
              background: 'repeating-linear-gradient(90deg, transparent, transparent 50px, rgba(0,0,0,0.02) 50px, rgba(0,0,0,0.02) 100px)',
              cursor: dragState.isDragging ? 'ew-resize' : 'default',
              overflowX: 'auto',
            }}
            onClick={(e) => {
              // 点击空白处取消选择
              if (e.target === e.currentTarget) {
                selectSegment(null)
              }
            }}
          >
            {/* 片段 */}
            {timelineSegments.map((segment) => (
              <TimelineSegmentComponent
                key={segment.id}
                segment={segment}
                isSelected={selectedSegmentId === segment.id}
                pixelsPerSecond={pixelsPerSecond}
                onSelect={selectSegment}
                onDelete={handleDeleteSegment}
                onDragStart={handleDragStart}
                onCrop={handleOpenCropModal}
                onSplit={handleOpenSplitModal}
                onMoveUp={(id) => handleMoveSegment(id, 'up')}
                onMoveDown={(id) => handleMoveSegment(id, 'down')}
                projectId={projectId}
              />
            ))}
          </div>
        </div>
      ) : (
        <Empty
          description={
            <div>
              <Text type="secondary" style={{ fontSize: '14px' }}>
                时间轴为空
              </Text>
              <br />
              <Text type="secondary" style={{ fontSize: '12px' }}>
                点击上方"添加切片"按钮，将视频切片添加到时间轴进行编辑
              </Text>
            </div>
          }
          image={<InboxOutlined style={{ fontSize: '64px', color: '#d9d9d9' }} />}
          style={{ padding: '60px 0' }}
        />
      )}

      {/* 底部提示 */}
      {currentSession && currentSession.segments.length > 0 && (
        <div
          style={{
            marginTop: '16px',
            padding: '12px 16px',
            background: '#f6ffed',
            borderRadius: '8px',
            border: '1px solid #b7eb8f',
          }}
        >
          <Space size="large">
            <Text type="secondary" style={{ fontSize: '12px' }}>
              <DragOutlined style={{ marginRight: '4px' }} />
              拖拽片段重新排序
            </Text>
            <Text type="secondary" style={{ fontSize: '12px' }}>
              <ColumnHeightOutlined style={{ marginRight: '4px' }} />
              拖拽边缘调整时间
            </Text>
            <Text type="secondary" style={{ fontSize: '12px' }}>
              <EditOutlined style={{ marginRight: '4px' }} />
              精确调整时间
            </Text>
            <Text type="secondary" style={{ fontSize: '12px' }}>
              <ScissorOutlined style={{ marginRight: '4px' }} />
              分割片段
            </Text>
          </Space>
        </div>
      )}

      {/* 精确时间调整模态框 */}
      <TimeAdjustModal
        visible={timeAdjustModalVisible}
        segment={currentEditSegment}
        onCancel={() => setTimeAdjustModalVisible(false)}
        onConfirm={handleConfirmCrop}
      />

      {/* 分割模态框 */}
      <SplitModal
        visible={splitModalVisible}
        segment={currentEditSegment}
        onCancel={() => setSplitModalVisible(false)}
        onConfirm={handleConfirmSplit}
      />
    </Card>
  )
}

export default TimelineEditor
