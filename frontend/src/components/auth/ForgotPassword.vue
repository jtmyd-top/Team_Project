<template>
  <div class="auth-page">
    <!-- 浮动光球背景 -->
    <div class="bg-orbs">
      <div class="orb orb-1"></div>
      <div class="orb orb-2"></div>
      <div class="orb orb-3"></div>
    </div>
    
    <!-- 主内容区 - 毛玻璃卡片 -->
    <div class="auth-content" :class="{ 'shake': isShaking }">
      <!-- 品牌标识 -->
      <div class="brand-section">
        <div class="brand-icon">
          <i class="fas fa-key"></i>
        </div>
        <h1 class="brand-title">重置密码</h1>
        <p class="brand-subtitle">输入您的邮箱地址，我们将发送重置链接</p>
      </div>

      <!-- 表单 -->
      <el-form
        ref="forgotFormRef"
        :model="forgotForm"
        :rules="forgotRules"
        class="auth-form"
        @submit.prevent="submitForm"
      >
        <div class="form-section">
          <el-form-item prop="email" class="form-item">
            <el-input
              v-model="forgotForm.email"
              type="email"
              placeholder="请输入您的邮箱地址"
              size="large"
              clearable
              class="auth-input"
              @input="handleEmailInput"
            >
              <template #prefix>
                <i class="fas fa-envelope input-icon"></i>
              </template>
            </el-input>
          </el-form-item>
        </div>

        <!-- 验证码 -->
        <div class="captcha-section">
          <CaptchaWidget
            ref="captchaWidgetRef"
            :turnstile-timeout="5000"
            @change="onCaptchaChange"
          />
        </div>

        <!-- 提交按钮 -->
        <div class="action-section">
          <el-button
            type="primary"
            size="large"
            :loading="isLoading"
            :disabled="isLoading || isCountingDown"
            @click="submitForm"
            class="primary-btn"
          >
            <template v-if="!isLoading && !isCountingDown">
              <i class="fas fa-paper-plane btn-icon"></i>
              发送重置链接
            </template>
            <template v-else-if="isLoading">
              <i class="fas fa-spinner fa-spin btn-icon"></i>
              发送中...
            </template>
            <template v-else>
              <i class="fas fa-clock btn-icon"></i>
              {{ countdown }}秒后可重新发送
            </template>
          </el-button>
        </div>

        <!-- 消息提示 -->
        <transition name="fade">
          <div v-if="message.text" class="message-box" :class="`message-${message.type}`">
            <i class="fas" :class="getMessageIcon()"></i>
            <span>{{ message.text }}</span>
          </div>
        </transition>
      </el-form>

      <!-- 返回链接 -->
      <div class="footer-links">
        <a href="/login" class="back-link">
          <i class="fas fa-arrow-left"></i>
          <span>返回登录</span>
        </a>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import CaptchaWidget from '@components/common/CaptchaWidget.vue'

const forgotFormRef = ref(null)
const captchaWidgetRef = ref(null)
const isLoading = ref(false)
const isCountingDown = ref(false)
const countdown = ref(60)
const isShaking = ref(false)

const captchaParams = ref({
  captcha_type: 'turnstile',
  turnstile_token: '',
  image_captcha: ''
})

const onCaptchaChange = (params) => {
  captchaParams.value = params
}

const forgotForm = reactive({
  email: ''
})

const message = reactive({
  text: '',
  type: 'info'
})

const validateEmail = (rule, value, callback) => {
  if (!value) {
    callback(new Error('请输入邮箱地址'))
    return
  }
  const emailRegex = /^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$/
  if (!emailRegex.test(value)) {
    callback(new Error('请输入正确的邮箱格式'))
    return
  }
  if (value.length > 254) {
    callback(new Error('邮箱地址过长'))
    return
  }
  if (value.includes('..')) {
    callback(new Error('邮箱格式不正确'))
    return
  }
  callback()
}

const forgotRules = {
  email: [
    { required: true, message: '请输入邮箱地址', trigger: 'blur' },
    { validator: validateEmail, trigger: 'blur' }
  ]
}

const handleEmailInput = () => {
  if (message.text) {
    message.text = ''
    message.type = 'info'
  }
}

const triggerShake = () => {
  isShaking.value = true
  setTimeout(() => {
    isShaking.value = false
  }, 500)
}

const getMessageIcon = () => {
  switch (message.type) {
    case 'success': return 'fa-check-circle'
    case 'error': return 'fa-exclamation-triangle'
    case 'warning': return 'fa-exclamation-circle'
    default: return 'fa-info-circle'
  }
}

const submitForm = async () => {
  if (!forgotFormRef.value) return

  try {
    await forgotFormRef.value.validateField('email')
    const email = forgotForm.email.trim()
    if (!email) {
      message.text = '请输入邮箱地址'
      message.type = 'error'
      triggerShake()
      return
    }

    if (captchaWidgetRef.value && !captchaWidgetRef.value.validate()) {
      triggerShake()
      return
    }

    await submitPasswordReset(email)
  } catch (error) {
    message.text = '请检查邮箱格式是否正确'
    message.type = 'error'
    triggerShake()
  }
}

const submitPasswordReset = async (email) => {
  isLoading.value = true

  try {
    const response = await fetch('/password-reset/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCSRFToken()
      },
      body: JSON.stringify({
        email: email,
        ...captchaParams.value
      })
    })

    const data = await response.json()

    if (data.status === 'success') {
      message.text = data.message || '重置密码链接已发送到您的邮箱，请查收'
      message.type = 'success'
      startCountdown()
      if (captchaWidgetRef.value) {
        captchaWidgetRef.value.reset()
      }
    } else {
      message.text = data.message || '发送失败，请稍后重试'
      message.type = 'error'
      triggerShake()
    }
  } catch (error) {
    message.text = '网络错误，请稍后重试'
    message.type = 'error'
    triggerShake()
  } finally {
    isLoading.value = false
  }
}

const startCountdown = () => {
  isCountingDown.value = true
  countdown.value = 60
  const timer = setInterval(() => {
    countdown.value--
    if (countdown.value <= 0) {
      clearInterval(timer)
      isCountingDown.value = false
    }
  }, 1000)
}

const getCSRFToken = () => {
  const name = 'csrftoken'
  let cookieValue = null
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';')
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim()
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1))
        break
      }
    }
  }
  return cookieValue
}

onMounted(() => {
  const initialData = window.FORGOT_PASSWORD_INITIAL || {}
  if (initialData.user_is_authenticated) {
    window.location.href = '/'
  }
})
</script>

<style scoped>
.auth-page {
  position: relative;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  overflow: hidden;
  background: none;
}

.bg-orbs {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 1;
}

.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.5;
}

.orb-1 {
  width: 500px;
  height: 500px;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.6), rgba(168, 85, 247, 0.6));
  top: -15%;
  left: -10%;
  animation: float1 20s ease-in-out infinite;
}

.orb-2 {
  width: 400px;
  height: 400px;
  background: linear-gradient(135deg, rgba(240, 147, 251, 0.5), rgba(245, 87, 108, 0.5));
  bottom: -10%;
  right: -10%;
  animation: float2 18s ease-in-out infinite 5s;
}

.orb-3 {
  width: 300px;
  height: 300px;
  background: linear-gradient(135deg, rgba(168, 85, 247, 0.4), rgba(102, 126, 234, 0.4));
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  animation: float3 22s ease-in-out infinite 10s;
}

@keyframes float1 {
  0%, 100% { transform: translate(0, 0); }
  50% { transform: translate(40px, -40px); }
}

@keyframes float2 {
  0%, 100% { transform: translate(0, 0); }
  50% { transform: translate(-50px, 30px); }
}

@keyframes float3 {
  0%, 100% { transform: translate(-50%, -50%); }
  50% { transform: translate(calc(-50% + 30px), calc(-50% - 30px)); }
}

.auth-content {
  position: relative;
  z-index: 10;
  width: 100%;
  max-width: 420px;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-radius: 24px;
  padding: 48px 40px;
  box-shadow: 
    0 8px 32px rgba(0, 0, 0, 0.1),
    0 2px 8px rgba(0, 0, 0, 0.05),
    inset 0 1px 0 rgba(255, 255, 255, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.5);
  animation: slideUp 0.6s ease-out;
}

.auth-content.shake {
  animation: shake 0.5s ease-in-out;
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(30px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes shake {
  0%, 100% { transform: translateX(0); }
  10%, 30%, 50%, 70%, 90% { transform: translateX(-5px); }
  20%, 40%, 60%, 80% { transform: translateX(5px); }
}

.brand-section {
  text-align: center;
  margin-bottom: 36px;
}

.brand-icon {
  width: 48px;
  height: 48px;
  margin: 0 auto 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  color: #1f2937;
}

.brand-title {
  font-size: 1.75rem;
  font-weight: 700;
  color: #1f2937;
  margin: 0 0 8px 0;
}

.brand-subtitle {
  font-size: 0.95rem;
  color: #6b7280;
  margin: 0;
  line-height: 1.5;
}

.auth-form {
  width: 100%;
}

.form-section {
  margin-bottom: 24px;
}

.form-item {
  margin-bottom: 0;
}

.auth-input :deep(.el-input__wrapper) {
  background: rgba(255, 255, 255, 0.95);
  border: none;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  padding: 6px 16px;
  transition: all 0.3s ease;
}

.auth-input :deep(.el-input__wrapper:hover) {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
}

.auth-input :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 4px 20px rgba(102, 126, 234, 0.15);
}

.auth-input :deep(.el-input__inner) {
  font-size: 15px;
  font-weight: 500;
  color: #1f2937;
}

.input-icon {
  color: #667eea;
  font-size: 15px;
}

.captcha-section {
  margin-bottom: 28px;
}

.action-section {
  margin-bottom: 20px;
}

.primary-btn {
  width: 100%;
  height: 50px;
  font-size: 16px;
  font-weight: 600;
  border-radius: 12px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.3);
  transition: all 0.3s ease;
}

.primary-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 10px 28px rgba(102, 126, 234, 0.4);
}

.primary-btn:disabled {
  opacity: 0.7;
}

.btn-icon {
  margin-right: 8px;
}

.message-box {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 20px;
}

.message-success {
  background: rgba(16, 185, 129, 0.1);
  color: #059669;
  border-left: 3px solid #10b981;
}

.message-error {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
  border-left: 3px solid #ef4444;
}

.message-warning {
  background: rgba(245, 158, 11, 0.1);
  color: #d97706;
  border-left: 3px solid #f59e0b;
}

.message-info {
  background: rgba(59, 130, 246, 0.1);
  color: #2563eb;
  border-left: 3px solid #3b82f6;
}

.footer-links {
  text-align: center;
  padding-top: 16px;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
}

.back-link {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #667eea;
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  padding: 8px 16px;
  border-radius: 8px;
  transition: all 0.25s ease;
}

.back-link:hover {
  color: #764ba2;
  background: rgba(102, 126, 234, 0.08);
}

.fade-enter-active,
.fade-leave-active {
  transition: all 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

@media (max-width: 480px) {
  .auth-page {
    padding: 30px 16px;
  }

  .auth-content {
    padding: 36px 28px;
  }

  .brand-title {
    font-size: 1.5rem;
  }

  .primary-btn {
    height: 46px;
    font-size: 15px;
  }
}
</style>
