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
  Progress,
  Tabs,
  List,
  Divider,
  Badge,
  Tooltip,
  Collapse,
  Radio,
  Select,
  Typography
} from 'antd'

const { Text } = Typography
import {
  BarChartOutlined,
  FireOutlined,
  ReloadOutlined,
  SmileOutlined,
  FrownOutlined,
  MehOutlined,
  WarningOutlined,
  UserOutlined,
  CloudOutlined,
  EyeOutlined,
  CopyOutlined
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import type { TabsProps } from 'antd/es/tabs'
import type { RadioChangeEvent } from 'antd/es/radio'

import { monitorApiService, TotalStats, DailyStat, DanmakuRecord, TopUser } from '../services/monitorApi'

const { Panel } = Collapse

interface RealtimeAnalysisData {
  timestamp: number
  total_danmaku_analyzed: number
  sentiment: {
    last_hour: {
      total: number
      positive: number
      neutral: number
      negative: number
      positive_ratio: number
      neutral_ratio: number
      negative_ratio: number
      avg_sentiment: number
      time_window_seconds: number
    }
    last_5min: {
      total: number
      positive: number
      neutral: number
      negative: number
      positive_ratio: number
      neutral_ratio: number
      negative_ratio: number
      avg_sentiment: number
      time_window_seconds: number
    }
  }
  hot_topics: Array<{
    keyword: string
    count: number
    trend_score: number
  }>
  duplicate_stats: Array<{
    content_hash: string
    content_sample: string
    count: number
    top_users: Array<{ username: string; count: number }>
    first_seen: number
    last_seen: number
    avg_sentiment: number
    time_span: number
  }>
  active_users: Array<{
    username: string
    total_danmaku: number
    positive: number
    neutral: number
    negative: number
    positive_ratio: number
    negative_ratio: number
    top_keywords: Array<{ word: string; count: number }>
    last_seen: number
    avg_sentiment: number
    duplicate_ratio: number
  }>
  suspicious_users: Array<{
    username: string
    risk_score: number
    total_danmaku: number
    avg_sentiment: number
    duplicate_ratio: number
    recent_negative_count: number
    last_seen: number
  }>
  suspicious_count: number
}

const MonitorAnalysisPage: React.FC = () => {
  const [loading, setLoading] = useState(false)
  const [totalStats, setTotalStats] = useState<TotalStats | null>(null)
  const [dailyStats, setDailyStats] = useState<DailyStat[]>([])
  const [topUsers, setTopUsers] = useState<TopUser[]>([])
  const [keywordFrequency, setKeywordFrequency] = useState<Array<{ word: string; count: number }>>([])
  const [realtimeAnalysis, setRealtimeAnalysis] = useState<RealtimeAnalysisData | null>(null)
  const [activeTab, setActiveTab] = useState('overview')
  const [timeWindow, setTimeWindow] = useState<number>(3600)

  const loadData = async () => {
    setLoading(true)
    try {
      const result = await monitorApiService.getStats(7)
      
      if (result.success) {
        setTotalStats(result.total_stats)
        setDailyStats(result.daily_stats || [])
        
        const recentData = result.recent_data || []
        const userCountMap: Record<string, number> = {}
        const keywordMap: Record<string, number> = {}
        
        recentData.forEach((item: DanmakuRecord) => {
          const username = item.username || '未知用户'
          userCountMap[username] = (userCountMap[username] || 0) + 1
          
          const content = item.content || ''
          const words = content.split(/[\s，。！？、；：""''（）【】《》\n\r]+/).filter((w: string) => w.length >= 2)
          words.forEach((word: string) => {
            keywordMap[word] = (keywordMap[word] || 0) + 1
          })
        })
        
        const userList = Object.entries(userCountMap)
          .map(([username, count]) => ({ username, count }))
          .sort((a, b) => b.count - a.count)
          .slice(0, 10)
        setTopUsers(userList)
        
        const keywordList = Object.entries(keywordMap)
          .map(([word, count]) => ({ word, count }))
          .sort((a, b) => b.count - a.count)
          .slice(0, 20)
        setKeywordFrequency(keywordList)
      }

      try {
        const realtimeResult = await monitorApiService.getRealtimeAnalysis()
        if (realtimeResult.success) {
          setRealtimeAnalysis(realtimeResult.data)
        }
      } catch (realtimeError) {
        console.log('实时分析数据获取失败（可能监控服务未启动）:', realtimeError)
      }
    } catch (error) {
      console.error('Failed to load analysis data:', error)
      message.error('加载分析数据失败，请确保监控服务已启动')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const handleTimeWindowChange = (e: RadioChangeEvent) => {
    setTimeWindow(e.target.value)
  }

  const getSentimentColor = (score: number) => {
    if (score >= 0.6) return '#52c41a'
    if (score <= 0.4) return '#ff4d4f'
    return '#faad14'
  }

  const getSentimentLabel = (score: number) => {
    if (score >= 0.6) return '正面'
    if (score <= 0.4) return '负面'
    return '中性'
  }

  const getRiskColor = (score: number) => {
    if (score >= 0.7) return '#ff4d4f'
    if (score >= 0.5) return '#faad14'
    return '#52c41a'
  }

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

  const topKeywords = keywordFrequency.map((kw, idx) => ({
    ...kw,
    rank: idx + 1,
  }))

  const tabItems: TabsProps['items'] = [
    {
      key: 'overview',
      label: '总览',
      children: (
        <Space direction="vertical" style={{ width: '100%' }} size="large">
          <Row gutter={[16, 16]}>
            <Col xs={12} sm={6}>
              <Card style={{ borderRadius: 12, boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}>
                <Statistic
                  title="今日数据"
                  value={totalStats?.today_count ?? 0}
                  valueStyle={{ color: '#52c41a' }}
                />
              </Card>
            </Col>
            <Col xs={12} sm={6}>
              <Card style={{ borderRadius: 12, boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}>
                <Statistic
                  title="本周数据"
                  value={totalStats?.week_count ?? 0}
                  valueStyle={{ color: '#1890ff' }}
                />
              </Card>
            </Col>
            <Col xs={12} sm={6}>
              <Card style={{ borderRadius: 12, boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}>
                <Statistic
                  title="总计数据"
                  value={totalStats?.total_count ?? 0}
                  valueStyle={{ color: '#faad14' }}
                />
              </Card>
            </Col>
            <Col xs={12} sm={6}>
              <Card style={{ borderRadius: 12, boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}>
                <Statistic
                  title="今日平均"
                  value={totalStats?.today_avg ?? '--'}
                  valueStyle={{ color: '#722ed1' }}
                />
              </Card>
            </Col>
          </Row>

          {realtimeAnalysis && (
            <Card title="实时情感分析" style={{ borderRadius: 12 }}>
              <Row gutter={[16, 16]}>
                <Col xs={24} md={12}>
                  <div style={{ marginBottom: 16 }}>
                    <Text strong>最近1小时情感分布</Text>
                  </div>
                  <Row gutter={[16, 8]}>
                    <Col span={8}>
                      <Card size="small" style={{ textAlign: 'center' }}>
                        <SmileOutlined style={{ fontSize: 24, color: '#52c41a' }} />
                        <div style={{ marginTop: 8, fontWeight: 'bold', color: '#52c41a' }}>
                          正面
                        </div>
                        <div style={{ fontSize: 20, fontWeight: 'bold' }}>
                          {realtimeAnalysis.sentiment.last_hour.positive}
                        </div>
                        <Progress
                          percent={Math.round(realtimeAnalysis.sentiment.last_hour.positive_ratio * 100)}
                          size="small"
                          strokeColor="#52c41a"
                          showInfo={false}
                          style={{ marginTop: 8 }}
                        />
                      </Card>
                    </Col>
                    <Col span={8}>
                      <Card size="small" style={{ textAlign: 'center' }}>
                        <MehOutlined style={{ fontSize: 24, color: '#faad14' }} />
                        <div style={{ marginTop: 8, fontWeight: 'bold', color: '#faad14' }}>
                          中性
                        </div>
                        <div style={{ fontSize: 20, fontWeight: 'bold' }}>
                          {realtimeAnalysis.sentiment.last_hour.neutral}
                        </div>
                        <Progress
                          percent={Math.round(realtimeAnalysis.sentiment.last_hour.neutral_ratio * 100)}
                          size="small"
                          strokeColor="#faad14"
                          showInfo={false}
                          style={{ marginTop: 8 }}
                        />
                      </Card>
                    </Col>
                    <Col span={8}>
                      <Card size="small" style={{ textAlign: 'center' }}>
                        <FrownOutlined style={{ fontSize: 24, color: '#ff4d4f' }} />
                        <div style={{ marginTop: 8, fontWeight: 'bold', color: '#ff4d4f' }}>
                          负面
                        </div>
                        <div style={{ fontSize: 20, fontWeight: 'bold' }}>
                          {realtimeAnalysis.sentiment.last_hour.negative}
                        </div>
                        <Progress
                          percent={Math.round(realtimeAnalysis.sentiment.last_hour.negative_ratio * 100)}
                          size="small"
                          strokeColor="#ff4d4f"
                          showInfo={false}
                          style={{ marginTop: 8 }}
                        />
                      </Card>
                    </Col>
                  </Row>
                  <div style={{ marginTop: 16, textAlign: 'center' }}>
                    <Tag color="blue">
                      平均情感分数: {realtimeAnalysis.sentiment.last_hour.avg_sentiment.toFixed(2)}
                    </Tag>
                  </div>
                </Col>
                <Col xs={24} md={12}>
                  <div style={{ marginBottom: 16 }}>
                    <Text strong>最近5分钟情感分布</Text>
                  </div>
                  <Row gutter={[16, 8]}>
                    <Col span={8}>
                      <Card size="small" style={{ textAlign: 'center' }}>
                        <SmileOutlined style={{ fontSize: 24, color: '#52c41a' }} />
                        <div style={{ marginTop: 8, fontWeight: 'bold', color: '#52c41a' }}>
                          正面
                        </div>
                        <div style={{ fontSize: 20, fontWeight: 'bold' }}>
                          {realtimeAnalysis.sentiment.last_5min.positive}
                        </div>
                        <Progress
                          percent={Math.round(realtimeAnalysis.sentiment.last_5min.positive_ratio * 100)}
                          size="small"
                          strokeColor="#52c41a"
                          showInfo={false}
                          style={{ marginTop: 8 }}
                        />
                      </Card>
                    </Col>
                    <Col span={8}>
                      <Card size="small" style={{ textAlign: 'center' }}>
                        <MehOutlined style={{ fontSize: 24, color: '#faad14' }} />
                        <div style={{ marginTop: 8, fontWeight: 'bold', color: '#faad14' }}>
                          中性
                        </div>
                        <div style={{ fontSize: 20, fontWeight: 'bold' }}>
                          {realtimeAnalysis.sentiment.last_5min.neutral}
                        </div>
                        <Progress
                          percent={Math.round(realtimeAnalysis.sentiment.last_5min.neutral_ratio * 100)}
                          size="small"
                          strokeColor="#faad14"
                          showInfo={false}
                          style={{ marginTop: 8 }}
                        />
                      </Card>
                    </Col>
                    <Col span={8}>
                      <Card size="small" style={{ textAlign: 'center' }}>
                        <FrownOutlined style={{ fontSize: 24, color: '#ff4d4f' }} />
                        <div style={{ marginTop: 8, fontWeight: 'bold', color: '#ff4d4f' }}>
                          负面
                        </div>
                        <div style={{ fontSize: 20, fontWeight: 'bold' }}>
                          {realtimeAnalysis.sentiment.last_5min.negative}
                        </div>
                        <Progress
                          percent={Math.round(realtimeAnalysis.sentiment.last_5min.negative_ratio * 100)}
                          size="small"
                          strokeColor="#ff4d4f"
                          showInfo={false}
                          style={{ marginTop: 8 }}
                        />
                      </Card>
                    </Col>
                  </Row>
                  <div style={{ marginTop: 16, textAlign: 'center' }}>
                    <Tag color="purple">
                      平均情感分数: {realtimeAnalysis.sentiment.last_5min.avg_sentiment.toFixed(2)}
                    </Tag>
                  </div>
                </Col>
              </Row>
            </Card>
          )}

          <Row gutter={[16, 16]}>
            <Col xs={24} lg={12}>
              <Card
                title={
                  <Space>
                    <BarChartOutlined />
                    <span>热门关键词 TOP 20</span>
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
                    <UserOutlined />
                    <span>活跃用户 TOP 10</span>
                  </Space>
                }
                style={{ borderRadius: 12 }}
              >
                {topUsers.length > 0 ? (
                  <div style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                    {topUsers.map((user, index) => (
                      <div
                        key={user.username}
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          padding: '12px 0',
                          borderBottom: index < topUsers.length - 1 ? '1px solid #f0f0f0' : 'none',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <Tag
                            color={
                              index === 0 ? 'gold' : index === 1 ? 'silver' : index === 2 ? 'orange' : 'default'
                            }
                            style={{ minWidth: 28, textAlign: 'center' }}
                          >
                            {index + 1}
                          </Tag>
                          <span>{user.username}</span>
                        </div>
                        <Tag color="blue">{user.count}次</Tag>
                      </div>
                    ))}
                  </div>
                ) : (
                  <Empty description="暂无活跃用户数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                )}
              </Card>
            </Col>
          </Row>

          <Card
            title={
              <Space>
                <BarChartOutlined />
                <span>近7日数据统计</span>
              </Space>
            }
            style={{ borderRadius: 12 }}
          >
            {dailyStats.length > 0 ? (
              <Row gutter={[16, 16]}>
                {dailyStats.slice(0, 7).map((stat, idx) => (
                  <Col xs={24} sm={12} md={8} lg={Math.floor(24 / Math.min(dailyStats.length, 7))} key={idx}>
                    <Card size="small" style={{ textAlign: 'center' }}>
                      <div style={{ color: '#999', fontSize: 12, marginBottom: 8 }}>
                        {stat.date}
                      </div>
                      <div style={{ fontSize: 28, fontWeight: 'bold', color: '#1890ff' }}>
                        {stat.count}
                      </div>
                      <Progress
                        percent={
                          dailyStats.length > 0
                            ? Math.round(
                                (stat.count /
                                  Math.max(...dailyStats.map((s) => s.count))) *
                                  100
                              )
                            : 0
                        }
                        size="small"
                        showInfo={false}
                        style={{ marginTop: 8 }}
                      />
                    </Card>
                  </Col>
                ))}
              </Row>
            ) : (
              <Empty description="暂无每日统计数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </Card>
        </Space>
      ),
    },
    {
      key: 'sentiment',
      label: '情感分析',
      children: (
        <Space direction="vertical" style={{ width: '100%' }} size="large">
          <Alert
            message="情感分析说明"
            description={
              <div>
                <p>基于 SnowNLP 库对弹幕内容进行情感倾向分析，帮助您了解观众的情绪变化：</p>
                <ul>
                  <li>正面情绪：观众对内容持积极态度</li>
                  <li>中性情绪：观众态度较为中立</li>
                  <li>负面情绪：观众对内容持消极态度</li>
                </ul>
                <p style={{ color: '#999', fontSize: 12, marginTop: 8 }}>
                  注意：情感分析需要监控服务正在运行，并且安装了 SnowNLP 库。
                </p>
              </div>
            }
            type="info"
            showIcon
            style={{ borderRadius: 12 }}
          />

          <Radio.Group value={timeWindow} onChange={handleTimeWindowChange} style={{ marginBottom: 16 }}>
            <Radio.Button value={300}>最近5分钟</Radio.Button>
            <Radio.Button value={3600}>最近1小时</Radio.Button>
            <Radio.Button value={86400}>最近24小时</Radio.Button>
          </Radio.Group>

          {realtimeAnalysis ? (
            <Row gutter={[16, 16]}>
              <Col xs={24} lg={12}>
                <Card title="情感分布详情" style={{ borderRadius: 12 }}>
                  <Row gutter={[16, 16]}>
                    <Col span={8}>
                      <div style={{ textAlign: 'center', padding: '20px 0' }}>
                        <SmileOutlined style={{ fontSize: 48, color: '#52c41a' }} />
                        <div style={{ marginTop: 16, fontSize: 24, fontWeight: 'bold', color: '#52c41a' }}>
                          {realtimeAnalysis.sentiment.last_hour.positive}
                        </div>
                        <div style={{ color: '#666', marginTop: 8 }}>正面弹幕</div>
                        <div style={{ marginTop: 8, fontSize: 18, fontWeight: 'bold' }}>
                          {Math.round(realtimeAnalysis.sentiment.last_hour.positive_ratio * 100)}%
                        </div>
                      </div>
                    </Col>
                    <Col span={8}>
                      <div style={{ textAlign: 'center', padding: '20px 0' }}>
                        <MehOutlined style={{ fontSize: 48, color: '#faad14' }} />
                        <div style={{ marginTop: 16, fontSize: 24, fontWeight: 'bold', color: '#faad14' }}>
                          {realtimeAnalysis.sentiment.last_hour.neutral}
                        </div>
                        <div style={{ color: '#666', marginTop: 8 }}>中性弹幕</div>
                        <div style={{ marginTop: 8, fontSize: 18, fontWeight: 'bold' }}>
                          {Math.round(realtimeAnalysis.sentiment.last_hour.neutral_ratio * 100)}%
                        </div>
                      </div>
                    </Col>
                    <Col span={8}>
                      <div style={{ textAlign: 'center', padding: '20px 0' }}>
                        <FrownOutlined style={{ fontSize: 48, color: '#ff4d4f' }} />
                        <div style={{ marginTop: 16, fontSize: 24, fontWeight: 'bold', color: '#ff4d4f' }}>
                          {realtimeAnalysis.sentiment.last_hour.negative}
                        </div>
                        <div style={{ color: '#666', marginTop: 8 }}>负面弹幕</div>
                        <div style={{ marginTop: 8, fontSize: 18, fontWeight: 'bold' }}>
                          {Math.round(realtimeAnalysis.sentiment.last_hour.negative_ratio * 100)}%
                        </div>
                      </div>
                    </Col>
                  </Row>
                  <Divider />
                  <div style={{ textAlign: 'center' }}>
                    <Text strong>总体情感倾向：</Text>
                    <Tag
                      color={getSentimentColor(realtimeAnalysis.sentiment.last_hour.avg_sentiment)}
                      style={{ fontSize: 16, padding: '4px 16px' }}
                    >
                      {getSentimentLabel(realtimeAnalysis.sentiment.last_hour.avg_sentiment)}
                      <span style={{ marginLeft: 8 }}>
                        ({realtimeAnalysis.sentiment.last_hour.avg_sentiment.toFixed(2)})
                      </span>
                    </Tag>
                  </div>
                </Card>
              </Col>
              <Col xs={24} lg={12}>
                <Card title="情感趋势对比" style={{ borderRadius: 12 }}>
                  <List
                    dataSource={[
                      {
                        label: '近1小时 vs 近5分钟',
                        desc: '情感变化趋势',
                        hourScore: realtimeAnalysis.sentiment.last_hour.avg_sentiment,
                        minScore: realtimeAnalysis.sentiment.last_5min.avg_sentiment,
                      },
                    ]}
                    renderItem={(item) => (
                      <List.Item>
                        <List.Item.Meta
                          title={item.label}
                          description={
                            <div>
                              <div style={{ marginBottom: 8 }}>
                                <Text>近1小时：</Text>
                                <Tag color={getSentimentColor(item.hourScore)}>
                                  {getSentimentLabel(item.hourScore)} ({item.hourScore.toFixed(2)})
                                </Tag>
                              </div>
                              <div>
                                <Text>近5分钟：</Text>
                                <Tag color={getSentimentColor(item.minScore)}>
                                  {getSentimentLabel(item.minScore)} ({item.minScore.toFixed(2)})
                                </Tag>
                              </div>
                              <div style={{ marginTop: 8 }}>
                                {item.minScore > item.hourScore ? (
                                  <Tag color="success">情绪正在上升 ↑</Tag>
                                ) : item.minScore < item.hourScore ? (
                                  <Tag color="error">情绪正在下降 ↓</Tag>
                                ) : (
                                  <Tag>情绪稳定 →</Tag>
                                )}
                              </div>
                            </div>
                          }
                        />
                      </List.Item>
                    )}
                  />
                </Card>
              </Col>
            </Row>
          ) : (
            <Alert
              message="暂无实时情感分析数据"
              description="请确保监控服务正在运行，并且有弹幕数据正在被分析。"
              type="warning"
              showIcon
              style={{ borderRadius: 12 }}
            />
          )}
        </Space>
      ),
    },
    {
      key: 'topics',
      label: '热门话题',
      children: (
        <Space direction="vertical" style={{ width: '100%' }} size="large">
          <Alert
            message="热门话题分析说明"
            description={
              <div>
                <p>基于 jieba 分词对弹幕内容进行关键词提取和话题分析：</p>
                <ul>
                  <li>热门关键词：出现频率最高的词汇</li>
                  <li>热门话题：结合时间趋势的话题热度分析</li>
                  <li>趋势分数：话题在近期的增长趋势</li>
                </ul>
              </div>
            }
            type="info"
            showIcon
            style={{ borderRadius: 12 }}
          />

          {realtimeAnalysis && realtimeAnalysis.hot_topics.length > 0 ? (
            <Card title="热门话题 TOP 10" style={{ borderRadius: 12 }}>
              <Row gutter={[16, 16]}>
                {realtimeAnalysis.hot_topics.map((topic, index) => (
                  <Col xs={24} sm={12} md={8} lg={6} key={topic.keyword}>
                    <Card
                      size="small"
                      style={{
                        borderRadius: 12,
                        borderLeft: `4px solid ${index === 0 ? '#1890ff' : index === 1 ? '#52c41a' : index === 2 ? '#faad14' : '#d9d9d9'}`,
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
                        <Tag
                          color={
                            index === 0 ? 'gold' : index === 1 ? 'silver' : index === 2 ? 'orange' : 'default'
                          }
                          style={{ marginRight: 8 }}
                        >
                          #{index + 1}
                        </Tag>
                        <Text strong style={{ fontSize: 16 }}>{topic.keyword}</Text>
                      </div>
                      <div style={{ marginBottom: 8 }}>
                        <Text type="secondary">出现次数：</Text>
                        <Text strong style={{ color: '#1890ff' }}>{topic.count}</Text>
                      </div>
                      <div>
                        <Text type="secondary">趋势分数：</Text>
                        <Tag
                          color={topic.trend_score > 0.5 ? 'success' : topic.trend_score > 0.3 ? 'warning' : 'default'}
                        >
                          {(topic.trend_score * 100).toFixed(0)}%
                        </Tag>
                        {topic.trend_score > 0.5 && <FireOutlined style={{ color: '#ff4d4f', marginLeft: 4 }} />}
                      </div>
                    </Card>
                  </Col>
                ))}
              </Row>
            </Card>
          ) : (
            <Alert
              message="暂无热门话题数据"
              description="请确保监控服务正在运行，并且有弹幕数据正在被分析。"
              type="warning"
              showIcon
              style={{ borderRadius: 12 }}
            />
          )}
        </Space>
      ),
    },
    {
      key: 'suspicious',
      label: '可疑行为检测',
      children: (
        <Space direction="vertical" style={{ width: '100%' }} size="large">
          <Alert
            message="可疑行为检测说明"
            description={
              <div>
                <p>系统自动检测潜在的"带节奏"行为和可疑用户：</p>
                <ul>
                  <li>短时间内发送大量重复内容</li>
                  <li>负面情绪倾向的内容在短时间内被大量转发</li>
                  <li>特定用户在短时间内发送大量负面弹幕</li>
                </ul>
                <p style={{ color: '#999', fontSize: 12, marginTop: 8 }}>
                  风险分数越高，表示该用户行为越可疑。
                </p>
              </div>
            }
            type="warning"
            showIcon
            style={{ borderRadius: 12 }}
          />

          {realtimeAnalysis && realtimeAnalysis.suspicious_users.length > 0 ? (
            <Card
              title={
                <Space>
                  <WarningOutlined style={{ color: '#faad14' }} />
                  <span>可疑用户列表</span>
                  <Badge count={realtimeAnalysis.suspicious_count} showZero style={{ backgroundColor: '#faad14' }} />
                </Space>
              }
              style={{ borderRadius: 12 }}
            >
              <List
                dataSource={realtimeAnalysis.suspicious_users}
                renderItem={(user, index) => (
                  <List.Item>
                    <List.Item.Meta
                      avatar={
                        <div
                          style={{
                            width: 48,
                            height: 48,
                            borderRadius: 24,
                            backgroundColor: getRiskColor(user.risk_score),
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: '#fff',
                            fontWeight: 'bold',
                            fontSize: 18,
                          }}
                        >
                          {user.username.charAt(0).toUpperCase()}
                        </div>
                      }
                      title={
                        <Space>
                          <Text strong>{user.username}</Text>
                          <Tag color={user.risk_score >= 0.7 ? 'error' : user.risk_score >= 0.5 ? 'warning' : 'success'}>
                            风险分数: {(user.risk_score * 100).toFixed(0)}%
                          </Tag>
                        </Space>
                      }
                      description={
                        <div>
                          <Space wrap>
                            <Tag>发送弹幕: {user.total_danmaku}条</Tag>
                            <Tag color={getSentimentColor(user.avg_sentiment)}>
                              平均情感: {getSentimentLabel(user.avg_sentiment)}
                            </Tag>
                            <Tag>重复率: {(user.duplicate_ratio * 100).toFixed(0)}%</Tag>
                            {user.recent_negative_count > 0 && (
                              <Tag color="error">近期负面弹幕: {user.recent_negative_count}条</Tag>
                            )}
                          </Space>
                        </div>
                      }
                    />
                  </List.Item>
                )}
              />
            </Card>
          ) : (
            <Alert
              message="未检测到可疑行为"
              description="当前没有检测到可疑的用户行为，系统运行正常。"
              type="success"
              showIcon
              style={{ borderRadius: 12 }}
            />
          )}

          {realtimeAnalysis && realtimeAnalysis.duplicate_stats.length > 0 && (
            <Card
              title={
                <Space>
                  <CopyOutlined />
                  <span>重复弹幕统计 TOP 5</span>
                </Space>
              }
              style={{ borderRadius: 12 }}
            >
              <List
                dataSource={realtimeAnalysis.duplicate_stats.slice(0, 5)}
                renderItem={(item, index) => (
                  <List.Item>
                    <List.Item.Meta
                      title={
                        <Space>
                          <Tag color={index === 0 ? 'gold' : 'default'}>#{index + 1}</Tag>
                          <Text
                            ellipsis
                            style={{ maxWidth: 400 }}
                          >
                            {item.content_sample}
                          </Text>
                        </Space>
                      }
                      description={
                        <div>
                          <Space wrap>
                            <Tag color="blue">重复次数: {item.count}次</Tag>
                            <Tag color={getSentimentColor(item.avg_sentiment)}>
                              平均情感: {getSentimentLabel(item.avg_sentiment)}
                            </Tag>
                            {item.top_users.length > 0 && (
                              <Tag>
                                主要发送用户: {item.top_users.slice(0, 3).map(u => u.username).join(', ')}
                                {item.top_users.length > 3 && ` 等${item.top_users.length}人`}
                              </Tag>
                            )}
                          </Space>
                        </div>
                      }
                    />
                  </List.Item>
                )}
              />
            </Card>
          )}
        </Space>
      ),
    },
  ]

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

      <Spin spinning={loading}>
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={tabItems}
          type="card"
          size="large"
        />
      </Spin>
    </div>
  )
}

export default MonitorAnalysisPage
