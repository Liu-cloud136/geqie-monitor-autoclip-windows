/**
 * 项目日志轮播 Hook
 * 提供项目处理日志的获取和轮播显示功能
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { Project } from '../store/useProjectStore'
import { projectApi } from '../services/api'

export interface LogEntry {
  timestamp: string
  module: string
  level: string
  message: string
}

export interface UseProjectLogsOptions {
  project: Project
  pollInterval?: number
  carouselInterval?: number
  maxLogs?: number
}

export interface UseProjectLogsResult {
  logs: LogEntry[]
  currentLogIndex: number
  currentLog: LogEntry | null
  isPolling: boolean
  startPolling: () => void
  stopPolling: () => void
  refreshLogs: () => Promise<void>
}

/**
 * 项目日志轮播 Hook
 * @param options - 配置选项
 * @returns 日志相关状态和方法
 */
export const useProjectLogs = (options: UseProjectLogsOptions): UseProjectLogsResult => {
  const { 
    project, 
    pollInterval = 3000,
    carouselInterval = 2000,
    maxLogs = 20
  } = options
  
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [currentLogIndex, setCurrentLogIndex] = useState(0)
  const [isPolling, setIsPolling] = useState(false)
  
  const logIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const carouselIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  
  /**
   * 过滤日志消息
   */
  const filterLog = useCallback((log: LogEntry): boolean => {
    return (
      log.message.includes('Step') || 
      log.message.includes('开始') || 
      log.message.includes('完成') ||
      log.message.includes('处理') ||
      log.level === 'ERROR'
    )
  }, [])
  
  /**
   * 刷新日志
   */
  const refreshLogs = useCallback(async () => {
    if (project.status !== 'processing') {
      setLogs([])
      return
    }
    
    try {
      const response = await projectApi.getProjectLogs(project.id, maxLogs)
      const filteredLogs = response.logs.filter(filterLog)
      setLogs(filteredLogs)
    } catch (error) {
      console.error('获取日志失败:', error)
    }
  }, [project.id, project.status, maxLogs, filterLog])
  
  /**
   * 开始轮询
   */
  const startPolling = useCallback(() => {
    if (project.status !== 'processing') return
    
    setIsPolling(true)
    refreshLogs()
    
    logIntervalRef.current = setInterval(refreshLogs, pollInterval)
  }, [project.status, refreshLogs, pollInterval])
  
  /**
   * 停止轮询
   */
  const stopPolling = useCallback(() => {
    setIsPolling(false)
    
    if (logIntervalRef.current) {
      clearInterval(logIntervalRef.current)
      logIntervalRef.current = null
    }
    
    if (carouselIntervalRef.current) {
      clearInterval(carouselIntervalRef.current)
      carouselIntervalRef.current = null
    }
  }, [])
  
  /**
   * 当前显示的日志
   */
  const currentLog = logs.length > 0 ? logs[currentLogIndex] : null
  
  useEffect(() => {
    if (project.status === 'processing') {
      startPolling()
    } else {
      stopPolling()
      setLogs([])
      setCurrentLogIndex(0)
    }
    
    return () => {
      stopPolling()
    }
  }, [project.status, startPolling, stopPolling])
  
  useEffect(() => {
    if (logs.length > 1) {
      carouselIntervalRef.current = setInterval(() => {
        setCurrentLogIndex(prev => (prev + 1) % logs.length)
      }, carouselInterval)
    } else {
      if (carouselIntervalRef.current) {
        clearInterval(carouselIntervalRef.current)
        carouselIntervalRef.current = null
      }
    }
    
    return () => {
      if (carouselIntervalRef.current) {
        clearInterval(carouselIntervalRef.current)
      }
    }
  }, [logs.length, carouselInterval])
  
  return {
    logs,
    currentLogIndex,
    currentLog,
    isPolling,
    startPolling,
    stopPolling,
    refreshLogs
  }
}

export default useProjectLogs
