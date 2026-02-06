import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { ElLoading, ElMessage } from 'element-plus'
import 'element-plus/dist/index.css'
import '@static/css/folder-layout.css' // 引入新的文件夹布局样式
import KnowledgeList from '@components/knowledge/KnowledgeList/index.vue'
import { setupGlobalErrorHandler } from '@utils/errorHandler'

// 创建Vue应用实例
const app = createApp(KnowledgeList)

// 创建并使用 Pinia
const pinia = createPinia()
app.use(pinia)

// 注册Element Plus组件
app.use(ElLoading)
app.use(ElMessage)

// 全局错误处理
setupGlobalErrorHandler(app)

// 全局配置
app.config.globalProperties.$window = window

// 挂载应用
app.mount('#knowledge-app')

// 定义全局变量供非组件脚本使用
window.knowledgeApp = app
