/**
 * 项目操作 Hook
 * 提供项目的重试、删除等操作功能
 */

import { useState, useCallback, useRef, useEffect } from 'react'
import { Project } from '../store/useProjectStore'
import { message } from 'antd'

export interface UseProjectActionsOptions {
  project: Project
  onDelete?: (id: string) => void
  onRetry?: (id: string) => void
  retryCooldown?: number
}

export interface UseProjectActionsResult {
  isRetrying: boolean
  isDeleting: boolean
  retryStatus: 'idle' | 'success' | 'error'
  showRetryDialog: boolean
  handleRetry: () => Promise<void>
  handleDelete: () => Promise<void>
  setShowRetryDialog: (show: boolean) => void
}

/**
 * 项目操作 Hook
 * @param options - 配置选项
 * @returns 操作相关状态和方法
 */
export const useProjectActions = (options: UseProjectActionsOptions): UseProjectActionsResult => {
  const { 
    project, 
    onDelete, 
    onRetry,
    retryCooldown = 3000
  } = options
  
  const [isRetrying, setIsRetrying] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [retryStatus, setRetryStatus] = useState<'idle' | 'success' | 'error'>('idle')
  const [showRetryDialog, setShowRetryDialog] = useState(false)
  
  const retryTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastRetryTimeRef = useRef<number>(0)
  
  /**
   * 处理重试
   */
  const handleRetry = useCallback(async () => {
    if (isRetrying) return
    
    const now = Date.now()
    const timeSinceLastRetry = now - lastRetryTimeRef.current
    
    if (timeSinceLastRetry < retryCooldown) {
      message.warning(`请等待 ${Math.ceil((retryCooldown - timeSinceLastRetry) / 1000)} 秒后再重试`)
      return
    }
    
    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current)
      retryTimeoutRef.current = null
    }
    
    lastRetryTimeRef.current = now
    setIsRetrying(true)
    setRetryStatus('idle')
    
    try {
      if (onRetry) {
        await onRetry(project.id)
      }
      setRetryStatus('success')
      message.success('任务已成功提交')
      
      retryTimeoutRef.current = setTimeout(() => {
        setRetryStatus('idle')
      }, 2000)
    } catch (error) {
      console.error('重试失败:', error)
      setRetryStatus('error')
      message.error('重试失败，请稍后再试')
      
      retryTimeoutRef.current = setTimeout(() => {
        setRetryStatus('idle')
      }, 3000)
    } finally {
      setIsRetrying(false)
    }
  }, [isRetrying, onRetry, project.id, retryCooldown])
  
  /**
   * 处理删除
   */
  const handleDelete = useCallback(async () => {
    if (isDeleting) return
    
    setIsDeleting(true)
    try {
      if (onDelete) {
        await onDelete(project.id)
      }
    } catch (error) {
      console.error('删除失败:', error)
      message.error('删除失败，请稍后再试')
    } finally {
      setIsDeleting(false)
    }
  }, [isDeleting, onDelete, project.id])
  
  useEffect(() => {
    return () => {
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current)
      }
    }
  }, [])
  
  return {
    isRetrying,
    isDeleting,
    retryStatus,
    showRetryDialog,
    handleRetry,
    handleDelete,
    setShowRetryDialog
  }
}

export default useProjectActions
