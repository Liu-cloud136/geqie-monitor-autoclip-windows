/**
 * 优化后的轮询 Hook
 * 根据任务进度动态调整轮询间隔，减少无效请求
 */

import { useEffect, useState, useRef, useCallback } from 'react'

interface UseOptimizedPollingOptions {
  /**
   * 获取任务状态的函数
   */
  fetchStatus: () => Promise<{ progress: number; status: string }>

  /**
   * 任务是否已完成
   */
  isCompleted: boolean

  /**
   * 轮询是否启用
   */
  enabled?: boolean

  /**
   * 基础轮询间隔（毫秒）
   */
  baseInterval?: number

  /**
   * 最小轮询间隔（毫秒）
   */
  minInterval?: number

  /**
   * 最大轮询间隔（毫秒）
   */
  maxInterval?: number

  /**
   * 进度回调函数
   */
  onProgressUpdate?: (status: { progress: number; status: string }) => void

  /**
   * 错误回调函数
   */
  onError?: (error: Error) => void
}

/**
 * 优化后的轮询 Hook
 *
 * 特性：
 * 1. 根据任务进度动态调整轮询间隔
 * 2. 任务快完成时加快轮询（1000ms）
 * 3. 任务刚开始时减慢轮询（5000ms）
 * 4. 任务中间阶段使用默认间隔（2000ms）
 * 5. 自动处理错误和重试
 * 6. 组件卸载时自动清理
 */
export function useOptimizedPolling(options: UseOptimizedPollingOptions) {
  const {
    fetchStatus,
    isCompleted,
    enabled = true,
    baseInterval = 2000,
    minInterval = 1000,
    maxInterval = 10000,
    onProgressUpdate,
    onError,
  } = options

  const [pollingInterval, setPollingInterval] = useState(baseInterval)
  const [currentProgress, setCurrentProgress] = useState(0)
  const [isPolling, setIsPolling] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  const timeoutRef = useRef<ReturnType<typeof setTimeout>>()
  const retryCountRef = useRef(0)
  const lastProgressRef = useRef(0)

  /**
   * 根据进度计算轮询间隔
   */
  const calculateInterval = useCallback((progress: number): number => {
    // 进度 > 80%: 快完成，加快轮询
    if (progress > 80) {
      return Math.max(minInterval, 1000)
    }
    // 进度 < 20%: 刚开始，减慢轮询
    if (progress < 20) {
      return Math.min(maxInterval, 5000)
    }
    // 中间阶段: 使用默认间隔
    return baseInterval
  }, [baseInterval, minInterval, maxInterval])

  /**
   * 执行轮询
   */
  const poll = useCallback(async () => {
    if (!enabled || isCompleted) {
      return
    }

    setIsPolling(true)
    setError(null)

    try {
      const status = await fetchStatus()
      setCurrentProgress(status.progress)

      // 检查进度是否有变化
      const progressChanged = status.progress !== lastProgressRef.current
      lastProgressRef.current = status.progress

      // 根据进度调整轮询间隔
      const newInterval = calculateInterval(status.progress)
      setPollingInterval(newInterval)

      // 重试计数
      if (progressChanged) {
        retryCountRef.current = 0
      }

      // 触发回调
      if (onProgressUpdate) {
        onProgressUpdate(status)
      }
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Polling failed')
      setError(error)

      // 指数退避重试
      retryCountRef.current++
      const backoffInterval = Math.min(
        maxInterval,
        baseInterval * Math.pow(2, retryCountRef.current)
      )
      setPollingInterval(backoffInterval)

      if (onError) {
        onError(error)
      }
    } finally {
      setIsPolling(false)
    }
  }, [enabled, isCompleted, fetchStatus, calculateInterval, baseInterval, maxInterval, onProgressUpdate, onError])

  /**
   * 设置下一次轮询
   */
  const scheduleNextPoll = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
    }

    timeoutRef.current = setTimeout(() => {
      poll()
    }, pollingInterval)
  }, [pollingInterval, poll])

  /**
   * 主轮询逻辑
   */
  useEffect(() => {
    if (!enabled || isCompleted) {
      // 清理定时器
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }
      return
    }

    // 立即执行一次
    poll()

    // 设置定时轮询
    scheduleNextPoll()

    // 清理函数
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }
    }
  }, [enabled, isCompleted, poll, scheduleNextPoll])

  /**
   * 手动触发轮询
   */
  const manualPoll = useCallback(() => {
    poll()
  }, [poll])

  /**
   * 重置轮询状态
   */
  const reset = useCallback(() => {
    setCurrentProgress(0)
    setError(null)
    retryCountRef.current = 0
    lastProgressRef.current = 0
    setPollingInterval(baseInterval)
  }, [baseInterval])

  return {
    // 状态
    currentProgress,
    isPolling,
    error,
    pollingInterval,

    // 方法
    manualPoll,
    reset,
  }
}

/**
 * 简化版的轮询 Hook
 * 用于简单的定时轮询场景
 */
export function useSimplePolling<T = unknown>(
  fetchFn: () => Promise<T>,
  interval: number = 2000,
  enabled: boolean = true,
  onResult?: (result: T) => void,
  onError?: (error: Error) => void
) {
  const [data, setData] = useState<T | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  const timeoutRef = useRef<ReturnType<typeof setTimeout>>()

  useEffect(() => {
    if (!enabled) {
      return
    }

    const poll = async () => {
      setIsLoading(true)
      try {
        const result = await fetchFn()
        setData(result)
        setError(null)
        if (onResult) {
          onResult(result)
        }
      } catch (err) {
        const error = err instanceof Error ? err : new Error('Polling failed')
        setError(error)
        if (onError) {
          onError(error)
        }
      } finally {
        setIsLoading(false)
      }
    }

    // 立即执行一次
    poll()

    // 设置定时轮询
    timeoutRef.current = setInterval(() => {
      poll()
    }, interval)

    // 清理函数
    return () => {
      if (timeoutRef.current) {
        clearInterval(timeoutRef.current)
      }
    }
  }, [fetchFn, interval, enabled, onResult, onError])

  return {
    data,
    isLoading,
    error,
  }
}

/**
 * 智能轮询 Hook
 * 根据数据变化自动调整轮询频率
 */
export function useSmartPolling<T>(
  fetchFn: () => Promise<T>,
  options: {
    enabled?: boolean
    baseInterval?: number
    onChangeOnly?: boolean // 仅在数据变化时触发回调
    onDataChange?: (data: T) => void
    onError?: (error: Error) => void
  } = {}
) {
  const {
    enabled = true,
    baseInterval = 2000,
    onChangeOnly = false,
    onDataChange,
    onError,
  } = options

  const [data, setData] = useState<T | null>(null)
  const [lastData, setLastData] = useState<T | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const [interval, setInterval] = useState(baseInterval)

  const timeoutRef = useRef<ReturnType<typeof setTimeout>>()

  useEffect(() => {
    if (!enabled) {
      return
    }

    const poll = async () => {
      setIsLoading(true)
      try {
        const result = await fetchFn()

        // 检查数据是否变化
        const hasChanged = JSON.stringify(result) !== JSON.stringify(lastData)

        if (hasChanged || !onChangeOnly) {
          setData(result)
          setLastData(result)

          if (onDataChange) {
            onDataChange(result)
          }

          // 数据变化时，加快轮询（可能有更多更新）
          if (hasChanged) {
            setInterval(Math.max(1000, baseInterval / 2))
          } else {
            // 数据无变化，减慢轮询
            setInterval(Math.min(10000, baseInterval * 2))
          }
        }

        setError(null)
      } catch (err) {
        const error = err instanceof Error ? err : new Error('Polling failed')
        setError(error)
        if (onError) {
          onError(error)
        }
      } finally {
        setIsLoading(false)
      }
    }

    // 立即执行一次
    poll()

    // 设置定时轮询
    const scheduleNext = () => {
      timeoutRef.current = setTimeout(() => {
        poll()
        scheduleNext() // 递归调用以支持动态间隔
      }, interval)
    }

    scheduleNext()

    // 清理函数
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }
    }
  }, [fetchFn, baseInterval, enabled, onChangeOnly, lastData, interval, onDataChange, onError])

  return {
    data,
    isLoading,
    error,
    interval,
  }
}
