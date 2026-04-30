import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 获取后端地址，优先使用环境变量，否则使用 localhost
const getBackendUrl = () => {
  return process.env.VITE_BACKEND_URL || 'http://localhost:8000'
}

// https://vitejs.dev/config/
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
        ws: true,
        configure: (proxy, options) => {
          proxy.on('proxyReq', (proxyReq, req, res) => {
            console.log('代理请求:', req.method, req.url, '->', options.target + req.url)
          })
          proxy.on('proxyRes', (proxyRes, req, res) => {
            console.log('代理响应:', proxyRes.statusCode, req.url)
          })
          proxy.on('error', (err, req, res) => {
            console.error('代理错误:', err)
          })
        }
      }
    },
    allowedHosts: [
      'localhost'
    ]
  }
})
