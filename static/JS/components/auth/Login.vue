<template>
  <div class="auth-container">
    <div class="auth-card">
      <!-- 卡片头部 -->
      <div class="auth-header">
        <div class="auth-logo">
          <i class="fas fa-book-open"></i>
        </div>
        <h2 class="auth-title">欢迎回来</h2>
        <p class="auth-subtitle">登录您的知识管理账户</p>
      </div>

      <!-- 卡片内容 -->
      <div class="auth-body">
        <!-- 第一步：用户名密码登录表单 -->
        <el-form
          v-if="!require2fa"
          ref="loginFormRef"
          :model="loginForm"
          :rules="loginRules"
          @submit.prevent="handleLogin"
          class="auth-form"
        >
          <el-form-item prop="username">
            <el-input
              v-model="loginForm.username"
              placeholder="请输入用户名"
              size="large"
              clearable
              :prefix-icon="User"
            />
          </el-form-item>

          <el-form-item prop="password">
            <el-input
              v-model="loginForm.password"
              type="password"
              placeholder="请输入密码"
              size="large"
              show-password
              :prefix-icon="Lock"
              @keyup.enter="handleLogin"
            />
          </el-form-item>

          <el-form-item>
            <el-button
              type="primary"
              size="large"
              :loading="loading"
              @click="handleLogin"
              class="auth-button"
            >
              <i class="fas fa-sign-in-alt" style="margin-right: 8px;"></i>
              {{ loading ? '登录中...' : '登录' }}
            </el-button>
          </el-form-item>

          <div class="forgot-password-link">
            <a href="/forgot-password/" class="forgot-link" @click="addRippleEffect">
              <i class="fas fa-key"></i>
              忘记密码？
            </a>
          </div>
        </el-form>

        <!-- 第二步：2FA验证表单 -->
        <div v-if="require2fa" class="twofa-section">
          <!-- 2FA信息提示 -->
          <div class="twofa-info">
            <div class="twofa-info-header">
              <i class="fas fa-shield-alt"></i>
              <strong>两因素认证</strong>
            </div>
            <p v-if="!useBackupCode && twoFaMethod === 'totp'" class="twofa-description">
              请打开您的身份验证器应用，输入显示的6位数字验证码
            </p>
            <p v-if="!useBackupCode && twoFaMethod === 'email'" class="twofa-description">
              验证码已发送到您的邮箱，请查收并输入
            </p>
            <p v-if="useBackupCode" class="twofa-description">
              请输入您的8位备用验证码
            </p>
          </div>

          <!-- 2FA验证表单 -->
          <el-form
            ref="twoFaFormRef"
            :model="twoFaForm"
            :rules="twoFaRules"
            @submit.prevent="verifyTwoFA"
            class="auth-form"
          >
            <el-form-item prop="code">
              <el-input
                v-model="twoFaForm.code"
                :placeholder="useBackupCode ? '请输入8位备用验证码' : '请输入6位验证码'"
                size="large"
                :maxlength="useBackupCode ? 8 : 6"
                :prefix-icon="Key"
                @keyup.enter="verifyTwoFA"
                class="twofa-input"
              />
            </el-form-item>

            <!-- 邮箱2FA倒计时和重发 -->
            <div v-if="twoFaMethod === 'email' && !useBackupCode" class="twofa-email-actions">
              <div v-if="countdown > 0" class="countdown">
                <i class="fas fa-clock"></i>
                {{ countdown }}秒后可重新发送
              </div>
              <el-button
                v-else
                type="text"
                @click="resendTwoFACode"
                :disabled="resendLoading"
                class="resend-button"
              >
                <i class="fas fa-redo"></i>
                {{ resendLoading ? '发送中...' : '重新发送验证码' }}
              </el-button>
            </div>

            <!-- 切换到备用码 -->
            <div v-if="!useBackupCode" class="twofa-switch">
              <el-button
                type="text"
                @click="useBackupCode = true"
                class="switch-button"
              >
                <i class="fas fa-key"></i>
                使用备用验证码
              </el-button>
            </div>

            <el-form-item class="twofa-submit-item">
              <el-button
                type="primary"
                size="large"
                :loading="twoFaLoading"
                @click="verifyTwoFA"
                class="auth-button"
              >
                <i class="fas fa-shield-alt" style="margin-right: 8px;"></i>
                {{ twoFaLoading ? '验证中...' : '验证' }}
              </el-button>
            </el-form-item>

            <!-- 切换回密码验证 -->
            <div class="twofa-back">
              <el-button
                type="text"
                @click="backToPassword"
                class="back-button"
              >
                <i class="fas fa-arrow-left"></i>
                返回密码验证
              </el-button>
            </div>
          </el-form>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { User, Lock, Key } from '@element-plus/icons-vue'
// apiService 已经挂载到 window 对象上

// ==================== 状态管理 ====================
const loginFormRef = ref()
const twoFaFormRef = ref()

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

// 2FA验证规则（动态根据是否使用备用码调整）
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
// 处理登录
const handleLogin = async () => {
  if (!loginFormRef.value) return

  // 验证表单 - 使用 .catch() 确保 Element Plus 正常显示字段错误
  const valid = await loginFormRef.value.validate().catch(() => false)
  if (!valid) {
    // 表单验证失败
    // 检查是否有字段已填写但不符合规则
    const hasContent = loginForm.username || loginForm.password
    if (hasContent) {
      // 用户已输入内容但不符合规则，提示用户名或密码错误
      ElMessage.error('用户名或密码格式不正确')
    } else {
      // 用户未输入内容，提示填写信息
      ElMessage.warning('请填写用户名和密码')
    }
    return
  }

  // 表单验证通过，开始登录
  loading.value = true
  
  try {
    const response = await window.apiService.auth.login({
      username: loginForm.username,
      password: loginForm.password
    })

    if (response.require_2fa) {
      // 需要2FA验证
      require2fa.value = true
      twoFaMethod.value = response.two_fa_method || 'totp'
      temporaryToken.value = response.temporary_token

      if (twoFaMethod.value === 'email') {
        startCountdown()
        ElMessage.info('验证码已发送到您的邮箱，请查收')
      }

      ElMessage.success('密码验证成功，请完成两因素认证')
    } else {
      // 登录成功，重定向到首页
      ElMessage.success('登录成功！')
      setTimeout(() => {
        window.location.href = '/'
      }, 1000)
    }
  } catch (error) {
    // 这里只处理API请求错误
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
        // Django表单验证格式: {username: ['错误1'], password: ['错误2']}
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

    // 显示错误信息
    ElMessage.error(errorMessage || '登录失败，请检查网络连接')
  } finally {
    loading.value = false
  }
}

// 验证2FA
const verifyTwoFA = async () => {
  if (!twoFaFormRef.value) return

  try {
    const valid = await twoFaFormRef.value.validate()
    if (!valid) return

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
    // 使用相同的错误处理逻辑
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

    if (errorMessage) {
      ElMessage.error(errorMessage)
    } else {
      ElMessage.error('验证失败，请检查网络连接')
    }
  } finally {
    twoFaLoading.value = false
  }
}

// 重新发送2FA验证码
const resendTwoFACode = async () => {
  try {
    resendLoading.value = true

    await window.apiService.auth.resend2FACode({
      temporary_token: temporaryToken.value
    })

    startCountdown()
    ElMessage.success('验证码已重新发送到您的邮箱')
  } catch (error) {
    // 使用统一的错误处理函数
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

// 开始倒计时
const startCountdown = () => {
  countdown.value = 60
  const timer = setInterval(() => {
    countdown.value--
    if (countdown.value <= 0) {
      clearInterval(timer)
    }
  }, 1000)
}

// 返回密码验证
const backToPassword = () => {
  require2fa.value = false
  twoFaForm.code = ''
  useBackupCode.value = false
  countdown.value = 0
}

// 添加高级水波效果
const addRippleEffect = (event) => {
  event.preventDefault()

  const link = event.currentTarget
  const rect = link.getBoundingClientRect()
  const x = event.clientX - rect.left
  const y = event.clientY - rect.top

  // 移除之前的效果
  link.classList.remove('ripple-effect')

  // 触发重绘
  void link.offsetWidth

  // 设置点击位置
  link.style.setProperty('--ripple-x', `${x}px`)
  link.style.setProperty('--ripple-y', `${y}px`)

  // 添加涟漪效果
  link.classList.add('ripple-effect')

  // 延迟导航以显示完整的水波效果
  setTimeout(() => {
    window.location.href = link.href
  }, 300)
}

// 组件挂载
onMounted(() => {
  // 可以在这里添加初始化逻辑，比如检查是否已经登录
})
</script>

<style scoped>
.auth-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
}


.auth-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 25px 50px rgba(0, 0, 0, 0.15);
}

.auth-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 40px 30px;
  text-align: center;
  color: white;
}

.auth-logo {
  font-size: 3rem;
  margin-bottom: 20px;
}

.auth-title {
  font-size: 2rem;
  font-weight: 700;
  margin: 0 0 10px 0;
}

.auth-subtitle {
  font-size: 1.1rem;
  opacity: 0.9;
  margin: 0;
}

.auth-body {
  padding: 40px 30px;
}

.auth-form {
  margin-top: 36px; /* 增加表单与标题的距离 */
}

.auth-button {
  width: 100%;
  height: 50px;
  font-size: 1.1rem;
  font-weight: 600;
  border-radius: 12px;
}

.forgot-password-link {
  text-align: center;
  margin-top: 20px;
}

.forgot-link {
  color: #667eea;
  text-decoration: none;
  font-size: 0.95rem;
  transition: color 0.3s ease;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.forgot-link:hover {
  color: #764ba2;
}


.twofa-section {
  margin-top: 20px;
}

.twofa-info {
  background: #f8f9ff;
  border-left: 4px solid #667eea;
  padding: 24px;
  border-radius: 12px;
  margin-bottom: 32px; /* 增加提示框和输入框的距离 */
}

.twofa-info-header {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #667eea;
  font-size: 1.1rem;
  margin-bottom: 14px;
}

.twofa-description {
  color: #666;
  line-height: 1.6;
  margin: 0;
  font-size: 0.95rem;
}

/* 2FA表单提交按钮项的间距 */
.twofa-submit-item {
  margin-top: 24px !important; /* 验证按钮的顶部间距 */
}

.twofa-email-actions {
  text-align: center;
  margin-bottom: 20px;
}

.countdown {
  color: #666;
  font-size: 0.95rem;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.resend-button {
  color: #667eea;
  font-weight: 500;
}

.twofa-switch {
  text-align: center;
  margin-bottom: 24px; /* 增加切换按钮的底部间距 */
}

.switch-button {
  color: #667eea;
  font-size: 0.95rem;
}

.twofa-back {
  text-align: center;
  margin-top: 24px; /* 增加返回按钮的顶部间距 */
}

.back-button {
  color: #999;
  font-size: 0.9rem;
}

.back-button:hover {
  color: #667eea;
}

/* 响应式设计 */
@media (max-width: 480px) {
  .auth-container {
    padding: 10px;
  }

  .auth-header {
    padding: 30px 20px;
  }

  .auth-body {
    padding: 30px 20px;
  }

  .auth-title {
    font-size: 1.75rem;
  }

  .auth-button {
    height: 45px;
    font-size: 1rem;
  }
}
</style>
