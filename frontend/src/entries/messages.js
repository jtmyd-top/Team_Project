import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'

// 导入主应用组件
import MessagesApp from '@components/messages/MessagesApp/index.vue'

// 导入用户状态管理
import { useUserStore } from '@stores/user.js'

// 创建 Vue 应用
const app = createApp(MessagesApp)

// 使用 Pinia 状态管理
const pinia = createPinia()
app.use(pinia)

// 使用 Element Plus UI 组件库
app.use(ElementPlus)

// 初始化用户数据（如果需要）
if (window.SETTINGS_INITIAL) {
  const userStore = useUserStore()
  userStore.initializeFromServer(window.SETTINGS_INITIAL)
}

// 挂载到 DOM
app.mount('#messages-app')
