import React, { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Layout,
  Card,
  Typography,
  Button,
  Space,
  Spin,
  Descriptions,
  Tag,
  message
} from 'antd'
import {
  ArrowLeftOutlined,
  PlayCircleOutlined,
  DownloadOutlined,
  ShareAltOutlined,
  ClockCircleOutlined,
  StarFilled
} from '@ant-design/icons'
import { Clip, useProjectStore } from '../store/useProjectStore'
import { projectApi, getBaseUrl } from '../services/api'

const { Content } = Layout
const { Title, Text, Paragraph } = Typography

const ClipDetailPage: React.FC = () => {
  const { projectId, clipId } = useParams<{ projectId: string; clipId: string }>()
  const navigate = useNavigate()
  const { currentProject } = useProjectStore()
  const [loading, setLoading] = useState(true)
  const [clip, setClip] = useState<Clip | null>(null)
  const [videoUrl, setVideoUrl] = useState<string | null>(null)
  const videoRef = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    if (projectId && clipId && currentProject) {
      loadClipData()
    }
  }, [projectId, clipId, currentProject])

  const loadClipData = () => {
    setLoading(true)
    try {
      // 从当前项目中查找对应的切片
      const foundClip = currentProject?.clips?.find(c => c.id === clipId)
      if (foundClip) {
        setClip(foundClip)
        // 生成视频URL
        const url = projectApi.getClipVideoUrl(
          projectId!,
          foundClip.id,
          foundClip.title || foundClip.generated_title
        )
        setVideoUrl(url)
      } else {
        message.error('找不到该切片')
      }
    } catch (error) {
      console.error('Failed to load clip:', error)
      message.error('加载切片失败')
    } finally {
      setLoading(false)
    }
  }

  const formatDuration = (seconds: number) => {
    if (!seconds || seconds <= 0) return '00:00'
    const minutes = Math.floor(seconds / 60)
    const remainingSeconds = Math.floor(seconds % 60)
    return `${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`
  }

  const formatTime = (timeStr: string | number) => {
    if (typeof timeStr === 'number') {
      return formatDuration(timeStr)
    }
    return timeStr
  }

  const calculateDuration = (startTime: string | number, endTime: string | number): number => {
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
  }

  const getScoreColor = (score: number) => {
    if (score >= 90) return '#52c41a'
    if (score >= 80) return '#1890ff'
    if (score >= 70) return '#faad14'
    if (score >= 60) return '#ff7a45'
    return '#ff4d4f'
  }

  const handleDownload = async () => {
    if (!videoUrl || !projectId || !clipId) {
      message.error('下载信息不完整')
      return
    }

    try {
      // 构建完整的下载URL
      const downloadUrl = `${getBaseUrl()}/api/v1/files/projects/${projectId}/clips/${clipId}`

      console.log(`开始下载视频: ${downloadUrl}`)

      // 直接使用a标签下载，避免跨域和blob问题
      const a = document.createElement('a')
      a.href = downloadUrl
      // 清理文件名中的非法字符
      const safeFileName = (clip?.title || clip?.generated_title || 'clip')
        .replace(/[<>:"/\\|?*]/g, '_')
        .substring(0, 100)
      a.download = `${safeFileName}.mp4`
      a.target = '_blank'

      // 触发下载
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)

      message.success('下载开始')
    } catch (error) {
      console.error('Download failed:', error)
      message.error(`下载失败: ${error instanceof Error ? error.message : '未知错误'}`)
    }
  }

  const handleShare = () => {
    if (navigator.share) {
      navigator.share({
        title: clip?.title || clip?.generated_title || '精彩片段',
        text: clip?.content?.join(' ') || '来看看这个精彩片段！',
        url: window.location.href
      })
    } else {
      navigator.clipboard.writeText(window.location.href)
      message.success('链接已复制到剪贴板')
    }
  }

  if (loading) {
    return (
      <Content style={{ padding: '24px', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
        <Spin size="large" />
      </Content>
    )
  }

  if (!clip) {
    return (
      <Content style={{ padding: '24px', background: '#ffffff' }}>
        <Card>
          <Button type="link" onClick={() => navigate(`/project/${projectId}`)}>
            返回项目
          </Button>
          <Title level={3}>切片不存在</Title>
        </Card>
      </Content>
    )
  }

  const duration = calculateDuration(clip.start_time, clip.end_time)

  return (
    <Content style={{ padding: '24px', background: '#f5f5f5', minHeight: '100vh' }}>
      <Card
        style={{
          maxWidth: '1200px',
          margin: '0 auto',
          borderRadius: '16px',
          border: '1px solid #e0e0e0'
        }}
      >
        {/* 头部 */}
        <div style={{ marginBottom: '24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Button
            type="link"
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate(`/project/${projectId}`)}
            style={{ padding: 0 }}
          >
            返回项目
          </Button>
          <Space>
            <Button
              icon={<DownloadOutlined />}
              onClick={handleDownload}
            >
              下载
            </Button>
            <Button
              icon={<ShareAltOutlined />}
              onClick={handleShare}
            >
              分享
            </Button>
          </Space>
        </div>

        {/* 标题 */}
        <Title level={2} style={{ marginBottom: '16px' }}>
          {clip.title || clip.generated_title || '未命名片段'}
        </Title>

        {/* 视频播放器 */}
        <div
          style={{
            width: '100%',
            aspectRatio: '16/9',
            backgroundColor: '#000',
            borderRadius: '12px',
            overflow: 'hidden',
            marginBottom: '24px'
          }}
        >
          {videoUrl ? (
            <video
              ref={videoRef}
              src={videoUrl}
              controls
              onError={() => {
                console.error('视频加载失败:', videoUrl)
                message.error('视频加载失败，请检查文件是否存在')
              }}
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'contain'
              }}
            />
          ) : (
            <div
              style={{
                width: '100%',
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'center',
                alignItems: 'center',
                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
              }}
            >
              <PlayCircleOutlined style={{ fontSize: '64px', color: 'white', marginBottom: '16px' }} />
              <Text style={{ color: 'white', fontSize: '16px' }}>视频加载中...</Text>
            </div>
          )}
        </div>

        {/* 信息标签 */}
        <Space size="middle" wrap style={{ marginBottom: '24px' }}>
          <Tag
            icon={<StarFilled />}
            color={getScoreColor(clip.final_score)}
            style={{ fontSize: '14px', padding: '4px 12px' }}
          >
            推荐分数: {Math.round(clip.final_score)}分
          </Tag>
          <Tag
            icon={<ClockCircleOutlined />}
            color="blue"
            style={{ fontSize: '14px', padding: '4px 12px' }}
          >
            时长: {formatDuration(duration)}
          </Tag>
          <Tag
            style={{ fontSize: '14px', padding: '4px 12px' }}
          >
            时间: {formatTime(clip.start_time)} - {formatTime(clip.end_time)}
          </Tag>
        </Space>

        {/* 详细信息 */}
        <Descriptions
          bordered
          column={{ xs: 1, sm: 1, md: 2 }}
          style={{ marginBottom: '24px' }}
        >
          <Descriptions.Item label="切片ID" span={2}>
            {clip.id}
          </Descriptions.Item>
          <Descriptions.Item label="开始时间">
            {formatTime(clip.start_time)}
          </Descriptions.Item>
          <Descriptions.Item label="结束时间">
            {formatTime(clip.end_time)}
          </Descriptions.Item>
          <Descriptions.Item label="推荐分数" span={2}>
            <Text style={{ color: getScoreColor(clip.final_score), fontWeight: 'bold', fontSize: '16px' }}>
              {clip.final_score.toFixed(2)}分
            </Text>
          </Descriptions.Item>
          <Descriptions.Item label="AI标题">
            {clip.generated_title || '-'}
          </Descriptions.Item>
          {clip.recommend_reason && (
            <Descriptions.Item label="视频简介" span={2}>
              <Paragraph>{clip.recommend_reason}</Paragraph>
            </Descriptions.Item>
          )}
          {clip.outline && (
            <Descriptions.Item label="内容大纲" span={2}>
              <Paragraph>{clip.outline}</Paragraph>
            </Descriptions.Item>
          )}
          {clip.content && clip.content.length > 0 && (
            <Descriptions.Item label="内容要点" span={2}>
              <div>
                {clip.content.map((point, index) => (
                  <div key={index} style={{ marginBottom: '8px' }}>
                    <Text>{index + 1}. {point}</Text>
                  </div>
                ))}
              </div>
            </Descriptions.Item>
          )}
        </Descriptions>
      </Card>
    </Content>
  )
}

export default ClipDetailPage
