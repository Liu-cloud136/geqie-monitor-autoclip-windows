import React, { useState, useEffect } from 'react'
import { Card, Typography, Spin, Alert, Empty, Button, Tabs, Divider } from 'antd'
import { useParams } from 'react-router-dom'
import { projectApi } from '../services/api'

const { Title, Text, Paragraph } = Typography

const AIResponsePage: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>()
  const [loading, setLoading] = useState(true)
  const [aiData, setAiData] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState('outline')

  useEffect(() => {
    const fetchAIResponse = async () => {
      try {
        if (!projectId) {
          setError('项目ID不存在')
          setLoading(false)
          return
        }

        setLoading(true)
        setError(null)

        // 获取项目数据
        const project = await projectApi.getProject(projectId)
        
        // 从项目数据中提取AI相关信息
        const metadata = project.processing_config || project.settings || project.project_metadata || {}
        
        // 构建AI响应数据
        const aiResponse = {
          outline: metadata.outline || {},
          timeline: metadata.timeline || {},
          scoring: metadata.scoring || {},
          titles: metadata.titles || {},
          clips: project.clips || [],
          rawOutputs: metadata.raw_outputs || {}
        }
        
        console.log('AI响应数据:', aiResponse)
        console.log('项目数据:', project)
        
        setAiData(aiResponse)
      } catch (err: any) {
        setError(err.userMessage || '获取AI响应数据失败')
        console.error('获取AI响应数据失败:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchAIResponse()
  }, [projectId])

  if (loading) {
    return (
      <div style={{ padding: '40px', textAlign: 'center' }}>
        <Spin size="large" tip="加载AI响应数据..." />
      </div>
    )
  }

  if (error) {
    return (
      <div style={{ padding: '40px' }}>
        <Alert
          message="加载失败"
          description={error}
          type="error"
          showIcon
          action={
            <Button type="primary" size="small" onClick={() => window.location.reload()}>
              重试
            </Button>
          }
        />
      </div>
    )
  }

  if (!aiData) {
    return (
      <div style={{ padding: '40px' }}>
        <Empty description="暂无AI响应数据" />
      </div>
    )
  }

  // 定义标签页内容
  const tabItems = [
    {
      key: 'outline',
      label: '大纲分析',
      children: (
        <Card title="AI 生成的大纲" bordered={true}>
          <div style={{ maxHeight: '600px', overflowY: 'auto', paddingRight: '10px' }}>
            {aiData.outline.topics ? (
              <div>
                <Text strong>主题聚类:</Text>
                <ul style={{ marginTop: '10px' }}>
                  {aiData.outline.topics.map((topic: any, index: number) => (
                    <li key={index} style={{ marginBottom: '8px', wordBreak: 'break-word' }}>
                      <Text strong>{topic.title}</Text>
                      {topic.subtopics && topic.subtopics.length > 0 && (
                        <Paragraph style={{ margin: '5px 0 0 20px', wordBreak: 'break-word' }}>
                          {topic.subtopics.map((sub: string, subIndex: number) => (
                            <div key={subIndex}>• {sub}</div>
                          ))}
                        </Paragraph>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <Empty description="暂无大纲数据" />
            )}
          </div>
        </Card>
      )
    },
    {
      key: 'timeline',
      label: '时间线分析',
      children: (
        <Card title="AI 生成的时间线" bordered={true}>
          <div style={{ maxHeight: '600px', overflowY: 'auto', paddingRight: '10px' }}>
            {aiData.timeline.segments ? (
              <div>
                {aiData.timeline.segments.map((segment: any, index: number) => (
                  <div key={index} style={{ marginBottom: '16px', paddingBottom: '16px', borderBottom: '1px dashed #f0f0f0', wordBreak: 'break-word' }}>
                    <Text strong>时间片段 {index + 1}:</Text>
                    <Paragraph style={{ margin: '5px 0', wordBreak: 'break-word' }}>
                      开始时间: {segment.start_time} - 结束时间: {segment.end_time}
                    </Paragraph>
                    {segment.outline && (
                      <Paragraph style={{ margin: '5px 0 0 20px', wordBreak: 'break-word' }}>
                        <Text type="secondary">主题: {segment.outline.title || segment.outline}</Text>
                      </Paragraph>
                    )}
                    {segment.content && segment.content.length > 0 && (
                      <Paragraph style={{ margin: '5px 0 0 20px', wordBreak: 'break-word' }}>
                        <Text italic>内容摘要: {Array.isArray(segment.content) ? segment.content.join('；') : segment.content}</Text>
                      </Paragraph>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <Empty description="暂无时间线数据" />
            )}
          </div>
        </Card>
      )
    },
    {
      key: 'scoring',
      label: '内容评分',
      children: (
        <Card title="AI 内容评分" bordered={true}>
          <div style={{ maxHeight: '600px', overflowY: 'auto', paddingRight: '10px' }}>
            {aiData.scoring.high_score_clips ? (
              <div>
                <Text strong>高评分片段:</Text>
                <ul style={{ marginTop: '10px' }}>
                  {aiData.scoring.high_score_clips.map((clip: any, index: number) => (
                    <li key={index} style={{ marginBottom: '12px', wordBreak: 'break-word' }}>
                      <Text strong>片段 {clip.id || index + 1} (评分: {Math.round(clip.final_score || clip.score)}分)</Text>
                      <Paragraph style={{ margin: '5px 0 0 20px', wordBreak: 'break-word' }}>
                        时间: {clip.start_time} - {clip.end_time}
                      </Paragraph>
                      {clip.recommend_reason && (
                        <Paragraph style={{ margin: '5px 0 0 20px', wordBreak: 'break-word' }}>
                          <Text type="success">推荐理由: {clip.recommend_reason}</Text>
                        </Paragraph>
                      )}
                      {clip.outline && (
                        <Paragraph style={{ margin: '5px 0 0 20px', wordBreak: 'break-word' }}>
                          <Text type="secondary">主题: {clip.outline.title || clip.outline}</Text>
                        </Paragraph>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <Empty description="暂无评分数据" />
            )}
          </div>
        </Card>
      )
    },
    {
      key: 'titles',
      label: '标题生成',
      children: (
        <Card title="AI 生成的标题" bordered={true}>
          <div style={{ maxHeight: '600px', overflowY: 'auto', paddingRight: '10px' }}>
            {aiData.titles.generated_titles ? (
              <div>
                <Text strong>生成的标题列表:</Text>
                <ul style={{ marginTop: '10px' }}>
                  {aiData.titles.generated_titles.map((title: any, index: number) => (
                    <li key={index} style={{ marginBottom: '8px', wordBreak: 'break-word' }}>
                      <Text strong>{index + 1}. {title}</Text>
                    </li>
                  ))}
                </ul>
              </div>
            ) : aiData.clips && aiData.clips.length > 0 ? (
              <div>
                <Text strong>切片标题:</Text>
                <ul style={{ marginTop: '10px' }}>
                  {aiData.clips.map((clip: any, index: number) => (
                    <li key={clip.id} style={{ marginBottom: '8px', wordBreak: 'break-word' }}>
                      <Text strong>{index + 1}. {clip.generated_title || clip.title}</Text>
                      <Paragraph style={{ margin: '5px 0 0 20px', wordBreak: 'break-word' }}>
                        <Text type="secondary">时间: {clip.start_time} - {clip.end_time}</Text>
                      </Paragraph>
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <Empty description="暂无标题数据" />
            )}
          </div>
        </Card>
      )
    },
    {
      key: 'raw',
      label: '原始输出',
      children: (
        <Card title="AI 原始输出" bordered={true}>
          <div style={{ maxHeight: '600px', overflowY: 'auto', paddingRight: '10px' }}>
            {aiData.rawOutputs ? (
              <div>
                {Object.entries(aiData.rawOutputs).map(([key, value]) => (
                  <div key={key} style={{ marginBottom: '16px', paddingBottom: '16px', borderBottom: '1px dashed #f0f0f0', wordBreak: 'break-word' }}>
                    <Text strong>{key}:</Text>
                    <Paragraph style={{ margin: '5px 0 0 20px', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                      {typeof value === 'string' ? value : JSON.stringify(value, null, 2)}
                    </Paragraph>
                  </div>
                ))}
              </div>
            ) : (
              <Empty description="暂无原始输出数据" />
            )}
          </div>
        </Card>
      )
    }
  ]

  return (
    <div style={{ padding: '20px' }}>
      <Title level={2}>AI 响应详情</Title>
      <Divider />
      <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} />
    </div>
  )
}

export default AIResponsePage