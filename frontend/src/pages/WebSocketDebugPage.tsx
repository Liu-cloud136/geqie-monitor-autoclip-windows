/**
 * WebSocket调试页面 - 用于测试WebSocket连接和进度更新
 */
import React, { useEffect, useState, useMemo } from 'react'
import { Card, Button, Space, Typography, Alert, List, Tag } from 'antd'
import { useSimpleProgressStore } from '../stores/useSimpleProgressStore'
import { useProjectStore } from '../store/useProjectStore'
import { projectApi } from '../services/api'
import { useWebSocket, ProgressUpdateMessage } from '../hooks/useWebSocket'

const { Title, Text, Paragraph } = Typography

const WebSocketDebugPage: React.FC = () => {
  const [connectionStatus, setConnectionStatus] = useState('未知')
  const [userId, setUserId] = useState('')
  const [logs, setLogs] = useState<string[]>([])
  const progressStore = useSimpleProgressStore()
  const projectStore = useProjectStore()

  // 获取用户ID
  const currentUserId = useMemo(() => {
    const stored = localStorage.getItem('websocket_user_id')
    if (stored) return stored
    const newId = `user_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
    localStorage.setItem('websocket_user_id', newId)
    return newId
  }, [])

  // 获取所有项目ID（用于订阅）
  const allProjectIds = useMemo(() => {
    return projectStore.projects.map(p => p.id)
  }, [projectStore.projects])

  // 建立WebSocket连接
  const wsHook = useWebSocket({
    userId: currentUserId,
    projectIds: allProjectIds,
    onProgress: (message: ProgressUpdateMessage) => {
      addLog(`收到进度更新: ${message.project_id} - ${message.stage} (${message.percent}%)`)
      progressStore.updateProgress(
        message.project_id,
        message.stage,
        message.percent,
        message.message,
        message.estimated_remaining
      )
    },
    onConnect: () => {
      addLog('✅ WebSocket已连接')
      setConnectionStatus('已连接')
    },
    onDisconnect: () => {
      addLog('⚠️ WebSocket已断开')
      setConnectionStatus('未连接')
    },
    onError: (error) => {
      addLog(`❌ WebSocket错误: ${error}`)
    }
  })

  useEffect(() => {
    setUserId(currentUserId)
    
    // 定期更新状态
    const interval = setInterval(() => {
      const connected = (window as any).__WS_CONNECTED__
      setConnectionStatus(connected ? '已连接' : '未连接')
    }, 1000)

    return () => clearInterval(interval)
  }, [currentUserId])

  const addLog = (message: string) => {
    setLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${message}`])
  }

  const testConnection = () => {
    addLog('测试WebSocket连接...')
    addLog(`WebSocket实例: ${wsHook ? '存在' : '不存在'}`)
    addLog(`连接状态: ${wsHook?.isConnected ? '已连接' : '未连接'}`)
    addLog(`用户ID: ${currentUserId}`)
    addLog(`订阅项目数: ${allProjectIds.length}`)
  }

  const testSubscribe = async () => {
    addLog('测试订阅...')
    
    if (allProjectIds.length === 0) {
      addLog('没有项目可以订阅')
      return
    }

    addLog(`当前已订阅 ${allProjectIds.length} 个项目`)
    addLog(`项目ID列表: ${allProjectIds.join(', ')}`)
    
    if (wsHook && wsHook.subscribeProjects) {
      wsHook.subscribeProjects(allProjectIds)
      addLog('已发送订阅请求')
    }
  }

  const testProgressUpdate = () => {
    addLog('测试进度更新...')
    const projects = projectStore.projects
    const project = projects[0]
    
    if (!project) {
      addLog('没有项目')
      return
    }

    progressStore.updateProgress(
      project.id,
      'TEST',
      50,
      '手动测试进度更新',
      120
    )
    addLog(`已更新项目 ${project.id} 的进度`)
  }

  const checkProgressStore = () => {
    addLog('检查进度store...')
    const allProgress = progressStore.getAllProgress()
    addLog(`进度数据: ${JSON.stringify(allProgress, null, 2)}`)
  }

  const triggerBackendProgress = async () => {
    addLog('触发后端进度消息...')
    
    if (allProjectIds.length === 0) {
      addLog('没有项目，请先创建一个项目')
      return
    }

    const projectId = allProjectIds[0]
    addLog(`使用项目ID: ${projectId}`)

    try {
      // 调用后端API触发进度更新
      const response = await fetch(`/api/v1/projects/${projectId}/trigger-progress?stage=TEST&percent=75&message=后端触发的测试进度`, {
        method: 'POST'
      })
      
      if (response.ok) {
        const result = await response.json()
        addLog(`✅ 后端进度触发成功: ${JSON.stringify(result)}`)
      } else {
        const error = await response.text()
        addLog(`❌ 后端进度触发失败: ${response.status} - ${error}`)
      }
    } catch (error) {
      addLog(`❌ 触发失败: ${error}`)
    }
  }

  const loadProjects = async () => {
    addLog('加载项目列表...')
    try {
      const projects = await projectApi.getProjects()
      projectStore.setProjects(projects || [])
      addLog(`✅ 已加载 ${projects?.length || 0} 个项目`)
    } catch (error) {
      addLog(`❌ 加载项目失败: ${error}`)
    }
  }

  const createTestProject = async () => {
    addLog('创建测试项目...')
    try {
      // 创建一个简单的测试项目
      const response = await fetch('/api/v1/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: `测试项目_${Date.now()}`,
          project_type: 'default',
          source_file: 'test_video.mp4'
        })
      })
      
      if (response.ok) {
        const project = await response.json()
        addLog(`✅ 测试项目创建成功: ${project.id}`)
        await loadProjects()
      } else {
        const error = await response.text()
        addLog(`❌ 创建失败: ${response.status} - ${error}`)
      }
    } catch (error) {
      addLog(`❌ 创建失败: ${error}`)
    }
  }

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <Title level={2}>WebSocket调试页面</Title>
      
      <Space direction="vertical" style={{ width: '100%' }} size="large">
        {/* 连接状态 */}
        <Card title="连接状态" size="small">
          <Space direction="vertical" style={{ width: '100%' }}>
            <div>
              <Text strong>状态: </Text>
              <Tag color={connectionStatus === '已连接' ? 'success' : 'default'}>
                {connectionStatus}
              </Tag>
            </div>
            <div>
              <Text strong>用户ID: </Text>
              <Text code>{userId}</Text>
            </div>
            <div>
              <Text strong>处理中的项目: </Text>
              <Text code>{projectStore.projects.filter(p => p.status === 'processing' || p.status === 'pending').length}</Text>
            </div>
          </Space>
        </Card>

        {/* 测试按钮 */}
        <Card title="测试操作" size="small">
          <Space wrap>
            <Button onClick={loadProjects}>加载项目</Button>
            <Button onClick={createTestProject} type="primary">创建测试项目</Button>
            <Button onClick={testConnection}>测试连接</Button>
            <Button onClick={testSubscribe}>测试订阅</Button>
            <Button onClick={testProgressUpdate}>测试进度更新</Button>
            <Button onClick={checkProgressStore}>检查进度Store</Button>
            <Button onClick={triggerBackendProgress} type="primary" danger>触发后端进度</Button>
          </Space>
        </Card>

        {/* 日志 */}
        <Card title="日志" size="small">
          <List
            dataSource={logs}
            renderItem={item => (
              <List.Item style={{ padding: '4px 0', border: 'none' }}>
                <Text style={{ fontSize: '12px', fontFamily: 'monospace' }}>{item}</Text>
              </List.Item>
            )}
            style={{ maxHeight: '300px', overflow: 'auto' }}
          />
        </Card>

        {/* 进度数据 */}
        <Card title="当前进度数据" size="small">
          <Paragraph>
            <pre style={{ fontSize: '12px', maxHeight: '300px', overflow: 'auto' }}>
              {JSON.stringify(progressStore.getAllProgress(), null, 2)}
            </pre>
          </Paragraph>
        </Card>

        {/* 项目列表 */}
        <Card title="项目列表" size="small">
          <List
            dataSource={projectStore.projects}
            renderItem={project => (
              <List.Item>
                <Space>
                  <Tag color={project.status === 'processing' ? 'processing' : 'default'}>
                    {project.status}
                  </Tag>
                  <Text code>{project.id}</Text>
                  <Text type="secondary">{project.name || '未命名'}</Text>
                </Space>
              </List.Item>
            )}
          />
        </Card>
      </Space>
    </div>
  )
}

export default WebSocketDebugPage
