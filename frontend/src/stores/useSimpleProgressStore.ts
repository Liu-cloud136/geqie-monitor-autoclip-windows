/**
 * 简化的进度状态管理 - 基于固定阶段和WebSocket实时更新
 */

import { create } from 'zustand'

export interface SimpleProgress {
  project_id: string
  stage: string
  percent: number
  message: string
  ts: number
  estimated_remaining?: number  // 预估剩余时间(秒)
}

interface SimpleProgressState {
  // 状态数据
  byId: Record<string, SimpleProgress>

  // WebSocket控制
  isUsingWebSocket: boolean

  // 操作方法
  upsert: (progress: SimpleProgress) => void
  updateProgress: (projectId: string, stage: string, percent: number, message: string, estimated_remaining?: number) => void
  clearProgress: (projectId: string) => void
  clearAllProgress: () => void

  // 获取方法
  getProgress: (projectId: string) => SimpleProgress | null
  getAllProgress: () => Record<string, SimpleProgress>

  // WebSocket模式切换（保留兼容性）
  setUseWebSocket: (useWebSocket: boolean) => void
}

export const useSimpleProgressStore = create<SimpleProgressState>((set, get) => ({
  // 初始状态
  byId: {},
  isUsingWebSocket: true,  // 默认启用WebSocket模式

  // 更新或插入进度数据
  upsert: (progress: SimpleProgress) => {
    set((state) => ({
      byId: {
        ...state.byId,
        [progress.project_id]: progress
      }
    }))
    console.log(`进度更新: ${progress.project_id} - ${progress.stage} (${progress.percent}%)${progress.estimated_remaining ? ` - 预计剩余: ${progress.estimated_remaining}秒` : ''}`)
  },

  // 直接更新进度（从WebSocket接收）
  updateProgress: (projectId: string, stage: string, percent: number, message: string, estimated_remaining?: number) => {
    const progress: SimpleProgress = {
      project_id: projectId,
      stage,
      percent,
      message,
      ts: Date.now(),
      estimated_remaining
    }
    get().upsert(progress)
  },

  // 清除单个项目进度
  clearProgress: (projectId: string) => {
    set((state) => {
      const newById = { ...state.byId }
      delete newById[projectId]
      return { byId: newById }
    })
  },

  // 清除所有进度
  clearAllProgress: () => {
    set({ byId: {} })
  },

  // 获取单个项目进度
  getProgress: (projectId: string) => {
    return get().byId[projectId] || null
  },

  // 获取所有进度
  getAllProgress: () => {
    return get().byId
  },

  // 设置WebSocket模式
  setUseWebSocket: (useWebSocket: boolean) => {
    set({ isUsingWebSocket: useWebSocket })
    console.log(`WebSocket模式: ${useWebSocket ? '已启用' : '已禁用'}`)
  }
}))

// 阶段显示名称映射
export const STAGE_DISPLAY_NAMES: Record<string, string> = {
  'INGEST': '素材准备',
  'SUBTITLE': '字幕处理',
  'ANALYZE': '内容分析', 
  'HIGHLIGHT': '片段定位',
  'EXPORT': '视频导出',
  'DONE': '处理完成'
}

// 阶段颜色映射
export const STAGE_COLORS: Record<string, string> = {
  'INGEST': '#1890ff',      // 蓝色
  'SUBTITLE': '#52c41a',    // 绿色
  'ANALYZE': '#fa8c16',     // 橙色
  'HIGHLIGHT': '#722ed1',   // 紫色
  'EXPORT': '#eb2f96',      // 粉色
  'DONE': '#13c2c2'         // 青色
}

// 获取阶段显示名称
export const getStageDisplayName = (stage: string): string => {
  return STAGE_DISPLAY_NAMES[stage] || stage
}

// 获取阶段颜色
export const getStageColor = (stage: string): string => {
  return STAGE_COLORS[stage] || '#666666'
}

// 判断是否为完成状态
export const isCompleted = (stage: string): boolean => {
  return stage === 'DONE'
}

// 判断是否为失败状态
export const isFailed = (message: string): boolean => {
  return message.includes('失败') || message.includes('错误') || message.includes('失败')
}
