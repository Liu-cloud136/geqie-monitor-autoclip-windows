/**
 * 切片列表标签页组件
 * 显示项目的视频切片列表
 */

import React from 'react'
import { Card, Title, Text, Radio, Empty, Tag, Button } from 'antd'
import { PlayCircleOutlined, VideoCameraOutlined } from '@ant-design/icons'
import ClipCard from '../components/ClipCard'
import { Clip } from '../types/api'

/**
 * 切片列表标签页组件属性
 */
export interface ClipsTabContentProps {
  currentProject: {
    id: string
    status: string
    clips?: Clip[]
    name?: string
  }
  sortBy: 'time' | 'score'
  setSortBy: (sort: 'time' | 'score') => void
  getSortedClips: () => Clip[]
  handleOpenSelectClips: () => void
}

/**
 * 切片列表标签页组件
 * @param props - 组件属性
 * @returns React组件
 */
const ClipsTabContent: React.FC<ClipsTabContentProps> = ({
  currentProject,
  sortBy,
  setSortBy,
  getSortedClips,
  handleOpenSelectClips
}) => {
  // 渲染处理中的切片列表
  if (currentProject.status !== 'completed') {
    return (
      <div>
        {currentProject.clips && currentProject.clips.length > 0 ? (
          <Card style={{ marginTop: '16px', borderRadius: '16px', border: '1px solid #e0e0e0' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
              <div>
                <Title level={4} style={{ margin: 0, fontWeight: 600 }}>已生成的片段（预览）</Title>
                <Text type="secondary" style={{ fontSize: '14px' }}>
                  正在处理中... 已生成 {currentProject.clips?.length || 0} 个片段
                </Text>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <Text style={{ fontSize: '13px', color: '#666666', fontWeight: 500 }}>排序</Text>
                <Radio.Group
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value)}
                  size="small"
                  buttonStyle="solid"
                >
                  <Radio.Button value="time" style={{ height: '28px', lineHeight: '26px' }}>时间</Radio.Button>
                  <Radio.Button value="score" style={{ height: '28px', lineHeight: '26px' }}>评分</Radio.Button>
                </Radio.Group>
              </div>
            </div>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
                gap: '20px',
                padding: '8px 0'
              }}
            >
              {getSortedClips().map((clip) => (
                <ClipCard
                  key={clip.id}
                  clip={clip}
                  projectId={currentProject.id}
                />
              ))}
            </div>

            <div style={{ marginTop: '16px', textAlign: 'center', padding: '12px', background: '#fffbe6', borderRadius: '8px' }}>
              <Text style={{ color: '#faad14', fontSize: '14px' }}>
                ℹ️ 更多片段正在处理中，完成后将自动更新...
              </Text>
            </div>
          </Card>
        ) : (
          <Card style={{ marginTop: '16px', borderRadius: '16px' }}>
            <Empty
              image={<PlayCircleOutlined style={{ fontSize: '64px', color: '#d9d9d9' }} />}
              description={
                <div>
                  <Text>项目还未完成处理</Text>
                  <br />
                  <Text type="secondary">处理完成后可查看视频片段</Text>
                </div>
              }
            />
          </Card>
        )}
      </div>
    )
  }

  // 已完成状态的切片列表
  return (
    <Card
      className="clip-list-card"
      style={{
        borderRadius: '16px',
        border: '1px solid #e0e0e0',
      }}
      styles={{
        body: {
          padding: '24px'
        }
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px' }}>
        <div>
          <Title level={4} style={{ margin: 0, color: '#1a1a1a', fontWeight: 600 }}>视频片段</Title>
          <Text type="secondary" style={{ color: '#666666', fontSize: '14px' }}>
            AI 已为您生成了 {currentProject.clips?.length || 0} 个精彩片段
          </Text>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <Button
            type="primary"
            icon={<VideoCameraOutlined />}
            onClick={handleOpenSelectClips}
            style={{
              background: 'linear-gradient(45deg, #52c41a, #73d13d)',
              border: 'none',
            }}
          >
            添加到时间轴
          </Button>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <Text style={{ fontSize: '13px', color: '#666666', fontWeight: 500 }}>排序</Text>
            <Radio.Group
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              size="small"
              buttonStyle="solid"
            >
              <Radio.Button
                 value="time"
                 style={{
                   fontSize: '13px',
                   height: '32px',
                   lineHeight: '30px',
                   padding: '0 16px',
                   background: sortBy === 'time' ? 'linear-gradient(45deg, #1890ff, #36cfc9)' : '#ffffff',
                   border: sortBy === 'time' ? '1px solid #1890ff' : '1px solid #d0d0d0',
                   color: sortBy === 'time' ? '#ffffff' : '#666666',
                   borderRadius: '6px 0 0 6px',
                   fontWeight: sortBy === 'time' ? 600 : 400,
                   boxShadow: sortBy === 'time' ? '0 2px 8px rgba(24, 144, 255, 0.3)' : 'none',
                   transition: 'all 0.2s ease'
                 }}
               >
                 时间
               </Radio.Button>
               <Radio.Button
                 value="score"
                 style={{
                   fontSize: '13px',
                   height: '32px',
                   lineHeight: '30px',
                   padding: '0 16px',
                   background: sortBy === 'score' ? 'linear-gradient(45deg, #1890ff, #36cfc9)' : '#ffffff',
                   border: sortBy === 'score' ? '1px solid #1890ff' : '1px solid #d0d0d0',
                   borderLeft: 'none',
                   color: sortBy === 'score' ? '#ffffff' : '#666666',
                   borderRadius: '0 6px 6px 0',
                   fontWeight: sortBy === 'score' ? 600 : 400,
                   boxShadow: sortBy === 'score' ? '0 2px 8px rgba(24, 144, 255, 0.3)' : 'none',
                   transition: 'all 0.2s ease'
                 }}
               >
                 评分
               </Radio.Button>
            </Radio.Group>
          </div>
        </div>
      </div>

      {currentProject.clips && currentProject.clips.length > 0 ? (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
            gap: '20px',
            padding: '8px 0'
          }}
        >
          {getSortedClips().map((clip) => (
            <ClipCard
              key={clip.id}
              clip={clip}
              projectId={currentProject.id}
            />
          ))}
        </div>
      ) : (
        <div style={{
          padding: '60px 0',
          textAlign: 'center',
          background: 'rgba(255,255,255,0.02)',
          borderRadius: '12px',
          border: '1px dashed #404040'
        }}>
          <Empty
            description={
              <Text style={{ color: '#888', fontSize: '14px' }}>暂无视频片段</Text>
            }
            image={<PlayCircleOutlined style={{ fontSize: '48px', color: '#555' }} />}
          />
        </div>
      )}
    </Card>
  )
}

export default ClipsTabContent
