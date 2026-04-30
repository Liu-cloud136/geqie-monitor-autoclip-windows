import React, { useState, useEffect, useMemo, useCallback, memo } from 'react'
import { Card } from 'antd'
import { ClockCircleOutlined, StarFilled } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { Clip } from '../store/useProjectStore'
import { projectApi } from '../services/api'
import './ClipCard.css'

interface ClipCardProps {
  clip: Clip
  videoUrl?: string
  projectId?: string
}

const ClipCard: React.FC<ClipCardProps> = ({
  clip,
  projectId
}) => {
  const navigate = useNavigate()
  const [videoThumbnail, setVideoThumbnail] = useState<string | null>(null)

  const handleThumbnailError = useCallback(() => {
    console.warn(`切片 ${clip.id} 缩略图加载失败`)
    setVideoThumbnail(null)
  }, [clip.id])

  const formatDuration = useCallback((seconds: number) => {
    if (!seconds || seconds <= 0) return '00:00'
    const minutes = Math.floor(seconds / 60)
    const remainingSeconds = Math.floor(seconds % 60)
    return `${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`
  }, [])

  const calculateDuration = useCallback((startTime: string | number, endTime: string | number): number => {
    if (!startTime || !endTime) return 0

    try {
      if (typeof startTime === 'number' && typeof endTime === 'number') {
        return Math.max(0, endTime - startTime)
      }

      const parseTime = (timeStr: string | number): number => {
        if (typeof timeStr === 'number') {
          return timeStr
        }

        const normalized = timeStr.replace(',', '.')
        const parts = normalized.split(':')
        if (parts.length !== 3) return 0

        const hours = parseInt(parts[0]) || 0
        const minutes = parseInt(parts[1]) || 0
        const seconds = parseFloat(parts[2]) || 0

        return hours * 3600 + minutes * 60 + seconds
      }

      const start = parseTime(startTime)
      const end = parseTime(endTime)

      return Math.max(0, end - start)
    } catch (error) {
      console.error('Error calculating duration:', error)
      return 0
    }
  }, [])

  const getDuration = useMemo(() => {
    if (!clip.start_time || !clip.end_time) return '00:00 - 00:00'

    const formatTime = (time: string | number): string => {
      if (typeof time === 'number') {
        return formatDuration(time)
      }
      
      const normalized = time.replace(',', '.')
      const parts = normalized.split(':')
      
      if (parts.length === 3) {
        const hours = parseInt(parts[0]) || 0
        const minutes = parseInt(parts[1]) || 0
        const seconds = parseFloat(parts[2]) || 0
        
        if (hours > 0) {
          return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${Math.floor(seconds).toString().padStart(2, '0')}`
        } else {
          return `${minutes.toString().padStart(2, '0')}:${Math.floor(seconds).toString().padStart(2, '0')}`
        }
      }
      
      return time
    }

    const startFormatted = formatTime(clip.start_time)
    const endFormatted = formatTime(clip.end_time)
    
    return `${startFormatted} - ${endFormatted}`
  }, [clip.start_time, clip.end_time, formatDuration])

  const getScoreColor = useCallback((score: number) => {
    if (score >= 90) return '#52c41a'
    if (score >= 80) return '#1890ff'
    if (score >= 70) return '#faad14'
    if (score >= 60) return '#ff7a45'
    return '#ff4d4f'
  }, [])

  const getDisplayContent = useMemo(() => {
    if (clip.recommend_reason && clip.recommend_reason.trim()) {
      return clip.recommend_reason
    }

    if (clip.content && clip.content.length > 0) {
      const contentPoints = clip.content.filter(item => {
        const text = item.trim()
        if (text.length > 100) return false
        if (text.split(/[，。！？；：""''（）【】]/).length > 3) return false
        return true
      })

      if (contentPoints.length > 0) {
        return contentPoints.join(' ')
      }
    }

    if (clip.outline && clip.outline.trim()) {
      return clip.outline
    }

    return '暂无内容要点'
  }, [clip.recommend_reason, clip.content, clip.outline])

  const duration = useMemo(() => formatDuration(calculateDuration(clip.start_time, clip.end_time)), [clip.start_time, clip.end_time, formatDuration, calculateDuration])

  const scoreColor = useMemo(() => getScoreColor(clip.final_score), [clip.final_score, getScoreColor])

  const handleClick = useCallback(() => {
    if (projectId) {
      navigate(`/project/${projectId}/clip/${clip.id}`)
    }
  }, [projectId, clip.id, navigate])

  // 直接使用后端生成的缩略图URL
  useEffect(() => {
    if (projectId && clip.id) {
      const thumbnailUrl = projectApi.getClipThumbnailUrl(projectId, clip.id)
      setVideoThumbnail(thumbnailUrl)
    }
  }, [projectId, clip.id])

  return (
    <Card
      className="clip-card"
      hoverable
      onClick={handleClick}
      style={{
        height: '320px',
        borderRadius: '16px',
        border: '1px solid #e0e0e0',
        background: 'linear-gradient(135deg, #ffffff 0%, #f5f5f5 100%)',
        overflow: 'hidden',
        cursor: 'pointer'
      }}
      styles={{
        body: {
          padding: 0,
        },
      }}
      cover={
        <div
          style={{
            height: '200px',
            background: videoThumbnail
              ? `url(${videoThumbnail}) center/cover`
              : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            position: 'relative',
            overflow: 'hidden'
          }}
        >
          {videoThumbnail && (
            <img
              src={videoThumbnail}
              alt={clip.title}
              style={{ display: 'none' }}
              onError={handleThumbnailError}
            />
          )}
          <div
            style={{
              position: 'absolute',
              top: '12px',
              right: '12px',
              background: scoreColor,
              color: 'white',
              padding: '4px 8px',
              borderRadius: '8px',
              fontSize: '12px',
              fontWeight: 500,
              display: 'flex',
              alignItems: 'center',
              gap: '4px'
            }}
          >
            <StarFilled style={{ fontSize: '12px' }} />
            {Math.round(clip.final_score)}分
          </div>

          <div
            style={{
              position: 'absolute',
              bottom: '12px',
              left: '12px',
              background: 'rgba(0,0,0,0.7)',
              color: 'white',
              padding: '4px 8px',
              borderRadius: '8px',
              fontSize: '12px',
              fontWeight: 500,
              display: 'flex',
              alignItems: 'center',
              gap: '4px'
            }}
          >
            <ClockCircleOutlined style={{ fontSize: '12px' }} />
            {getDuration}
          </div>

          <div
            style={{
              position: 'absolute',
              bottom: '12px',
              right: '12px',
              background: 'rgba(0,0,0,0.7)',
              color: 'white',
              padding: '4px 8px',
              borderRadius: '8px',
              fontSize: '12px',
              fontWeight: 500
            }}
          >
            {duration}
          </div>
        </div>
      }
    >
      <div style={{
        padding: '16px',
        height: '120px',
        display: 'flex',
        flexDirection: 'column'
      }}>
        <div style={{
          fontSize: '16px',
          fontWeight: 600,
          lineHeight: '1.4',
          color: '#1a1a1a',
          marginBottom: '8px',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          display: '-webkit-box',
          WebkitLineClamp: 2,
          WebkitBoxOrient: 'vertical'
        }}>
          {clip.title || clip.generated_title || '未命名片段'}
        </div>

        <div style={{
          fontSize: '13px',
          lineHeight: '1.5',
          color: '#666666',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          display: '-webkit-box',
          WebkitLineClamp: 2,
          WebkitBoxOrient: 'vertical',
          wordBreak: 'break-word'
        }}>
          {getDisplayContent}
        </div>
      </div>
    </Card>
  )
}

export default memo(ClipCard)