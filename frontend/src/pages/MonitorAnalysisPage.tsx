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

import { monitorApiService, TotalStats, DailyStat, DanmakuRecord, TopUser } from '../services/monitorApi'

const MonitorAnalysisPage: React.FC = () => {
  const [loading, setLoading] = useState(false)
  const [totalStats, setTotalStats] = useState<TotalStats | null>(null)
  const [dailyStats, setDailyStats] = useState<DailyStat[]>([])
  const [topUsers, setTopUsers] = useState<TopUser[]>([])
  const [keywordFrequency, setKeywordFrequency] = useState<Array<{ word: string; count: number }>>([])

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
              <li>活跃用户排行</li>
              <li>每日数据统计</li>
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
                  活跃用户 TOP 10
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

        <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
          <Col span={24}>
            <Card
              title={
                <Space>
                  <BarChartOutlined />
                  近7日数据统计
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
          </Col>
        </Row>
      </Spin>
    </div>
  )
}

export default MonitorAnalysisPage