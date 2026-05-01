import axios from 'axios'

const monitorApi = axios.create({
  baseURL: '/monitor-api/',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

monitorApi.interceptors.request.use(
  (config) => {
    console.log('📊 Monitor API Request:', config.method?.toUpperCase(), config.baseURL + config.url)
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

monitorApi.interceptors.response.use(
  (response) => {
    console.log('✅ Monitor API Response:', response.config.url, 'Status:', response.status)
    return response.data
  },
  (error) => {
    console.error('❌ Monitor API Error:', error)
    return Promise.reject(error)
  }
)

export interface DanmakuRecord {
  id: number
  username: string
  content: string
  time_display: string
  datetime_display: string
  timestamp: number
  rating?: number
  reason?: string
  email_status?: string
  email_sent_time?: string | null
  live_duration?: string
}

export interface TotalStats {
  today_count: number
  total_count: number
  week_count: number
  top_user_count?: number
  top_user?: string
  today_avg?: number
}

export interface DailyStat {
  date: string
  count: number
}

export interface RoomInfo {
  room_id: number
  nickname: string
  enabled: boolean
  live_status: number
  is_live: boolean
  is_monitoring: boolean
  online: number
  room_title?: string
  keyword_count: number
  total_danmaku: number
  db_total_count: number
  db_today_count: number
  db_week_count: number
}

export interface GlobalStats {
  total_rooms: number
  active_rooms: number
  monitoring_rooms: number
  total_danmaku: number
  total_keyword_matches: number
}

export interface MultiRoomStatus {
  success: boolean
  data: {
    global_stats: GlobalStats
    rooms: RoomInfo[]
    is_multi_room_enabled: boolean
  }
}

export interface TopUser {
  username: string
  count: number
}

export const monitorApiService = {
  getTodayData: async (): Promise<{
    success: boolean
    data: DanmakuRecord[]
    count: number
  }> => {
    return monitorApi.get('today')
  },

  getStats: async (days: number = 7): Promise<{
    success: boolean
    total_stats: TotalStats
    daily_stats: DailyStat[]
    recent_data: DanmakuRecord[]
  }> => {
    return monitorApi.get('stats', { params: { days } })
  },

  getDateData: async (dateStr: string): Promise<{
    success: boolean
    data: DanmakuRecord[]
    count: number
  }> => {
    return monitorApi.get(`date/${dateStr}`)
  },

  getHistoryData: async (startDate: string, endDate: string): Promise<{
    success: boolean
    data: DanmakuRecord[]
    count: number
  }> => {
    return monitorApi.get('history', {
      params: { start_date: startDate, end_date: endDate }
    })
  },

  getMultiRoomStatus: async (): Promise<MultiRoomStatus> => {
    return monitorApi.get('multi-room/status')
  },

  getRoomComparison: async (days: number = 7): Promise<{
    success: boolean
    comparison_data: unknown
    keyword_frequency: unknown
    days: number
  }> => {
    return monitorApi.get('multi-room/comparison', { params: { days } })
  },

  getRoomStats: async (roomId: number, days: number = 7): Promise<{
    success: boolean
    room_stats: {
      top_users: TopUser[]
      daily_stats: DailyStat[]
    }
    room_data: DanmakuRecord[]
    keyword_frequency: unknown
    days: number
  }> => {
    return monitorApi.get(`multi-room/${roomId}/stats`, { params: { days } })
  },

  getRoomTodayData: async (roomId: number): Promise<{
    success: boolean
    data: DanmakuRecord[]
    count: number
  }> => {
    return monitorApi.get(`multi-room/${roomId}/today`)
  },

  getRoomInfo: async (): Promise<{
    success: boolean
    room_info: {
      room_id?: number
      room_title?: string
      is_live?: boolean
      online?: number
    }
  }> => {
    return monitorApi.get('room_info')
  },

  getConfig: async (): Promise<{
    success: boolean
    config: Record<string, unknown>
  }> => {
    return monitorApi.get('config')
  },
}

export default monitorApi