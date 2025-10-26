import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  
  // 开发服务器配置
  server: {
    port: 5173,
    open: false,
  },
  
  // 构建配置
  build: {
    // 输出到 static/JS/dist 目录
    outDir: 'static/JS/dist',
    emptyOutDir: true,
    
    rollupOptions: {
      input: {
        settings: path.resolve(__dirname, 'static/JS/settings_entry.js')
      },
      output: {
        format: 'iife',  // 输出为立即执行函数，浏览器可直接运行
        entryFileNames: '[name].js',
        chunkFileNames: 'chunks/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash][extname]'
      }
    }
  },
  
  // 路径别名
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'static/JS'),
      '@components': path.resolve(__dirname, 'static/JS/components'),
      '@stores': path.resolve(__dirname, 'static/JS/stores'),
      '@services': path.resolve(__dirname, 'static/JS/services'),
      '@utils': path.resolve(__dirname, 'static/JS/utils')
    }
  }
})
