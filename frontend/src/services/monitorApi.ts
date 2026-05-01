/**
 * 弹幕监控 API 服务
 * 用于调用弹幕监控系统 (http://localhost:5000) 的 API
 */

import axios from 'axios'

const MONITOR_BASE_URL = '/monitor-api'

export interface RoomInfo {
  room_id: number
  room_title: string
  live_status: number
  online: number
  api_source: string
}

export interface TodayDataItem {
  id: number
  room_id: number
  username: string
  content: string
  timestamp: number
  rating: number
  time_display: string
  datetime_display: string
  live_duration: string
  email_status: string
  email_sent_time: string | null
}

export interface DailyStats {
  date: string
  count: number
}

export interface TotalStats {
  total_count: number
  today_count: number
  week_count: number
  keyword_count: number
}

export interface MultiRoomConfig {
  enabled: boolean
  rooms: {
    room_id: number
    nickname: string
    enabled: boolean
  }[]
}

export interface MultiRoomStatus {
  global_stats: {
    total_rooms: number
    active_rooms: number
    total_danmaku: number
    total_keyword_matches: number
  }
  rooms: {
    room_id: number
    nickname: string
    enabled: boolean
    live_status: number
    is_live: boolean
    is_monitoring: boolean
    online: number
    room_title: string
    keyword_count: number
    total_danmaku: number
    db_total_count: number
    db_today_count: number
    db_week_count: number
  }[]
  is_multi_room_enabled: boolean
}

const monitorApi = axios.create({
  baseURL: MONITOR_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

monitorApi.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('弹幕监控API请求失败:', error)
    if (error.code === 'ECONNREFUSED' || error.message?.includes('500')) {
      console.warn('弹幕监控服务可能未运行，请确认端口 5000 已启动')
    }
    return Promise.reject(error)
  }
)

export const monitorApiService = {
  async getRoomInfo(forceRefresh = false): Promise<RoomInfo> {
    const url = forceRefresh ? '/room_info/refresh' : '/room_info'
    const response = await monitorApi.get(url)
    return response.data.room_info
  },

  async getTodayData(): Promise<{
    success: boolean
    data: TodayDataItem[]
    count: number
  }> {
    const response = await monitorApi.get('/today')
    return response.data
  },

  async getStats(days = 7): Promise<{
    success: boolean
    total_stats: TotalStats
    daily_stats: DailyStats[]
    recent_data: TodayDataItem[]
  }> {
    const response = await monitorApi.get('/stats', {
      params: { days }
    })
    return response.data
  },

  async getDateData(dateStr: string): Promise<{
    success: boolean
    data: TodayDataItem[]
    count: number
  }> {
    const response = await monitorApi.get(`/date/${dateStr}`)
    return response.data
  },

  async getHistoryData(startDate: string, endDate: string): Promise<{
    success: boolean
    data: TodayDataItem[]
    count: number
  }> {
    const response = await monitorApi.get('/history', {
      params: { start_date: startDate, end_date: endDate }
    })
    return response.data
  },

  async getConfig(): Promise<{
    success: boolean
    config: Record<string, unknown>
    timestamp: number
  }> {
    const response = await monitorApi.get('/config')
    return response.data
  },

  async verifyPassword(password: string): Promise<{
    success: boolean
    message: string
  }> {
    const response = await monitorApi.post('/verify_password', { password })
    return response.data
  },

  async getMultiRoomConfig(): Promise<{
    success: boolean
    config: MultiRoomConfig
  }> {
    const response = await monitorApi.get('/multi-room/config')
    return response.data
  },

  async getMultiRoomStatus(): Promise<{
    success: boolean
    data: MultiRoomStatus
  }> {
    const response = await monitorApi.get('/multi-room/status')
    return response.data
  },

  getMonitorUrl(): string {
    return 'http://localhost:5000'
  },

  openMonitorInNewTab(path?: string): void {
    const baseUrl = this.getMonitorUrl()
    const targetUrl = path ? `${baseUrl}${path}` : baseUrl
    window.open(targetUrl, '_blank', 'noopener,noreferrer')
  },

  openTodayData(): void {
    this.openMonitorInNewTab('/')
  },

  openMultiRoom(): void {
    this.openMonitorInNewTab('/multi-room')
  },

  openAnalysis(): void {
    this.openMonitorInNewTab('/analysis')
  },

  async isMonitorAvailable(): Promise<boolean> {
    try {
      await this.getRoomInfo()
      return true
    } catch (error) {
      return false
    }
  }
}

export default monitorApiService
