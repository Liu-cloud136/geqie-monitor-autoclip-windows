import React, { useState, useEffect } from 'react'
import {
  Card,
  Row,
  Col,
  Statistic,
  Spin,
  Button,
  Tabs,
  Tag,
  Modal,
  Table,
  Space,
  Empty,
  Alert,
  App,
  Select,
  Checkbox,
  Divider,
  Progress,
  Badge,
  Tooltip,
  List,
  Typography,
  Form,
  Input,
  InputNumber,
  Switch,
  message as AntMessage,
} from 'antd'
import {
  HomeOutlined,
  VideoCameraOutlined,
  BarChartOutlined,
  ReloadOutlined,
  DownloadOutlined,
  EyeOutlined,
  CloseOutlined,
  ScissorOutlined,
  FolderOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  SortAscendingOutlined,
  SortDescendingOutlined,
  SettingOutlined,
  EditOutlined,
  DeleteOutlined,
  PlusOutlined,
  SaveOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { sortBy } from 'lodash'

import { monitorApiService, RoomInfo, DanmakuRecord, TopUser, DailyStat } from '../services/monitorApi'

const { Text } = Typography
const { Option } = Select
const { Checkbox: CheckboxComponent } = Checkbox
const { TextArea } = Input

interface ComparisonData {
  room_id: number
  nickname: string
  room_title?: string
  total_count: number
  today_count: number
  week_count: number
  keyword_count: number
  is_live: boolean
}

interface KeywordFreqItem {
  keyword: string
  count: number
  room_distribution: Record<string, number>
}

const MonitorMultiRoomPage: React.FC = () => {
  const { message } = App.useApp()
  const [loading, setLoading] = useState(false)
  const [comparisonLoading, setComparisonLoading] = useState(false)
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
  
  const [comparisonDays, setComparisonDays] = useState(7)
  const [comparisonData, setComparisonData] = useState<ComparisonData[]>([])
  const [keywordFrequency, setKeywordFrequency] = useState<KeywordFreqItem[]>([])
  const [sortField, setSortField] = useState<'today' | 'week' | 'total' | 'keyword'>('today')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')
  
  const [editRoomModalVisible, setEditRoomModalVisible] = useState(false)
  const [editingRoom, setEditingRoom] = useState<RoomInfo | null>(null)
  const [editForm] = Form.useForm()
  const [editLoading, setEditLoading] = useState(false)
  
  const [addRoomModalVisible, setAddRoomModalVisible] = useState(false)
  const [addForm] = Form.useForm()
  const [addLoading, setAddLoading] = useState(false)
  
  const [settingsTab, setSettingsTab] = useState('rooms')

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

  const loadComparisonData = async () => {
    setComparisonLoading(true)
    try {
      const result = await monitorApiService.getRoomComparison(comparisonDays)
      if (result.success) {
        const rawComparison = result.comparison_data as unknown[]
        const processed: ComparisonData[] = (rawComparison || []).map((item: Record<string, unknown>) => ({
          room_id: Number(item.room_id) || 0,
          nickname: String(item.nickname || `直播间 ${item.room_id}`),
          room_title: item.room_title ? String(item.room_title) : undefined,
          total_count: Number(item.total_count || 0),
          today_count: Number(item.today_count || 0),
          week_count: Number(item.week_count || 0),
          keyword_count: Number(item.keyword_count || 0),
          is_live: Boolean(item.is_live),
        }))
        setComparisonData(processed)
        setKeywordFrequency((result.keyword_frequency || []) as KeywordFreqItem[])
      }
    } catch (error) {
      console.error('Failed to load comparison data:', error)
    } finally {
      setComparisonLoading(false)
    }
  }

  useEffect(() => {
    loadRooms()
  }, [])

  useEffect(() => {
    if (activeTab === 'comparison') {
      loadComparisonData()
    }
  }, [activeTab, comparisonDays])

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

  const getRoomDisplayName = (room: RoomInfo | ComparisonData) => {
    if (room.room_title && room.room_title.trim()) {
      return room.room_title
    }
    return (room as RoomInfo).nickname || `直播间 ${room.room_id}`
  }

  const getSortedComparisonData = () => {
    if (comparisonData.length === 0) {
      return (rooms || []).map(room => ({
        room_id: room.room_id,
        nickname: room.nickname,
        room_title: room.room_title,
        total_count: room.db_total_count,
        today_count: room.db_today_count,
        week_count: room.db_week_count,
        keyword_count: room.keyword_count,
        is_live: room.is_live,
      }))
    }
    return sortBy(comparisonData, [
      (item: ComparisonData) => {
        switch (sortField) {
          case 'today': return item.today_count
          case 'week': return item.week_count
          case 'total': return item.total_count
          case 'keyword': return item.keyword_count
          default: return item.today_count
        }
      }
    ], [sortOrder === 'desc' ? 'desc' : 'asc'])
  }

  const toggleSort = (field: 'today' | 'week' | 'total' | 'keyword') => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortOrder('desc')
    }
  }

  const getMaxCount = () => {
    const data = getSortedComparisonData()
    if (data.length === 0) return 1
    return Math.max(...data.map(d => Math.max(d.today_count, d.week_count, d.total_count, d.keyword_count, 1)))
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

  const handleEditRoom = (room: RoomInfo, e: React.MouseEvent) => {
    e.stopPropagation()
    setEditingRoom(room)
    editForm.setFieldsValue({
      nickname: room.nickname,
      enabled: room.enabled,
      auto_clip_enabled: room.auto_clip_enabled,
      record_folder: room.record_folder,
    })
    setEditRoomModalVisible(true)
  }

  const handleSaveEditRoom = async () => {
    if (!editingRoom) return
    
    setEditLoading(true)
    try {
      const values = await editForm.validateFields()
      const result = await monitorApiService.updateRoomConfig(editingRoom.room_id, values)
      
      if (result.success) {
        message.success('房间配置已更新')
        setEditRoomModalVisible(false)
        loadRooms()
      } else {
        message.error('更新失败')
      }
    } catch (error) {
      console.error('Failed to update room:', error)
      message.error('更新房间配置失败')
    } finally {
      setEditLoading(false)
    }
  }

  const handleAddRoom = () => {
    addForm.resetFields()
    setAddRoomModalVisible(true)
  }

  const handleSaveAddRoom = async () => {
    setAddLoading(true)
    try {
      const values = await addForm.validateFields()
      const result = await monitorApiService.addRoom({
        room_id: values.room_id,
        nickname: values.nickname || `直播间 ${values.room_id}`,
        enabled: values.enabled ?? true,
        auto_clip_enabled: values.auto_clip_enabled ?? true,
        record_folder: values.record_folder || '',
      })
      
      if (result.success) {
        message.success('房间已添加')
        setAddRoomModalVisible(false)
        loadRooms()
      } else {
        message.error('添加失败，可能房间已存在')
      }
    } catch (error) {
      console.error('Failed to add room:', error)
      message.error('添加房间失败')
    } finally {
      setAddLoading(false)
    }
  }

  const handleDeleteRoom = async (roomId: number, e: React.MouseEvent) => {
    e.stopPropagation()
    
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除房间 ${roomId} 吗？此操作不可恢复。`,
      okText: '确认删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          const result = await monitorApiService.removeRoom(roomId)
          if (result.success) {
            message.success('房间已删除')
            loadRooms()
          } else {
            message.error('删除失败')
          }
        } catch (error) {
          console.error('Failed to delete room:', error)
          message.error('删除房间失败')
        }
      },
    })
  }

  const handleToggleAutoClip = async (room: RoomInfo, checked: boolean, e: React.MouseEvent) => {
    e.stopPropagation()
    
    try {
      const result = await monitorApiService.updateRoomConfig(room.room_id, {
        auto_clip_enabled: checked,
      })
      
      if (result.success) {
        message.success(checked ? '自动切片已开启' : '自动切片已关闭')
        loadRooms()
      } else {
        message.error('更新失败')
      }
    } catch (error) {
      console.error('Failed to toggle auto clip:', error)
      message.error('更新自动切片状态失败')
    }
  }

  const renderSettingsTab = () => (
    <Spin spinning={loading}>
      <Tabs
        activeKey={settingsTab}
        onChange={setSettingsTab}
        items={[
          {
            key: 'rooms',
            label: '房间管理',
            children: (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                  <Text strong>已配置 {rooms.length} 个房间</Text>
                  <Button
                    type="primary"
                    icon={<PlusOutlined />}
                    onClick={handleAddRoom}
                  >
                    添加房间
                  </Button>
                </div>
                
                <List
                  dataSource={rooms}
                  renderItem={(room) => (
                    <List.Item
                      actions={[
                        <Tooltip key="edit" title="编辑配置">
                          <Button
                            type="text"
                            icon={<EditOutlined />}
                            onClick={(e) => handleEditRoom(room, e)}
                          />
                        </Tooltip>,
                        <Tooltip key="delete" title="删除房间">
                          <Button
                            type="text"
                            danger
                            icon={<DeleteOutlined />}
                            onClick={(e) => handleDeleteRoom(room.room_id, e)}
                          />
                        </Tooltip>,
                      ]}
                    >
                      <List.Item.Meta
                        avatar={
                          <Badge status={room.is_live ? 'success' : 'default'} />
                        }
                        title={
                          <Space>
                            <Text strong>{getRoomDisplayName(room)}</Text>
                            {room.enabled ? (
                              <Tag color="green">已启用</Tag>
                            ) : (
                              <Tag color="default">已禁用</Tag>
                            )}
                            {room.auto_clip_enabled && (
                              <Tag color="green" icon={<ScissorOutlined />}>自动切片</Tag>
                            )}
                          </Space>
                        }
                        description={
                          <Space size={[16, 8]} wrap>
                            <span>房间号: {room.room_id}</span>
                            {room.nickname && <span>昵称: {room.nickname}</span>}
                            <span>今日: {room.db_today_count}</span>
                            <span>本周: {room.db_week_count}</span>
                            {room.record_folder && (
                              <span>
                                <FolderOutlined /> {room.record_folder}
                              </span>
                            )}
                          </Space>
                        }
                      />
                    </List.Item>
                  )}
                />
              </div>
            ),
          },
          {
            key: 'monitor',
            label: '弹幕监控设置',
            children: (
              <div>
                <Alert
                  message="弹幕监控设置"
                  description="这里可以配置弹幕监控的全局设置，包括监控关键词、邮件通知、连接参数等。"
                  type="info"
                  showIcon
                  style={{ marginBottom: 24 }}
                />
                
                <Card title="监控基本设置" size="small" style={{ marginBottom: 16 }}>
                  <Form layout="vertical">
                    <Row gutter={16}>
                      <Col span={12}>
                        <Form.Item label="监控关键词">
                          <Input placeholder="鸽切" disabled />
                        </Form.Item>
                      </Col>
                      <Col span={12}>
                        <Form.Item label="邮件冷却时间（秒）">
                          <InputNumber min={1} max={3600} defaultValue={60} disabled style={{ width: '100%' }} />
                        </Form.Item>
                      </Col>
                    </Row>
                    <Row gutter={16}>
                      <Col span={12}>
                        <Form.Item label="最大重连次数">
                          <InputNumber min={1} max={100} defaultValue={10} disabled style={{ width: '100%' }} />
                        </Form.Item>
                      </Col>
                      <Col span={12}>
                        <Form.Item label="重连延迟（秒）">
                          <InputNumber min={1} max={300} defaultValue={30} disabled style={{ width: '100%' }} />
                        </Form.Item>
                      </Col>
                    </Row>
                  </Form>
                </Card>
                
                <Card title="邮件通知设置" size="small" style={{ marginBottom: 16 }}>
                  <Form layout="vertical">
                    <Form.Item label="邮件通知">
                      <Space>
                        <Tag color="green">直播开始</Tag>
                        <Tag color="green">直播结束</Tag>
                        <Tag color="green">监控启动</Tag>
                      </Space>
                    </Form.Item>
                    <Row gutter={16}>
                      <Col span={12}>
                        <Form.Item label="SMTP服务器">
                          <Input placeholder="smtp.qq.com" disabled />
                        </Form.Item>
                      </Col>
                      <Col span={12}>
                        <Form.Item label="SMTP端口">
                          <InputNumber min={1} max={65535} defaultValue={587} disabled style={{ width: '100%' }} />
                        </Form.Item>
                      </Col>
                    </Row>
                  </Form>
                </Card>
                
                <Alert
                  message="提示"
                  description="当前版本中，弹幕监控设置需要通过修改 config.yaml 文件来完成。未来版本将支持在界面中直接修改这些设置。"
                  type="warning"
                  showIcon
                />
              </div>
            ),
          },
        ]}
      />
    </Spin>
  )

  const renderOverviewTab = () => (
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
                }}
                bodyStyle={{ padding: 16 }}
              >
                <div onClick={() => showRoomDetail(room)} style={{ cursor: 'pointer' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8, marginBottom: 8 }}>
                    <span style={{ fontWeight: 'bold', flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {getRoomDisplayName(room)}
                    </span>
                    <Tag color={room.is_live ? 'success' : 'default'}>
                      {room.is_live ? '直播中' : '未开播'}
                    </Tag>
                  </div>
                  
                  <div style={{ color: '#999', fontSize: 12, marginBottom: 8 }}>
                    {room.nickname && room.nickname !== getRoomDisplayName(room) ? 
                      <span>{room.nickname} | </span> : null}
                    房间号: {room.room_id}
                  </div>
                  
                  <Row gutter={[16, 0]} style={{ marginBottom: 12 }}>
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
                
                <Divider style={{ margin: '8px 0' }} />
                
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Space>
                    <Tooltip title={room.auto_clip_enabled ? '点击关闭自动切片' : '点击开启自动切片'}>
                      <div 
                        style={{ 
                          display: 'flex', 
                          alignItems: 'center', 
                          gap: 6, 
                          cursor: 'pointer',
                          color: room.auto_clip_enabled ? '#52c41a' : '#999'
                        }}
                        onClick={(e) => {
                          e.stopPropagation()
                          handleToggleAutoClip(room, !room.auto_clip_enabled, e)
                        }}
                      >
                        <ScissorOutlined />
                        <span style={{ fontSize: 12 }}>
                          {room.auto_clip_enabled ? '自动切片: 开' : '自动切片: 关'}
                        </span>
                      </div>
                    </Tooltip>
                    {room.record_folder && (
                      <Tooltip title={`录制文件夹: ${room.record_folder}`}>
                        <FolderOutlined style={{ color: '#1890ff' }} />
                      </Tooltip>
                    )}
                  </Space>
                  <Space size={4}>
                    <Tooltip title="编辑配置">
                      <Button
                        type="text"
                        size="small"
                        icon={<EditOutlined />}
                        onClick={(e) => handleEditRoom(room, e)}
                      />
                    </Tooltip>
                  </Space>
                </div>
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

  const renderComparisonTab = () => {
    const sortedData = getSortedComparisonData()
    const maxCount = getMaxCount()

    return (
      <Spin spinning={comparisonLoading}>
        <Alert
          message="对比分析功能"
          description="查看多个房间的数据对比，支持按数据量排序。数据包含今日、本周、总计以及关键词匹配统计。"
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
        />

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, flexWrap: 'wrap', gap: 12 }}>
          <Space>
            <span style={{ color: '#666' }}>时间范围：</span>
            <Select
              value={comparisonDays}
              onChange={setComparisonDays}
              style={{ width: 120 }}
            >
              <Option value={1}>今天</Option>
              <Option value={7}>近7天</Option>
              <Option value={14}>近14天</Option>
              <Option value={30}>近30天</Option>
            </Select>
            <Button
              icon={<ReloadOutlined />}
              onClick={loadComparisonData}
            >
              刷新
            </Button>
          </Space>
          <Space>
            <Text type="secondary">排序方式：</Text>
            <Select
              value={sortField}
              onChange={(v: 'today' | 'week' | 'total' | 'keyword') => {
                setSortField(v)
                setSortOrder('desc')
              }}
              style={{ width: 100 }}
            >
              <Option value="today">今日</Option>
              <Option value="week">本周</Option>
              <Option value="total">总计</Option>
              <Option value="keyword">关键词</Option>
            </Select>
            <Button
              icon={sortOrder === 'asc' ? <SortAscendingOutlined /> : <SortDescendingOutlined />}
              onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
            >
              {sortOrder === 'asc' ? '升序' : '降序'}
            </Button>
          </Space>
        </div>

        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          <Col xs={12} sm={6}>
            <Card size="small" style={{ borderRadius: 8 }}>
              <Statistic
                title="房间总数"
                value={sortedData.length || rooms.length}
                prefix={<HomeOutlined style={{ color: '#1890ff' }} />}
              />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card size="small" style={{ borderRadius: 8 }}>
              <Statistic
                title="直播中"
                value={sortedData.filter(d => d.is_live).length || rooms.filter(r => r.is_live).length}
                prefix={<VideoCameraOutlined style={{ color: '#52c41a' }} />}
                valueStyle={{ color: '#52c41a' }}
              />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card size="small" style={{ borderRadius: 8 }}>
              <Statistic
                title="今日总数据"
                value={sortedData.reduce((s, d) => s + d.today_count, 0) || rooms.reduce((s, r) => s + (r.db_today_count || 0), 0)}
                prefix={<BarChartOutlined style={{ color: '#1890ff' }} />}
              />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card size="small" style={{ borderRadius: 8 }}>
              <Statistic
                title="本周总数据"
                value={sortedData.reduce((s, d) => s + d.week_count, 0) || rooms.reduce((s, r) => s + (r.db_week_count || 0), 0)}
                prefix={<EyeOutlined style={{ color: '#722ed1' }} />}
              />
            </Card>
          </Col>
        </Row>

        <Card title="房间数据对比" size="small" style={{ marginBottom: 16, borderRadius: 8 }}>
          {sortedData.length > 0 ? (
            <List
              dataSource={sortedData}
              renderItem={(item, index) => (
                <List.Item
                  style={{ padding: '12px 0', borderBottom: index < sortedData.length - 1 ? '1px solid #f0f0f0' : 'none' }}
                >
                  <div style={{ width: '100%' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <Space>
                        <Tag
                          color={index === 0 ? 'gold' : index === 1 ? 'silver' : index === 2 ? 'orange' : 'default'}
                          style={{ minWidth: 32, textAlign: 'center' }}
                        >
                          {index + 1}
                        </Tag>
                        <Badge status={item.is_live ? 'success' : 'default'} />
                        <Text strong>{getRoomDisplayName(item)}</Text>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          ({item.nickname || item.room_id})
                        </Text>
                      </Space>
                      <Space>
                        <Tag color="blue">今日: {item.today_count}</Tag>
                        <Tag color="green">本周: {item.week_count}</Tag>
                        <Tag color="orange">总计: {item.total_count}</Tag>
                      </Space>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 16px' }}>
                      <div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                          <Text type="secondary" style={{ fontSize: 12 }}>今日数据</Text>
                          <Text strong style={{ fontSize: 12 }}>{item.today_count}</Text>
                        </div>
                        <Progress
                          percent={maxCount > 0 ? Math.round((item.today_count / maxCount) * 100) : 0}
                          showInfo={false}
                          strokeColor="#1890ff"
                          size="small"
                        />
                      </div>
                      <div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                          <Text type="secondary" style={{ fontSize: 12 }}>本周数据</Text>
                          <Text strong style={{ fontSize: 12 }}>{item.week_count}</Text>
                        </div>
                        <Progress
                          percent={maxCount > 0 ? Math.round((item.week_count / maxCount) * 100) : 0}
                          showInfo={false}
                          strokeColor="#52c41a"
                          size="small"
                        />
                      </div>
                      <div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                          <Text type="secondary" style={{ fontSize: 12 }}>总计数据</Text>
                          <Text strong style={{ fontSize: 12 }}>{item.total_count}</Text>
                        </div>
                        <Progress
                          percent={maxCount > 0 ? Math.round((item.total_count / maxCount) * 100) : 0}
                          showInfo={false}
                          strokeColor="#faad14"
                          size="small"
                        />
                      </div>
                      <div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                          <Text type="secondary" style={{ fontSize: 12 }}>关键词匹配</Text>
                          <Text strong style={{ fontSize: 12 }}>{item.keyword_count}</Text>
                        </div>
                        <Progress
                          percent={maxCount > 0 ? Math.round((item.keyword_count / maxCount) * 100) : 0}
                          showInfo={false}
                          strokeColor="#722ed1"
                          size="small"
                        />
                      </div>
                    </div>
                  </div>
                </List.Item>
              )}
            />
          ) : (
            <Empty description="暂无对比数据" />
          )}
        </Card>

        {keywordFrequency.length > 0 && (
          <Card title="关键词分布（按房间）" size="small" style={{ borderRadius: 8 }}>
            <List
              dataSource={keywordFrequency.slice(0, 20)}
              renderItem={(item, index) => (
                <List.Item>
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Space>
                        <Tag color="blue">{index + 1}</Tag>
                        <Text strong>{item.keyword}</Text>
                      </Space>
                      <Tag color="orange">总计: {item.count}</Tag>
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                      {Object.entries(item.room_distribution || {}).slice(0, 5).map(([roomName, count]) => (
                        <Tag key={roomName}>{roomName}: {count}</Tag>
                      ))}
                      {Object.keys(item.room_distribution || {}).length > 5 && (
                        <Tag color="default">+{Object.keys(item.room_distribution || {}).length - 5} 个房间</Tag>
                      )}
                    </div>
                  </Space>
                </List.Item>
              )}
            />
          </Card>
        )}
      </Spin>
    )
  }

  return (
    <div style={{ padding: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24, flexWrap: 'wrap', gap: 12 }}>
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
              children: renderOverviewTab(),
            },
            {
              key: 'comparison',
              label: '对比分析',
              children: renderComparisonTab(),
            },
            {
              key: 'settings',
              label: (
                <span>
                  <SettingOutlined style={{ marginRight: 4 }} />
                  设置
                </span>
              ),
              children: renderSettingsTab(),
            },
          ]}
        />
      </Card>

      <Modal
        title="编辑房间配置"
        open={editRoomModalVisible}
        onCancel={() => setEditRoomModalVisible(false)}
        footer={[
          <Button key="cancel" onClick={() => setEditRoomModalVisible(false)}>
            取消
          </Button>,
          <Button 
            key="save" 
            type="primary" 
            icon={<SaveOutlined />}
            onClick={handleSaveEditRoom}
            loading={editLoading}
          >
            保存
          </Button>,
        ]}
        width={600}
      >
        <Form
          form={editForm}
          layout="vertical"
          style={{ marginTop: 16 }}
        >
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item label="房间ID">
                <InputNumber 
                  value={editingRoom?.room_id} 
                  disabled 
                  style={{ width: '100%' }}
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="nickname" label="主播昵称">
                <Input placeholder="请输入主播昵称" />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="enabled" label="启用监控" valuePropName="checked">
            <Switch 
              checkedChildren="已启用" 
              unCheckedChildren="已禁用"
            />
          </Form.Item>
          <Form.Item name="auto_clip_enabled" label="自动切片" valuePropName="checked">
            <Switch 
              checkedChildren="已开启" 
              unCheckedChildren="已关闭"
            />
          </Form.Item>
          <Form.Item name="record_folder" label="录制文件夹路径">
            <Input placeholder="请输入录制文件夹的完整路径（可选）" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="添加新房间"
        open={addRoomModalVisible}
        onCancel={() => setAddRoomModalVisible(false)}
        footer={[
          <Button key="cancel" onClick={() => setAddRoomModalVisible(false)}>
            取消
          </Button>,
          <Button 
            key="save" 
            type="primary" 
            icon={<PlusOutlined />}
            onClick={handleSaveAddRoom}
            loading={addLoading}
          >
            添加
          </Button>,
        ]}
        width={600}
      >
        <Alert
          message="提示"
          description="请输入B站直播间的房间号（不是用户UID）。房间号可以在直播间URL中找到，例如：https://live.bilibili.com/22391541 中的 22391541。"
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
        />
        <Form
          form={addForm}
          layout="vertical"
        >
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item 
                name="room_id" 
                label="房间号" 
                rules={[{ required: true, message: '请输入房间号' }]}
              >
                <InputNumber 
                  placeholder="请输入房间号"
                  style={{ width: '100%' }}
                  min={1}
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="nickname" label="主播昵称">
                <Input placeholder="请输入主播昵称（可选）" />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="enabled" label="启用监控" valuePropName="checked" initialValue={true}>
            <Switch 
              checkedChildren="已启用" 
              unCheckedChildren="已禁用"
            />
          </Form.Item>
          <Form.Item name="auto_clip_enabled" label="自动切片" valuePropName="checked" initialValue={true}>
            <Switch 
              checkedChildren="已开启" 
              unCheckedChildren="已关闭"
            />
          </Form.Item>
          <Form.Item name="record_folder" label="录制文件夹路径">
            <Input placeholder="请输入录制文件夹的完整路径（可选）" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
            <span>
              <VideoCameraOutlined style={{ marginRight: 8 }} />
              {getRoomDisplayName(selectedRoom as RoomInfo)} - 房间详情
            </span>
            <Space>
              {selectedRoom?.auto_clip_enabled && (
                <Tag color="green" icon={<ScissorOutlined />}>
                  自动切片已开启
                </Tag>
              )}
              {selectedRoom?.record_folder && (
                <Tag color="blue" icon={<FolderOutlined />}>
                  监控: {selectedRoom.record_folder}
                </Tag>
              )}
              <Tag color={selectedRoom?.is_live ? 'success' : 'default'}>
                {selectedRoom?.is_live ? '直播中' : '未开播'}
              </Tag>
            </Space>
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

              {selectedRoom.nickname && (
                <Alert
                  message={
                    <Space>
                      <Text strong>主播名称:</Text>
                      <Text>{selectedRoom.nickname}</Text>
                      <Text type="secondary">|</Text>
                      <Text strong>房间号:</Text>
                      <Text>{selectedRoom.room_id}</Text>
                    </Space>
                  }
                  type="info"
                  showIcon
                  style={{ marginBottom: 16 }}
                />
              )}

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
