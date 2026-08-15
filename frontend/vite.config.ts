import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
    // ⭐ 忽略编辑器原子替换的临时目录（*.tmpdir），防止 Windows watcher EBUSY 崩溃
    watch: {
      ignored: ['**/*.tmpdir/**'],
    },
  },
})
