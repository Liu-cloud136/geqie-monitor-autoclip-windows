import React from 'react'
import { Layout, Button, Menu, Dropdown, Space, Badge } from 'antd'
import {
  SettingOutlined,
  HomeOutlined,
  VideoCameraOutlined,
  BarChartOutlined,
  HistoryOutlined,
  GlobalOutlined,
  DashboardOutlined
} from '@ant-design/icons'
import { useNavigate, useLocation } from 'react-router-dom'

const { Header: AntHeader } = Layout

const Header: React.FC = () => {
  const navigate = useNavigate()
  const location = useLocation()

  const isMonitorPath = location.pathname.startsWith('/monitor')
  const isAIClipPath = !isMonitorPath && location.pathname !== '/settings'
  const isSettingsPath = location.pathname === '/settings'

  const monitorMenuItems = [
    {
      key: '/monitor/today',
      icon: <DashboardOutlined />,
      label: '今日数据',
      onClick: () => navigate('/monitor/today')
    },
    {
      key: '/monitor/multi-room',
      icon: <GlobalOutlined />,
      label: '多房间监控',
      onClick: () => navigate('/monitor/multi-room')
    },
    {
      key: '/monitor/analysis',
      icon: <BarChartOutlined />,
      label: '弹幕分析',
      onClick: () => navigate('/monitor/analysis')
    },
    {
      key: '/monitor/history',
      icon: <HistoryOutlined />,
      label: '历史数据',
      onClick: () => navigate('/monitor/history')
    }
  ]

  const aiClipMenuItems = [
    {
      key: '/',
      icon: <HomeOutlined />,
      label: '项目列表',
      onClick: () => navigate('/')
    }
  ]

  return (
    <AntHeader
      style={{
        padding: '0 32px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        height: '72px',
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        zIndex: 1000,
        backdropFilter: 'blur(20px)',
        background: 'rgba(26, 26, 26, 0.95)',
        borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.15)'
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
          <span
            style={{
              marginLeft: '8px',
              fontSize: '12px',
              color: '#8c8c8c',
              fontWeight: 500
            }}
          >
            全能系统
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <Dropdown
            menu={{
              items: monitorMenuItems,
              selectedKeys: [location.pathname]
            }}
            placement="bottomLeft"
            trigger={['click']}
          >
            <Button
              type={isMonitorPath ? 'primary' : 'text'}
              icon={<VideoCameraOutlined />}
              style={{
                color: isMonitorPath ? '#fff' : '#b0b0b0',
                background: isMonitorPath
                  ? 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)'
                  : 'transparent',
                border: 'none',
                borderRadius: '8px',
                height: '40px',
                padding: '0 20px',
                fontWeight: isMonitorPath ? 600 : 500,
                fontSize: '14px'
              }}
            >
              <Space>
                弹幕监控
                <Badge
                  dot
                  style={{
                    backgroundColor: isMonitorPath ? '#52c41a' : '#8c8c8c'
                  }}
                />
              </Space>
            </Button>
          </Dropdown>

          <Button
            type={isAIClipPath ? 'primary' : 'text'}
            icon={<DashboardOutlined />}
            onClick={() => navigate('/')}
            style={{
              color: isAIClipPath ? '#fff' : '#b0b0b0',
              background: isAIClipPath
                ? 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)'
                : 'transparent',
              border: 'none',
              borderRadius: '8px',
              height: '40px',
              padding: '0 20px',
              fontWeight: isAIClipPath ? 600 : 500,
              fontSize: '14px'
            }}
          >
            AI 切片
          </Button>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <Button
          type={isSettingsPath ? 'primary' : 'text'}
          icon={<SettingOutlined />}
          onClick={() => navigate('/settings')}
          style={{
            color: isSettingsPath ? '#fff' : '#b0b0b0',
            background: isSettingsPath
              ? 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)'
              : 'transparent',
            border: 'none',
            borderRadius: '8px',
            height: '40px',
            padding: '0 16px',
            fontWeight: 500
          }}
        >
          设置
        </Button>
      </div>
    </AntHeader>
  )
}

export default Header