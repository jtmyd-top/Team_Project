<template>
  <!-- 注意：外层glassmorphism容器由模板提供 -->
  <div class="forgot-password-wrapper">
    <!-- 优化的渐变背景 -->
    <div class="background-gradient">
      <div class="gradient-orb orb-1"></div>
      <div class="gradient-orb orb-2"></div>
      <div class="gradient-orb orb-3"></div>
      <div class="gradient-mesh"></div>
    </div>

    <div class="forgot-password-container">
      <!-- 玻璃态卡片 -->
      <div class="glass-card" :class="{ 'shake': isShaking }">
        <!-- 头部图标动画 -->
        <div class="card-icon-wrapper">
          <div class="icon-circle">
            <i class="fas fa-key icon-main"></i>
          </div>
          <div class="icon-pulse"></div>
        </div>

        <!-- 标题区域 -->
        <div class="card-header">
          <h1 class="card-title">
            <span class="title-gradient">重置密码</span>
          </h1>
          <p class="card-subtitle">
            输入您的邮箱地址，我们将发送重置密码的链接
          </p>
        </div>

        <!-- 表单区域 -->
        <el-form
          ref="forgotFormRef"
          :model="forgotForm"
          :rules="forgotRules"
          class="forgot-form"
          label-position="top"
        >
          <div class="form-item-animated">
            <div class="input-wrapper">
              <el-input
                v-model="forgotForm.email"
                type="email"
                placeholder="请输入您的邮箱地址"
                size="large"
                clearable
                @focus="handleInputFocus"
                @blur="handleInputBlur"
                @input="handleEmailInput"
              >
                <template #prefix>
                  <i class="fas fa-envelope input-icon"></i>
                </template>
              </el-input>
              <div class="input-border" :class="{ 'active': isFocused }"></div>
            </div>
          </div>

          <!-- Turnstile验证码 -->
          <div class="form-item-animated">
            <Turnstile
              ref="turnstileRef"
              :site-key="turnstileSiteKey"
              language="zh-CN"
              @verified="onTurnstileVerified"
              @error="onTurnstileError"
              @expired="onTurnstileExpired"
            />
          </div>

          <!-- 提交按钮 -->
          <el-form-item>
            <button
              type="button"
              class="submit-button"
              :class="{ 'loading': isLoading, 'disabled': isCountingDown }"
              :disabled="isLoading || isCountingDown"
              @click="submitForm"
            >
              <span class="button-content" v-if="!isLoading && !isCountingDown">
                <i class="fas fa-paper-plane"></i>
                <span>发送重置链接</span>
              </span>
              <span class="button-content" v-else-if="isLoading">
                <i class="fas fa-spinner fa-spin"></i>
                <span>发送中...</span>
              </span>
              <span class="button-content" v-else>
                <i class="fas fa-clock"></i>
                <span>{{ countdown }}秒后可重新发送</span>
              </span>
              <div class="button-ripple"></div>
            </button>
          </el-form-item>

          <!-- 消息提示 -->
          <transition name="message-fade">
            <div v-if="message.text" class="message-container" :class="`message-${message.type}`">
              <i class="fas" :class="getMessageIcon()"></i>
              <span>{{ message.text }}</span>
            </div>
          </transition>
        </el-form>

        <!-- 底部链接 -->
        <div class="card-footer">
          <a href="/login" class="back-link">
            <i class="fas fa-arrow-left"></i>
            <span>返回登录</span>
          </a>
        </div>
      </div>

      <!-- 装饰元素 -->
      <div class="decorative-elements">
        <div class="deco-circle circle-1"></div>
        <div class="deco-circle circle-2"></div>
        <div class="deco-circle circle-3"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import Turnstile from './Turnstile.vue'
import { useTurnstile } from '../composables/useTurnstile'

const forgotFormRef = ref(null)
const turnstileRef = ref(null)
const isLoading = ref(false)
const isCountingDown = ref(false)
const countdown = ref(60)
const isFocused = ref(false)
const isShaking = ref(false)

// 使用 useTurnstile composable
const {
  token: turnstileToken,
  siteKey: turnstileSiteKey,
  onVerified: handleTurnstileVerified,
  onError: handleTurnstileError,
  onExpired: handleTurnstileExpired,
  fetchSiteKey,
  reset: resetTurnstile
} = useTurnstile({
  showMessage: true,
  messageHandler: (type, message) => ElMessage[type](message)
})

const isSubmitting = ref(false)

// Turnstile 回调绑定
const onTurnstileVerified = handleTurnstileVerified
const onTurnstileError = handleTurnstileError
const onTurnstileExpired = handleTurnstileExpired

// 表单数据
const forgotForm = reactive({
  email: ''
})

// 消息提示
const message = reactive({
  text: '',
  type: 'info'
})

// 自定义邮箱验证函数
const validateEmail = (rule, value, callback) => {
  if (!value) {
    callback(new Error('请输入邮箱地址'))
    return
  }

  // 更严格的邮箱格式验证
  const emailRegex = /^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$/

  if (!emailRegex.test(value)) {
    callback(new Error('请输入正确的邮箱格式'))
    return
  }

  // 检查邮箱长度
  if (value.length > 254) {
    callback(new Error('邮箱地址过长'))
    return
  }

  // 检查是否包含连续的点
  if (value.includes('..')) {
    callback(new Error('邮箱格式不正确'))
    return
  }

  callback()
}

// 验证规则
const forgotRules = {
  email: [
    { required: true, message: '请输入邮箱地址', trigger: 'blur' },
    { validator: validateEmail, trigger: 'blur' }
  ]
}

// 输入框事件处理
const handleInputFocus = () => {
  isFocused.value = true
}

const handleInputBlur = () => {
  isFocused.value = false
}

const handleEmailInput = () => {
  // 清除之前的消息
  if (message.text) {
    message.text = ''
    message.type = 'info'
  }
}

// 触发抖动效果
const triggerShake = () => {
  isShaking.value = true
  setTimeout(() => {
    isShaking.value = false
  }, 500)
}

// 获取消息图标
const getMessageIcon = () => {
  switch (message.type) {
    case 'success':
      return 'fa-check-circle'
    case 'error':
      return 'fa-exclamation-triangle'
    case 'warning':
      return 'fa-exclamation-circle'
    default:
      return 'fa-info-circle'
  }
}

// 提交表单
const submitForm = async () => {
  if (!forgotFormRef.value) return

  try {
    // 手动触发表单验证
    await forgotFormRef.value.validateField('email')

    // 再次手动验证邮箱格式
    const email = forgotForm.email.trim()
    if (!email) {
      message.text = '请输入邮箱地址'
      message.type = 'error'
      triggerShake()
      return
    }

    const emailRegex = /^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$/

    if (!emailRegex.test(email)) {
      message.text = '请输入正确的邮箱格式'
      message.type = 'error'
      triggerShake()
      return
    }

    if (email.length > 254) {
      message.text = '邮箱地址过长'
      message.type = 'error'
      triggerShake()
      return
    }

    if (email.includes('..')) {
      message.text = '邮箱格式不正确'
      message.type = 'error'
      triggerShake()
      return
    }

    // 检查Turnstile验证码
    if (!turnstileToken.value) {
      message.text = '请完成人机验证'
      message.type = 'error'
      triggerShake()
      return
    }

    // 邮箱格式验证通过，直接提交重置请求
    await submitPasswordReset(email)

  } catch (error) {
    message.text = '请检查邮箱格式是否正确'
    message.type = 'error'
    triggerShake()
  }
}

// 提交密码重置请求
const submitPasswordReset = async (email) => {
  isSubmitting.value = true

  try {
    // 调用API发送重置密码链接
    const response = await fetch('/password-reset/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCSRFToken()
      },
      body: JSON.stringify({
        email: email,
        turnstile_token: turnstileToken.value
      })
    })

    const data = await response.json()

    if (data.status === 'success') {
      message.text = data.message || '重置密码链接已发送到您的邮箱，请查收'
      message.type = 'success'
      startCountdown()
      // 重置Turnstile
      if (turnstileRef.value) {
        turnstileRef.value.reset()
      }
      resetTurnstile()
    } else {
      message.text = data.message || '发送失败，请稍后重试'
      message.type = 'error'
      triggerShake()
    }
  } catch (error) {
    console.error('密码重置请求失败:', error)

    // 详细错误处理逻辑
    let errorMessage = ''

    if (error.response?.data) {
      const data = error.response.data

      // 处理各种可能的错误格式
      if (typeof data === 'string') {
        errorMessage = data
      } else if (data.status === 'error' && data.message) {
        errorMessage = data.message
      } else if (data.error) {
        errorMessage = data.error
      } else if (data.message) {
        errorMessage = data.message
      } else if (data.errors) {
        // {errors: {...}}
        const errors = []
        for (const [field, messages] of Object.entries(data.errors)) {
          if (Array.isArray(messages)) {
            messages.forEach(msg => {
              if (typeof msg === 'object' && msg.message) {
                errors.push(msg.message)
              } else if (typeof msg === 'string') {
                errors.push(msg)
              }
            })
          } else if (typeof messages === 'string') {
            errors.push(messages)
          }
        }
        errorMessage = errors.join('; ')
      } else if (typeof data === 'object' && data !== null) {
        // Django表单验证格式
        const errors = []
        for (const [field, messages] of Object.entries(data)) {
          if (Array.isArray(messages)) {
            messages.forEach(msg => {
              if (typeof msg === 'object' && msg.message) {
                errors.push(msg.message)
              } else if (typeof msg === 'string') {
                errors.push(msg)
              }
            })
          } else if (typeof messages === 'string') {
            errors.push(messages)
          } else if (typeof messages === 'object' && messages.message) {
            errors.push(messages.message)
          }
        }
        errorMessage = errors.join('; ')
      }
    } else if (error.message && error.message !== '请求失败') {
      errorMessage = error.message
    }

    message.text = errorMessage || '网络错误，请稍后重试'
    message.type = 'error'
    triggerShake()
  } finally {
    isSubmitting.value = false
  }
}

// 倒计时
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

// 获取CSRF Token
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

// 组件挂载
onMounted(() => {
  // 检查用户是否已登录（后端已检查，这是双重保险）
  // 如果后端传递了用户登录状态，前端再次确认并跳转
  const initialData = window.FORGOT_PASSWORD_INITIAL || {}
  if (initialData.user_is_authenticated) {
    window.location.href = '/'
    return
  }

  // 使用 composable 的 fetchSiteKey
  fetchSiteKey('/api/turnstile/config/').then(key => {
    if (!key) {
      ElMessage.error('获取验证码配置失败')
    }
  })
})
</script>

<style scoped>
/* ===== 全局容器 ===== */
.forgot-password-wrapper {
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* ===== 背景动画 ===== */
.background-animation {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  z-index: 0;
}

.gradient-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.6;
  animation: float 20s ease-in-out infinite;
}

.orb-1 {
  width: 500px;
  height: 500px;
  background: radial-gradient(circle, #667eea 0%, transparent 70%);
  top: -200px;
  left: -200px;
  animation-delay: 0s;
}

.orb-2 {
  width: 400px;
  height: 400px;
  background: radial-gradient(circle, #764ba2 0%, transparent 70%);
  bottom: -150px;
  right: -150px;
  animation-delay: 5s;
}

.orb-3 {
  width: 300px;
  height: 300px;
  background: radial-gradient(circle, #a855f7 0%, transparent 70%);
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  animation-delay: 10s;
}

@keyframes float {
  0%, 100% {
    transform: translate(0, 0) scale(1);
  }
  25% {
    transform: translate(30px, -50px) scale(1.05);
  }
  50% {
    transform: translate(-30px, 30px) scale(0.95);
  }
  75% {
    transform: translate(50px, 30px) scale(1.02);
  }
}

/* ===== 忘记密码容器 ===== */
.forgot-password-container {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 450px;
  padding: 20px;
}

/* ===== 玻璃态卡片 ===== */
.glass-card {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(30px);
  -webkit-backdrop-filter: blur(30px);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 24px;
  padding: 40px;
  box-shadow:
    0 32px 64px rgba(0, 0, 0, 0.1),
    0 16px 32px rgba(0, 0, 0, 0.05),
    inset 0 1px 0 rgba(255, 255, 255, 0.5);
  transition: all 0.3s ease;
  overflow: hidden;
}

.glass-card:hover {
  transform: translateY(-5px);
  box-shadow:
    0 40px 80px rgba(0, 0, 0, 0.15),
    0 20px 40px rgba(0, 0, 0, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.6);
}

/* ===== 头部图标 ===== */
.card-icon-wrapper {
  position: relative;
  text-align: center;
  margin-bottom: 32px;
}

.icon-circle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 80px;
  height: 80px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 50%;
  box-shadow:
    0 16px 32px rgba(102, 126, 234, 0.3),
    inset 0 1px 0 rgba(255, 255, 255, 0.2);
  position: relative;
  z-index: 2;
  animation: iconFloat 3s ease-in-out infinite;
}

@keyframes iconFloat {
  0%, 100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-10px);
  }
}

.icon-main {
  font-size: 36px;
  color: white;
  animation: iconRotate 4s linear infinite;
}

@keyframes iconRotate {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}

.icon-pulse {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 100px;
  height: 100px;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.4), rgba(118, 75, 162, 0.4));
  border-radius: 50%;
  animation: pulse 2s ease-in-out infinite;
  z-index: 1;
}

@keyframes pulse {
  0% {
    transform: translate(-50%, -50%) scale(0.8);
    opacity: 1;
  }
  50% {
    transform: translate(-50%, -50%) scale(1.2);
    opacity: 0.7;
  }
  100% {
    transform: translate(-50%, -50%) scale(0.8);
    opacity: 1;
  }
}

/* ===== 卡片头部 ===== */
.card-header {
  text-align: center;
  margin-bottom: 40px;
}

.card-title {
  font-size: 2rem;
  font-weight: 700;
  margin-bottom: 12px;
  line-height: 1.2;
}

.title-gradient {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.card-subtitle {
  color: #64748b;
  font-size: 0.95rem;
  line-height: 1.5;
  margin: 0;
  font-weight: 400;
}

/* ===== 表单样式 ===== */
.forgot-form {
  margin-bottom: 24px;
}

.form-item-animated {
  margin-bottom: 24px;
}

.input-wrapper {
  position: relative;
}

.modern-input {
  position: relative;
  z-index: 2;
}

.modern-input :deep(.el-input__wrapper) {
  background: rgba(255, 255, 255, 0.8);
  border: 2px solid transparent;
  border-radius: 16px;
  box-shadow:
    0 4px 16px rgba(0, 0, 0, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.6);
  transition: all 0.3s ease;
  padding: 16px 20px;
}

.modern-input :deep(.el-input__wrapper:hover) {
  background: rgba(255, 255, 255, 0.9);
  border-color: rgba(102, 126, 234, 0.3);
  box-shadow:
    0 8px 24px rgba(0, 0, 0, 0.12),
    inset 0 1px 0 rgba(255, 255, 255, 0.8);
}

.modern-input :deep(.el-input__wrapper.is-focus) {
  background: rgba(255, 255, 255, 0.95);
  border-color: #667eea;
  box-shadow:
    0 0 0 4px rgba(102, 126, 234, 0.1),
    0 8px 24px rgba(102, 126, 234, 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 1);
}

.modern-input :deep(.el-input__inner) {
  font-size: 16px;
  color: #1f2937;
  font-weight: 500;
  padding: 0;
  background: transparent;
}

.modern-input :deep(.el-input__inner::placeholder) {
  color: #9ca3af;
  font-weight: 400;
}

.input-icon {
  color: #6b7280;
  font-size: 18px;
  transition: color 0.3s ease;
}

.modern-input:focus-within .input-icon {
  color: #667eea;
}

.input-border {
  position: absolute;
  bottom: 0;
  left: 50%;
  width: 0;
  height: 3px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 3px;
  transition: all 0.3s ease;
  z-index: 3;
}

.input-border.active {
  left: 0;
  width: 100%;
}

/* ===== 提交按钮 ===== */
.submit-button {
  position: relative;
  width: 100%;
  height: 56px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  border-radius: 16px;
  color: white;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  overflow: hidden;
  transition: all 0.3s ease;
  box-shadow:
    0 8px 24px rgba(102, 126, 234, 0.3),
    inset 0 1px 0 rgba(255, 255, 255, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.submit-button:hover:not(.disabled):not(.loading) {
  transform: translateY(-2px);
  box-shadow:
    0 12px 32px rgba(102, 126, 234, 0.4),
    inset 0 1px 0 rgba(255, 255, 255, 0.3);
}

.submit-button:active:not(.disabled):not(.loading) {
  transform: translateY(0);
  box-shadow:
    0 4px 16px rgba(102, 126, 234, 0.3),
    inset 0 1px 0 rgba(255, 255, 255, 0.2);
}

.submit-button.disabled {
  background: linear-gradient(135deg, #9ca3af 0%, #6b7280 100%);
  cursor: not-allowed;
  opacity: 0.6;
}

.submit-button.loading {
  cursor: default;
}

.button-content {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  gap: 8px;
}

.button-ripple {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.2), transparent);
  opacity: 0;
  transition: opacity 0.3s ease;
}

.submit-button:hover:not(.disabled):not(.loading) .button-ripple {
  opacity: 1;
}

/* ===== 消息提示 ===== */
.message-container {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 500;
  animation: messageSlideIn 0.3s ease;
}

.message-success {
  background: rgba(34, 197, 94, 0.1);
  color: #16a34a;
  border: 1px solid rgba(34, 197, 94, 0.2);
}

.message-error {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
  border: 1px solid rgba(239, 68, 68, 0.2);
}

.message-warning {
  background: rgba(245, 158, 11, 0.1);
  color: #d97706;
  border: 1px solid rgba(245, 158, 11, 0.2);
}

.message-info {
  background: rgba(59, 130, 246, 0.1);
  color: #2563eb;
  border: 1px solid rgba(59, 130, 246, 0.2);
}

@keyframes messageSlideIn {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.message-fade-enter-active,
.message-fade-leave-active {
  transition: all 0.3s ease;
}

.message-fade-enter-from {
  opacity: 0;
  transform: translateY(-10px);
}

.message-fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

/* ===== 底部链接 ===== */
.card-footer {
  text-align: center;
  margin-top: 32px;
}

.back-link {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #667eea;
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.3s ease;
  padding: 8px 16px;
  border-radius: 8px;
}

.back-link:hover {
  color: #764ba2;
  background: rgba(102, 126, 234, 0.05);
  transform: translateX(-2px);
}

/* ===== 装饰元素 ===== */
.decorative-elements {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  overflow: hidden;
}

.deco-circle {
  position: absolute;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.1), rgba(118, 75, 162, 0.1));
  animation: decoFloat 15s ease-in-out infinite;
}

.circle-1 {
  width: 120px;
  height: 120px;
  top: -30px;
  right: -30px;
  animation-delay: 0s;
}

.circle-2 {
  width: 80px;
  height: 80px;
  bottom: -20px;
  left: -20px;
  animation-delay: 5s;
}

.circle-3 {
  width: 60px;
  height: 60px;
  top: 50%;
  right: -15px;
  animation-delay: 10s;
}

@keyframes decoFloat {
  0%, 100% {
    transform: translateY(0) rotate(0deg);
  }
  50% {
    transform: translateY(-20px) rotate(180deg);
  }
}

/* ===== 抖动动画 ===== */
@keyframes shake {
  0%, 100% {
    transform: translateX(0);
  }
  10%, 30%, 50%, 70%, 90% {
    transform: translateX(-5px);
  }
  20%, 40%, 60%, 80% {
    transform: translateX(5px);
  }
}

.glass-card.shake {
  animation: shake 0.5s ease-in-out;
}

/* ===== 响应式设计 ===== */
@media (max-width: 768px) {
  .forgot-password-container {
    padding: 16px;
  }

  .glass-card {
    padding: 32px 24px;
  }

  .card-title {
    font-size: 1.5rem;
  }

  .submit-button {
    height: 48px;
    font-size: 14px;
  }
}

@media (max-width: 480px) {
  .forgot-password-container {
    padding: 12px;
  }

  .glass-card {
    padding: 24px 20px;
  }

  .card-header {
    margin-bottom: 32px;
  }

  .card-title {
    font-size: 1.25rem;
  }

  .icon-circle {
    width: 60px;
    height: 60px;
  }

  .icon-main {
    font-size: 28px;
  }
}
</style>