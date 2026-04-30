import { useEffect, useRef, useCallback, useMemo } from 'react'
import { throttle } from 'lodash'

export interface TaskUpdateMessage {
  task_id: string;
  status: string;
  progress?: number;
  message?: string;
  error?: string;
  timestamp: string;
}

export interface ProjectUpdateMessage {
  project_id: string;
  status: string;
  progress?: number;
  message?: string;
  timestamp: string;
}

export interface ProgressUpdateMessage {
  type: 'progress';
  project_id: string;
  stage: string;
  percent: number;
  message: string;
  ts: number;
  estimated_remaining?: number;  // 预估剩余时间(秒)
}

export interface SystemNotificationMessage {
  type: 'system_notification';
  notification_type: string;
  title: string;
  message: string;
  level: 'info' | 'success' | 'warning' | 'error';
  timestamp: string;
}

export interface TaskProgressUpdateMessage {
  type: 'task_progress_update'
  project_id: string
  progress: number
  step_name: string
  status: string
  timestamp: string
  task_id?: string
  message?: string
  estimated_remaining?: number
}

export interface TaskUpdateMessage {
  type: 'task_update'
  task_id: string
  status: string
  progress?: number
  message?: string
  error?: string
  result?: any
  timestamp: string
  project_id?: string
}

export type WebSocketMessage = ProgressUpdateMessage | SystemNotificationMessage | TaskProgressUpdateMessage | TaskUpdateMessage

export interface UseWebSocketOptions {
  userId: string;
  projectIds?: string[];
  onProgress?: (message: ProgressUpdateMessage) => void;
  onNotification?: (message: SystemNotificationMessage) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Error) => void;
  reconnectInterval?: number;
  reconnectAttempts?: number;
}

export interface UseWebSocketReturn {
  isConnected: boolean;
  sendMessage: (message: Record<string, unknown>) => void;
  subscribeProjects: (projectIds: string[]) => void;
  unsubscribe: () => void;
  reconnect: () => void;
}

export function useWebSocket({
  userId,
  projectIds = [],
  onProgress,
  onNotification,
  onConnect,
  onDisconnect,
  onError,
  reconnectInterval = 3000,
  reconnectAttempts = 5,
}: UseWebSocketOptions): UseWebSocketReturn {
  const wsRef = useRef<WebSocket | null>(null)
  const isConnectedRef = useRef(false)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectCountRef = useRef(0)

  const throttledOnProgress = useMemo(() => {
    if (!onProgress) return undefined
    return throttle((message: ProgressUpdateMessage) => {
      onProgress(message)
    }, 200)
  }, [onProgress])

  const connect = useCallback(() => {
    if (!userId) {
      console.warn('userId is required for WebSocket connection')
      return
    }

    const wsUrl = `ws://localhost:8000/api/v1/ws/${userId}`
    console.log(`WebSocket URL: ${wsUrl}`)

    try {
      console.log(`Connecting to WebSocket: ${wsUrl}`)

      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        console.log('✅ WebSocket连接成功')
        console.log('WebSocket readyState:', ws.readyState)
        console.log('WebSocket URL:', ws.url)
        console.log('Project IDs:', projectIds)
        isConnectedRef.current = true
        reconnectCountRef.current = 0

        if (projectIds.length > 0) {
          console.log('开始订阅项目:', projectIds)
          subscribeToProjects(ws, projectIds)
        } else {
          console.log('没有需要订阅的项目')
        }

        onConnect?.()
        
        // 添加全局调试
        if (typeof window !== 'undefined') {
          ;(window as any).__WS_CONNECTED__ = true
          ;(window as any).__WS_USER_ID__ = userId
        }
      }

      ws.onmessage = (event) => {
        try {
          console.log('📥 WebSocket收到消息:', event.data)
          const message: WebSocketMessage = JSON.parse(event.data)

          console.log('📋 WebSocket消息解析成功:', message)

          if (message.type === 'progress' && throttledOnProgress) {
            console.log('🚀 处理进度更新消息:', message)
            const progressMessage: ProgressUpdateMessage = {
              type: 'progress',
              project_id: message.project_id,
              stage: message.stage,
              percent: typeof message.percent === 'string' ? parseInt(message.percent, 10) : message.percent,
              message: message.message,
              ts: Date.now(),
              estimated_remaining: message.estimated_remaining !== undefined 
                ? (typeof message.estimated_remaining === 'string' ? parseInt(message.estimated_remaining, 10) : message.estimated_remaining)
                : undefined
            }
            throttledOnProgress(progressMessage)
          } else if (message.type === 'task_update' && throttledOnProgress) {
            console.log('🚀 处理任务更新消息:', message)
            // 将任务更新消息转换为进度更新消息
            if (message.project_id) {
              const progressMessage: ProgressUpdateMessage = {
                type: 'progress',
                project_id: message.project_id,
                stage: message.status === 'completed' ? 'DONE' : 'ANALYZE',
                percent: message.progress || (message.status === 'completed' ? 100 : 0),
                message: message.message || (message.status === 'completed' ? '处理完成' : '处理中'),
                ts: Date.now()
              }
              throttledOnProgress(progressMessage)
            }
          } else if (message.type === 'task_progress_update' && throttledOnProgress) {
            console.log('🚀 处理任务进度更新消息:', message)
            const progressMessage: ProgressUpdateMessage = {
              type: 'progress',
              project_id: message.project_id,
              stage: message.step_name,
              percent: typeof message.progress === 'string' ? parseInt(message.progress, 10) : message.progress,
              message: message.message || message.step_name,
              ts: Date.now(),
              estimated_remaining: message.estimated_remaining !== undefined 
                ? (typeof message.estimated_remaining === 'string' ? parseInt(message.estimated_remaining, 10) : message.estimated_remaining)
                : undefined
            }
            throttledOnProgress(progressMessage)
          } else if (message.type === 'system_notification' && onNotification) {
            console.log('🔔 处理系统通知消息:', message)
            onNotification(message)
          } else {
            console.warn('⚠️ 未知消息类型:', message.type)
          }
        } catch (error) {
          console.error('❌ WebSocket消息解析失败:', error, '原始消息:', event.data)
        }
      }

      ws.onerror = (error) => {
        console.error('❌ WebSocket错误:', error)
        onError?.(error as unknown as Error)
      }

      ws.onclose = () => {
        console.log('WebSocket closed')
        isConnectedRef.current = false
        wsRef.current = null

        onDisconnect?.()

        if (reconnectCountRef.current < reconnectAttempts) {
          reconnectCountRef.current++
          const delay = reconnectInterval * reconnectCountRef.current
          console.log(`Reconnecting in ${delay}ms (attempt ${reconnectCountRef.current}/${reconnectAttempts})`)

          reconnectTimeoutRef.current = setTimeout(() => {
            connect()
          }, delay)
        } else {
          console.warn('Max reconnect attempts reached')
        }
      }
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error)
      onError?.(error as unknown as Error)
    }
  }, [userId, projectIds, reconnectInterval, reconnectAttempts, onConnect, onDisconnect, onError, throttledOnProgress, onNotification])

  const subscribeToProjects = (ws: WebSocket, ids: string[]) => {
    const message = {
      type: 'sync_subscriptions',
      channels: ids.map(id => `progress:project:${id}`),
    }
    ws.send(JSON.stringify(message))
    console.log('Subscribed to projects:', ids)
  }

  const sendMessage = useCallback((message: any) => {
    const ws = wsRef.current
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(message))
    } else {
      console.warn('WebSocket is not connected')
    }
  }, [])

  const subscribeProjects = useCallback((ids: string[]) => {
    const ws = wsRef.current
    if (ws && ws.readyState === WebSocket.OPEN) {
      subscribeToProjects(ws, ids)
    } else {
      console.warn('WebSocket is not connected, will subscribe when connected')
    }
  }, [])

  const unsubscribe = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }

    const ws = wsRef.current
    if (ws) {
      ws.close()
      wsRef.current = null
    }

    isConnectedRef.current = false
  }, [])

  const reconnect = useCallback(() => {
    unsubscribe()
    reconnectCountRef.current = 0
    setTimeout(() => {
      connect()
    }, 100)
  }, [unsubscribe, connect])

  // 组件挂载时连接
  useEffect(() => {
    if (userId) {
      connect()
    }

    return () => {
      unsubscribe()
    }
  }, [userId]) // 只在userId变化时重新连接

  // 当 projectIds 变化时，重新订阅
  useEffect(() => {
    const ws = wsRef.current
    console.log('projectIds 变化:', projectIds)
    console.log('WebSocket 状态:', ws?.readyState)
    if (ws && ws.readyState === WebSocket.OPEN && projectIds.length > 0) {
      console.log('WebSocket重新订阅项目:', projectIds)
      subscribeToProjects(ws, projectIds)
    } else {
      console.log('不满足重新订阅条件:', {
        hasWs: !!ws,
        isOpen: ws?.readyState === WebSocket.OPEN,
        hasProjectIds: projectIds.length > 0
      })
    }
  }, [projectIds])

  return {
    isConnected: isConnectedRef.current,
    sendMessage,
    subscribeProjects,
    unsubscribe,
    reconnect,
  }
}
