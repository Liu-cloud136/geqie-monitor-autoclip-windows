import { Routes, Route } from 'react-router-dom'
import { Layout } from 'antd'
import HomePage from './pages/HomePage'
import ProjectDetailPage from './pages/ProjectDetailPage'
import ClipDetailPage from './pages/ClipDetailPage'
import SettingsPage from './pages/SettingsPage'
import AIResponsePage from './pages/AIResponsePage'
import WebSocketDebugPage from './pages/WebSocketDebugPage'
import MonitorTodayPage from './pages/MonitorTodayPage'
import MonitorMultiRoomPage from './pages/MonitorMultiRoomPage'
import MonitorAnalysisPage from './pages/MonitorAnalysisPage'
import MonitorHistoryPage from './pages/MonitorHistoryPage'
import Header from './components/Header'

const { Content } = Layout

function App() {
  console.log('🎬 App组件已加载');
  
  return (
    <Layout style={{ minHeight: '100vh', background: '#f5f5f7' }}>
      <Header />
      <Content style={{ marginTop: '72px' }}>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/project/:id" element={<ProjectDetailPage />} />
          <Route path="/project/:projectId/clip/:clipId" element={<ClipDetailPage />} />
          <Route path="/project/:projectId/ai" element={<AIResponsePage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/debug/websocket" element={<WebSocketDebugPage />} />
          
          <Route path="/monitor/today" element={<MonitorTodayPage />} />
          <Route path="/monitor/multi-room" element={<MonitorMultiRoomPage />} />
          <Route path="/monitor/analysis" element={<MonitorAnalysisPage />} />
          <Route path="/monitor/history" element={<MonitorHistoryPage />} />
        </Routes>
      </Content>
    </Layout>
  )
}

export default App