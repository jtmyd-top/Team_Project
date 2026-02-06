// forgot_password_entry.js - 忘记密码功能入口文件
import { createApp } from 'vue';
import ElementPlus from 'element-plus';
import 'element-plus/dist/index.css';
import ForgotPassword from '@components/auth/ForgotPassword/index.vue';

// 创建Vue应用
const app = createApp(ForgotPassword);

// 注册Element Plus插件
app.use(ElementPlus);

// 挂载应用
app.mount('#forgot-password-app');
