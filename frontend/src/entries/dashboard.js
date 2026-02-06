// frontend/src/entries/dashboard.js
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import Dashboard from '@components/dashboard/Dashboard/index.vue'

const app = createApp(Dashboard)
const pinia = createPinia()
app.use(pinia)
app.use(ElementPlus)
app.mount('#dashboard-app')
