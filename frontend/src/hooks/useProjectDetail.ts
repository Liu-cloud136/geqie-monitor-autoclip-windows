/**
 * 项目详情页面自定义Hook
 * 提供项目详情页面的状态管理和业务逻辑
 */

import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { message } from 'antd'
import { useProjectStore } from '../store/useProjectStore'
import { projectApi, clipEditApi } from '../services/api'
import { useClipEditStore } from '../stores/useClipEditStore'
import { Clip } from '../types/api'

/**
 * 项目详情页面的状态和操作
 */
export interface ProjectDetailState {
  currentProject: any
  loading: boolean
  error: string | null
  statusLoading: boolean
  sortBy: 'time' | 'score'
  activeTab: 'clips' | 'editor'
  selectClipsModalVisible: boolean
  selectedClipIdsForAdd: string[]
  currentSession: any
  loadProject: () => Promise<void>
  loadProcessingStatus: () => Promise<void>
  handleStartProcessing: () => Promise<void>
  getSortedClips: () => Clip[]
  handleOpenSelectClips: () => void
  handleConfirmAddClips: (clipIds: string[]) => Promise<void>
  setSortBy: (sort: 'time' | 'score') => void
  setActiveTab: (tab: 'clips' | 'editor') => void
  setSelectClipsModalVisible: (visible: boolean) => void
  setSelectedClipIdsForAdd: (ids: string[]) => void
}

/**
 * 项目详情页面自定义Hook
 * @returns 项目详情页面的状态和操作
 */
export const useProjectDetail = (): ProjectDetailState => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const {
    currentProject,
    loading,
    error,
    setCurrentProject
  } = useProjectStore()

  // 编辑状态
  const {
    currentSession,
    setSession,
    setSegments,
    addSegment,
  } = useClipEditStore()

  const [statusLoading, setStatusLoading] = useState(false)
  const [sortBy, setSortBy] = useState<'time' | 'score'>('score')
  const [activeTab, setActiveTab] = useState<'clips' | 'editor'>('clips')
  const [selectClipsModalVisible, setSelectClipsModalVisible] = useState(false)
  const [selectedClipIdsForAdd, setSelectedClipIdsForAdd] = useState<string[]>([])

  useEffect(() => {
    if (id) {
      if (!currentProject || currentProject.id !== id) {
        loadProject()
      }
      loadProcessingStatus()
    }
  }, [id])

  const loadProject = async () => {
    if (!id) return
    try {
      console.log('🔄 开始加载项目:', id)
      const project = await projectApi.getProject(id)
      console.log('📦 完整项目数据:', project)
      console.log('🎬 Loaded project with clips:', project.clips?.length || 0, 'clips')
      setCurrentProject(project)

      const { projects } = useProjectStore.getState()
      const updatedProjects = projects.map(p =>
        p.id === id ? project : p
      )
      useProjectStore.setState({ projects: updatedProjects })
    } catch (error) {
      console.error('Failed to load project:', error)
      message.error('加载项目失败')
    }
  }

  const loadProcessingStatus = async () => {
    if (!id) return
    setStatusLoading(true)
    try {
      await projectApi.getProcessingStatus(id)
    } catch (error) {
      console.error('Failed to load processing status:', error)
    } finally {
      setStatusLoading(false)
    }
  }

  const handleStartProcessing = async () => {
    if (!id) return
    try {
      await projectApi.startProcessing(id)
      message.success('开始处理')
      loadProcessingStatus()
    } catch (error) {
      console.error('Failed to start processing:', error)
      message.error('启动处理失败')
    }
  }

  const getSortedClips = useCallback(() => {
    if (!currentProject?.clips) return []
    const clips = [...currentProject.clips]
    
    if (sortBy === 'score') {
      return clips.sort((a: any, b: any) => b.final_score - a.final_score)
    } else {
      return clips.sort((a: any, b: any) => {
        const getTimeInSeconds = (timeStr: string | number) => {
          if (typeof timeStr === 'number') {
            return timeStr
          }
          const parts = timeStr.split(':')
          const hours = parseInt(parts[0])
          const minutes = parseInt(parts[1])
          const seconds = parseFloat(parts[2].replace(',', '.'))
          return hours * 3600 + minutes * 60 + seconds
        }
        
        const aTime = getTimeInSeconds(a.start_time)
        const bTime = getTimeInSeconds(b.start_time)
        return aTime - bTime
      })
    }
  }, [currentProject, sortBy])

  // 打开选择切片模态框
  const handleOpenSelectClips = useCallback(() => {
    const existingIds = currentSession?.segments?.map((s: any) => String(s.original_clip_id)) || []
    setSelectedClipIdsForAdd(existingIds)
    setSelectClipsModalVisible(true)
  }, [currentSession])

  // 确认添加选择的切片到时间轴
  const handleConfirmAddClips = useCallback(async (clipIds: string[]) => {
    if (!currentSession || !id) return

    const existingIds = new Set(currentSession.segments.map((s: any) => String(s.original_clip_id)))
    const newIds = clipIds.filter(clipId => !existingIds.has(clipId))

    if (newIds.length === 0) {
      message.info('这些切片已在时间轴中')
      return
    }

    try {
      const result = await clipEditApi.addClipsToSession(currentSession.id, newIds)
      if (result.success) {
        message.success(`已添加 ${result.added_count} 个切片到时间轴`)
        // 重新加载会话数据
        const sessionResult = await clipEditApi.getSession(currentSession.id)
        if (sessionResult.success) {
          setSession(sessionResult.session as any)
        }
        // 切换到编辑标签
        setActiveTab('editor')
      }
    } catch (error) {
      message.error('添加切片失败')
    }
  }, [currentSession, id, setSession])

  return {
    currentProject,
    loading,
    error,
    statusLoading,
    sortBy,
    activeTab,
    selectClipsModalVisible,
    selectedClipIdsForAdd,
    currentSession,
    loadProject,
    loadProcessingStatus,
    handleStartProcessing,
    getSortedClips,
    handleOpenSelectClips,
    handleConfirmAddClips,
    setSortBy,
    setActiveTab,
    setSelectClipsModalVisible,
    setSelectedClipIdsForAdd
  }
}
