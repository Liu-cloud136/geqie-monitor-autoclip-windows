import React, { useState, useEffect, useCallback } from 'react'
import {
  Card,
  Row,
  Col,
  Statistic,
  Table,
  Tag,
  Spin,
  message,
  Button,
  DatePicker,
  Space,
  Empty
} from 'antd'
import {
  CalendarOutlined,
  BarChartOutlined,
  TrophyOutlined,
  HistoryOutlined,
  ReloadOutlined,
  EyeOutlined
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'

import { monitorApiService, DanmakuRecord, TotalStats, DailyStat, TopUser } from '../services/monitorApi'

const MonitorTodayPage: React.FC = () => {
  const [loading, setLoading] = useState(false)
  const [todayData, setTodayData] = useState<DanmakuRecord[]>([])
  const [totalStats, setTotalStats] = useState<TotalStats | null>(null)
  const [dailyStats, setDailyStats] = useState<DailyStat[]>([])
  const [topUsers, setTopUsers] = useState<TopUser[]>([])
  const [selectedDate, setSelectedDate] = useState<string>(dayjs().format('YYYY-MM-DD'))

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [todayRes, statsRes] = await Promise.all([
        monitorApiService.getTodayData(),
        monitorApiService.getStats(7),
      ])

      if (todayRes.success) {
        setTodayData(todayRes.data)
      }

      if (statsRes.success) {
        setTotalStats(statsRes.total_stats)
        setDailyStats(statsRes.daily_stats)
        
        // 安全地处理 recent_data，确保是数组
        const recentData = Array.isArray(statsRes.recent_data) ? statsRes.recent_data : []
        const userCountMap: Record<string, number> = {}
        recentData.forEach((item) => {
          const username = item.username || '未知用户'
          userCountMap[username] = (userCountMap[username] || 0) + 1
        })
        const userList = Object.entries(userCountMap)
          .map(([username, count]) => ({ username, count }))
          .sort((a, b) => b.count - a.count)
          .slice(0, 5)
        setTopUsers(userList)
      }
    } catch (error) {
      console.error('Failed to load today data:', error)
      message.error('加载今日数据失败，请确保监控服务已启动')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  const columns: ColumnsType<DanmakuRecord> = [
    {
      title: '时间',
      dataIndex: 'time_display',
      key: 'time_display',
      width: 120,
    },
    {
      title: '用户',
      dataIndex: 'username',
      key: 'username',
      width: 150,
      render: (text: string) => (
        <Tag color="blue">{text || '未知用户'}</Tag>
      ),
    },
    {
      title: '内容',
      dataIndex: 'content',
      key: 'content',
      ellipsis: true,
    },
    {
      title: '评分',
      dataIndex: 'rating',
      key: 'rating',
      width: 100,
      align: 'center',
      render: (rating: number) => {
        const r = rating ?? 0
        let color = 'default'
        if (r >= 8) color = 'success'
        else if (r >= 5) color = 'warning'
        else color = 'error'
        return <Tag color={color}>{r}分</Tag>
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      align: 'center',
      render: (_, record) => (
        <Button
          type="link"
          size="small"
          icon={<EyeOutlined />}
          onClick={() => {
            if (record.reason) {
              message.info(`不切原因: ${record.reason}`)
            } else {
              message.info('暂无不切原因')
            }
          }}
        >
          详情
        </Button>
      ),
    },
  ]

  const statCardStyle = {
    borderRadius: 12,
    boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
  }

  return (
    <div style={{ padding: '24px' }}>
      <div style={{ marginBottom: 24 }}>
        <Row gutter={16}>
          <Col span={24}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
              <h2 style={{ margin: 0 }}>
                <CalendarOutlined style={{ marginRight: 8, color: '#1890ff' }} />
                今日数据
              </h2>
              <Space>
                <DatePicker
                  value={dayjs(selectedDate)}
                  onChange={(date) => date && setSelectedDate(date.format('YYYY-MM-DD'))}
                  allowClear={false}
                />
                <Button
                  type="primary"
                  icon={<ReloadOutlined />}
                  onClick={loadData}
                  loading={loading}
                >
                  刷新数据
                </Button>
              </Space>
            </div>

            <Row gutter={[16, 16]}>
              <Col xs={12} sm={6}>
                <Card style={statCardStyle}>
                  <Statistic
                    title="今日鸽切"
                    value={totalStats?.today_count ?? todayData.length}
                    prefix={<CalendarOutlined style={{ color: '#52c41a' }} />}
                    valueStyle={{ color: '#52c41a' }}
                  />
                </Card>
              </Col>
              <Col xs={12} sm={6}>
                <Card style={statCardStyle}>
                  <Statistic
                    title="总鸽切次数"
                    value={totalStats?.total_count ?? 0}
                    prefix={<BarChartOutlined style={{ color: '#1890ff' }} />}
                    valueStyle={{ color: '#1890ff' }}
                  />
                </Card>
              </Col>
              <Col xs={12} sm={6}>
                <Card style={statCardStyle}>
                  <Statistic
                    title="本周鸽切"
                    value={totalStats?.week_count ?? 0}
                    prefix={<HistoryOutlined style={{ color: '#faad14' }} />}
                    valueStyle={{ color: '#faad14' }}
                  />
                </Card>
              </Col>
              <Col xs={12} sm={6}>
                <Card style={statCardStyle}>
                  <Statistic
                    title="最活跃用户"
                    value={totalStats?.top_user ?? '-'}
                    prefix={<TrophyOutlined style={{ color: '#722ed1' }} />}
                    valueStyle={{ color: '#722ed1' }}
                  />
                </Card>
              </Col>
            </Row>
          </Col>
        </Row>
      </div>

      <Row gutter={16}>
        <Col xs={24} lg={18}>
          <Card
            title={
              <Space>
                <CalendarOutlined />
                今日记录
              </Space>
            }
            extra={
              <Tag color="blue">
                共 {todayData.length} 条记录
              </Tag>
            }
            style={{ borderRadius: 12 }}
          >
            <Spin spinning={loading}>
              {todayData.length > 0 ? (
                <Table
                  columns={columns}
                  dataSource={todayData}
                  rowKey="id"
                  pagination={{
                    pageSize: 20,
                    showSizeChanger: true,
                    showQuickJumper: true,
                    showTotal: (total) => `共 ${total} 条记录`,
                  }}
                  size="small"
                  scroll={{ x: 600 }}
                />
              ) : (
                <Empty
                  description={
                    <div>
                      <p>暂无今日数据</p>
                      <p style={{ color: '#999', fontSize: 12 }}>请确保监控服务已启动且配置正确</p>
                    </div>
                  }
                />
              )}
            </Spin>
          </Card>
        </Col>

        <Col xs={24} lg={6}>
          <Card
            title={
              <Space>
                <TrophyOutlined />
                活跃用户榜 TOP 5
              </Space>
            }
            style={{ borderRadius: 12, marginBottom: 16 }}
          >
            <Spin spinning={loading}>
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
            </Spin>
          </Card>

          <Card
            title={
              <Space>
                <BarChartOutlined />
                实时统计
              </Space>
            }
            style={{ borderRadius: 12 }}
          >
            <div style={{ textAlign: 'center', padding: '16px 0' }}>
              <div style={{ fontSize: 24, fontWeight: 'bold', color: '#52c41a' }}>
                {totalStats?.today_avg ?? '--'}
              </div>
              <div style={{ color: '#999', fontSize: 12, marginTop: 4 }}>
                今日平均
              </div>
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export default MonitorTodayPage