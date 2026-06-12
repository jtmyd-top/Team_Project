import { createApp } from 'vue'
import { createPinia } from 'pinia'
import 'element-plus/es/components/message/style/css'

import Dashboard from '@components/dashboard/Dashboard/index.vue'

const app = createApp(Dashboard)
const pinia = createPinia()

app.use(pinia)
app.mount('#dashboard-app')
