import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const getBackendUrl = () => {
  return process.env.VITE_BACKEND_URL || 'http://localhost:8000'
}

const getMonitorUrl = () => {
  return process.env.VITE_MONITOR_URL || 'http://localhost:5000'
}

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: getBackendUrl(),
        changeOrigin: true,
        secure: false,
        ws: true
      },
      '/monitor-api': {
        target: getMonitorUrl(),
        changeOrigin: true,
        secure: false,
        ws: true,
        rewrite: (path) => path.replace(/^\/monitor-api/, '/api')
      },
      '/monitor-static': {
        target: getMonitorUrl(),
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path.replace(/^\/monitor-static/, '/static')
      }
    },
    allowedHosts: [
      'localhost'
    ]
  }
})
