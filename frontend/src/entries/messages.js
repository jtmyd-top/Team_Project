import { createApp } from 'vue'
import { createPinia } from 'pinia'
import 'element-plus/es/components/icon/style/css'
import 'element-plus/es/components/message/style/css'
import 'element-plus/es/components/message-box/style/css'

import MessagesApp from '@components/messages/MessagesApp/index.vue'
import { useUserStore } from '@stores/user.js'

const app = createApp(MessagesApp)
const pinia = createPinia()

app.use(pinia)

if (window.SETTINGS_INITIAL) {
  const userStore = useUserStore()
  userStore.initializeFromServer(window.SETTINGS_INITIAL)
}

app.mount('#messages-app')
