import { create } from 'zustand'

export interface Clip {
  id: string | number
  project_id: string | number
  title: string
  description?: string
  start_time: string | number
  end_time: string | number
  duration: number
  score?: number
  recommendation_reason?: string
  video_path?: string
  thumbnail_path?: string
  processing_step?: number
  tags?: string[]
  clip_metadata?: {
    final_score?: number
    recommend_reason?: string
    outline?: string
    content?: Array<{
      time_range: string
      content: string
    }>
    chunk_index?: number
    generated_title?: string
    metadata_file?: string
  }
  created_at: string
  updated_at: string
  status?: string
  is_processing?: boolean
  is_completed?: boolean
  has_error?: boolean
  final_score?: number
  recommend_reason?: string
  outline?: string
  content?: Array<{
    time_range: string
    content: string
  }>
  chunk_index?: number
  generated_title?: string
}

// 项目状态类型定义，与后端保持一致
type ProjectStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'error'

export interface Project {
  id: string
  name: string
  description?: string
  project_type?: string
  status: ProjectStatus
  source_url?: string
  source_file?: string
  settings?: Record<string, unknown>
  processing_config?: {
    download_status?: string
    download_progress?: number
    download_message?: string
    [key: string]: unknown
  }
  project_metadata?: {
    [key: string]: unknown
  }
  created_at: string
  updated_at: string
  completed_at?: string
  total_clips?: number
  total_tasks?: number
  // 前端特有字段
  video_path?: string
  thumbnail?: string
  clips?: Clip[]
  current_step?: number
  total_steps?: number
  error_message?: string
}

interface ProjectStore {
  projects: Project[]
  currentProject: Project | null
  loading: boolean
  error: string | null
  lastEditTimestamp: number
  isDragging: boolean
  
  // Actions
  setProjects: (projects: Project[] | ((prev: Project[]) => Project[])) => void
  setCurrentProject: (project: Project | null) => void
  addProject: (project: Project) => void
  updateProject: (id: string, updates: Partial<Project>) => void
  deleteProject: (id: string) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  updateClip: (projectId: string, clipId: string, updates: Partial<Clip>) => void
  setDragging: (isDragging: boolean) => void
}

export const useProjectStore = create<ProjectStore>((set, get) => ({
  projects: [],
  currentProject: null,
  loading: false,
  error: null,
  lastEditTimestamp: 0,
  isDragging: false,

  setProjects: (projectsOrUpdater) => {
    const state = get()
    
    // 支持函数式更新：setProjects(prevProjects => ...)
    const newProjects = typeof projectsOrUpdater === 'function' 
      ? projectsOrUpdater(state.projects)
      : projectsOrUpdater
    
    console.log('setProjects called:', {
      isDragging: state.isDragging,
      projectsCount: newProjects.length,
      projects: newProjects
    })
    
    // 如果正在拖拽，则跳过更新以避免冲突
    if (state.isDragging) {
      console.log('Skipping update: dragging in progress')
      return
    }
    
    console.log('Applying update with new data')
    set({ projects: newProjects })
  },
  
  setCurrentProject: (project) => set({ currentProject: project }),
  
  addProject: (project) => set((state) => ({ 
    projects: [project, ...state.projects] 
  })),
  
  updateProject: (id, updates) => set((state) => ({
    projects: state.projects.map(p => p.id === id ? { ...p, ...updates } : p),
    currentProject: state.currentProject?.id === id 
      ? { ...state.currentProject, ...updates } 
      : state.currentProject
  })),
  
  deleteProject: (id) => {
    // 清理缩略图缓存
    const thumbnailCacheKey = `thumbnail_${id}`
    localStorage.removeItem(thumbnailCacheKey)
    
    set((state) => ({
      projects: state.projects.filter(p => p.id !== id),
      currentProject: state.currentProject?.id === id ? null : state.currentProject
    }))
  },
  
  setLoading: (loading) => set({ loading }),
  
  setError: (error) => set({ error }),
  
  updateClip: (projectId, clipId, updates) => set((state) => ({
    projects: state.projects.map(p => 
      p.id === projectId 
        ? { ...p, clips: (p.clips || []).map(c => c.id === clipId ? { ...c, ...updates } : c) }
        : p
    ),
    currentProject: state.currentProject?.id === projectId
      ? { 
          ...state.currentProject, 
          clips: (state.currentProject.clips || []).map(c => c.id === clipId ? { ...c, ...updates } : c)
        }
      : state.currentProject
  })),

  setDragging: (isDragging) => set({ isDragging }),
}))
