import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import Home from '@components/pages/Home.vue'

const app = createApp(Home)

// 注册 Element Plus
app.use(ElementPlus)

// 注册所有图�?
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

// 挂载应用
app.mount('#home-app')
