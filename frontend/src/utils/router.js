import { createRouter, createWebHistory } from 'vue-router'

// 路由配置
const routes = [
  {
    path: '/login/',
    name: 'Login',
    component: () => import('@components/auth/Login.vue')
  },
  {
    path: '/signup/',
    name: 'Signup',
    component: () => import('@components/auth/Signup.vue')
  },
  {
    path: '/forgot-password/',
    name: 'ForgotPassword',
    component: () => import('@components/auth/ForgotPassword.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫
router.beforeEach((to, from, next) => {
  // 可以在这里添加权限验证等逻辑
  next()
})

export default router