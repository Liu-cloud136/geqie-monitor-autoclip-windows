/**
 * 时间轴编辑标签页组件
 * 显示时间轴编辑器
 */

import React from 'react'
import { Card, Empty, Typography } from 'antd'
import { VideoCameraOutlined } from '@ant-design/icons'
import TimelineEditor from '../components/TimelineEditor'

const { Text } = Typography

/**
 * 时间轴编辑标签页组件属性
 */
export interface EditorTabContentProps {
  currentProject: {
    id: string
    status: string
  }
  handleOpenSelectClips: () => void
}

/**
 * 时间轴编辑标签页组件
 * @param props - 组件属性
 * @returns React组件
 */
const EditorTabContent: React.FC<EditorTabContentProps> = ({
  currentProject,
  handleOpenSelectClips
}) => {
  if (currentProject.status !== 'completed') {
    return (
      <Card style={{ marginTop: '16px', borderRadius: '16px' }}>
        <Empty
          description={
            <div>
              <Text>项目还未完成处理</Text>
              <br />
              <Text type="secondary">处理完成后可使用时间轴编辑功能</Text>
            </div>
          }
          image={<VideoCameraOutlined style={{ fontSize: '64px', color: '#d9d9d9' }} />}
        />
      </Card>
    )
  }

  return (
    <div style={{ marginTop: '16px' }}>
      <TimelineEditor
        projectId={currentProject.id}
        onAddClips={handleOpenSelectClips}
      />
    </div>
  )
}

export default EditorTabContent
