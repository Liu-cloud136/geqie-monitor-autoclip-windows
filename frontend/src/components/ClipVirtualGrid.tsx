import React, { useCallback } from 'react'
import { Grid } from 'react-window'
import ClipCard from './ClipCard'
import { Clip } from '../store/useProjectStore'

interface ClipVirtualGridProps {
  clips: Clip[]
  projectId: string
  columnCount?: number
  columnWidth?: number
  rowHeight?: number
}

const ClipVirtualGrid: React.FC<ClipVirtualGridProps> = ({
  clips,
  projectId,
  columnCount = 3,
  columnWidth = 340, // 卡片宽度 + gap
  rowHeight = 320,   // 卡片高度 + gap
}) => {
  // 计算总行数
  const rowCount = Math.ceil(clips.length / columnCount)

  // Grid cell 渲染器
  const Cell = useCallback((props: { columnIndex: number; rowIndex: number; style: React.CSSProperties; clips: Clip[]; projectId: string }) => {
    const { columnIndex, rowIndex, style, clips, projectId: cellProjectId } = props
    const itemIndex = rowIndex * columnCount + columnIndex
    const clip = clips[itemIndex]

    if (!clip) {
      return <div style={style} />
    }

    return (
      <div style={style}>
        <ClipCard
          key={clip.id}
          clip={clip}
          projectId={cellProjectId}
        />
      </div>
    )
  }, [columnCount])

  return (
    <Grid
      className="clip-virtual-grid"
      columnCount={columnCount}
      columnWidth={columnWidth}
      defaultHeight={rowHeight}
      defaultWidth={columnWidth}
      rowCount={rowCount}
      rowHeight={rowHeight}
      cellComponent={Cell}
      cellProps={{ clips, projectId } as any}
      style={{ overflowX: 'hidden', height: Math.min(1000, rowCount * rowHeight) }}
    />
  )
}

export default ClipVirtualGrid
