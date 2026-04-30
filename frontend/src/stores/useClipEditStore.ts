import { create } from 'zustand'
import {
  ClipEditSession,
  EditSegment,
  EditSessionStatus,
} from '../types/api'

interface ClipEditState {
  currentSession: ClipEditSession | null
  isLoading: boolean
  error: string | null
  selectedSegmentId: string | null
  isGenerating: boolean
  generationProgress: number

  setSession: (session: ClipEditSession | null) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  selectSegment: (segmentId: string | null) => void
  setGenerating: (isGenerating: boolean) => void
  setGenerationProgress: (progress: number) => void

  addSegment: (segment: EditSegment) => void
  updateSegment: (segmentId: string, updates: Partial<EditSegment>) => void
  removeSegment: (segmentId: string) => void
  reorderSegments: (segmentOrders: Array<{ segment_id: string; segment_order: number }>) => void
  setSegments: (segments: EditSegment[]) => void

  updateSessionStatus: (status: EditSessionStatus) => void
  clearSession: () => void
}

export const useClipEditStore = create<ClipEditState>((set, get) => ({
  currentSession: null,
  isLoading: false,
  error: null,
  selectedSegmentId: null,
  isGenerating: false,
  generationProgress: 0,

  setSession: (session) => set({ currentSession: session }),
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
  selectSegment: (segmentId) => set({ selectedSegmentId: segmentId }),
  setGenerating: (isGenerating) => set({ isGenerating }),
  setGenerationProgress: (progress) => set({ generationProgress: progress }),

  addSegment: (segment) => set((state) => {
    if (!state.currentSession) return state
    const newSegments = [...state.currentSession.segments, segment]
    newSegments.sort((a, b) => a.segment_order - b.segment_order)
    return {
      currentSession: {
        ...state.currentSession,
        segments: newSegments,
        total_duration: newSegments.reduce((sum, s) => sum + s.duration, 0),
      },
    }
  }),

  updateSegment: (segmentId, updates) => set((state) => {
    if (!state.currentSession) return state
    const newSegments = state.currentSession.segments.map((s) =>
      s.id === segmentId ? { ...s, ...updates } : s
    )
    newSegments.sort((a, b) => a.segment_order - b.segment_order)
    return {
      currentSession: {
        ...state.currentSession,
        segments: newSegments,
        total_duration: newSegments.reduce((sum, s) => sum + s.duration, 0),
      },
    }
  }),

  removeSegment: (segmentId) => set((state) => {
    if (!state.currentSession) return state
    const newSegments = state.currentSession.segments
      .filter((s) => s.id !== segmentId)
      .sort((a, b) => a.segment_order - b.segment_order)
      .map((s, index) => ({ ...s, segment_order: index }))
    
    const newSelectedId = get().selectedSegmentId === segmentId ? null : get().selectedSegmentId
    
    return {
      currentSession: {
        ...state.currentSession,
        segments: newSegments,
        total_duration: newSegments.reduce((sum, s) => sum + s.duration, 0),
      },
      selectedSegmentId: newSelectedId,
    }
  }),

  reorderSegments: (segmentOrders) => set((state) => {
    if (!state.currentSession) return state
    const orderMap = new Map(segmentOrders.map((o) => [o.segment_id, o.segment_order]))
    const newSegments = state.currentSession.segments
      .map((s) => ({
        ...s,
        segment_order: orderMap.get(s.id) ?? s.segment_order,
      }))
      .sort((a, b) => a.segment_order - b.segment_order)
    return {
      currentSession: {
        ...state.currentSession,
        segments: newSegments,
      },
    }
  }),

  setSegments: (segments) => set((state) => {
    if (!state.currentSession) return state
    const sortedSegments = [...segments].sort((a, b) => a.segment_order - b.segment_order)
    return {
      currentSession: {
        ...state.currentSession,
        segments: sortedSegments,
        total_duration: sortedSegments.reduce((sum, s) => sum + s.duration, 0),
      },
    }
  }),

  updateSessionStatus: (status) => set((state) => {
    if (!state.currentSession) return state
    return {
      currentSession: {
        ...state.currentSession,
        status,
      },
    }
  }),

  clearSession: () => set({
    currentSession: null,
    isLoading: false,
    error: null,
    selectedSegmentId: null,
    isGenerating: false,
    generationProgress: 0,
  }),
}))
