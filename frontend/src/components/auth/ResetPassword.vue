<template>
  <div class="auth-page">
    <!-- 浮动光球背景 -->
    <div class="bg-orbs">
      <div class="orb orb-1"></div>
      <div class="orb orb-2"></div>
      <div class="orb orb-3"></div>
    </div>

    <!-- 错误状态 -->
    <div v-if="error || !isValidRequest" class="auth-content">
      <div class="error-state">
        <div class="error-icon">
          <i class="fas fa-exclamation-circle"></i>
        </div>
        <h2 class="error-title">链接已失效</h2>
        <p class="error-message">{{ error || '重置链接无效，请重新获取' }}</p>
        <a href="/forgot-password/" class="primary-link-btn">
          <i class="fas fa-redo-alt"></i>
          <span>重新获取链接</span>
        </a>
      </div>
    </div>

    <!-- 主表单 - 毛玻璃卡片 -->
    <div v-else class="auth-content" :class="{ 'shake': isShaking }">
      <!-- 品牌标识 -->
      <div class="brand-section">
        <div class="brand-icon">
          <i class="fas fa-lock-open"></i>
        </div>
        <h1 class="brand-title">重置密码</h1>
        <p class="brand-subtitle">
          您好，<span class="username-highlight">{{ username }}</span>
        </p>
        <p class="brand-desc">请输入您的新密码</p>
      </div>

      <!-- 表单 -->
      <el-form
        ref="resetFormRef"
        :model="resetForm"
        :rules="resetRules"
        class="auth-form"
        @submit.prevent="submitForm"
      >
        <!-- 新密码 -->
        <div class="form-section">
          <el-form-item prop="password" class="form-item">
            <el-input
              v-model="resetForm.password"
              type="password"
              placeholder="请输入新密码（至少8位）"
              size="large"
              show-password
              class="auth-input"
              @input="checkPasswordStrength"
              @keyup.enter="submitForm"
            >
              <template #prefix>
                <i class="fas fa-key input-icon"></i>
              </template>
            </el-input>
          </el-form-item>

          <!-- 密码强度指示器 -->
          <transition name="fade">
            <div v-if="resetForm.password" class="password-strength">
              <div class="strength-bars">
                <div
                  v-for="i in 4"
                  :key="i"
                  class="strength-bar"
                  :class="{ 'active': i <= passwordStrength, [`level-${passwordStrength}`]: i <= passwordStrength }"
                ></div>
              </div>
              <span class="strength-label" :class="`level-${passwordStrength}`">
                {{ getStrengthText() }}
              </span>
            </div>
          </transition>

          <!-- 密码复杂度提示 -->
          <div v-if="shouldShowPasswordError" class="validation-rules custom-validation">
            <div class="validation-rule rule-invalid">
              <span class="error-dot">●</span>
              <span>{{ getPasswordErrorMessage() }}</span>
            </div>
          </div>

          <!-- 确认密码 -->
          <el-form-item prop="confirmPassword" class="form-item">
            <el-input
              v-model="resetForm.confirmPassword"
              type="password"
              placeholder="请再次输入新密码"
              size="large"
              show-password
              class="auth-input"
              @keyup.enter="submitForm"
            >
              <template #prefix>
                <i class="fas fa-shield-alt input-icon"></i>
              </template>
            </el-input>
          </el-form-item>
        </div>

        <!-- 提交按钮 -->
        <div class="action-section">
          <el-button
            type="primary"
            size="large"
            :loading="isLoading"
            :disabled="isLoading"
            @click="submitForm"
            class="primary-btn"
          >
            <i class="fas fa-check-circle btn-icon"></i>
            {{ isLoading ? '正在重置...' : '确认重置密码' }}
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

      <!-- 成功覆盖层 -->
      <transition name="overlay-fade">
        <div v-if="showSuccess" class="success-overlay">
          <div class="success-content">
            <div class="success-checkmark">
              <svg class="checkmark" viewBox="0 0 52 52">
                <circle class="checkmark-circle" cx="26" cy="26" r="25" fill="none"/>
                <path class="checkmark-check" fill="none" d="M14.1 27.2l7.1 7.2 16.7-16.8"/>
              </svg>
            </div>
            <h2 class="success-title">重置成功！</h2>
            <p class="success-subtitle">您的密码已成功更新</p>
            <p class="success-redirect">正在跳转到登录页面...</p>
          </div>
        </div>
      </transition>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { usePasswordStrength } from '@composables/usePasswordStrength'

const passwordRef = ref('')
const {
  strength,
  rules: passwordRulesData,
  isValid: isPasswordStrongEnough,
  strengthText,
  strengthLevel
} = usePasswordStrength(passwordRef)

const resetFormRef = ref(null)
const isLoading = ref(false)
const isShaking = ref(false)
const showSuccess = ref(false)

const initialData = window.RESET_PASSWORD_INITIAL || {}
const error = ref(initialData.error)
const userId = ref(initialData.userId)
const token = ref(initialData.token)
const username = ref(initialData.username || '用户')

const isValidRequest = ref(!!userId.value && !!token.value && !error.value)

const resetForm = reactive({
  password: '',
  confirmPassword: ''
})

watch(() => resetForm.password, (newVal) => {
  passwordRef.value = newVal
})

const passwordStrength = computed(() => strengthLevel.value)

// 密码复杂度验证 - 与注册页面保持一致
const shouldShowPasswordError = computed(() => {
  const password = resetForm.password
  if (!password) return false

  const hasMinLength = password.length >= 8
  const hasUpperCase = /[A-Z]/.test(password)
  const hasLowerCase = /[a-z]/.test(password)
  const hasNumber = /\d/.test(password)

  return !(hasMinLength && hasUpperCase && hasLowerCase && hasNumber && strengthLevel.value >= 2)
})

const getPasswordErrorMessage = () => {
  const password = resetForm.password

  if (!password) return '请输入密码'
  if (password.length < 8) return '密码至少8位'
  if (!/[A-Z]/.test(password)) return '密码必须包含大写字母'
  if (!/[a-z]/.test(password)) return '密码必须包含小写字母'
  if (!/\d/.test(password)) return '密码必须包含数字'
  if (strengthLevel.value < 2) return '密码强度太弱，请增加复杂度'

  return ''
}

const isPasswordValid = computed(() => {
  const password = resetForm.password
  if (!password) return false

  const hasMinLength = password.length >= 8
  const hasUpperCase = /[A-Z]/.test(password)
  const hasLowerCase = /[a-z]/.test(password)
  const hasNumber = /\d/.test(password)

  return hasMinLength && hasUpperCase && hasLowerCase && hasNumber && strengthLevel.value >= 2
})

const message = reactive({
  text: '',
  type: 'info'
})

const resetRules = {
  password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 8, message: '密码长度至少为8位', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== resetForm.password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

const checkPasswordStrength = () => {
  // composable 会自动处理
}

const getStrengthText = () => {
  return strengthText.value || '太弱'
}

const getMessageIcon = () => {
  const icons = {
    success: 'fa-check-circle',
    error: 'fa-times-circle',
    warning: 'fa-exclamation-triangle',
    info: 'fa-info-circle'
  }
  return icons[message.type] || icons.info
}

const triggerShake = () => {
  isShaking.value = true
  setTimeout(() => {
    isShaking.value = false
  }, 600)
}

const submitForm = async () => {
  if (!resetFormRef.value) return

  try {
    await resetFormRef.value.validate()
  } catch (validationError) {
    triggerShake()
    return
  }

  // 检查密码复杂度 - 与注册页面保持一致
  if (!isPasswordValid.value) {
    message.text = getPasswordErrorMessage()
    message.type = 'error'
    triggerShake()
    return
  }

  try {
    if (!userId.value || !token.value) {
      message.text = '重置链接无效，请重新获取重置链接'
      message.type = 'error'
      triggerShake()
      return
    }

    isLoading.value = true
    message.text = ''

    const formData = new FormData()
    formData.append('password', resetForm.password)
    formData.append('confirm_password', resetForm.confirmPassword)
    formData.append('csrfmiddlewaretoken', getCSRFToken())

    const response = await fetch(`/reset-password/${userId.value}/${token.value}/`, {
      method: 'POST',
      body: formData,
      headers: {
        'X-Requested-With': 'XMLHttpRequest'
      }
    })

    if (response.ok) {
      const contentType = response.headers.get('content-type')
      if (contentType && contentType.includes('application/json')) {
        const data = await response.json()
        if (data.status === 'success') {
          showSuccessAnimation(data.redirect_url || '/')
        } else {
          message.text = data.message || '重置失败，请稍后重试'
          message.type = 'error'
          triggerShake()
        }
      } else {
        const text = await response.text()
        if (text.includes('重置成功') || response.redirected) {
          showSuccessAnimation(response.url || '/')
        } else {
          message.text = '重置失败，请稍后重试'
          message.type = 'error'
          triggerShake()
        }
      }
    } else {
      try {
        const errorData = await response.json()
        if (errorData.password || errorData.confirmPassword) {
          const errors = []
          if (errorData.password?.[0]) errors.push(errorData.password[0].message)
          if (errorData.confirmPassword?.[0]) errors.push(errorData.confirmPassword[0].message)
          message.text = errors.join('; ') || '重置失败，请稍后重试'
        } else if (errorData.message) {
          message.text = errorData.message
        } else {
          message.text = '重置失败，请稍后重试'
        }
      } catch (e) {
        message.text = '重置失败，请稍后重试'
      }
      message.type = 'error'
      triggerShake()
    }
  } catch (err) {
    message.text = '网络错误，请稍后重试'
    message.type = 'error'
    triggerShake()
  } finally {
    isLoading.value = false
  }
}

const showSuccessAnimation = (redirectUrl) => {
  showSuccess.value = true
  setTimeout(() => {
    window.location.href = redirectUrl
  }, 2000)
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
  if (initialData.user_is_authenticated) {
    window.location.href = '/'
    return
  }
  if (error.value) {
    message.text = error.value
    message.type = 'error'
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
  animation: shake 0.6s ease-in-out;
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(30px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes shake {
  0%, 100% { transform: translateX(0); }
  10%, 30%, 50%, 70%, 90% { transform: translateX(-8px); }
  20%, 40%, 60%, 80% { transform: translateX(8px); }
}

/* 错误状态 */
.error-state {
  text-align: center;
  padding: 20px 0;
}

.error-icon {
  font-size: 56px;
  color: #ef4444;
  margin-bottom: 20px;
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.05); opacity: 0.8; }
}

.error-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: #1f2937;
  margin: 0 0 12px 0;
}

.error-message {
  color: #6b7280;
  font-size: 0.95rem;
  margin: 0 0 28px 0;
}

.primary-link-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 12px 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  text-decoration: none;
  border-radius: 12px;
  font-weight: 600;
  transition: all 0.3s ease;
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.3);
}

.primary-link-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 28px rgba(102, 126, 234, 0.4);
}

/* 品牌区域 */
.brand-section {
  text-align: center;
  margin-bottom: 32px;
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
  font-size: 1rem;
  color: #6b7280;
  margin: 0 0 4px 0;
}

.username-highlight {
  color: #667eea;
  font-weight: 600;
}

.brand-desc {
  font-size: 0.9rem;
  color: #9ca3af;
  margin: 0;
}

/* 表单样式 */
.auth-form {
  width: 100%;
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: 18px;
  margin-bottom: 28px;
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

/* 密码强度 */
.password-strength {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: -8px;
  padding: 10px 14px;
  background: rgba(0, 0, 0, 0.03);
  border-radius: 8px;
}

.strength-bars {
  display: flex;
  gap: 4px;
  flex: 1;
}

.strength-bar {
  flex: 1;
  height: 4px;
  background: rgba(0, 0, 0, 0.1);
  border-radius: 2px;
  transition: all 0.3s ease;
}

.strength-bar.active.level-1 { background: #ef4444; }
.strength-bar.active.level-2 { background: #f59e0b; }
.strength-bar.active.level-3 { background: #3b82f6; }
.strength-bar.active.level-4 { background: #10b981; }

.strength-label {
  font-size: 12px;
  font-weight: 600;
}

.strength-label.level-1 { color: #ef4444; }
.strength-label.level-2 { color: #f59e0b; }
.strength-label.level-3 { color: #3b82f6; }
.strength-label.level-4 { color: #10b981; }

/* 密码复杂度验证提示 */
.validation-rules {
  margin-top: 8px;
  padding: 10px 14px;
  background: rgba(245, 108, 108, 0.1);
  border: 1px solid rgba(245, 108, 108, 0.3);
  border-radius: 8px;
}

.validation-rule {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #f56c6c;
}

.error-dot {
  flex-shrink: 0;
}

/* 操作按钮 */
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

.btn-icon {
  margin-right: 8px;
}

/* 消息提示 */
.message-box {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
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

/* 成功覆盖层 */
.success-overlay {
  position: absolute;
  inset: 0;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 24px;
  z-index: 100;
}

.success-content {
  text-align: center;
  animation: successSlideUp 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes successSlideUp {
  from { opacity: 0; transform: translateY(30px) scale(0.9); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.success-checkmark {
  margin-bottom: 20px;
}

.checkmark {
  width: 72px;
  height: 72px;
  stroke-width: 3;
  stroke: #10b981;
}

.checkmark-circle {
  stroke-dasharray: 166;
  stroke-dashoffset: 166;
  animation: stroke 0.6s cubic-bezier(0.65, 0, 0.45, 1) forwards;
}

.checkmark-check {
  stroke-dasharray: 48;
  stroke-dashoffset: 48;
  animation: stroke 0.3s cubic-bezier(0.65, 0, 0.45, 1) 0.8s forwards;
}

@keyframes stroke {
  100% { stroke-dashoffset: 0; }
}

.success-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: #1f2937;
  margin: 0 0 8px 0;
}

.success-subtitle {
  font-size: 1rem;
  color: #6b7280;
  margin: 0 0 4px 0;
}

.success-redirect {
  font-size: 0.85rem;
  color: #9ca3af;
  font-style: italic;
  margin: 0;
}

/* 过渡动画 */
.fade-enter-active,
.fade-leave-active {
  transition: all 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

.overlay-fade-enter-active,
.overlay-fade-leave-active {
  transition: all 0.4s ease;
}

.overlay-fade-enter-from,
.overlay-fade-leave-to {
  opacity: 0;
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
