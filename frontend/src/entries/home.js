import { createApp } from 'vue'

import Home from '@components/pages/Home/index.vue'

const app = createApp(Home)

// 挂载应用
app.mount('#home-app')
