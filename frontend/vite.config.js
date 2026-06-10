import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],

  esbuild: {
    drop: process.env.NODE_ENV === 'production' ? ['console', 'debugger'] : [],
  },

  // 依赖优化：确保 crypto-js 被正确预构建
  optimizeDeps: {
    include: ['crypto-js']
  },

  // 生产环境资源 URL 前缀
  base: '/static/dist/',

  // 开发服务器配置
  server: {
    port: 5173,
    open: false,
    // 允许跨域访问（Django 在 8000 端口）
    cors: true,
    // 配置代理，将 API 请求转发到 Django
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/uploads': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/protected_uploads': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
    // 允许外部访问
    host: true,
  },

  // 构建配置
  build: {
    // 输出到 Django 的 static/dist 目录
    outDir: '../static/dist',
    emptyOutDir: true,

    // 生成 manifest.json 供 Django 识别哈希文件名
    manifest: true,

    // 调整 chunk 大小警告限制
    chunkSizeWarningLimit: 1000,

    rollupOptions: {
      input: {
        // 设置页面
        settings: path.resolve(__dirname, 'src/entries/settings.js'),
        // 认证相关入口文件
        login: path.resolve(__dirname, 'src/entries/login.js'),
        signup: path.resolve(__dirname, 'src/entries/signup.js'),
        'forgot-password': path.resolve(__dirname, 'src/entries/forgot-password.js'),
        'reset-password': path.resolve(__dirname, 'src/entries/reset-password.js'),
        // 首页
        home: path.resolve(__dirname, 'src/entries/home.js'),
        // 公共笔记页面
        'public-note-entry': path.resolve(__dirname, 'src/entries/public-note-entry.js'),
        'public-note-page': path.resolve(__dirname, 'src/entries/public-note-page.js'),
        'public-notes-list': path.resolve(__dirname, 'src/entries/public-notes-list.js'),
        // 知识笔记列表页面
        'knowledge-list': path.resolve(__dirname, 'src/entries/knowledge-list.js'),
        // 主题管理器
        'theme-manager': path.resolve(__dirname, 'src/entries/theme-manager.js'),
        // 战情室大屏
        'dashboard': path.resolve(__dirname, 'src/entries/dashboard.js'),
        // 私信页面
        'messages': path.resolve(__dirname, 'src/entries/messages.js'),
        // 举报处置中心
        'moderation': path.resolve(__dirname, 'src/entries/moderation.js'),
      },
      output: {
        format: 'es',  // 主格式为 ES 模块
        entryFileNames: '[name].js',
        chunkFileNames: 'chunks/[name]-[hash].js',
        // CSS 使用固定文件名，方便模板引用
        assetFileNames: (assetInfo) => {
          if (assetInfo.name?.endsWith('.css')) {
            // CSS 文件使用固定名称，只按 entry 分组
            const name = assetInfo.name.replace(/-[\w\d]+\.css$/, '.css')
            return `assets/${name}`
          }
          return 'assets/[name]-[hash][extname]'
        },

        // 手动分割代码块，优化加载性能
        manualChunks(id) {
          // 将 node_modules 中的依赖分离到 vendor chunk
          if (id.includes('node_modules')) {
            // Element Plus 单独打包
            if (id.includes('element-plus')) {
              return 'element-plus';
            }
            // ECharts 单独打包
            if (id.includes('echarts') || id.includes('zrender')) {
              return 'echarts-vendor';
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
      '@': path.resolve(__dirname, 'src'),
      '@components': path.resolve(__dirname, 'src/components'),
      '@composables': path.resolve(__dirname, 'src/composables'),
      '@stores': path.resolve(__dirname, 'src/stores'),
      '@services': path.resolve(__dirname, 'src/services'),
      '@utils': path.resolve(__dirname, 'src/utils'),
      '@api': path.resolve(__dirname, 'src/api'),
      '@lib': path.resolve(__dirname, 'src/lib'),
      '@entries': path.resolve(__dirname, 'src/entries'),
      // Django 静态资源目录
      '@static': path.resolve(__dirname, '../static'),
    }
  }
})
