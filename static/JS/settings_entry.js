// Vite 入口文件 - 用于构建设置页面
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'

// 导入主应用组件
import SettingsApp from '@components/settings/SettingsApp.vue'

// 创建 Vue 应用
const app = createApp(SettingsApp)

// 使用 Pinia 状态管理
app.use(createPinia())

// 使用 Element Plus UI 组件库
app.use(ElementPlus)

// 挂载到 DOM
app.mount('#settings-app')
