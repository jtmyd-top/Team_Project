// frontend/src/entries/moderation.js
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import ModerationApp from '@components/moderation/ModerationApp/index.vue'

const app = createApp(ModerationApp)
const pinia = createPinia()
app.use(pinia)
app.use(ElementPlus)
app.mount('#moderation-app')
