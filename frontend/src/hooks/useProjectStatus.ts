/**
 * 项目状态 Hook
 * 提供项目状态计算和格式化功能
 */

import { useMemo } from 'react'
import { Project } from '../store/useProjectStore'

export type ProjectStatusType = Project['status']
export type NormalizedStatusType = 'importing' | 'processing' | 'completed' | 'failed' | 'error' | 'default'

export interface UseProjectStatusOptions {
  project: Project
}

export interface UseProjectStatusResult {
  isImporting: boolean
  normalizedStatus: NormalizedStatusType
  progressPercent: number
  statusColor: 'success' | 'processing' | 'error' | 'default'
  statusTooltip: string
}

/**
 * 项目状态 Hook
 * @param options - 配置选项
 * @returns 状态相关计算结果
 */
export const useProjectStatus = (options: UseProjectStatusOptions): UseProjectStatusResult => {
  const { project } = options
  
  /**
   * 检查是否是导入中状态
   */
  const isImporting = useMemo(() => {
    return project.status === 'pending'
  }, [project.status])
  
  /**
   * 标准化状态
   */
  const normalizedStatus = useMemo((): NormalizedStatusType => {
    if (project.status === 'error') {
      return 'failed'
    }
    if (isImporting) {
      return 'importing'
    }
    return project.status as NormalizedStatusType
  }, [project.status, isImporting])
  
  /**
   * 获取状态颜色
   */
  const statusColor = useMemo((): 'success' | 'processing' | 'error' | 'default' => {
    switch (project.status) {
      case 'completed':
        return 'success'
      case 'processing':
        return 'processing'
      case 'error':
        return 'error'
      case 'pending':
      default:
        return 'default'
    }
  }, [project.status])
  
  /**
   * 获取状态提示文本
   */
  const statusTooltip = useMemo(() => {
    switch (project.status) {
      case 'pending':
        return '项目正在导入中'
      case 'processing':
        return '项目正在处理中'
      case 'completed':
        return '项目处理完成'
      case 'error':
      case 'failed':
        return '项目处理失败'
      default:
        return '项目状态未知'
    }
  }, [project.status])
  
  /**
   * 计算进度百分比
   */
  const progressPercent = useMemo(() => {
    if (project.status === 'completed') {
      return 100
    }
    if (project.status === 'failed' || project.status === 'error') {
      return 0
    }
    if (isImporting) {
      return project.processing_config?.download_progress || 20
    }
    if (project.current_step && project.total_steps) {
      return Math.round((project.current_step / project.total_steps) * 100)
    }
    if (project.status === 'processing') {
      return 10
    }
    return 0
  }, [
    project.status, 
    project.current_step, 
    project.total_steps, 
    project.processing_config,
    isImporting
  ])
  
  return {
    isImporting,
    normalizedStatus,
    progressPercent,
    statusColor,
    statusTooltip
  }
}

export default useProjectStatus
