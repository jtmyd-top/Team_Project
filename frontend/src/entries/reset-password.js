import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import ResetPassword from '@components/auth/ResetPassword/index.vue'

const app = createApp(ResetPassword)
app.use(ElementPlus)
app.mount('#reset-password-app')
