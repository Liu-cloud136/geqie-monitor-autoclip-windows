import React, { useState, useMemo, useCallback } from 'react'
import {
  Modal,
  Checkbox,
  Input,
  Space,
  Typography,
  Empty,
  Button,
  Tooltip,
  Tag,
  Card,
  Radio,
} from 'antd'
import {
  SearchOutlined,
  ClockCircleOutlined,
  StarFilled,
  VideoCameraOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons'
import { Clip } from '../store/useProjectStore'
import { formatSecondsToTime } from '../utils/time'

const { Title, Text } = Typography

interface SelectClipsModalProps {
  visible: boolean
  clips: Clip[]
  projectId: string
  selectedClipIds: string[]
  onCancel: () => void
  onConfirm: (clipIds: string[]) => void
}

const SelectClipsModal: React.FC<SelectClipsModalProps> = ({
  visible,
  clips,
  projectId,
  selectedClipIds,
  onCancel,
  onConfirm,
}) => {
  const [localSelected, setLocalSelected] = useState<string[]>(selectedClipIds)
  const [searchText, setSearchText] = useState('')
  const [sortBy, setSortBy] = useState<'score' | 'time'>('time')

  const filteredClips = useMemo(() => {
    let result = [...clips]

    if (searchText) {
      const lowerSearch = searchText.toLowerCase()
      result = result.filter((clip) => {
        const title = (clip.title || clip.generated_title || '').toLowerCase()
        const reason = (clip.recommend_reason || '').toLowerCase()
        const outline = (clip.outline || '').toLowerCase()
        return (
          title.includes(lowerSearch) ||
          reason.includes(lowerSearch) ||
          outline.includes(lowerSearch)
        )
      })
    }

    if (sortBy === 'score') {
      result.sort((a, b) => b.final_score - a.final_score)
    } else {
      result.sort((a, b) => {
        const getSeconds = (time: string | number): number => {
          if (typeof time === 'number') return time
          const parts = time.split(':')
          const hours = parseInt(parts[0]) || 0
          const minutes = parseInt(parts[1]) || 0
          const seconds = parseFloat(parts[2]?.replace(',', '.') || '0')
          return hours * 3600 + minutes * 60 + seconds
        }
        return getSeconds(a.start_time) - getSeconds(b.start_time)
      })
    }

    return result
  }, [clips, searchText, sortBy])

  const handleToggleClip = useCallback((clipId: string) => {
    setLocalSelected((prev) => {
      if (prev.includes(clipId)) {
        return prev.filter((id) => id !== clipId)
      }
      return [...prev, clipId]
    })
  }, [])

  const handleSelectAll = useCallback(() => {
    if (localSelected.length === filteredClips.length) {
      setLocalSelected([])
    } else {
      setLocalSelected(filteredClips.map((c) => String(c.id)))
    }
  }, [localSelected.length, filteredClips])

  const handleConfirm = () => {
    onConfirm(localSelected)
    onCancel()
  }

  const getScoreColor = (score: number) => {
    if (score >= 90) return '#52c41a'
    if (score >= 80) return '#1890ff'
    if (score >= 70) return '#faad14'
    if (score >= 60) return '#ff7a45'
    return '#ff4d4f'
  }

  const getTimeDisplay = (startTime: string | number, endTime: string | number) => {
    const formatTime = (time: string | number): string => {
      if (typeof time === 'number') {
        return formatSecondsToTime(time)
      }
      const parts = time.split(':')
      if (parts.length === 3) {
        const hours = parseInt(parts[0]) || 0
        const minutes = parseInt(parts[1]) || 0
        const seconds = parseFloat(parts[2]?.replace(',', '.') || '0')
        if (hours > 0) {
          return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${Math.floor(seconds).toString().padStart(2, '0')}`
        }
        return `${minutes.toString().padStart(2, '0')}:${Math.floor(seconds).toString().padStart(2, '0')}`
      }
      return time
    }
    return `${formatTime(startTime)} - ${formatTime(endTime)}`
  }

  const getDuration = (startTime: string | number, endTime: string | number): string => {
    const getSeconds = (time: string | number): number => {
      if (typeof time === 'number') return time
      const parts = time.split(':')
      const hours = parseInt(parts[0]) || 0
      const minutes = parseInt(parts[1]) || 0
      const seconds = parseFloat(parts[2]?.replace(',', '.') || '0')
      return hours * 3600 + minutes * 60 + seconds
    }
    const start = getSeconds(startTime)
    const end = getSeconds(endTime)
    return formatSecondsToTime(end - start)
  }

  return (
    <Modal
      title={
        <div>
          <VideoCameraOutlined style={{ marginRight: '8px' }} />
          选择要添加的切片
        </div>
      }
      open={visible}
      onCancel={onCancel}
      onOk={handleConfirm}
      okText={`添加 (${localSelected.length})`}
      cancelText="取消"
      width={800}
      style={{ top: 20 }}
      okButtonProps={{
        disabled: localSelected.length === 0,
        type: 'primary',
        style: {
          background: 'linear-gradient(45deg, #1890ff, #36cfc9)',
          border: 'none',
        },
      }}
    >
      {/* 搜索和筛选 */}
      <div
        style={{
          marginBottom: '16px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: '16px',
        }}
      >
        <Input
          placeholder="搜索切片标题、推荐理由..."
          prefix={<SearchOutlined />}
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          style={{ flex: 1, maxWidth: 400 }}
          allowClear
        />
        <Radio.Group
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value)}
          buttonStyle="solid"
          size="small"
        >
          <Radio.Button value="time">按时间</Radio.Button>
          <Radio.Button value="score">按评分</Radio.Button>
        </Radio.Group>
        <Checkbox checked={localSelected.length === filteredClips.length && filteredClips.length > 0} onChange={handleSelectAll}>
          全选
        </Checkbox>
      </div>

      {/* 已选择提示 */}
      {localSelected.length > 0 && (
        <div
          style={{
            marginBottom: '12px',
            padding: '8px 12px',
            background: '#e6f7ff',
            borderRadius: '6px',
            border: '1px solid #91d5ff',
          }}
        >
          <Space>
            <CheckCircleOutlined style={{ color: '#1890ff' }} />
            <Text strong>已选择 {localSelected.length} 个切片</Text>
            <Tag color="blue">
              点击"添加"按钮将这些切片添加到时间轴
            </Tag>
          </Space>
        </div>
      )}

      {/* 切片列表 */}
      <div
        style={{
          maxHeight: '500px',
          overflowY: 'auto',
          paddingRight: '8px',
        }}
      >
        {filteredClips.length === 0 ? (
          <Empty
            description={searchText ? '未找到匹配的切片' : '暂无切片'}
            style={{ padding: '40px 0' }}
          />
        ) : (
          <div style={{ display: 'grid', gap: '12px' }}>
            {filteredClips.map((clip, index) => {
              const isSelected = localSelected.includes(String(clip.id))
              return (
                <Card
                  key={clip.id}
                  size="small"
                  hoverable
                  onClick={() => handleToggleClip(String(clip.id))}
                  style={{
                    cursor: 'pointer',
                    border: isSelected ? '2px solid #1890ff' : '1px solid #e0e0e0',
                    background: isSelected ? '#f0f7ff' : '#ffffff',
                    transition: 'all 0.2s',
                    borderRadius: '12px',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: '12px',
                    }}
                  >
                    {/* 复选框 */}
                    <div style={{ paddingTop: '4px' }}>
                      <Checkbox checked={isSelected} />
                    </div>

                    {/* 序号 */}
                    <div
                      style={{
                        width: '32px',
                        height: '32px',
                        borderRadius: '50%',
                        background: isSelected ? '#1890ff' : '#e8e8e8',
                        color: isSelected ? '#fff' : '#666',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontWeight: 600,
                        fontSize: '14px',
                        flexShrink: 0,
                      }}
                    >
                      {index + 1}
                    </div>

                    {/* 内容 */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'flex-start',
                          gap: '16px',
                        }}
                      >
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <Text
                            strong
                            style={{
                              fontSize: '14px',
                              color: '#1a1a1a',
                              display: 'block',
                              marginBottom: '4px',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            {clip.title || clip.generated_title || '未命名片段'}
                          </Text>
                          <Text
                            type="secondary"
                            style={{
                              fontSize: '12px',
                              display: '-webkit-box',
                              WebkitLineClamp: 1,
                              WebkitBoxOrient: 'vertical',
                              overflow: 'hidden',
                            }}
                          >
                            {clip.recommend_reason || clip.outline || '暂无描述'}
                          </Text>
                        </div>

                        {/* 右侧元信息 */}
                        <Space direction="vertical" size="small" style={{ flexShrink: 0, textAlign: 'right' }}>
                          {/* 评分 */}
                          <Tag
                            icon={<StarFilled style={{ fontSize: '10px' }} />}
                            style={{
                              background: getScoreColor(clip.final_score),
                              color: '#fff',
                              border: 'none',
                              margin: 0,
                            }}
                          >
                            {Math.round(clip.final_score)}分
                          </Tag>

                          {/* 时间范围 */}
                          <Space size="small" style={{ fontSize: '11px' }}>
                            <ClockCircleOutlined style={{ color: '#999' }} />
                            <Text type="secondary">
                              {getTimeDisplay(clip.start_time, clip.end_time)}
                            </Text>
                          </Space>

                          {/* 时长 */}
                          <Tag color="blue" style={{ margin: 0 }}>
                            {getDuration(clip.start_time, clip.end_time)}
                          </Tag>
                        </Space>
                      </div>
                    </div>
                  </div>
                </Card>
              )
            })}
          </div>
        )}
      </div>

      {/* 底部提示 */}
      <div
        style={{
          marginTop: '16px',
          paddingTop: '16px',
          borderTop: '1px solid #f0f0f0',
        }}
      >
        <Text type="secondary" style={{ fontSize: '12px' }}>
          提示：点击卡片选择切片，选择完成后点击"添加"按钮将切片添加到时间轴进行编辑
        </Text>
      </div>
    </Modal>
  )
}

export default SelectClipsModal
