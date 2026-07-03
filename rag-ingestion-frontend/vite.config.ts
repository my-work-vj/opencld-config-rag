import path from 'path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  base: '/ingestion/',
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3001,
    allowedHosts: true,
    proxy: {
      '/ingestion/api': {
        target: 'http://localhost:8081/api/v1',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/ingestion\/api/, ''),
      },
    },
  },
})
