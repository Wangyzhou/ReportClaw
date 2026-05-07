import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      // 把 chat stream 转发到本机 Python 5-Agent server (DeepSeek 真链路)
      '/api/chat/stream': {
        target: 'http://localhost:8081',
        changeOrigin: true,
      },
      // 其他 API (sessions / kb / tasks) 仍走 Spring Boot
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },
})
