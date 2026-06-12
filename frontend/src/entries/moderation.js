import { createApp } from 'vue'
import { createPinia } from 'pinia'
import {
  ElButton,
  ElCheckbox,
  ElDialog,
  ElEmpty,
  ElImage,
  ElInput,
  ElOption,
  ElOptionGroup,
  ElRadio,
  ElRadioButton,
  ElRadioGroup,
  ElSelect,
  ElTag
} from 'element-plus'
import 'element-plus/es/components/button/style/css'
import 'element-plus/es/components/checkbox/style/css'
import 'element-plus/es/components/dialog/style/css'
import 'element-plus/es/components/empty/style/css'
import 'element-plus/es/components/image/style/css'
import 'element-plus/es/components/input/style/css'
import 'element-plus/es/components/message/style/css'
import 'element-plus/es/components/message-box/style/css'
import 'element-plus/es/components/option/style/css'
import 'element-plus/es/components/option-group/style/css'
import 'element-plus/es/components/radio/style/css'
import 'element-plus/es/components/radio-button/style/css'
import 'element-plus/es/components/radio-group/style/css'
import 'element-plus/es/components/select/style/css'
import 'element-plus/es/components/tag/style/css'

import ModerationApp from '@components/moderation/ModerationApp/index.vue'
import { registerElementComponents } from './element-plus-components'

const app = createApp(ModerationApp)
const pinia = createPinia()

app.use(pinia)
registerElementComponents(app, [
  ElButton,
  ElCheckbox,
  ElDialog,
  ElEmpty,
  ElImage,
  ElInput,
  ElOption,
  ElOptionGroup,
  ElRadio,
  ElRadioButton,
  ElRadioGroup,
  ElSelect,
  ElTag
])
app.mount('#moderation-app')
