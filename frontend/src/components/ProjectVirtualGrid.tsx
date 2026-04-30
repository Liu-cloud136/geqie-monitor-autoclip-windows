import React, { useCallback } from 'react'
import { Grid } from 'react-window'
import ProjectCard from './ProjectCard'
import { Project } from '../store/useProjectStore'

interface ProjectVirtualGridProps {
  projects: Project[]
  onDelete: (id: string) => void
  onRetry: (projectId: string) => void
  onClick: (project: Project) => void
  columnCount?: number
  columnWidth?: number
  rowHeight?: number
}

const ProjectVirtualGrid: React.FC<ProjectVirtualGridProps> = ({
  projects,
  onDelete,
  onRetry,
  onClick,
  columnCount = 4,
  columnWidth = 360, // 卡片宽度 + gap
  rowHeight = 380,    // 卡片高度 + gap
}) => {
  // 计算总行数
  const rowCount = Math.ceil(projects.length / columnCount)

  // Grid cell 渲染器
  const Cell = useCallback((props: { columnIndex: number; rowIndex: number; style: React.CSSProperties; projects: Project[]; onDelete: (id: string) => void; onRetry: (projectId: string) => void; onClick: (project: Project) => void }) => {
    const { columnIndex, rowIndex, style, projects: cellProjects, onDelete: cellOnDelete, onRetry: cellOnRetry, onClick: cellOnClick } = props
    const itemIndex = rowIndex * columnCount + columnIndex
    const project = cellProjects[itemIndex]

    if (!project) {
      return <div style={style} />
    }

    return (
      <div style={style}>
        <ProjectCard
          project={project}
          onDelete={cellOnDelete}
          onRetry={() => cellOnRetry(project.id)}
          onClick={() => cellOnClick(project)}
        />
      </div>
    )
  }, [columnCount])

  return (
    <Grid
      className="project-virtual-grid"
      columnCount={columnCount}
      columnWidth={columnWidth}
      defaultHeight={rowHeight}
      defaultWidth={columnWidth}
      rowCount={rowCount}
      rowHeight={rowHeight}
      cellComponent={Cell}
      cellProps={{ projects, onDelete, onRetry, onClick } as any}
      style={{ overflowX: 'hidden', height: Math.min(800, rowCount * rowHeight) }}
    />
  )
}

export default ProjectVirtualGrid
