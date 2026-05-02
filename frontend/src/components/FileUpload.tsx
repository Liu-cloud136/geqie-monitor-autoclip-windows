import React, { useState } from 'react'
import { Button, message, Progress, Space, Typography, Input, Select } from 'antd'
import { InboxOutlined, VideoCameraOutlined, MessageOutlined } from '@ant-design/icons'
import { useDropzone } from 'react-dropzone'
import { projectApi } from '../services/api'
import { useProjectStore } from '../store/useProjectStore'

const { Text, Title } = Typography

interface FileUploadProps {
  onUploadSuccess?: (projectId: string) => void
}

const DANMAKU_SOURCE_TYPES = [
  { value: 'bilibili', label: '哔哩哔哩 (Bilibili)' },
  { value: 'youtube', label: 'YouTube' },
  { value: 'douyu', label: '斗鱼 (Douyu)' },
  { value: 'huya', label: '虎牙 (Huya)' },
  { value: 'custom', label: '自定义 (Custom)' },
]

const FileUpload: React.FC<FileUploadProps> = ({ onUploadSuccess }) => {
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [projectName, setProjectName] = useState('')
  const [danmakuSourceType, setDanmakuSourceType] = useState('bilibili')
  const [files, setFiles] = useState<{
    video?: File
    danmaku?: File
  }>({})

  const { addProject } = useProjectStore()

  const onDrop = (acceptedFiles: File[]) => {
    const newFiles = { ...files }

    acceptedFiles.forEach(file => {
      const extension = file.name.split('.').pop()?.toLowerCase()

      if (['mp4', 'avi', 'mov', 'mkv', 'webm'].includes(extension || '')) {
        newFiles.video = file
        setProjectName(file.name.replace(/\.[^/.]+$/, ''))
      } else if (['xml', 'json', 'ass', 'txt'].includes(extension || '')) {
        newFiles.danmaku = file
      }
    })

    setFiles(newFiles)
  }

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'video/*': ['.mp4', '.avi', '.mov', '.mkv', '.webm'],
      'application/xml': ['.xml'],
      'application/json': ['.json'],
      'text/plain': ['.ass', '.txt']
    },
    multiple: true
  })

  const handleUpload = async () => {
    if (!files.video) {
      message.error('请选择视频文件')
      return
    }

    if (!projectName.trim()) {
      message.error('请输入项目名称')
      return
    }

    setUploading(true)
    setUploadProgress(0)

    try {
      console.log('开始上传文件:', {
        video_file: files.video.name,
        danmaku_file: files.danmaku?.name,
        project_name: projectName.trim(),
        danmaku_source_type: danmakuSourceType
      })

      const newProject = await projectApi.uploadFiles({
        video_file: files.video,
        danmaku_file: files.danmaku,
        project_name: projectName.trim(),
        danmaku_source_type: danmakuSourceType
      }, {
        onUploadProgress: (progressEvent) => {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          setUploadProgress(progress)
        }
      })
      
      console.log('上传成功，项目信息:', newProject)
      
      addProject(newProject)
      const danmakuMessage = files.danmaku ? `弹幕文件: ${files.danmaku.name}` : ''
      message.success(`项目创建成功！${danmakuMessage ? danmakuMessage + '，' : ''}AI正在自动处理视频，请稍候...`)

      // 重置状态
      setFiles({})
      setProjectName('')
      setUploadProgress(0)
      setUploading(false)
      
      if (onUploadSuccess) {
        onUploadSuccess(newProject.id)
      }
      
    } catch (error: unknown) {
      console.error('上传失败，详细错误:', error)
      
      let errorMessage = '上传失败，请重试'
      let errorType = 'error'
      
      const axiosError = error as { response?: { status?: number; data?: { detail?: string } }; code?: string; userMessage?: string; message?: string }
      
      // 根据错误类型提供更友好的错误信息
      if (axiosError.response?.status === 413) {
        errorMessage = '文件太大，请选择较小的视频文件'
        errorType = 'warning'
      } else if (axiosError.response?.status === 415) {
        errorMessage = '不支持的文件格式，请选择MP4、AVI、MOV、MKV或WEBM格式的视频'
        errorType = 'warning'
      } else if (axiosError.response?.status === 400) {
        if (axiosError.response?.data?.detail) {
          errorMessage = axiosError.response.data.detail
        } else {
          errorMessage = '文件格式或内容有问题，请检查后重试'
        }
      } else if (axiosError.response?.status === 500) {
        errorMessage = '服务器处理文件时出错，请稍后重试'
      } else if (axiosError.code === 'ECONNABORTED') {
        errorMessage = '上传超时，请检查网络连接后重试'
      } else if (axiosError.response?.data?.detail) {
        errorMessage = axiosError.response.data.detail
      } else if (axiosError.userMessage) {
        errorMessage = axiosError.userMessage
      } else if (axiosError.message) {
        errorMessage = axiosError.message
      }
      
      // 显示错误信息
      if (errorType === 'warning') {
        message.warning(errorMessage)
      } else {
        message.error(errorMessage)
      }
      
      // 如果是网络错误，提供重试建议
      if (axiosError.code === 'ECONNABORTED' || (axiosError.response?.status !== undefined && axiosError.response.status >= 500)) {
        message.info('如果问题持续存在，请检查网络连接或联系技术支持', 5)
      }
    } finally {
      setUploading(false)
    }
  }

  const removeFile = (type: 'video' | 'danmaku') => {
    setFiles(prev => {
      const newFiles = { ...prev }
      delete newFiles[type]
      return newFiles
    })
  }

  return (
    <div style={{
      borderRadius: '16px',
      padding: '0',
      transition: 'all 0.3s ease',
      position: 'relative',
      overflow: 'hidden',
      width: '100%',
      margin: '0 auto'
    }}>
      <div
        {...getRootProps()}
        className={`upload-area ${isDragActive ? 'dragover' : ''}`}
        style={{
          padding: '24px 16px',
          textAlign: 'center',
          marginBottom: '16px',
          background: isDragActive ? 'rgba(79, 172, 254, 0.08)' : '#ffffff',
          border: `2px dashed ${isDragActive ? '#4facfe' : '#d0d0d0'}`,
          borderRadius: '16px',
          cursor: 'pointer',
          transition: 'all 0.3s ease',
          position: 'relative',
          boxSizing: 'border-box'
        }}
      >
        <input {...getInputProps()} />
        <div style={{
          width: '48px',
          height: '48px',
          margin: '0 auto 12px',
          background: isDragActive ? 'rgba(79, 172, 254, 0.2)' : 'rgba(79, 172, 254, 0.1)',
          borderRadius: '50%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          transition: 'all 0.3s ease',
          border: '1px solid rgba(79, 172, 254, 0.2)'
        }}>
          <InboxOutlined style={{
            fontSize: '20px',
            color: isDragActive ? '#4facfe' : '#4facfe'
          }} />
        </div>
        <div>
          <Text strong style={{
            color: '#1a1a1a',
            fontSize: '16px',
            display: 'block',
            marginBottom: '8px',
            fontWeight: 600
          }}>
            {isDragActive ? '松开鼠标导入文件' : '点击或拖拽文件到此区域'}
          </Text>
          <Text style={{ color: '#666666', fontSize: '14px', lineHeight: '1.5' }}>
            支持视频（MP4、AVI、MOV、MKV、WebM）和弹幕（XML、JSON、ASS、TXT）格式
          </Text>
        </div>
      </div>

      {/* 项目名称输入 - 只有在选择文件后才显示 */}
      {files.video && (
        <div style={{ marginBottom: '16px' }}>
          <Text strong style={{ color: '#1a1a1a', fontSize: '14px', marginBottom: '8px', display: 'block' }}>
            项目名称
          </Text>
          <Input
            value={projectName}
            onChange={(e) => setProjectName(e.target.value)}
            placeholder="请输入项目名称，用于标识您的视频项目"
            style={{ 
              height: '40px',
              borderRadius: '12px',
              fontSize: '14px',
              background: '#ffffff',
              border: '1px solid #d0d0d0',
              color: '#1a1a1a'
            }}
          />
        </div>
      )}

      {/* 文件列表 */}
      {Object.keys(files).length > 0 && (
        <div style={{ marginBottom: '16px' }}>
          <Text strong style={{ color: '#1a1a1a', fontSize: '14px', marginBottom: '12px', display: 'block' }}>
            已选择文件
          </Text>
          <Space direction="vertical" style={{ width: '100%' }} size="small">
            {files.video && (
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'space-between',
                padding: '16px',
                background: '#ffffff',
                borderRadius: '12px',
                border: '1px solid #e0e0e0'
              }}>
                <Space size="middle">
                  <div style={{
                    width: '36px',
                    height: '36px',
                    background: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
                    borderRadius: '8px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    boxShadow: '0 4px 12px rgba(79, 172, 254, 0.3)'
                  }}>
                    <VideoCameraOutlined style={{ color: '#ffffff', fontSize: '16px' }} />
                  </div>
                  <div>
                    <Text style={{ color: '#1a1a1a', fontWeight: 600, display: 'block', fontSize: '14px' }}>
                      {files.video.name}
                    </Text>
                    <Text style={{ color: '#999999', fontSize: '13px' }}>
                      {(files.video.size / 1024 / 1024).toFixed(2)} MB
                    </Text>
                  </div>
                </Space>
                <Button 
                  size="small" 
                  type="text" 
                  onClick={() => removeFile('video')}
                  style={{ 
                    color: '#ff6b6b',
                    borderRadius: '8px',
                    padding: '4px 12px',
                    fontSize: '12px'
                  }}
                >
                  移除
                </Button>
              </div>
            )}

            {files.danmaku && (
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'space-between',
                padding: '16px',
                background: '#ffffff',
                borderRadius: '12px',
                border: '1px solid #e0e0e0'
              }}>
                <Space size="middle">
                  <div style={{
                    width: '36px',
                    height: '36px',
                    background: 'linear-gradient(135deg, #52c41a 0%, #73d13d 100%)',
                    borderRadius: '8px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    boxShadow: '0 4px 12px rgba(82, 196, 26, 0.3)'
                  }}>
                    <MessageOutlined style={{ color: '#ffffff', fontSize: '16px' }} />
                  </div>
                  <div>
                    <Text style={{ color: '#1a1a1a', fontWeight: 600, display: 'block', fontSize: '14px' }}>
                      {files.danmaku.name}
                    </Text>
                    <Text style={{ color: '#999999', fontSize: '13px' }}>
                      {(files.danmaku.size / 1024).toFixed(2)} KB
                    </Text>
                  </div>
                </Space>
                <Button 
                  size="small" 
                  type="text" 
                  onClick={() => removeFile('danmaku')}
                  style={{ 
                    color: '#ff6b6b',
                    borderRadius: '8px',
                    padding: '4px 12px',
                    fontSize: '12px'
                  }}
                >
                  移除
                </Button>
              </div>
            )}
          </Space>
        </div>
      )}

      {/* 弹幕来源类型选择器 - 只有在选择弹幕文件后才显示 */}
      {files.danmaku && (
        <div style={{ marginBottom: '16px' }}>
          <Text strong style={{ color: '#1a1a1a', fontSize: '14px', marginBottom: '8px', display: 'block' }}>
            弹幕来源类型
          </Text>
          <Select
            value={danmakuSourceType}
            onChange={setDanmakuSourceType}
            style={{ width: '100%' }}
            size="large"
            options={DANMAKU_SOURCE_TYPES}
          />
          <Text type="secondary" style={{ fontSize: '12px', marginTop: '4px', display: 'block' }}>
            选择弹幕来源平台，以便正确解析弹幕格式
          </Text>
        </div>
      )}

      {/* 导入进度 */}
      {uploading && (
        <div style={{
          marginBottom: '16px',
          padding: '20px',
          background: '#ffffff',
          borderRadius: '16px',
          border: '1px solid #e0e0e0'
        }}>
          <div style={{ marginBottom: '12px' }}>
            <Text style={{ color: '#1a1a1a', fontWeight: 600, fontSize: '14px' }}>导入进度</Text>
            <Text style={{ color: '#4facfe', float: 'right', fontWeight: 600, fontSize: '14px' }}>
              {uploadProgress}%
            </Text>
          </div>
          <Progress
            percent={uploadProgress}
            status="active"
            strokeColor={{
              '0%': '#4facfe',
              '100%': '#00f2fe',
            }}
            trailColor="#f0f0f0"
            strokeWidth={6}
            showInfo={false}
            style={{ marginBottom: '8px' }}
          />
          <Text style={{ color: '#999999', fontSize: '13px', marginTop: '8px', display: 'block', textAlign: 'center' }}>
            正在导入文件，请稍候...
          </Text>
        </div>
      )}

      {/* 上传按钮 - 只有在选择文件后才显示 */}
      {files.video && (
        <div style={{ textAlign: 'center', marginTop: '8px' }}>
          <Button 
            type="primary" 
            size="large"
            loading={uploading}
            disabled={!files.video || !projectName.trim()}
            onClick={handleUpload}
            style={{
              height: '48px',
              padding: '0 32px',
              borderRadius: '24px',
              background: uploading ? '#d0d0d0' : 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
              border: 'none',
              fontSize: '16px',
              fontWeight: 600,
              boxShadow: uploading ? 'none' : '0 4px 20px rgba(79, 172, 254, 0.4)',
              transition: 'all 0.3s ease'
            }}
          >
            {uploading ? '导入中...' : '开始导入并处理'}
          </Button>
        </div>
      )}
    </div>
  )
}

export default FileUpload