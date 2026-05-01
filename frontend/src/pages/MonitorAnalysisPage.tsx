import React, { useState, useEffect } from 'react'
import {
  Card,
  Row,
  Col,
  Spin,
  message,
  Button,
  Tag,
  Table,
  Empty,
  Alert,
  Space,
  Statistic,
  Progress
} from 'antd'
import {
  BarChartOutlined,
  FireOutlined,
  ReloadOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined,
  MinusOutlined
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'

import { monitorApiService } from '../services/monitorApi'

const MonitorAnalysisPage: React.FC = () => {
  const [loading, setLoading] = useState(false)
  const [keywordFrequency, setKeywordFrequency] = useState<Array<{ word: string; count: number }>>([])
  const [sentimentStats, setSentimentStats] = useState<{ positive: number; negative: number; neutral: number } | null>(null)
  const [hourlyDistribution, setHourlyDistribution] = useState<Array<{ hour: number; count: number }>>([])
  const [weeklyDistribution, setWeeklyDistribution] = useState<Array<{ day: string; count: number }>>([])
  const [heatPoints, setHeatPoints] = useState<Array<{
    start_time: number
    end_time: number
    center_time: number
    danmaku_count: number
    density: number
    heat_score: number
    keywords: string[]
    sentiment_score: number
  }>>([])

  const loadData = async () => {
    setLoading(true)
    try {
      const [analysisRes, heatRes] = await Promise.all([
        monitorApiService.getDanmakuAnalysis(),
        monitorApiService.getHeatPoints(),
      ])

      if (analysisRes.success) {
        setKeywordFrequency(analysisRes.keyword_frequency || [])
        setSentimentStats(analysisRes.sentiment_stats)
        setHourlyDistribution(analysisRes.hourly_distribution || [])
        setWeeklyDistribution(analysisRes.weekly_distribution || [])
      }

      if (heatRes.success) {
        setHeatPoints(heatRes.heat_points || [])
      }
    } catch (error) {
      console.error('Failed to load analysis data:', error)
      message.error('加载分析数据失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const formatTime = (seconds: number) => {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    const secs = Math.floor(seconds % 60)
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }

  const getSentimentColor = (score: number) => {
    if (score > 0.6) return '#52c41a'
    if (score < 0.4) return '#ff4d4f'
    return '#faad14'
  }

  const getSentimentIcon = (score: number) => {
    if (score > 0.6) return <ArrowUpOutlined style={{ color: '#52c41a' }} />
    if (score < 0.4) return <ArrowDownOutlined style={{ color: '#ff4d4f' }} />
    return <MinusOutlined style={{ color: '#faad14' }} />
  }

  const heatPointColumns: ColumnsType<typeof heatPoints[0]> = [
    {
      title: '开始时间',
      dataIndex: 'start_time',
      key: 'start_time',
      render: (time: number) => <Tag color="blue">{formatTime(time)}</Tag>,
    },
    {
      title: '结束时间',
      dataIndex: 'end_time',
      key: 'end_time',
      render: (time: number) => <Tag color="cyan">{formatTime(time)}</Tag>,
    },
    {
      title: '弹幕数量',
      dataIndex: 'danmaku_count',
      key: 'danmaku_count',
      align: 'center',
      render: (count: number) => (
        <Tag color={count > 50 ? 'red' : count > 20 ? 'orange' : 'green'}>
          {count}
        </Tag>
      ),
    },
    {
      title: '热度评分',
      dataIndex: 'heat_score',
      key: 'heat_score',
      align: 'center',
      render: (score: number) => (
        <Progress
          percent={Math.round(score * 100)}
          size="small"
          status={score > 0.7 ? 'active' : score > 0.4 ? 'normal' : 'exception'}
        />
      ),
    },
    {
      title: '情感倾向',
      dataIndex: 'sentiment_score',
      key: 'sentiment_score',
      align: 'center',
      render: (score: number) => (
        <Space>
          {getSentimentIcon(score)}
          <span style={{ color: getSentimentColor(score), fontWeight: 'bold' }}>
            {(score * 100).toFixed(1)}%
          </span>
        </Space>
      ),
    },
    {
      title: '关键词',
      dataIndex: 'keywords',
      key: 'keywords',
      render: (keywords: string[]) => (
        <Space size={[4, 4]} wrap>
          {keywords.slice(0, 3).map((kw, idx) => (
            <Tag key={idx} color="purple">{kw}</Tag>
          ))}
          {keywords.length > 3 && <Tag>+{keywords.length - 3}</Tag>}
        </Space>
      ),
    },
  ]

  const keywordColumns: ColumnsType<{ word: string; count: number; rank: number }> = [
    {
      title: '排名',
      dataIndex: 'rank',
      key: 'rank',
      width: 80,
      align: 'center',
      render: (rank: number) => (
        <Tag
          color={
            rank === 1 ? 'gold' : rank === 2 ? 'silver' : rank === 3 ? 'orange' : 'default'
          }
        >
          {rank}
        </Tag>
      ),
    },
    {
      title: '关键词',
      dataIndex: 'word',
      key: 'word',
    },
    {
      title: '出现次数',
      dataIndex: 'count',
      key: 'count',
      align: 'center',
      render: (count: number) => (
        <span style={{ fontWeight: 'bold', color: '#1890ff' }}>
          {count}
        </span>
      ),
    },
  ]

  const topKeywords = keywordFrequency.slice(0, 20).map((kw, idx) => ({
    ...kw,
    rank: idx + 1,
  }))

  const totalSentiment = sentimentStats
    ? sentimentStats.positive + sentimentStats.negative + sentimentStats.neutral
    : 0

  return (
    <div style={{ padding: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h2 style={{ margin: 0 }}>
          <BarChartOutlined style={{ marginRight: 8, color: '#1890ff' }} />
          弹幕分析
        </h2>
        <Button
          type="primary"
          icon={<ReloadOutlined />}
          onClick={loadData}
          loading={loading}
        >
          刷新数据
        </Button>
      </div>

      <Alert
        message="弹幕分析功能说明"
        description={
          <div>
            <p>通过对弹幕数据的深入分析，帮助您了解：</p>
            <ul>
              <li>热门关键词和话题趋势</li>
              <li>观众情感倾向变化</li>
              <li>高热度时段识别</li>
              <li>弹幕分布规律</li>
            </ul>
          </div>
        }
        type="info"
        showIcon
        style={{ marginBottom: 24, borderRadius: 12 }}
      />

      <Spin spinning={loading}>
        <Row gutter={[16, 16]}>
          {sentimentStats && (
            <>
              <Col xs={12} sm={8}>
                <Card style={{ borderRadius: 12, boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}>
                  <Statistic
                    title="正面情感"
                    value={sentimentStats.positive}
                    valueStyle={{ color: '#52c41a' }}
                    suffix={totalSentiment > 0 ? `(${(sentimentStats.positive / totalSentiment * 100).toFixed(1)}%)` : ''}
                  />
                </Card>
              </Col>
              <Col xs={12} sm={8}>
                <Card style={{ borderRadius: 12, boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}>
                  <Statistic
                    title="中性情感"
                    value={sentimentStats.neutral}
                    valueStyle={{ color: '#faad14' }}
                    suffix={totalSentiment > 0 ? `(${(sentimentStats.neutral / totalSentiment * 100).toFixed(1)}%)` : ''}
                  />
                </Card>
              </Col>
              <Col xs={12} sm={8}>
                <Card style={{ borderRadius: 12, boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}>
                  <Statistic
                    title="负面情感"
                    value={sentimentStats.negative}
                    valueStyle={{ color: '#ff4d4f' }}
                    suffix={totalSentiment > 0 ? `(${(sentimentStats.negative / totalSentiment * 100).toFixed(1)}%)` : ''}
                  />
                </Card>
              </Col>
            </>
          )}
        </Row>

        <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
          <Col xs={24} lg={12}>
            <Card
              title={
                <Space>
                  <BarChartOutlined />
                  热门关键词 TOP 20
                </Space>
              }
              style={{ borderRadius: 12 }}
            >
              {topKeywords.length > 0 ? (
                <Table
                  columns={keywordColumns}
                  dataSource={topKeywords}
                  rowKey="word"
                  pagination={false}
                  size="small"
                />
              ) : (
                <Empty description="暂无关键词数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              )}
            </Card>
          </Col>

          <Col xs={24} lg={12}>
            <Card
              title={
                <Space>
                  <BarChartOutlined />
                  时段分布
                </Space>
              }
              style={{ borderRadius: 12 }}
            >
              {hourlyDistribution.length > 0 ? (
                <div>
                  <h4 style={{ marginBottom: 16 }}>24小时分布</h4>
                  <div style={{ maxHeight: 200, overflowY: 'auto' }}>
                    {hourlyDistribution.map((item, idx) => (
                      <div
                        key={idx}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          marginBottom: 8,
                        }}
                      >
                        <Tag style={{ width: 60, textAlign: 'center' }}>
                          {item.hour.toString().padStart(2, '0')}:00
                        </Tag>
                        <div style={{ flex: 1, marginLeft: 12 }}>
                          <Progress
                            percent={
                              hourlyDistribution.length > 0
                                ? Math.round(
                                    (item.count /
                                      Math.max(...hourlyDistribution.map((h) => h.count))) *
                                      100
                                  )
                                : 0
                            }
                            size="small"
                            format={() => <span style={{ color: '#1890ff' }}>{item.count}</span>}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <Empty description="暂无时段分布数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              )}
            </Card>
          </Col>
        </Row>

        <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
          <Col span={24}>
            <Card
              title={
                <Space>
                  <FireOutlined />
                  高热度时段分析
                </Space>
              }
              style={{ borderRadius: 12 }}
            >
              {heatPoints.length > 0 ? (
                <Table
                  columns={heatPointColumns}
                  dataSource={heatPoints}
                  rowKey={(record, idx) => `${record.start_time}-${idx}`}
                  pagination={{
                    pageSize: 10,
                    showSizeChanger: true,
                    showTotal: (total) => `共 ${total} 个高热度时段`,
                  }}
                  scroll={{ x: 800 }}
                />
              ) : (
                <Empty description="暂无高热度时段数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              )}
            </Card>
          </Col>
        </Row>
      </Spin>
    </div>
  )
}

export default MonitorAnalysisPage