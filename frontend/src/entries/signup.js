import { createApp } from 'vue'
import { ElAlert, ElButton, ElCheckbox, ElDialog, ElForm, ElFormItem, ElInput } from 'element-plus'
import 'element-plus/es/components/alert/style/css'
import 'element-plus/es/components/button/style/css'
import 'element-plus/es/components/checkbox/style/css'
import 'element-plus/es/components/dialog/style/css'
import 'element-plus/es/components/form/style/css'
import 'element-plus/es/components/form-item/style/css'
import 'element-plus/es/components/input/style/css'
import 'element-plus/es/components/message/style/css'
import '@services/apiService'

import Signup from '@components/auth/Signup/index.vue'
import { registerElementComponents } from './element-plus-components'

const app = createApp(Signup)

registerElementComponents(app, [ElAlert, ElButton, ElCheckbox, ElDialog, ElForm, ElFormItem, ElInput])

app.config.globalProperties.$filters = {}

app.mount('#signup-app')
