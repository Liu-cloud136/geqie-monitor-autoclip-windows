import React, { useState } from 'react'
import { Layout, Button, Menu, Dropdown, Space, Typography, Badge } from 'antd'
import {
  SettingOutlined,
  HomeOutlined,
  VideoCameraOutlined,
  BarChartOutlined,
  FileTextOutlined,
  GlobalOutlined,
  MoreOutlined,
  DownOutlined
} from '@ant-design/icons'
import { useNavigate, useLocation } from 'react-router-dom'

const { Header: AntHeader } = Layout
const { Text } = Typography

const MONITOR_URL = 'http://localhost:5000'

const Header: React.FC = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const isHomePage = location.pathname === '/'
  const isSettingsPage = location.pathname === '/settings'
  const isMonitorPage = location.pathname.startsWith('/monitor')

  const navigateToMonitor = (path?: string) => {
    const targetPath = path ? `${MONITOR_URL}${path}` : MONITOR_URL
    window.open(targetPath, '_blank')
  }

  const monitorMenuItems = [
    {
      key: 'today',
      icon: <FileTextOutlined />,
      label: '今日数据',
      onClick: () => navigateToMonitor('/')
    },
    {
      key: 'multi-room',
      icon: <GlobalOutlined />,
      label: '多房间监控',
      onClick: () => navigateToMonitor('/multi-room')
    },
    {
      key: 'analysis',
      icon: <BarChartOutlined />,
      label: '弹幕分析',
      onClick: () => navigateToMonitor('/analysis')
    }
  ]

  const aiClipMenuItems = [
    {
      key: 'home',
      icon: <HomeOutlined />,
      label: '项目列表',
      onClick: () => navigate('/')
    },
    {
      key: 'settings',
      icon: <SettingOutlined />,
      label: '设置',
      onClick: () => navigate('/settings')
    }
  ]

  return (
    <AntHeader
      className="glass-effect"
      style={{
        padding: '0 32px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        height: '72px',
        position: 'sticky',
        top: 0,
        zIndex: 1000,
        backdropFilter: 'blur(20px)',
        background: 'rgba(26, 26, 26, 0.9)',
        borderBottom: '1px solid rgba(255, 255, 255, 0.1)'
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '32px' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            cursor: 'pointer',
            transition: 'all 0.2s ease'
          }}
          onClick={() => navigate('/')}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = 'scale(1.05)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = 'scale(1)'
          }}
        >
          <span
            style={{
              fontSize: '24px',
              fontWeight: '700',
              background: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
              fontFamily:
                '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
              letterSpacing: '-0.5px',
              textShadow: '0 0 20px rgba(79, 172, 254, 0.3)',
              filter: 'drop-shadow(0 2px 4px rgba(79, 172, 254, 0.2))'
            }}
          >
            AutoClip
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Button
            type={isMonitorPage ? 'primary' : 'text'}
            icon={<VideoCameraOutlined />}
            onClick={() => navigateToMonitor('/')}
            style={{
              color: isMonitorPage ? '#fff' : '#666666',
              background: isMonitorPage
                ? 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)'
                : 'transparent',
              border: 'none',
              borderRadius: '8px',
              height: '40px',
              padding: '0 16px',
              fontWeight: isMonitorPage ? 500 : 400
            }}
          >
            <Space>
              弹幕监控
              <DownOutlined style={{ fontSize: '10px' }} />
            </Space>
          </Button>

          <Button
            type={!isMonitorPage && !isSettingsPage ? 'primary' : 'text'}
            icon={<FileTextOutlined />}
            onClick={() => navigate('/')}
            style={{
              color: !isMonitorPage && !isSettingsPage ? '#fff' : '#666666',
              background:
                !isMonitorPage && !isSettingsPage
                  ? 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)'
                  : 'transparent',
              border: 'none',
              borderRadius: '8px',
              height: '40px',
              padding: '0 16px',
              fontWeight: !isMonitorPage && !isSettingsPage ? 500 : 400
            }}
          >
            AI 切片
          </Button>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        {!isHomePage && !isMonitorPage && (
          <Button
            type="default"
            icon={<HomeOutlined />}
            onClick={() => navigate('/')}
            style={{
              borderRadius: '8px',
              height: '40px',
              padding: '0 16px'
            }}
          >
            返回项目列表
          </Button>
        )}

        <Button
          type="text"
          icon={<SettingOutlined />}
          onClick={() => navigate('/settings')}
          style={{
            color: '#666666',
            border: '1px solid transparent',
            borderRadius: '8px',
            height: '40px',
            padding: '0 16px'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = '#f5f5f5'
            e.currentTarget.style.borderColor = '#d0d0d0'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'transparent'
            e.currentTarget.style.borderColor = 'transparent'
          }}
        >
          设置
        </Button>

        <Dropdown
          menu={{ items: monitorMenuItems }}
          placement="bottomRight"
          arrow
        >
          <Button
            type="text"
            icon={<MoreOutlined />}
            style={{
              color: '#666666',
              borderRadius: '8px',
              height: '40px',
              padding: '0 12px'
            }}
          />
        </Dropdown>
      </div>
    </AntHeader>
  )
}

export default Header
