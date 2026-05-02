/**
 * 项目缩略图生成 Hook
 * 提供项目视频缩略图的生成和缓存功能
 */

import { useState, useEffect, useCallback } from 'react'
import { Project } from '../store/useProjectStore'
import { projectApi } from '../services/api'

export interface UseProjectThumbnailOptions {
  project: Project
  maxWidth?: number
  maxHeight?: number
  cacheLimit?: number
}

export interface UseProjectThumbnailResult {
  videoThumbnail: string | null
  thumbnailLoading: boolean
  generateThumbnail: () => Promise<void>
  clearCache: () => void
}

/**
 * 项目缩略图生成 Hook
 * @param options - 配置选项
 * @returns 缩略图相关状态和方法
 */
export const useProjectThumbnail = (options: UseProjectThumbnailOptions): UseProjectThumbnailResult => {
  const { 
    project, 
    maxWidth = 320, 
    maxHeight = 180,
    cacheLimit = 50
  } = options
  
  const [videoThumbnail, setVideoThumbnail] = useState<string | null>(null)
  const [thumbnailLoading, setThumbnailLoading] = useState(false)
  
  const thumbnailCacheKey = `thumbnail_${project.id}`
  
  /**
   * 清除当前项目的缩略图缓存
   */
  const clearCache = useCallback(() => {
    localStorage.removeItem(thumbnailCacheKey)
    setVideoThumbnail(null)
  }, [thumbnailCacheKey])
  
  /**
   * 生成视频缩略图
   */
  const generateThumbnail = useCallback(async () => {
    if (project.thumbnail) {
      setVideoThumbnail(project.thumbnail)
      console.log(`使用后端提供的缩略图: ${project.id}`)
      return
    }
    
    if (!project.video_path) {
      console.log('项目没有视频路径:', project.id)
      return
    }
    
    const cachedThumbnail = localStorage.getItem(thumbnailCacheKey)
    if (cachedThumbnail) {
      setVideoThumbnail(cachedThumbnail)
      return
    }
    
    setThumbnailLoading(true)
    
    try {
      const video = document.createElement('video')
      video.crossOrigin = 'anonymous'
      video.muted = true
      video.preload = 'metadata'
      
      const possiblePaths = [
        'input/input.mp4',
        'input.mp4',
        project.video_path,
        `${project.video_path}/input.mp4`
      ].filter(Boolean)
      
      let videoLoaded = false
      
      for (const path of possiblePaths) {
        if (videoLoaded) break
        
        try {
          const videoUrl = projectApi.getProjectFileUrl(project.id, path)
          console.log('尝试加载视频:', videoUrl)
          
          await new Promise<void>((resolve, reject) => {
            const timeoutId = setTimeout(() => {
              reject(new Error('视频加载超时'))
            }, 10000)
            
            video.onloadedmetadata = () => {
              clearTimeout(timeoutId)
              console.log('视频元数据加载成功:', videoUrl)
              video.currentTime = Math.min(5, video.duration / 4)
            }
            
            video.onseeked = () => {
              clearTimeout(timeoutId)
              try {
                const canvas = document.createElement('canvas')
                const ctx = canvas.getContext('2d')
                if (!ctx) {
                  reject(new Error('无法获取canvas上下文'))
                  return
                }
                
                const aspectRatio = video.videoWidth / video.videoHeight
                let width = maxWidth
                let height = maxHeight
                
                if (aspectRatio > maxWidth / maxHeight) {
                  height = maxWidth / aspectRatio
                } else {
                  width = maxHeight * aspectRatio
                }
                
                canvas.width = width
                canvas.height = height
                ctx.drawImage(video, 0, 0, width, height)
                
                const thumbnail = canvas.toDataURL('image/jpeg', 0.7)
                setVideoThumbnail(thumbnail)
                
                try {
                  localStorage.setItem(thumbnailCacheKey, thumbnail)
                } catch (e) {
                  const keys = Object.keys(localStorage).filter(key => key.startsWith('thumbnail_'))
                  if (keys.length > cacheLimit) {
                    keys.slice(0, 10).forEach(key => localStorage.removeItem(key))
                    localStorage.setItem(thumbnailCacheKey, thumbnail)
                  }
                }
                
                videoLoaded = true
                resolve()
              } catch (error) {
                reject(error)
              }
            }
            
            video.onerror = (error) => {
              clearTimeout(timeoutId)
              console.error('视频加载失败:', videoUrl, error)
              reject(error)
            }
            
            video.src = videoUrl
          })
          
          break
        } catch (error) {
          console.warn(`路径 ${path} 加载失败:`, error)
          continue
        }
      }
      
      if (!videoLoaded) {
        console.error('所有视频路径都加载失败')
      }
    } catch (error) {
      console.error('生成缩略图时发生错误:', error)
    } finally {
      setThumbnailLoading(false)
    }
  }, [project.id, project.video_path, project.thumbnail, thumbnailCacheKey, maxWidth, maxHeight, cacheLimit])
  
  useEffect(() => {
    generateThumbnail()
  }, [generateThumbnail])
  
  return {
    videoThumbnail,
    thumbnailLoading,
    generateThumbnail,
    clearCache
  }
}

export default useProjectThumbnail
