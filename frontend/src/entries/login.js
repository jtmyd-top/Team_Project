import { createApp } from 'vue'
import { ElButton, ElCheckbox, ElForm, ElFormItem, ElInput } from 'element-plus'
import 'element-plus/es/components/button/style/css'
import 'element-plus/es/components/checkbox/style/css'
import 'element-plus/es/components/form/style/css'
import 'element-plus/es/components/form-item/style/css'
import 'element-plus/es/components/input/style/css'
import 'element-plus/es/components/message/style/css'
import '@services/apiService'

import Login from '@components/auth/Login/index.vue'
import { registerElementComponents } from './element-plus-components'

const app = createApp(Login)

registerElementComponents(app, [ElButton, ElCheckbox, ElForm, ElFormItem, ElInput])

app.config.globalProperties.$filters = {}

app.mount('#login-app')
