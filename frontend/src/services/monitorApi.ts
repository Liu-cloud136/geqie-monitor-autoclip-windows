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
  async (error) => {
    console.error('❌ Monitor API Error:', error)
    
    if (error.response?.status === 400 && error.config?.responseType === 'blob') {
      try {
        const responseText = await error.response.data.text()
        const errorData = JSON.parse(responseText)
        console.error('   错误详情:', errorData)
        return Promise.reject(new Error(errorData.error || '请求参数错误'))
      } catch (parseError) {
        console.error('   无法解析错误响应:', parseError)
      }
    }
    
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

  exportData: async (params: {
    format?: 'excel' | 'csv' | 'pdf'
    rooms?: number[]
    dateRange?: 'today' | '7days' | '14days' | '30days' | 'all' | 'custom'
    startDate?: string
    endDate?: string
    template?: 'standard' | 'visual' | 'full'
    metricBasic?: boolean
    metricRating?: boolean
    metricRoom?: boolean
    metricCharts?: boolean
    metricStats?: boolean
  }): Promise<Blob> => {
    const queryParams = new URLSearchParams()
    
    if (params.format) queryParams.append('format', params.format)
    if (params.rooms && params.rooms.length > 0) {
      queryParams.append('rooms', params.rooms.join(','))
    }
    if (params.dateRange) queryParams.append('date_range', params.dateRange)
    if (params.startDate) queryParams.append('start_date', params.startDate)
    if (params.endDate) queryParams.append('end_date', params.endDate)
    if (params.template) queryParams.append('template', params.template)
    if (params.metricBasic !== undefined) queryParams.append('metric_basic', String(params.metricBasic))
    if (params.metricRating !== undefined) queryParams.append('metric_rating', String(params.metricRating))
    if (params.metricRoom !== undefined) queryParams.append('metric_room', String(params.metricRoom))
    if (params.metricCharts !== undefined) queryParams.append('metric_charts', String(params.metricCharts))
    if (params.metricStats !== undefined) queryParams.append('metric_stats', String(params.metricStats))
    
    const response = await monitorApi.get(`export/data?${queryParams.toString()}`, {
      responseType: 'blob'
    })
    
    return response as unknown as Blob
  },

  getRealtimeAnalysis: async (): Promise<{
    success: boolean
    data: {
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
  }> => {
    return monitorApi.get('danmaku/analysis/realtime')
  },

  getSentimentAnalysis: async (timeWindow: number = 3600): Promise<{
    success: boolean
    data: {
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
  }> => {
    return monitorApi.get('danmaku/analysis/sentiment', {
      params: { time_window: timeWindow }
    })
  },

  getWordcloudData: async (timeWindow: number = 3600, maxWords: number = 100): Promise<{
    success: boolean
    data: {
      words: Array<{ text: string; value: number }>
      total_words: number
      time_window_seconds: number
    }
  }> => {
    return monitorApi.get('danmaku/analysis/wordcloud', {
      params: { time_window: timeWindow, max_words: maxWords }
    })
  },

  getHotTopics: async (timeWindow: number = 3600, topN: number = 10): Promise<{
    success: boolean
    data: Array<{
      keyword: string
      count: number
      trend_score: number
      related_danmaku: Array<{
        username: string
        content: string
        timestamp: number
        sentiment: string
      }>
    }>
  }> => {
    return monitorApi.get('danmaku/analysis/hot_topics', {
      params: { time_window: timeWindow, top_n: topN }
    })
  },

  getDuplicateStats: async (topN: number = 20): Promise<{
    success: boolean
    data: Array<{
      content_hash: string
      content_sample: string
      count: number
      top_users: Array<{ username: string; count: number }>
      first_seen: number
      last_seen: number
      avg_sentiment: number
      time_span: number
    }>
  }> => {
    return monitorApi.get('danmaku/analysis/duplicates', {
      params: { top_n: topN }
    })
  },

  getActiveUsers: async (timeWindow: number = 3600, topN: number = 20): Promise<{
    success: boolean
    data: Array<{
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
  }> => {
    return monitorApi.get('danmaku/analysis/active_users', {
      params: { time_window: timeWindow, top_n: topN }
    })
  },

  getSuspiciousUsers: async (timeWindow: number = 3600): Promise<{
    success: boolean
    data: Array<{
      username: string
      risk_score: number
      total_danmaku: number
      avg_sentiment: number
      duplicate_ratio: number
      recent_negative_count: number
      last_seen: number
    }>
  }> => {
    return monitorApi.get('danmaku/analysis/suspicious_users', {
      params: { time_window: timeWindow }
    })
  },

  getWordFrequency: async (timeWindow: number = 3600, topN: number = 100): Promise<{
    success: boolean
    data: Array<{ word: string; count: number }>
  }> => {
    return monitorApi.get('danmaku/analysis/word_frequency', {
      params: { time_window: timeWindow, top_n: topN }
    })
  },
}

export default monitorApi