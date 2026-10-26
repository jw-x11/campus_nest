import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5001',
        changeOrigin: true,
        // Forward WebSocket upgrades too, for /api/messages/ws.
        ws: true,
      },
      '/media': {
        target: 'http://127.0.0.1',
        changeOrigin: true,
      },
    },
  },
})
