import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

// 导入 API 服务（会自动挂载到 window.apiService）
import '@services/apiService'

import Signup from '@components/auth/Signup/index.vue'

const app = createApp(Signup)

// 注册 Element Plus
app.use(ElementPlus)

// 注册所有图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

// 全局配置
app.config.globalProperties.$filters = {
  // 可以添加全局过滤器
}

// 挂载应用
app.mount('#signup-app')