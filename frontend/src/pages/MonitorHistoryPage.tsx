import React, { useState, useEffect } from 'react'
import {
  Card,
  DatePicker,
  Table,
  Tag,
  Spin,
  Button,
  Space,
  Row,
  Col,
  Statistic,
  Empty,
  Pagination,
  Modal,
  Radio,
  Select,
  Divider,
  App
} from 'antd'
import {
  HistoryOutlined,
  ReloadOutlined,
  DownloadOutlined,
  CalendarOutlined,
  EyeOutlined,
  FileExcelOutlined,
  FileTextOutlined,
  FilePdfOutlined
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import type { RadioChangeEvent } from 'antd/es/radio'
import dayjs from 'dayjs'

import { monitorApiService, DanmakuRecord } from '../services/monitorApi'

const MonitorHistoryPage: React.FC = () => {
  const { message } = App.useApp()
  const [loading, setLoading] = useState(false)
  const [selectedDate, setSelectedDate] = useState<string>(dayjs().format('YYYY-MM-DD'))
  const [records, setRecords] = useState<DanmakuRecord[]>([])
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  
  const [exportModalVisible, setExportModalVisible] = useState(false)
  const [exportFormat, setExportFormat] = useState<'excel' | 'csv' | 'pdf'>('excel')
  const [exportDateRange, setExportDateRange] = useState<'today' | '7days' | '14days' | '30days' | 'all' | 'custom'>('today')
  const [exportStartDate, setExportStartDate] = useState<string>('')
  const [exportEndDate, setExportEndDate] = useState<string>('')
  const [exporting, setExporting] = useState(false)

  const loadHistoryData = async () => {
    if (!selectedDate) {
      message.warning('请选择日期')
      return
    }

    setLoading(true)
    try {
      const result = await monitorApiService.getDateData(selectedDate)
      if (result.success) {
        setRecords(result.data)
      }
    } catch (error) {
      console.error('Failed to load history data:', error)
      message.error('加载历史数据失败，请确保监控服务已启动')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadHistoryData()
  }, [selectedDate])

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
      title: '创建时间',
      dataIndex: 'datetime_display',
      key: 'datetime_display',
      width: 180,
      render: (time: string) => (
        <span style={{ color: '#999', fontSize: 12 }}>
          {time || '-'}
        </span>
      ),
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

  const handleExport = () => {
    setExportModalVisible(true)
  }

  const handleFormatChange = (e: RadioChangeEvent) => {
    setExportFormat(e.target.value as 'excel' | 'csv' | 'pdf')
  }

  const handleDateRangeChange = (value: string) => {
    setExportDateRange(value as 'today' | '7days' | '14days' | '30days' | 'all' | 'custom')
  }

  const downloadFile = (blob: Blob, filename: string) => {
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  }

  const handleExportConfirm = async () => {
    setExporting(true)
    try {
      let startDate: string | undefined
      let endDate: string | undefined
      let dateRange: 'today' | '7days' | '14days' | '30days' | 'all' | 'custom' = exportDateRange

      if (exportDateRange === 'custom') {
        if (!exportStartDate || !exportEndDate) {
          message.warning('请选择开始日期和结束日期')
          setExporting(false)
          return
        }
        startDate = exportStartDate
        endDate = exportEndDate
      } else if (exportDateRange === 'today') {
        startDate = selectedDate
        endDate = selectedDate
      }

      const blob = await monitorApiService.exportData({
        format: exportFormat,
        dateRange: dateRange,
        startDate: startDate,
        endDate: endDate,
        metricBasic: true,
        metricRating: true,
        metricRoom: true,
        metricCharts: true,
        metricStats: true
      })

      const extensions: Record<string, string> = {
        excel: 'xlsx',
        csv: 'csv',
        pdf: 'pdf'
      }
      const filename = `export_${dayjs().format('YYYYMMDD_HHmmss')}.${extensions[exportFormat]}`
      
      downloadFile(blob, filename)
      message.success('导出成功')
      setExportModalVisible(false)
    } catch (error) {
      console.error('导出失败:', error)
      message.error('导出失败，请确保监控服务已启动并安装了导出依赖')
    } finally {
      setExporting(false)
    }
  }

  const paginatedRecords = records.slice(
    (currentPage - 1) * pageSize,
    currentPage * pageSize
  )

  return (
    <div style={{ padding: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h2 style={{ margin: 0 }}>
          <HistoryOutlined style={{ marginRight: 8, color: '#1890ff' }} />
          历史数据查询
        </h2>
        <Space>
          <Button
            icon={<DownloadOutlined />}
            onClick={handleExport}
          >
            导出数据
          </Button>
        </Space>
      </div>

      <Card style={{ borderRadius: 12, marginBottom: 24 }}>
        <Row gutter={[16, 16]} align="middle">
          <Col xs={24} sm={12}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <CalendarOutlined style={{ fontSize: 24, color: '#1890ff' }} />
              <div>
                <div style={{ color: '#999', fontSize: 12, marginBottom: 4 }}>选择日期</div>
                <DatePicker
                  value={dayjs(selectedDate)}
                  onChange={(date) => {
                    if (date) {
                      setSelectedDate(date.format('YYYY-MM-DD'))
                      setCurrentPage(1)
                    }
                  }}
                  allowClear={false}
                  style={{ width: 200 }}
                  size="large"
                />
              </div>
            </div>
          </Col>
          <Col xs={24} sm={12}>
            <div style={{ textAlign: 'right' }}>
              <Button
                type="primary"
                icon={<ReloadOutlined />}
                onClick={loadHistoryData}
                loading={loading}
                size="large"
              >
                查询数据
              </Button>
            </div>
          </Col>
        </Row>
      </Card>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={12} sm={6}>
          <Card style={{ borderRadius: 12, boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}>
            <Statistic
              title="查询日期"
              value={selectedDate}
              prefix={<CalendarOutlined style={{ color: '#1890ff' }} />}
              valueStyle={{ color: '#1890ff', fontSize: 20 }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card style={{ borderRadius: 12, boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}>
            <Statistic
              title="数据总数"
              value={records.length}
              prefix={<HistoryOutlined style={{ color: '#52c41a' }} />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card style={{ borderRadius: 12, boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}>
            <Statistic
              title="当前页"
              value={currentPage}
              suffix={`/ ${Math.ceil(records.length / pageSize) || 1}`}
              prefix={<EyeOutlined style={{ color: '#faad14' }} />}
              valueStyle={{ color: '#faad14' }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card style={{ borderRadius: 12, boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}>
            <Statistic
              title="每页显示"
              value={pageSize}
              suffix="条"
              prefix={<HistoryOutlined style={{ color: '#722ed1' }} />}
              valueStyle={{ color: '#722ed1' }}
            />
          </Card>
        </Col>
      </Row>

      <Card style={{ borderRadius: 12 }}>
        <Spin spinning={loading}>
          {records.length > 0 ? (
            <>
              <Table
                columns={columns}
                dataSource={paginatedRecords}
                rowKey="id"
                pagination={false}
                size="small"
                scroll={{ x: 800 }}
              />
              <div style={{ marginTop: 16, textAlign: 'right' }}>
                <Pagination
                  current={currentPage}
                  pageSize={pageSize}
                  total={records.length}
                  showSizeChanger
                  showQuickJumper
                  showTotal={(total) => `共 ${total} 条记录`}
                  onChange={(page, size) => {
                    setCurrentPage(page)
                    setPageSize(size)
                  }}
                />
              </div>
            </>
          ) : (
            <Empty
              description={
                <div>
                  <p>该日期暂无历史数据</p>
                  <p style={{ color: '#999', fontSize: 12 }}>请选择其他日期查询</p>
                </div>
              }
            />
          )}
        </Spin>
      </Card>

      <Modal
        title={
          <Space>
            <DownloadOutlined />
            <span>数据导出</span>
          </Space>
        }
        open={exportModalVisible}
        onCancel={() => setExportModalVisible(false)}
        footer={[
          <Button
            key="cancel"
            onClick={() => setExportModalVisible(false)}
          >
            取消
          </Button>,
          <Button
            key="export"
            type="primary"
            icon={<DownloadOutlined />}
            onClick={handleExportConfirm}
            loading={exporting}
          >
            开始导出
          </Button>
        ]}
        width={600}
      >
        <Divider orientation="left">导出格式</Divider>
        <Radio.Group value={exportFormat} onChange={handleFormatChange}>
          <Space direction="vertical" style={{ width: '100%' }}>
            <Radio.Button value="excel" style={{ height: 60, display: 'flex', alignItems: 'center', padding: '0 24px' }}>
              <Space>
                <FileExcelOutlined style={{ fontSize: 24, color: '#52c41a' }} />
                <div>
                  <div style={{ fontWeight: 600 }}>Excel (.xlsx)</div>
                  <div style={{ fontSize: 12, color: '#999' }}>适合数据处理和分析</div>
                </div>
              </Space>
            </Radio.Button>
            <Radio.Button value="csv" style={{ height: 60, display: 'flex', alignItems: 'center', padding: '0 24px' }}>
              <Space>
                <FileTextOutlined style={{ fontSize: 24, color: '#1890ff' }} />
                <div>
                  <div style={{ fontWeight: 600 }}>CSV (.csv)</div>
                  <div style={{ fontSize: 12, color: '#999' }}>通用格式，兼容性最好</div>
                </div>
              </Space>
            </Radio.Button>
            <Radio.Button value="pdf" style={{ height: 60, display: 'flex', alignItems: 'center', padding: '0 24px' }}>
              <Space>
                <FilePdfOutlined style={{ fontSize: 24, color: '#ff4d4f' }} />
                <div>
                  <div style={{ fontWeight: 600 }}>PDF (.pdf)</div>
                  <div style={{ fontSize: 12, color: '#999' }}>适合报告和分享</div>
                </div>
              </Space>
            </Radio.Button>
          </Space>
        </Radio.Group>

        <Divider orientation="left" style={{ marginTop: 24 }}>时间范围</Divider>
        <Select
          value={exportDateRange}
          onChange={handleDateRangeChange}
          style={{ width: '100%', marginBottom: 16 }}
          options={[
            { value: 'today', label: '今天' },
            { value: '7days', label: '最近7天' },
            { value: '14days', label: '最近14天' },
            { value: '30days', label: '最近30天' },
            { value: 'all', label: '全部数据' },
            { value: 'custom', label: '自定义日期范围' }
          ]}
        />

        {exportDateRange === 'custom' && (
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col span={12}>
              <div style={{ marginBottom: 4, color: '#666', fontSize: 12 }}>开始日期</div>
              <DatePicker
                value={exportStartDate ? dayjs(exportStartDate) : null}
                onChange={(date) => setExportStartDate(date ? date.format('YYYY-MM-DD') : '')}
                style={{ width: '100%' }}
              />
            </Col>
            <Col span={12}>
              <div style={{ marginBottom: 4, color: '#666', fontSize: 12 }}>结束日期</div>
              <DatePicker
                value={exportEndDate ? dayjs(exportEndDate) : null}
                onChange={(date) => setExportEndDate(date ? date.format('YYYY-MM-DD') : '')}
                style={{ width: '100%' }}
              />
            </Col>
          </Row>
        )}

        <Divider orientation="left" style={{ marginTop: 24 }}>导出说明</Divider>
        <div style={{ color: '#666', fontSize: 13, lineHeight: 1.6 }}>
          <p>• Excel 和 CSV 格式包含所有数据字段</p>
          <p>• PDF 格式包含统计摘要和可视化图表</p>
          <p>• 导出功能需要监控服务已启动</p>
          <p>• PDF 导出需要安装 reportlab 库</p>
        </div>
      </Modal>
    </div>
  )
}

export default MonitorHistoryPage