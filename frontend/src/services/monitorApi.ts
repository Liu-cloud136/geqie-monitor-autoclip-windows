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

export interface TodayStats {
  today_count: number
  total_count: number
  week_count: number
  top_user_count: number
  today_avg: number
}

export interface DanmakuRecord {
  id: number
  username: string
  content: string
  time_display: string
  rating: number
  created_at: string
  reason?: string
}

export interface TopUser {
  username: string
  count: number
}

export interface DailyStat {
  date: string
  count: number
}

export interface RoomInfo {
  room_id: number
  nickname: string
  is_live: boolean
  room_title: string
  db_today_count: number
  db_week_count: number
  db_total_count: number
  keyword_count: number
}

export interface GlobalStats {
  active_rooms: number
  total_danmaku: number
  total_keyword_matches: number
}

export interface MultiRoomStatus {
  success: boolean
  data: {
    rooms: RoomInfo[]
    global_stats: GlobalStats
  }
}

export const monitorApiService = {
  getTodayStats: async (): Promise<TodayStats> => {
    return monitorApi.get('today/stats')
  },

  getTodayRecords: async (page: number = 1, limit: number = 50): Promise<{
    success: boolean
    data: DanmakuRecord[]
    total: number
    page: number
    limit: number
  }> => {
    return monitorApi.get('today/records', { params: { page, limit } })
  },

  getTopUsers: async (limit: number = 10): Promise<TopUser[]> => {
    return monitorApi.get('today/top-users', { params: { limit } })
  },

  getDailyStats: async (days: number = 7): Promise<DailyStat[]> => {
    return monitorApi.get('stats/daily', { params: { days } })
  },

  getHistoryData: async (date: string, page: number = 1, limit: number = 50): Promise<{
    success: boolean
    data: DanmakuRecord[]
    total: number
    page: number
    limit: number
  }> => {
    return monitorApi.get('history/records', { params: { date, page, limit } })
  },

  getMultiRoomStatus: async (): Promise<MultiRoomStatus> => {
    return monitorApi.get('multi-room/status')
  },

  getRoomStats: async (roomId: number, days: number = 7): Promise<{
    success: boolean
    room_stats: {
      top_users: TopUser[]
      daily_stats: DailyStat[]
    }
  }> => {
    return monitorApi.get(`multi-room/${roomId}/stats`, { params: { days } })
  },

  getRoomTodayRecords: async (roomId: number): Promise<{
    success: boolean
    data: DanmakuRecord[]
  }> => {
    return monitorApi.get(`multi-room/${roomId}/today`)
  },

  getComparisonData: async (days: number = 7): Promise<{
    success: boolean
    comparison_data: {
      comparison_data: Array<{
        room_id: number
        room_title: string
        total_count: number
        keyword_ratio: number
        daily_data: DailyStat[]
      }>
    }
    keyword_frequency: {
      all_keywords: Array<{ keyword: string; count: number }>
      room_keywords: Array<{
        room_id: number
        room_title: string
        total_danmaku: number
        keywords: Array<{ keyword: string; count: number }>
      }>
    }
  }> => {
    return monitorApi.get('multi-room/comparison', { params: { days } })
  },

  getDanmakuAnalysis: async (): Promise<{
    success: boolean
    keyword_frequency: Array<{ word: string; count: number }>
    sentiment_stats: {
      positive: number
      negative: number
      neutral: number
    }
    hourly_distribution: Array<{ hour: number; count: number }>
    weekly_distribution: Array<{ day: string; count: number }>
  }> => {
    return monitorApi.get('analysis/stats')
  },

  getHeatPoints: async (): Promise<{
    success: boolean
    heat_points: Array<{
      start_time: number
      end_time: number
      center_time: number
      danmaku_count: number
      density: number
      heat_score: number
      keywords: string[]
      sentiment_score: number
    }>
  }> => {
    return monitorApi.get('analysis/heat-points')
  },

  exportData: async (
    format: 'excel' | 'csv' | 'pdf',
    roomIds: number[],
    dateRange: string,
    startDate?: string,
    endDate?: string,
    metrics?: string[]
  ): Promise<Blob> => {
    const response = await monitorApi.post('export/data', {
      format,
      room_ids: roomIds,
      date_range: dateRange,
      start_date: startDate,
      end_date: endDate,
      metrics,
    }, {
      responseType: 'blob',
    })
    return response
  },
}

export default monitorApi