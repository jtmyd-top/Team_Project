import { createApp } from 'vue'
import { ElButton, ElForm, ElFormItem, ElInput } from 'element-plus'
import 'element-plus/es/components/button/style/css'
import 'element-plus/es/components/form/style/css'
import 'element-plus/es/components/form-item/style/css'
import 'element-plus/es/components/input/style/css'
import 'element-plus/es/components/message/style/css'

import ResetPassword from '@components/auth/ResetPassword/index.vue'
import { registerElementComponents } from './element-plus-components'

const app = createApp(ResetPassword)

registerElementComponents(app, [ElButton, ElForm, ElFormItem, ElInput])

app.mount('#reset-password-app')
