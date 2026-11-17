import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 开发模式：把 /api 请求转发给本地 FastAPI（127.0.0.1:8000）
// 生产构建：产物由 FastAPI 托管，不需要代理
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    chunkSizeWarningLimit: 1500,
  },
})
