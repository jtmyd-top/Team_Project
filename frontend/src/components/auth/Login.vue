<template>
  <div class="auth-page">
    <!-- 浮动光球背景 -->
    <div class="bg-orbs">
      <div class="orb orb-1"></div>
      <div class="orb orb-2"></div>
      <div class="orb orb-3"></div>
    </div>
    
    <!-- 主内容区 - 去容器化设计 -->
    <div class="auth-content">
      <!-- 品牌标识 -->
      <div class="brand-section">
        <div class="brand-icon">
          <i class="fas fa-book-open"></i>
        </div>
        <h1 class="brand-title">欢迎回来</h1>
        <p class="brand-subtitle">登录您的知识管理账户</p>
      </div>

      <!-- 第一步：用户名密码登录表单 -->
      <el-form
        v-if="!require2fa"
        ref="loginFormRef"
        :model="loginForm"
        :rules="loginRules"
        @submit.prevent="handleLogin"
        class="auth-form"
      >
        <div class="form-section">
          <el-form-item prop="username" class="form-item">
            <el-input
              v-model="loginForm.username"
              placeholder="请输入用户名"
              size="large"
              clearable
              class="auth-input"
            >
              <template #prefix>
                <i class="fas fa-user input-icon"></i>
              </template>
            </el-input>
          </el-form-item>

          <el-form-item prop="password" class="form-item">
            <el-input
              v-model="loginForm.password"
              type="password"
              placeholder="请输入密码"
              size="large"
              show-password
              class="auth-input"
              @keyup.enter="handleLogin"
            >
              <template #prefix>
                <i class="fas fa-lock input-icon"></i>
              </template>
            </el-input>
          </el-form-item>
        </div>

        <!-- 验证码组件 -->
        <div class="captcha-section">
          <CaptchaWidget
            ref="captchaWidgetRef"
            :turnstile-timeout="8000"
            @change="onCaptchaChange"
            @enter="handleLogin"
          />
        </div>

        <!-- 登录按钮 -->
        <div class="action-section">
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            @click="handleLogin"
            class="primary-btn"
          >
            <i class="fas fa-sign-in-alt btn-icon"></i>
            {{ loading ? '登录中...' : '登录' }}
          </el-button>
        </div>

        <!-- 底部链接 -->
        <div class="footer-links">
          <a href="/forgot-password/" class="link-item">
            <i class="fas fa-key"></i>
            <span>忘记密码？</span>
          </a>
        </div>
      </el-form>

      <!-- 第二步：2FA验证表单 -->
      <div v-if="require2fa" class="twofa-content">
        <!-- 2FA信息提示 - 优化样式 -->
        <div class="twofa-notice">
          <div class="notice-icon">
            <i class="fas fa-shield-alt"></i>
          </div>
          <div class="notice-text">
            <strong>两因素认证</strong>
            <p v-if="!useBackupCode && twoFaMethod === 'totp'">
              请打开您的身份验证器应用，输入显示的6位数字验证码
            </p>
            <p v-if="!useBackupCode && twoFaMethod === 'email'">
              验证码已发送到您的邮箱，请查收并输入
            </p>
            <p v-if="useBackupCode">
              请输入您的8位备用验证码
            </p>
          </div>
        </div>

        <!-- 2FA验证表单 -->
        <el-form
          ref="twoFaFormRef"
          :model="twoFaForm"
          :rules="twoFaRules"
          @submit.prevent="verifyTwoFA"
          class="auth-form"
        >
          <div class="form-section">
            <el-form-item prop="code" class="form-item">
              <el-input
                v-model="twoFaForm.code"
                :placeholder="useBackupCode ? '请输入8位备用验证码' : '请输入6位验证码'"
                size="large"
                :maxlength="useBackupCode ? 8 : 6"
                class="auth-input code-input"
                @keyup.enter="verifyTwoFA"
                @input="handleVerificationCodeInput"
              >
                <template #prefix>
                  <i class="fas fa-key input-icon"></i>
                </template>
              </el-input>
            </el-form-item>
          </div>

          <!-- 邮箱2FA倒计时和重发 -->
          <div v-if="twoFaMethod === 'email' && !useBackupCode" class="resend-section">
            <div v-if="countdown > 0" class="countdown-text">
              <i class="fas fa-clock"></i>
              <span>{{ countdown }}秒后可重新发送</span>
            </div>
            <button
              v-else
              type="button"
              @click="resendTwoFACode"
              :disabled="resendLoading"
              class="resend-btn"
            >
              <i class="fas fa-redo"></i>
              <span>{{ resendLoading ? '发送中...' : '重新发送验证码' }}</span>
            </button>
          </div>

          <!-- 操作按钮区 - 优化布局 -->
          <div class="twofa-actions">
            <!-- 主按钮：验证 -->
            <el-button
              type="primary"
              size="large"
              :loading="twoFaLoading"
              @click="verifyTwoFA"
              class="primary-btn"
            >
              <i class="fas fa-check-circle btn-icon"></i>
              {{ twoFaLoading ? '验证中...' : '验证' }}
            </el-button>

            <!-- 次要按钮：使用备用验证码 -->
            <el-button
              v-if="!useBackupCode"
              type="primary"
              size="large"
              @click="useBackupCode = true"
              class="primary-btn secondary-btn"
            >
              <i class="fas fa-key btn-icon"></i>
              使用备用验证码
            </el-button>
          </div>

          <!-- 返回链接 -->
          <div class="back-link-section">
            <el-button
              v-if="useBackupCode"
              type="primary"
              size="large"
              @click="useBackupCode = false; twoFaForm.code = ''"
              class="primary-btn secondary-btn"
            >
              <i class="fas fa-arrow-left btn-icon"></i>
              返回2FA验证
            </el-button>
            <el-button
              v-else
              type="primary"
              size="large"
              @click="backToPassword"
              class="primary-btn secondary-btn"
            >
              <i class="fas fa-arrow-left btn-icon"></i>
              返回密码验证
            </el-button>
          </div>
        </el-form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { User, Lock, Key } from '@element-plus/icons-vue'
import CaptchaWidget from '@components/common/CaptchaWidget.vue'

// ==================== 状态管理 ====================
const loginFormRef = ref()
const twoFaFormRef = ref()
const captchaWidgetRef = ref()

// 验证码参数
const captchaParams = ref({
  captcha_type: 'turnstile',
  turnstile_token: '',
  image_captcha: ''
})

const onCaptchaChange = (params) => {
  captchaParams.value = params
}

const refreshCaptcha = () => {
  if (captchaWidgetRef.value) {
    captchaWidgetRef.value.reset()
  }
}

// 登录表单数据
const loginForm = reactive({
  username: '',
  password: ''
})

// 登录表单验证规则
const loginRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 6, message: '用户名至少6位', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 8, message: '密码至少8位', trigger: 'blur' }
  ]
}

// 2FA验证表单数据
const twoFaForm = reactive({
  code: ''
})

// 状态变量
const loading = ref(false)
const require2fa = ref(false)
const twoFaLoading = ref(false)
const twoFaMethod = ref('totp')
const useBackupCode = ref(false)
const countdown = ref(0)
const resendLoading = ref(false)
const temporaryToken = ref('')

// 2FA验证规则
const twoFaRules = computed(() => {
  if (useBackupCode.value) {
    return {
      code: [
        { required: true, message: '请输入备用验证码', trigger: 'blur' },
        { len: 8, message: '备用验证码为8位', trigger: 'blur' }
      ]
    }
  } else {
    return {
      code: [
        { required: true, message: '请输入验证码', trigger: 'blur' },
        { len: 6, message: '验证码为6位', trigger: 'blur' }
      ]
    }
  }
})

// ==================== 方法定义 ====================
const handleLogin = async () => {
  if (!loginFormRef.value) return

  const valid = await loginFormRef.value.validate().catch(() => false)
  if (!valid) {
    const hasContent = loginForm.username || loginForm.password
    if (hasContent) {
      ElMessage.error('用户名或密码格式不正确')
    } else {
      ElMessage.warning('请填写用户名和密码')
    }
    return
  }

  if (captchaWidgetRef.value && !captchaWidgetRef.value.validate()) {
    return
  }

  loading.value = true

  try {
    const response = await window.apiService.auth.login({
      username: loginForm.username,
      password: loginForm.password,
      ...captchaParams.value
    })

    if (response.require_2fa) {
      require2fa.value = true
      twoFaMethod.value = response.two_fa_method || 'totp'
      temporaryToken.value = response.temporary_token

      if (twoFaMethod.value === 'email') {
        startCountdown()
        ElMessage.info('验证码已发送到您的邮箱，请查收')
      }

      ElMessage.success('密码验证成功，请完成两因素认证')
    } else {
      ElMessage.success('登录成功！')
      setTimeout(() => {
        window.location.href = '/'
      }, 1000)
    }
  } catch (error) {
    let errorMessage = ''

    if (error.response?.data) {
      const data = error.response.data
      
      if (typeof data === 'string') {
        errorMessage = data
      } else if (data.status === 'error' && data.message) {
        errorMessage = data.message
      } else if (data.error) {
        errorMessage = data.error
      } else if (data.message) {
        errorMessage = data.message
      } else if (data.errors) {
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

    ElMessage.error(errorMessage || '登录失败，请检查网络连接')
    refreshCaptcha()
  } finally {
    loading.value = false
  }
}

const verifyTwoFA = async () => {
  if (!twoFaFormRef.value) return

  try {
    const codeValue = twoFaForm.code.trim()

    if (!codeValue) {
      ElMessage.error('验证码错误')
      return
    }

    twoFaLoading.value = true

    const response = await window.apiService.auth.verify2FA({
      code: twoFaForm.code,
      use_backup_code: useBackupCode.value,
      temporary_token: temporaryToken.value
    })

    ElMessage.success('登录成功！')
    setTimeout(() => {
      window.location.href = '/'
    }, 1000)
  } catch (error) {
    let errorMessage = ''

    if (error.response?.data) {
      const data = error.response.data

      if (typeof data === 'string') {
        errorMessage = data
      } else if (data.status === 'error' && data.message) {
        errorMessage = data.message
      } else if (data.error) {
        errorMessage = data.error
      } else if (data.message) {
        errorMessage = data.message
      } else if (data.errors) {
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

    ElMessage.error(errorMessage || '验证失败，请检查网络连接')
  } finally {
    twoFaLoading.value = false
  }
}

const resendTwoFACode = async () => {
  try {
    resendLoading.value = true

    await window.apiService.auth.resend2FACode({
      temporary_token: temporaryToken.value
    })

    startCountdown()
    ElMessage.success('验证码已重新发送到您的邮箱')
  } catch (error) {
    let errorMessage = ''

    if (error.message) {
      errorMessage = error.message
    } else if (error.response?.data) {
      const data = error.response.data
      if (data.error) {
        errorMessage = data.error
      } else if (data.message) {
        errorMessage = data.message
      }
    }

    ElMessage.error(errorMessage || '发送失败，请稍后重试')
  } finally {
    resendLoading.value = false
  }
}

const startCountdown = () => {
  countdown.value = 60
  const timer = setInterval(() => {
    countdown.value--
    if (countdown.value <= 0) {
      clearInterval(timer)
    }
  }, 1000)
}

const backToPassword = () => {
  require2fa.value = false
  twoFaForm.code = ''
  useBackupCode.value = false
  countdown.value = 0
  refreshCaptcha()
}

const handleVerificationCodeInput = () => {
  // 获取期望的验证码长度
  const expectedLength = useBackupCode.value ? 8 : 6
  const currentLength = twoFaForm.code.length

  // 当输入达到预期长度时，自动触发验证
  if (currentLength === expectedLength) {
    // 延迟20ms确保输入完全更新，避免验证时收到不完整的输入
    setTimeout(() => {
      verifyTwoFA()
    }, 20)
  }
}

onMounted(() => {
  // CaptchaWidget 会自动初始化验证码
})
</script>

<style scoped>
/* ========== 页面容器 ========== */
.auth-page {
  position: relative;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  overflow: hidden;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

/* ========== 背景光球 ========== */
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

/* ========== 主内容区 - 毛玻璃卡片 ========== */
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

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* ========== 品牌区域 ========== */
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
  letter-spacing: -0.5px;
}

.brand-subtitle {
  font-size: 0.95rem;
  color: #6b7280;
  margin: 0;
  font-weight: 400;
}

/* ========== 表单样式 ========== */
.auth-form {
  width: 100%;
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: 20px;
  margin-bottom: 28px;
}

.form-item {
  margin-bottom: 0;
}

.form-item :deep(.el-form-item__error) {
  padding-top: 6px;
  font-size: 13px;
}

/* 输入框样式 - 下划线风格 */
.auth-input :deep(.el-input__wrapper) {
  background: rgba(255, 255, 255, 0.95);
  border: none;
  border-radius: 14px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
  padding: 6px 16px;
  transition: all 0.3s ease;
}

.auth-input :deep(.el-input__wrapper:hover) {
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.12);
  transform: translateY(-1px);
}

.auth-input :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 6px 28px rgba(102, 126, 234, 0.2);
  transform: translateY(-2px);
}

.auth-input :deep(.el-input__inner) {
  font-size: 15px;
  font-weight: 500;
  color: #1f2937;
}

.auth-input :deep(.el-input__inner::placeholder) {
  color: #9ca3af;
  font-weight: 400;
}

.input-icon {
  color: #667eea;
  font-size: 15px;
}

.code-input :deep(.el-input__inner) {
  letter-spacing: 4px;
  font-weight: 600;
  text-align: center;
}

/* ========== 验证码区域 ========== */
.captcha-section {
  margin-bottom: 32px;
}

/* ========== 操作按钮区 ========== */
.action-section {
  margin-bottom: 24px;
}

.primary-btn {
  width: 100%;
  height: 52px;
  font-size: 16px;
  font-weight: 600;
  border-radius: 14px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  box-shadow: 0 8px 24px rgba(102, 126, 234, 0.35);
  transition: all 0.3s ease;
}

.primary-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 32px rgba(102, 126, 234, 0.45);
}

.primary-btn:active {
  transform: translateY(0);
}

/* 次要按钮样式 - 较小的阴影和高度 */
.secondary-btn {
  height: 48px;
  font-size: 15px;
  box-shadow: 0 4px 16px rgba(102, 126, 234, 0.25);
}

.secondary-btn:hover {
  box-shadow: 0 8px 24px rgba(102, 126, 234, 0.35);
}

.btn-icon {
  margin-right: 8px;
}

/* ========== 底部链接 ========== */
.footer-links {
  text-align: center;
}

.link-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #667eea;
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  padding: 8px 16px;
  border-radius: 8px;
  transition: all 0.25s ease;
}

.link-item:hover {
  background: rgba(102, 126, 234, 0.1);
  color: #764ba2;
}

/* ========== 2FA 内容区 ========== */
.twofa-content {
  width: 100%;
}

/* 2FA 提示框 - 适配白色背景 */
.twofa-notice {
  display: flex;
  gap: 16px;
  padding: 20px;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.08) 0%, rgba(118, 75, 162, 0.08) 100%);
  border-radius: 16px;
  border-left: 4px solid #667eea;
  margin-bottom: 32px;
}

.notice-icon {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 18px;
}

.notice-text {
  flex: 1;
}

.notice-text strong {
  display: block;
  color: #1f2937;
  font-size: 15px;
  margin-bottom: 6px;
}

.notice-text p {
  color: #6b7280;
  font-size: 14px;
  line-height: 1.5;
  margin: 0;
}

/* 重发验证码区域 */
.resend-section {
  text-align: center;
  margin-bottom: 24px;
}

.countdown-text {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #6b7280;
  font-size: 14px;
}

.resend-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: transparent;
  border: none;
  color: #667eea;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  padding: 8px 16px;
  border-radius: 8px;
  transition: all 0.25s ease;
}

.resend-btn:hover:not(:disabled) {
  background: rgba(102, 126, 234, 0.1);
  color: #764ba2;
}

.resend-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 2FA 操作按钮区 */
.twofa-actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 24px;
}

/* Ghost 按钮 - 适配白色背景 */
.ghost-btn {
  width: 100%;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid rgba(102, 126, 234, 0.3);
  border-radius: 12px;
  color: #667eea;
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.25s ease;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.ghost-btn:hover {
  background: rgba(102, 126, 234, 0.08);
  border-color: #667eea;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
}

/* 返回链接区域 */
.back-link-section {
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
  padding: 8px 16px;
  border-radius: 8px;
  transition: all 0.25s ease;
}

.back-link:hover {
  color: #764ba2;
  background: rgba(102, 126, 234, 0.08);
}

/* ========== 响应式设计 ========== */
@media (max-width: 480px) {
  .auth-page {
    padding: 30px 16px;
  }

  .brand-section {
    margin-bottom: 36px;
  }

  .brand-icon {
    width: 64px;
    height: 64px;
    font-size: 28px;
  }

  .brand-title {
    font-size: 1.75rem;
  }

  .primary-btn {
    height: 48px;
    font-size: 15px;
  }
}
</style>
