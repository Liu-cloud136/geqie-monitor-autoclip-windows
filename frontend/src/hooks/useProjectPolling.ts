import { useEffect, useRef, useState, useCallback } from 'react'
import { projectApi } from '../services/api'
import { Project, useProjectStore } from '../store/useProjectStore'

interface UseProjectPollingOptions {
  interval?: number // 基础轮询间隔，默认10秒
  onProjectsUpdate?: (projects: Project[]) => void
  enabled?: boolean // 是否启用轮询
}

/**
 * 优化的项目轮询 Hook
 * 根据项目状态动态调整轮询频率，减少无效请求
 */
export const useProjectPolling = ({
  interval = 10000,
  onProjectsUpdate,
  enabled = true
}: UseProjectPollingOptions = {}) => {
  const [isPolling, setIsPolling] = useState(false)
  const timeoutRef = useRef<ReturnType<typeof setTimeout>>()
  const [lastUpdateTime, setLastUpdateTime] = useState<number>(Date.now())
  const [currentInterval, setCurrentInterval] = useState<number>(interval)
  const onProjectsUpdateRef = useRef(onProjectsUpdate)
  const lastProjectsRef = useRef<Project[]>([])

  // 更新回调引用
  useEffect(() => {
    onProjectsUpdateRef.current = onProjectsUpdate
  }, [onProjectsUpdate])

  /**
   * 根据项目状态计算动态轮询间隔
   */
  const calculateDynamicInterval = useCallback((projects: Project[]): number => {
    const hasProcessingProjects = projects.some(p => p.status === 'processing')

    // 如果有正在处理的项目，使用较快间隔（5秒）
    if (hasProcessingProjects) {
      return 5000
    }

    // 如果没有处理中的项目，检查项目是否有变化
    const projectsChanged = JSON.stringify(projects) !== JSON.stringify(lastProjectsRef.current)

    if (projectsChanged) {
      // 项目有变化，使用默认间隔
      return interval
    } else {
      // 项目无变化，延长轮询间隔（减少无效请求）
      return Math.min(30000, interval * 2) // 最长30秒
    }
  }, [interval])

  const poll = useCallback(async () => {
    try {
      // 实时获取isDragging状态
      const currentIsDragging = useProjectStore.getState().isDragging

      // 如果正在拖拽，跳过这次轮询
      if (currentIsDragging) {
        console.log('Skipping poll: dragging in progress')
        // 拖拽时延迟下次轮询
        timeoutRef.current = setTimeout(poll, currentInterval)
        return
      }

      console.log('Polling projects...', `interval: ${currentInterval}ms`)
      const projects = await projectApi.getProjects()
      console.log('Polled projects:', projects?.length, 'projects')

      if (onProjectsUpdateRef.current) {
        console.log('Calling onProjectsUpdate with:', projects)
        onProjectsUpdateRef.current(projects || [])
      }

      setLastUpdateTime(Date.now())

      // 计算下一次的轮询间隔
      const newInterval = calculateDynamicInterval(projects || [])

      // 如果间隔有变化，更新状态
      if (newInterval !== currentInterval) {
        console.log('Adjusting polling interval:', currentInterval, '->', newInterval)
        setCurrentInterval(newInterval)
      }

      // 更新上次的项目引用
      lastProjectsRef.current = projects || []

      // 安排下一次轮询
      if (enabled) {
        timeoutRef.current = setTimeout(poll, newInterval)
      }
    } catch (error) {
      console.error('Polling error:', error)

      // 发生错误时使用较长的延迟（指数退避）
      const backoffInterval = Math.min(60000, currentInterval * 2) // 最长60秒
      console.log('Backing off for', backoffInterval, 'ms')

      if (enabled) {
        timeoutRef.current = setTimeout(poll, backoffInterval)
      }
    }
  }, [currentInterval, enabled, calculateDynamicInterval])

  const refreshNow = useCallback(async () => {
    try {
      const projects = await projectApi.getProjects()
      if (onProjectsUpdateRef.current) {
        onProjectsUpdateRef.current(projects || [])
      }
      setLastUpdateTime(Date.now())
      lastProjectsRef.current = projects || []
      return projects
    } catch (error) {
      console.error('Manual refresh error:', error)
      throw error
    }
  }, [])

  // 启动轮询
  useEffect(() => {
    if (!enabled) {
      return
    }

    setIsPolling(true)

    // 立即执行一次
    poll()

    // 清理函数
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }
      setIsPolling(false)
    }
  }, [enabled, poll])

  return {
    isPolling,
    lastUpdateTime,
    currentInterval,
    refreshNow
  }
}

export default useProjectPolling