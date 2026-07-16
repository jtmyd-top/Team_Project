import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],

  esbuild: {
    drop: process.env.NODE_ENV === 'production' ? ['console', 'debugger'] : [],
  },

  // 渚濊禆浼樺寲锛氱‘淇?crypto-js 琚纭鏋勫缓
  optimizeDeps: {
    include: ['crypto-js']
  },

  // 鐢熶骇鐜璧勬簮 URL 鍓嶇紑
  base: '/static/dist/',

  // 寮€鍙戞湇鍔″櫒閰嶇疆
  server: {
    port: 5173,
    open: false,
    // 鍏佽璺ㄥ煙璁块棶锛圖jango 鍦?8000 绔彛锛?
    cors: true,
    // 閰嶇疆浠ｇ悊锛屽皢 API 璇锋眰杞彂鍒?Django
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
    // 鍏佽澶栭儴璁块棶
    host: true,
  },

  // 鏋勫缓閰嶇疆
  build: {
    // 杈撳嚭鍒?Django 鐨?static/dist 鐩綍
    outDir: '../static/dist',
    emptyOutDir: true,

    // 鐢熸垚 manifest.json 渚?Django 璇嗗埆鍝堝笇鏂囦欢鍚?
    manifest: true,

    // 璋冩暣 chunk 澶у皬璀﹀憡闄愬埗
    chunkSizeWarningLimit: 1000,

    rollupOptions: {
      input: {
        // 璁剧疆椤甸潰
        settings: path.resolve(__dirname, 'src/entries/settings.js'),
        // 璁よ瘉鐩稿叧鍏ュ彛鏂囦欢
        login: path.resolve(__dirname, 'src/entries/login.js'),
        signup: path.resolve(__dirname, 'src/entries/signup.js'),
        'forgot-password': path.resolve(__dirname, 'src/entries/forgot-password.js'),
        'reset-password': path.resolve(__dirname, 'src/entries/reset-password.js'),
        // 棣栭〉
        home: path.resolve(__dirname, 'src/entries/home.js'),
        // 鍏叡绗旇椤甸潰
        'public-note-entry': path.resolve(__dirname, 'src/entries/public-note-entry.js'),
        'public-note-page': path.resolve(__dirname, 'src/entries/public-note-page.js'),
        'public-notes-list': path.resolve(__dirname, 'src/entries/public-notes-list.js'),
        // 鐭ヨ瘑绗旇鍒楄〃椤甸潰
        'knowledge-list': path.resolve(__dirname, 'src/entries/knowledge-list.js'),
        'knowledge-element': path.resolve(__dirname, 'src/entries/knowledge-element.js'),
        // 涓婚绠＄悊鍣?
        'theme-manager': path.resolve(__dirname, 'src/entries/theme-manager.js'),
        // 鎴樻儏瀹ゅぇ灞?
        'dashboard': path.resolve(__dirname, 'src/entries/dashboard.js'),
        // 绉佷俊椤甸潰
        'messages': path.resolve(__dirname, 'src/entries/messages.js'),
        // 涓炬姤澶勭疆涓績
        'moderation': path.resolve(__dirname, 'src/entries/moderation.js'),
        'command-palette': path.resolve(__dirname, 'src/entries/command-palette.js'),
        'insights': path.resolve(__dirname, 'src/entries/insights.js'),
      },
      output: {
        format: 'es',  // 涓绘牸寮忎负 ES 妯″潡
        entryFileNames: '[name].js',
        chunkFileNames: 'chunks/[name]-[hash].js',
        // CSS 浣跨敤鍥哄畾鏂囦欢鍚嶏紝鏂逛究妯℃澘寮曠敤
        assetFileNames: (assetInfo) => {
          if (assetInfo.name?.endsWith('.css')) {
            // CSS 鏂囦欢浣跨敤鍥哄畾鍚嶇О锛屽彧鎸?entry 鍒嗙粍
            const legacyNames = {
              'knowledge-list.css': 'knowledge.css',
            }
            const name = legacyNames[assetInfo.name] || assetInfo.name.replace(/-[\w\d_-]{8,}\.css$/, '.css')
            return `assets/${name}`
          }
          return 'assets/[name]-[hash][extname]'
        },

        // 鎵嬪姩鍒嗗壊浠ｇ爜鍧楋紝浼樺寲鍔犺浇鎬ц兘
        manualChunks(id) {
          // 灏?node_modules 涓殑渚濊禆鍒嗙鍒?vendor chunk
          if (id.includes('node_modules')) {
            // ECharts 鍗曠嫭鎵撳寘
            if (id.includes('echarts') || id.includes('zrender')) {
              return 'echarts-vendor';
            }
            // Vue 鐩稿叧搴撳崟鐙墦鍖?
            if (id.includes('vue') || id.includes('pinia')) {
            // Element Plus 单独打包
            if (id.includes('element-plus')) {
              return 'element-plus-vendor';
            }
              return 'vue-vendor';
            }
          }
        }
      }
    }
  },

  // 璺緞鍒悕
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
      // Django 闈欐€佽祫婧愮洰褰?
      '@static': path.resolve(__dirname, '../static'),
    }
  }
})
