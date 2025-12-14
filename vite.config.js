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

    // 调整 chunk 大小警告限制
    chunkSizeWarningLimit: 1000,

    rollupOptions: {
      input: {
        settings: path.resolve(__dirname, 'static/JS/settings_entry.js'),
        // 认证相关入口文件
        login: path.resolve(__dirname, 'static/JS/login_entry.js'),
        signup: path.resolve(__dirname, 'static/JS/signup_entry.js'),
        // 添加其他需要构建的JavaScript文件
        'theme-manager': path.resolve(__dirname, 'static/JS/theme-manager.js'),
        'api-service': path.resolve(__dirname, 'static/JS/services/apiService.js'),
        'public-note-page': path.resolve(__dirname, 'static/JS/public_note_page.js'),
        'public-notes-list': path.resolve(__dirname, 'static/JS/public_notes_list.js'),
        'forgot-password': path.resolve(__dirname, 'static/JS/forgot_password_entry.js'),
      },
      output: {
        format: 'es',  // 主格式为 ES 模块
        entryFileNames: '[name].js',
        chunkFileNames: 'chunks/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash][extname]',

        // 手动分割代码块，优化加载性能
        manualChunks(id) {
          // 将 node_modules 中的依赖分离到 vendor chunk
          if (id.includes('node_modules')) {
            // Element Plus 单独打包
            if (id.includes('element-plus')) {
              return 'element-plus';
            }
            // Vue 相关库单独打包
            if (id.includes('vue') || id.includes('pinia')) {
              return 'vue-vendor';
            }
            // 其他第三方库打包到 vendor
            return 'vendor';
          }
        }
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
