import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    // Allow ngrok (and similar tunnels) when sharing the dev server externally
    allowedHosts: process.env.VITE_ALLOW_ALL_HOSTS === 'true'
      ? true
      : ['.ngrok-free.dev', '.ngrok.io', '.ngrok.app', 'localhost'],
    proxy: {
      '/api': {
        target: process.env.VITE_API_PROXY_TARGET || 'http://localhost:8000',
        changeOrigin: true,
      },
      '/health': {
        target: process.env.VITE_API_PROXY_TARGET || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
