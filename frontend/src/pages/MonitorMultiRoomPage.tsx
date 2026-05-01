import React, { useState, useEffect } from 'react'
import {
  Card,
  Row,
  Col,
  Statistic,
  Spin,
  message,
  Button,
  Tabs,
  Tag,
  Modal,
  Table,
  Space,
  Empty,
  Alert
} from 'antd'
import {
  HomeOutlined,
  VideoCameraOutlined,
  BarChartOutlined,
  ReloadOutlined,
  DownloadOutlined,
  EyeOutlined,
  CloseOutlined
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'

import { monitorApiService, RoomInfo, DanmakuRecord, TopUser, DailyStat } from '../services/monitorApi'

const MonitorMultiRoomPage: React.FC = () => {
  const [loading, setLoading] = useState(false)
  const [rooms, setRooms] = useState<RoomInfo[]>([])
  const [globalStats, setGlobalStats] = useState<{
    total_rooms: number
    active_rooms: number
    monitoring_rooms: number
    total_danmaku: number
    total_keyword_matches: number
  } | null>(null)
  const [selectedRoom, setSelectedRoom] = useState<RoomInfo | null>(null)
  const [roomDetailVisible, setRoomDetailVisible] = useState(false)
  const [roomDetailLoading, setRoomDetailLoading] = useState(false)
  const [roomTodayRecords, setRoomTodayRecords] = useState<DanmakuRecord[]>([])
  const [roomTopUsers, setRoomTopUsers] = useState<TopUser[]>([])
  const [activeTab, setActiveTab] = useState('overview')

  const loadRooms = async () => {
    setLoading(true)
    try {
      const result = await monitorApiService.getMultiRoomStatus()
      if (result.success) {
        setRooms(result.data.rooms || [])
        setGlobalStats(result.data.global_stats || null)
      }
    } catch (error) {
      console.error('Failed to load multi-room data:', error)
      message.error('加载多房间数据失败，请确保监控服务已启动')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadRooms()
  }, [])

  const showRoomDetail = async (room: RoomInfo) => {
    setSelectedRoom(room)
    setRoomDetailVisible(true)
    setRoomDetailLoading(true)

    try {
      const [statsRes, todayRes] = await Promise.all([
        monitorApiService.getRoomStats(room.room_id, 7),
        monitorApiService.getRoomTodayData(room.room_id),
      ])

      if (statsRes.success) {
        setRoomTopUsers(statsRes.room_stats?.top_users || [])
      }

      if (todayRes.success) {
        setRoomTodayRecords(todayRes.data)
      }
    } catch (error) {
      console.error('Failed to load room detail:', error)
      message.error('加载房间详情失败')
    } finally {
      setRoomDetailLoading(false)
    }
  }

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
  ]

  const getLiveStatusColor = (isLive: boolean) => {
    return isLive ? '#52c41a' : '#999'
  }

  return (
    <div style={{ padding: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h2 style={{ margin: 0 }}>
          <HomeOutlined style={{ marginRight: 8, color: '#1890ff' }} />
          多房间监控中心
        </h2>
        <Space>
          <Button
            type="primary"
            icon={<ReloadOutlined />}
            onClick={loadRooms}
            loading={loading}
          >
            刷新数据
          </Button>
          <Button
            icon={<DownloadOutlined />}
            onClick={() => message.info('导出功能开发中')}
          >
            导出数据
          </Button>
        </Space>
      </div>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={12} sm={6}>
          <Card style={{ borderRadius: 12, boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}>
            <Statistic
              title="监控房间数"
              value={globalStats?.total_rooms ?? rooms.length}
              prefix={<HomeOutlined style={{ color: '#1890ff' }} />}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card style={{ borderRadius: 12, boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}>
            <Statistic
              title="直播中房间"
              value={globalStats?.active_rooms ?? rooms.filter(r => r.is_live).length}
              prefix={<VideoCameraOutlined style={{ color: '#52c41a' }} />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card style={{ borderRadius: 12, boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}>
            <Statistic
              title="今日总数据"
              value={globalStats?.total_danmaku ?? rooms.reduce((sum, r) => sum + (r.db_today_count || 0), 0)}
              prefix={<BarChartOutlined style={{ color: '#faad14' }} />}
              valueStyle={{ color: '#faad14' }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card style={{ borderRadius: 12, boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}>
            <Statistic
              title="关键词匹配"
              value={globalStats?.total_keyword_matches ?? rooms.reduce((sum, r) => sum + (r.keyword_count || 0), 0)}
              prefix={<EyeOutlined style={{ color: '#722ed1' }} />}
              valueStyle={{ color: '#722ed1' }}
            />
          </Card>
        </Col>
      </Row>

      <Card style={{ borderRadius: 12 }}>
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={[
            {
              key: 'overview',
              label: '概览视图',
              children: (
                <Spin spinning={loading}>
                  {rooms.length > 0 ? (
                    <Row gutter={[16, 16]}>
                      {rooms.map((room) => (
                        <Col xs={24} sm={12} lg={8} key={room.room_id}>
                          <Card
                            hoverable
                            style={{
                              borderRadius: 12,
                              borderLeft: `4px solid ${getLiveStatusColor(room.is_live)}`,
                              cursor: 'pointer',
                            }}
                            onClick={() => showRoomDetail(room)}
                          >
                            <Card.Meta
                              title={
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                  <span style={{ fontWeight: 'bold' }}>
                                    {room.nickname || `直播间 ${room.room_id}`}
                                  </span>
                                  <Tag color={room.is_live ? 'success' : 'default'}>
                                    {room.is_live ? '直播中' : '未开播'}
                                  </Tag>
                                </div>
                              }
                              description={
                                <div style={{ marginTop: 8 }}>
                                  <div style={{ color: '#999', fontSize: 12, marginBottom: 8 }}>
                                    {room.room_title || '暂无标题'}
                                  </div>
                                  <Row gutter={[16, 0]}>
                                    <Col span={8}>
                                      <div style={{ textAlign: 'center' }}>
                                        <div style={{ fontSize: 18, fontWeight: 'bold', color: '#1890ff' }}>
                                          {room.db_today_count || 0}
                                        </div>
                                        <div style={{ fontSize: 11, color: '#999' }}>今日</div>
                                      </div>
                                    </Col>
                                    <Col span={8}>
                                      <div style={{ textAlign: 'center' }}>
                                        <div style={{ fontSize: 18, fontWeight: 'bold', color: '#52c41a' }}>
                                          {room.db_week_count || 0}
                                        </div>
                                        <div style={{ fontSize: 11, color: '#999' }}>本周</div>
                                      </div>
                                    </Col>
                                    <Col span={8}>
                                      <div style={{ textAlign: 'center' }}>
                                        <div style={{ fontSize: 18, fontWeight: 'bold', color: '#faad14' }}>
                                          {room.keyword_count || 0}
                                        </div>
                                        <div style={{ fontSize: 11, color: '#999' }}>关键词</div>
                                      </div>
                                    </Col>
                                  </Row>
                                </div>
                              }
                            />
                          </Card>
                        </Col>
                      ))}
                    </Row>
                  ) : (
                    <Empty
                      description={
                        <div>
                          <p>暂未配置多房间监控</p>
                          <p style={{ color: '#999', fontSize: 12 }}>请确保监控服务已启动且配置了多房间</p>
                        </div>
                      }
                    />
                  )}
                </Spin>
              )
            },
            {
              key: 'comparison',
              label: '对比分析',
              children: (
                <>
                  <Alert
                    message="对比分析功能"
                    description="选择时间范围查看多个房间的数据对比，支持按数据量、关键词占比等指标进行对比分析。"
                    type="info"
                    showIcon
                    style={{ marginBottom: 16 }}
                  />
                  <Empty
                    description={
                      <div>
                        <p>对比分析功能开发中...</p>
                        <p style={{ color: '#999', fontSize: 12 }}>将支持：房间数据对比图表、关键词按房间分布、数据导出等功能</p>
                      </div>
                    }
                  />
                </>
              )
            }
          ]}
        />
      </Card>

      <Modal
        title={
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>
              <VideoCameraOutlined style={{ marginRight: 8 }} />
              {selectedRoom?.nickname || `直播间 ${selectedRoom?.room_id}`} - 房间详情
            </span>
            <Tag color={selectedRoom?.is_live ? 'success' : 'default'}>
              {selectedRoom?.is_live ? '直播中' : '未开播'}
            </Tag>
          </div>
        }
        open={roomDetailVisible}
        onCancel={() => setRoomDetailVisible(false)}
        footer={[
          <Button key="close" onClick={() => setRoomDetailVisible(false)}>
            <CloseOutlined /> 关闭
          </Button>,
        ]}
        width={1000}
      >
        <Spin spinning={roomDetailLoading}>
          {selectedRoom && (
            <>
              <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
                <Col span={6}>
                  <Card size="small">
                    <Statistic title="今日数据" value={selectedRoom.db_today_count || 0} valueStyle={{ color: '#52c41a' }} />
                  </Card>
                </Col>
                <Col span={6}>
                  <Card size="small">
                    <Statistic title="本周数据" value={selectedRoom.db_week_count || 0} valueStyle={{ color: '#1890ff' }} />
                  </Card>
                </Col>
                <Col span={6}>
                  <Card size="small">
                    <Statistic title="总计数据" value={selectedRoom.db_total_count || 0} valueStyle={{ color: '#faad14' }} />
                  </Card>
                </Col>
                <Col span={6}>
                  <Card size="small">
                    <Statistic
                      title="直播状态"
                      value={selectedRoom.is_live ? '直播中' : '未开播'}
                      valueStyle={{ color: selectedRoom.is_live ? '#52c41a' : '#999' }}
                    />
                  </Card>
                </Col>
              </Row>

              <Row gutter={16}>
                <Col span={16}>
                  <Card
                    title={
                      <Space>
                        <BarChartOutlined />
                        今日数据记录
                      </Space>
                    }
                    size="small"
                  >
                    {roomTodayRecords.length > 0 ? (
                      <Table
                        columns={columns}
                        dataSource={roomTodayRecords.slice(0, 10)}
                        rowKey="id"
                        pagination={{
                          total: roomTodayRecords.length,
                          pageSize: 10,
                          showSizeChanger: false,
                        }}
                        size="small"
                        scroll={{ x: 500 }}
                      />
                    ) : (
                      <Empty description="暂无今日数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                    )}
                  </Card>
                </Col>
                <Col span={8}>
                  <Card
                    title={
                      <Space>
                        <BarChartOutlined />
                        活跃用户 TOP 5
                      </Space>
                    }
                    size="small"
                  >
                    {roomTopUsers.length > 0 ? (
                      <div style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                        {roomTopUsers.slice(0, 5).map((user, index) => (
                          <div
                            key={user.username}
                            style={{
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'center',
                              padding: '8px 0',
                              borderBottom: index < Math.min(roomTopUsers.length - 1, 4) ? '1px solid #f0f0f0' : 'none',
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <Tag
                                color={
                                  index === 0 ? 'gold' : index === 1 ? 'silver' : index === 2 ? 'orange' : 'default'
                                }
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
            </>
          )}
        </Spin>
      </Modal>
    </div>
  )
}

export default MonitorMultiRoomPage