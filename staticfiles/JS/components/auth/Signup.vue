<template>
  <div class="auth-container">
    <!-- 浮动光球 -->
    <div class="orb orb-1"></div>
    <div class="orb orb-2"></div>
    <div class="orb orb-3"></div>
    
    <div class="auth-card">
      <!-- 卡片头部 -->
      <div class="auth-header">
        <div class="auth-logo">
          <i class="fas fa-user-plus"></i>
        </div>
        <h2 class="auth-title">创建新账户</h2>
        <p class="auth-subtitle">加入知识管理平台</p>
      </div>

      <!-- 卡片内容 -->
      <div class="auth-body">
        <!-- 后端错误显示 -->
        <div v-if="serverErrors.length > 0" class="server-errors">
          <el-alert
            v-for="error in serverErrors"
            :key="error"
            :title="error"
            type="error"
            :closable="false"
            style="margin-bottom: 10px;"
          />
        </div>

        <!-- 注册表单 -->
        <el-form
          ref="signupFormRef"
          :model="signupForm"
          :rules="signupRules"
          @submit.prevent="submitForm"
          class="auth-form"
        >
          <!-- 用户名 -->
          <el-form-item prop="username">
            <el-input
              v-model.trim="signupForm.username"
              placeholder="请输入用户名"
              size="large"
              clearable
              :prefix-icon="User"
              @focus="handleUsernameFocus"
              @blur="[handleUsernameBlur, checkUsernameOnServer]"
              :loading="usernameCheckLoading"
            />
          <!-- 显示用户名验证提示 - 统一为红色边框样式 -->
            <div v-if="shouldShowUsernameError" class="validation-rules custom-validation"
                 style="display: block !important; visibility: visible !important; overflow: visible !important; margin-top: 8px; padding: 8px 12px; background: rgba(245, 108, 108, 0.1); border: 1px solid rgba(245, 108, 108, 0.3); border-radius: 6px; position: relative; z-index: 1000; max-width: 100%; box-sizing: border-box;">
              <div class="validation-rule rule-invalid"
                   style="color: #f56c6c !important; font-size: 14px; display: flex; align-items: center; gap: 6px; overflow: visible !important; word-wrap: break-word; word-break: break-all; line-height:0%;height: 100%;">
                <span style="color: #f56c6c; flex-shrink: 0;">●</span>
                <span style="flex: 1; min-width: 0;">{{ getUsernameErrorMessage() }}</span>
              </div>
            </div>
            <div v-if="usernameError" class="field-error">
              <i class="fas fa-exclamation-circle"></i>
              {{ usernameError }}
            </div>
          </el-form-item>

          <!-- 邮箱 -->
          <el-form-item prop="email">
            <el-input
              v-model.trim="signupForm.email"
              placeholder="请输入邮箱地址"
              size="large"
              clearable
              :prefix-icon="Message"
              @input="validateEmail"
              @blur="checkEmailOnServer"
              :loading="emailCheckLoading"
            />
            <!-- 显示邮箱验证提示 - 统一为红色边框样式 -->
            <div v-if="shouldShowEmailError" class="validation-rules custom-validation"
                 style="display: block !important; visibility: visible !important; overflow: visible !important; margin-top: 8px; padding: 8px 12px; background: rgba(245, 108, 108, 0.1); border: 1px solid rgba(245, 108, 108, 0.3); border-radius: 6px; position: relative; z-index: 1000; max-width: 100%; box-sizing: border-box;">
              <div class="validation-rule rule-invalid"
                   style="color: #f56c6c !important; font-size: 14px; display: flex; align-items: center; gap: 6px; overflow: visible !important; word-wrap: break-word; word-break: break-all; line-height: 0%; min-height: auto;">
                <span style="color: #f56c6c; flex-shrink: 0;">●</span>
                <span style="flex: 1; min-width: 0;">{{ getEmailErrorMessage() }}</span>
              </div>
            </div>
            <div v-if="emailError" class="field-error">
              <i class="fas fa-exclamation-circle"></i>
              {{ emailError }}
            </div>
          </el-form-item>

  
          <!-- 密码 -->
          <el-form-item prop="password">
            <el-input
              v-model="signupForm.password"
              type="password"
              placeholder="请输入密码"
              size="large"
              show-password
              :prefix-icon="Lock"
              @focus="handlePasswordFocus"
              @blur="handlePasswordBlur"
              @input="validatePassword"
            />
            <!-- 显示密码验证提示 - 统一为红色边框样式 -->
            <div v-if="shouldShowPasswordError" class="validation-rules custom-validation"
                 style="display: block !important; visibility: visible !important; overflow: visible !important; margin-top: 8px; padding: 8px 12px; background: rgba(245, 108, 108, 0.1); border: 1px solid rgba(245, 108, 108, 0.3); border-radius: 6px; position: relative; z-index: 1000; max-width: 100%; box-sizing: border-box;">
              <div class="validation-rule rule-invalid"
                   style="color: #f56c6c !important; font-size: 14px; display: flex; align-items: center; gap: 6px; overflow: visible !important; word-wrap: break-word; word-break: break-all; line-height: 0%; min-height: auto;">
                <span style="color: #f56c6c; flex-shrink: 0;">●</span>
                <span style="flex: 1; min-width: 0;">{{ getPasswordErrorMessage() }}</span>
              </div>
            </div>
          </el-form-item>

          <!-- 确认密码 -->
          <el-form-item prop="confirmPassword">
            <el-input
              v-model="signupForm.confirmPassword"
              type="password"
              placeholder="请再次输入密码"
              size="large"
              show-password
              :prefix-icon="Lock"
              @input="validateConfirmPassword"
            />
            <!-- 显示确认密码验证提示 - 统一为红色边框样式 -->
            <div v-if="shouldShowConfirmPasswordError" class="validation-rules custom-validation"
                 style="display: block !important; visibility: visible !important; overflow: visible !important; margin-top: 8px; padding: 8px 12px; background: rgba(245, 108, 108, 0.1); border: 1px solid rgba(245, 108, 108, 0.3); border-radius: 6px; position: relative; z-index: 1000; max-width: 100%; box-sizing: border-box;">
              <div class="validation-rule rule-invalid"
                   style="color: #f56c6c !important; font-size: 14px; display: flex; align-items: center; gap: 6px; overflow: visible !important; word-wrap: break-word; word-break: break-all; line-height:0%;height: 100%;">
                <span style="color: #f56c6c; flex-shrink: 0;">●</span>
                <span style="flex: 1; min-width: 0;">{{ getConfirmPasswordErrorMessage() }}</span>
              </div>
            </div>
          </el-form-item>

          <!-- Turnstile验证码 -->
          <el-form-item>
            <Turnstile
              ref="turnstileRef"
              :site-key="turnstileSiteKey"
              language="zh-CN"
              @verified="onTurnstileVerified"
              @error="onTurnstileError"
              @expired="onTurnstileExpired"
            />
          </el-form-item>

          <!-- 邮箱验证码 -->
          <el-form-item prop="emailCode">
            <div class="email-code-container">
              <el-input
                v-model="signupForm.emailCode"
                placeholder="请输入邮箱验证码"
                size="large"
                :prefix-icon="Key"
                maxlength="6"
                class="email-code-input"
              />
              <el-button
                :disabled="countdown > 0 || !isEmailValid || emailCodeLoading || emailCheckLoading || !turnstileToken"
                :loading="emailCodeLoading || emailCheckLoading"
                @click="handleSendVerificationCode"
                class="email-code-button"
                size="large"
              >
                {{ emailCheckLoading ? '检查中...' : emailCodeButtonText }}
              </el-button>
            </div>
          </el-form-item>

          <!-- 服务条款 -->
          <el-form-item prop="agreeTerms">
            <el-checkbox v-model="signupForm.agreeTerms" class="terms-checkbox">
              我已阅读并同意
              <a href="#" class="terms-link" @click.prevent>服务条款</a>
              和
              <a href="#" class="terms-link" @click.prevent>隐私政策</a>
            </el-checkbox>
          </el-form-item>

          <!-- 提交按钮 -->
          <el-form-item>
            <el-button
              type="primary"
              size="large"
              :loading="submitLoading"
              :disabled="!canSubmit"
              @click="submitForm"
              class="auth-button"
            >
              <i class="fas fa-user-plus" style="margin-right: 8px;"></i>
              {{ submitLoading ? '注册中...' : '创建账户' }}
            </el-button>
          </el-form-item>

          <!-- 登录链接 -->
          <div class="login-link">
            已有账户？
            <a href="/login/" class="login-link-text" @click="addRippleEffect">
              立即登录
            </a>
          </div>
        </el-form>
      </div>
    </div>

    <!-- 成功/错误提示模态框 -->
    <el-dialog
      v-model="showPrompt"
      :title="promptTitle"
      width="400px"
      :before-close="closePrompt"
      center
    >
      <div class="prompt-content">
        <div class="prompt-icon" :class="promptType">
          <i :class="promptType === 'success' ? 'fas fa-check-circle' : 'fas fa-times-circle'"></i>
        </div>
        <p class="prompt-message">{{ promptMessage }}</p>
      </div>
      <template #footer>
        <el-button @click="closePrompt" type="primary">确定</el-button>
      </template>
    </el-dialog>

    </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { User, Lock, Message, Key } from '@element-plus/icons-vue'
import Turnstile from '../Turnstile.vue'
import { usePasswordStrength } from '../../composables/usePasswordStrength'
import { useTurnstile } from '../../composables/useTurnstile'
// apiService 已经挂载到 window 对象上

// ==================== Composables ====================
// 使用密码强度检测
const {
  strength: passwordStrengthData,
  rules: passwordRulesData,
  isValid: isPasswordValid,
  strengthText,
  strengthLevel,
  updateStrength: updatePasswordStrength
} = usePasswordStrength()

// 使用 Turnstile 验证码
const {
  token: turnstileToken,
  siteKey: turnstileSiteKey,
  isVerified: isTurnstileVerified,
  onVerified: onTurnstileVerified,
  onError: onTurnstileError,
  onExpired: onTurnstileExpired,
  fetchSiteKey: fetchTurnstileSiteKey
} = useTurnstile()

// ==================== 状态管理 ====================
const signupFormRef = ref()
const turnstileRef = ref()

// 注册表单数据
const signupForm = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
  emailCode: '',
  agreeTerms: false
})

// 加载状态
const usernameCheckLoading = ref(false)
const emailCheckLoading = ref(false)
const emailCodeLoading = ref(false)
const submitLoading = ref(false)

// 错误状态
const serverErrors = ref([])
const usernameError = ref('')
const emailError = ref('')

// 验证码倒计时
const countdown = ref(0)
const emailCodeSent = ref(false)

// 提示框状态
const showPrompt = ref(false)
const promptType = ref('success')
const promptTitle = ref('')
const promptMessage = ref('')

// 验证规则显示状态
const showPasswordRules = ref(false)
const showUsernameRules = ref(false)

// ==================== 验证函数定义 ====================
// 验证密码
const validatePasswordRule = (rule, value, callback) => {
  if (passwordStrength.value.level < 2) {
    callback(new Error('密码强度太弱，请按照要求设置密码'))
  } else {
    callback()
  }
}

// 表单验证需要的验证函数
const validateConfirmPasswordForm = (rule, value, callback) => {
  if (value !== signupForm.password) {
    callback(new Error('两次输入的密码不一致'))
    return
  }
  callback()
}


// ==================== 验证规则 ====================
// 用户名验证规则
const usernameRules = ref([
  { text: '至少6个字符', valid: false },
  { text: '以小写字母开头', valid: false },
  { text: '只能包含小写字母、数字、下划线', valid: false }
])

// 密码验证规则
const passwordRules = ref([
  { text: '至少8个字符', valid: false },
  { text: '包含大写字母', valid: false },
  { text: '包含小写字母', valid: false },
  { text: '包含数字', valid: false }
])

// 邮箱验证规则
const emailRules = ref([
  { text: '请输入邮箱地址', valid: false },
  { text: '邮箱格式不正确', valid: false }
])

// 确认密码验证规则
const confirmPasswordRules = ref([
  { text: '请再次输入密码', valid: false },
  { text: '两次输入的密码不一致', valid: false }
])

// 密码强度
const passwordStrength = ref({
  level: 0,
  text: '请输入密码'
})

// 表单验证规则 - 完全禁用Element Plus的错误显示，只保留后端验证
const signupRules = {
  username: [],  // 清空所有Element Plus验证规则，完全依赖自定义验证
  email: [],     // 清空所有Element Plus验证规则，完全依赖自定义验证
  password: [],  // 清空所有Element Plus验证规则，完全依赖自定义验证
  confirmPassword: [],  // 清空所有Element Plus验证规则，完全依赖自定义验证
  emailCode: [], // 清空所有Element Plus验证规则，完全依赖自定义验证
  agreeTerms: [] // 清空所有Element Plus验证规则，完全依赖自定义验证
}

// ==================== 计算属性 ====================
// 邮箱是否有效
const isEmailValid = computed(() => {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  return emailRegex.test(signupForm.email)
})

// 邮箱验证码按钮文本
const emailCodeButtonText = computed(() => {
  if (countdown.value > 0) {
    return `${countdown.value}秒后重发`
  }
  return '发送验证码'
})

// 是否可以提交
const canSubmit = computed(() => {
  return (
    signupForm.username &&
    signupForm.email &&
    signupForm.password &&
    signupForm.confirmPassword &&
    signupForm.emailCode &&
    signupForm.agreeTerms &&
    !usernameError.value &&
    !emailError.value &&
    passwordStrength.value.level >= 2
  )
})

// Turnstile 回调函数已移至 useTurnstile composable

// ==================== 方法定义 ====================
// 验证密码 - 使用 composable
const validatePassword = () => {
  // 更新 composable 中的密码值并触发验证
  passwordStrengthData.value = signupForm.password
  updatePasswordStrength()

  const password = signupForm.password

  // 验证各个规则
  const isValidLength = password.length >= 8
  const hasUpperCase = /[A-Z]/.test(password)
  const hasLowerCase = /[a-z]/.test(password)
  const hasNumber = /\d/.test(password)

  // 更新密码规则
  passwordRules.value = [
    { text: '至少8个字符', valid: isValidLength },
    { text: '包含大写字母', valid: hasUpperCase },
    { text: '包含小写字母', valid: hasLowerCase },
    { text: '包含数字', valid: hasNumber }
  ]

  // 如果所有规则都符合，隐藏验证提示
  if (isValidLength && hasUpperCase && hasLowerCase && hasNumber) {
    showPasswordRules.value = false
  } else if (password.length > 0) {
    // 有输入但不符合规则，显示提示
    showPasswordRules.value = true
  }

  // 计算密码强度
  let strength = 0
  if (password.length >= 8) strength++
  if (password.length >= 12) strength++
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) strength++
  if (/\d/.test(password)) strength++
  if (/[^a-zA-Z\d]/.test(password)) strength++

  const strengthLevels = [
    { level: 0, text: '请输入密码' },
    { level: 1, text: '密码强度：弱' },
    { level: 2, text: '密码强度：中' },
    { level: 3, text: '密码强度：强' },
    { level: 4, text: '密码强度：很强' }
  ]

  passwordStrength.value = strengthLevels[Math.min(strength, 4)]
}

// 验证邮箱
const validateEmail = () => {
  const email = signupForm.email

  // 验证各个规则
  const hasValue = email.length > 0
  const isValidFormat = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)

  // 更新邮箱规则
  emailRules.value = [
    { text: '请输入邮箱地址', valid: hasValue },
    { text: '邮箱格式不正确', valid: isValidFormat }
  ]
}

// 验证确认密码
const validateConfirmPassword = () => {
  const confirmPassword = signupForm.confirmPassword
  const password = signupForm.password

  // 验证各个规则
  const hasValue = confirmPassword.length > 0
  const isMatch = confirmPassword === password && password.length > 0

  // 更新确认密码规则
  confirmPasswordRules.value = [
    { text: '请再次输入密码', valid: hasValue },
    { text: '两次输入的密码不一致', valid: isMatch }
  ]
}

// 获取邮箱错误提示信息
const getEmailErrorMessage = () => {
  const email = signupForm.email

  if (!email) {
    return '请输入邮箱地址'
  }

  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  if (!emailRegex.test(email)) {
    return '请输入正确的邮箱格式'
  }

  return '' // 符合要求，返回空字符串不显示提示
}

// 获取确认密码错误提示信息
const getConfirmPasswordErrorMessage = () => {
  const confirmPassword = signupForm.confirmPassword
  const password = signupForm.password

  if (!confirmPassword) {
    return '请再次输入密码'
  }

  if (confirmPassword !== password) {
    return '两次输入的密码不一致'
  }

  return '' // 符合要求，返回空字符串不显示提示
}

// 获取用户名错误提示信息
const getUsernameErrorMessage = () => {
  const username = signupForm.username

  if (!username) {
    return '请输入用户名'
  }

  if (username.length < 6) {
    return '用户名至少6位'
  }

  if (!/^[a-z]/.test(username)) {
    return '用户名必须以小写字母开头'
  }

  if (!/^[a-z0-9_]*$/.test(username)) {
    return '用户名只能包含小写字母、数字、下划线'
  }

  return '' // 符合要求，返回空字符串不显示提示
}

// 获取密码错误提示信息
const getPasswordErrorMessage = () => {
  const password = signupForm.password

  if (!password) {
    return '请输入密码'
  }

  if (password.length < 8) {
    return '密码至少8位'
  }

  const hasUpperCase = /[A-Z]/.test(password)
  const hasLowerCase = /[a-z]/.test(password)
  const hasNumber = /\d/.test(password)

  if (!hasUpperCase) {
    return '密码必须包含大写字母'
  }

  if (!hasLowerCase) {
    return '密码必须包含小写字母'
  }

  if (!hasNumber) {
    return '密码必须包含数字'
  }

  if (passwordStrength.value.level < 2) {
    return '密码强度太弱，请增加复杂度'
  }

  return '' // 符合要求，返回空字符串不显示提示
}

// 判断是否应该显示邮箱错误提示 - 改为计算属性以确保响应式更新
const shouldShowEmailError = computed(() => {
  const email = signupForm.email
  if (!email) {
    return false
  }

  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  const isValid = emailRegex.test(email)
  return !isValid
})

// 判断是否应该显示确认密码错误提示 - 改为计算属性以确保响应式更新
const shouldShowConfirmPasswordError = computed(() => {
  const confirmPassword = signupForm.confirmPassword
  const password = signupForm.password

  if (!confirmPassword) {
    return false
  }
  const isMatch = confirmPassword === password
  return !isMatch
})

// 判断是否应该显示用户名错误提示 - 改为计算属性以确保响应式更新
const shouldShowUsernameError = computed(() => {
  const username = signupForm.username

  if (!username) {
    return false
  }

  // 检查用户名验证规则
  const hasMinLength = username.length >= 6
  const startsWithLower = /^[a-z]/.test(username)
  const validChars = /^[a-z0-9_]*$/.test(username)

  const isValid = hasMinLength && startsWithLower && validChars
  return !isValid
})

// 判断是否应该显示密码错误提示 - 改为计算属性以确保响应式更新
const shouldShowPasswordError = computed(() => {
  const password = signupForm.password

  if (!password) {
    return false
  }

  // 检查密码验证规则
  const hasMinLength = password.length >= 8
  const hasUpperCase = /[A-Z]/.test(password)
  const hasLowerCase = /[a-z]/.test(password)
  const hasNumber = /\d/.test(password)

  const isValid = hasMinLength && hasUpperCase && hasLowerCase && hasNumber && passwordStrength.value.level >= 2
  return !isValid
})

// 检查用户名
const checkUsernameOnServer = async () => {
  if (!signupForm.username) return

  usernameCheckLoading.value = true
  usernameError.value = ''

  try {
    const response = await window.apiService.auth.checkUsername(signupForm.username)
    if (response.is_taken) {
      usernameError.value = response.message || '用户名已被使用'
    }
  } catch (error) {
    // 静默处理错误
  } finally {
    usernameCheckLoading.value = false
  }
}

// 检查邮箱可用性
const checkEmailOnServer = async () => {
  if (!isEmailValid.value) return

  emailCheckLoading.value = true
  emailError.value = ''

  try {
    const response = await window.apiService.auth.checkEmail(signupForm.email)
    if (response.is_taken) {
      emailError.value = '该邮箱已被绑定'
    }
  } catch (error) {
    // 静默处理错误
  } finally {
    emailCheckLoading.value = false
  }
}

// 发送验证码前的验证
const handleSendVerificationCode = async () => {
  if (!isEmailValid.value) return
  if (!turnstileToken.value) {
    ElMessage.warning('请先完成人机验证')
    return
  }

  // 先检查邮箱是否可用
  emailCheckLoading.value = true
  emailError.value = ''

  try {
    const response = await window.apiService.auth.checkEmail(signupForm.email)
    if (response.is_taken) {
      emailError.value = '该邮箱已被绑定'
      return
    }

    // 邮箱可用，发送验证码（包含Turnstile token进行验证）
    const data = await window.apiService.auth.sendEmailCode({
      email: signupForm.email,
      purpose: 'register',
      turnstile_token: turnstileToken.value
    })

    ElMessage.success('验证码已发送到您的邮箱，请查收')
    emailCodeSent.value = true
    startCountdown()
  } catch (error) {
    // 处理后端返回的详细错误信息
    let errorMessage = '发送验证码失败，请稍后重试'

    if (error.response?.data) {
      const data = error.response.data
      if (data.status === 'error' && data.message) {
        errorMessage = data.message
      } else if (data.error) {
        errorMessage = data.error
      } else if (data.message) {
        errorMessage = data.message
      }
    } else if (error.message) {
      errorMessage = error.message
    }

    ElMessage.error(errorMessage)
  } finally {
    emailCheckLoading.value = false
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

// 显示提示
const showPromptMessage = (type, title, message) => {
  promptType.value = type
  promptTitle.value = title
  promptMessage.value = message
  showPrompt.value = true
}

// 关闭提示
const closePrompt = () => {
  showPrompt.value = false
  if (promptType.value === 'success') {
    window.location.href = '/login/'
  }
}

// 提交表单
const submitForm = async () => {
  if (!signupFormRef.value) return

  // 跳过Element Plus表单验证，直接进行自定义验证
  const customValidationErrors = []

  // 自定义验证逻辑
  if (!signupForm.username) {
    customValidationErrors.push('请输入用户名')
  } else if (signupForm.username.length < 6) {
    customValidationErrors.push('用户名至少6位')
  } else if (!/^[a-z][a-z0-9_]*$/.test(signupForm.username)) {
    customValidationErrors.push('用户名必须以小写字母开头，只能包含小写字母数字下划线')
  }

  if (!signupForm.email) {
    customValidationErrors.push('请输入邮箱地址')
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(signupForm.email)) {
    customValidationErrors.push('请输入正确的邮箱格式')
  }

  if (!signupForm.password) {
    customValidationErrors.push('请输入密码')
  } else if (signupForm.password.length < 8) {
    customValidationErrors.push('密码至少8位')
  } else if (passwordStrength.value.level < 2) {
    customValidationErrors.push('密码强度太弱，请按照要求设置密码')
  }

  if (!signupForm.confirmPassword) {
    customValidationErrors.push('请再次输入密码')
  } else if (signupForm.confirmPassword !== signupForm.password) {
    customValidationErrors.push('两次输入的密码不一致')
  }

  if (!signupForm.emailCode) {
    customValidationErrors.push('请输入邮箱验证码')
  }

  if (!signupForm.agreeTerms) {
    customValidationErrors.push('请同意服务条款和隐私政策')
  }

  if (customValidationErrors.length > 0) {
    // 显示自定义验证错误
    customValidationErrors.forEach(error => {
      ElMessage.error(error)
    })
    return
  }

  // 检查Turnstile验证码
  if (!turnstileToken.value) {
    // 如果邮箱验证码已填写且表单其他部分都验证通过，可能是token过期
    if (signupForm.emailCode) {
      ElMessage.warning('人机验证已过期，请重新完成验证')
    } else {
      ElMessage.warning('请完成人机验证')
    }
    return
  }

  // 表单验证通过，开始注册
  submitLoading.value = true
  serverErrors.value = []

  try {
    const formData = {
      username: signupForm.username,
      email: signupForm.email,
      password: signupForm.password,
      confirm_password: signupForm.confirmPassword,
      email_code: signupForm.emailCode,
      agree_terms: signupForm.agreeTerms,
      turnstile_token: turnstileToken.value
    }

    await window.apiService.auth.register(formData)

    showPromptMessage('success', '注册成功！', '您的账户已创建成功，请登录')
  } catch (error) {
    // 解析后端返回的错误信息
    if (error.response?.data) {
      const data = error.response.data
      const errors = []
      
      // 处理各种可能的错误格式
      if (typeof data === 'string') {
        // 简单字符串错误
        errors.push(data)
      } else if (data.status === 'error' && data.message) {
        // {status: 'error', message: '...'}
        errors.push(data.message)
      } else if (data.error) {
        // {error: '...'}
        errors.push(data.error)
      } else if (data.errors) {
        // {errors: {...}}
        for (const [field, messages] of Object.entries(data.errors)) {
          if (Array.isArray(messages)) {
            // Django表单验证格式: {field: [{message: '...'}, ...]}
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
      } else if (typeof data === 'object' && data !== null) {
        // Django表单验证格式: {username: ['错误1'], email: ['错误2']}
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
      }
      
      serverErrors.value = errors.length > 0 ? errors : ['注册失败，请检查信息后重试']
    } else if (error.message && error.message !== '请求失败') {
      // 如果是人机验证相关错误，给出更友好的提示
      if (error.message.includes('人机验证')) {
        serverErrors.value = ['人机验证已过期，请重新完成验证后重试']
      } else {
        serverErrors.value = [error.message]
      }
    } else {
      serverErrors.value = ['网络错误，请稍后重试']
    }
  } finally {
    submitLoading.value = false
  }
}

// 监听用户名变化
watch(() => signupForm.username, (newUsername) => {
  usernameError.value = ''
  if (newUsername) {
    const isValidLength = newUsername.length >= 6
    const isValidStart = /^[a-z]/.test(newUsername)
    const isValidChars = /^[a-z0-9_]*$/.test(newUsername)

    usernameRules.value = [
      { text: '至少6个字符', valid: isValidLength },
      { text: '以小写字母开头', valid: isValidStart },
      { text: '只能包含字母、数字、下划线', valid: isValidChars }
    ]

    // 如果所有规则都符合，隐藏验证提示
    if (isValidLength && isValidStart && isValidChars) {
      showUsernameRules.value = false
    } else {
      // 显示验证提示，但只显示第一条错误的规则
      showUsernameRules.value = true
    }
  } else {
    usernameRules.value.forEach(rule => rule.valid = false)
    showUsernameRules.value = false
  }
})

// 监听邮箱变化
watch(() => signupForm.email, () => {
  emailError.value = ''
})

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

// 验证规则显示控制
const handlePasswordFocus = () => {
  showPasswordRules.value = true
}

const handlePasswordBlur = () => {
  // 如果密码为空，则隐藏验证规则
  if (!signupForm.password) {
    showPasswordRules.value = false
  }
}

const handleUsernameFocus = () => {
  showUsernameRules.value = true
}

const handleUsernameBlur = () => {
  // 如果用户名为空，则隐藏验证规则（参考密码输入框逻辑）
  if (!signupForm.username) {
    showUsernameRules.value = false
  }
  // 注意：这里不要根据验证状态隐藏，让用户能看到验证结果
}

// 获取用户名第一条无效规则
const getUsernameFirstInvalidRule = () => {
  // 返回第一条无效的规则
  const invalidRule = usernameRules.value.find(rule => !rule.valid)
  return invalidRule ? [invalidRule] : []
}

// 获取密码第一条无效规则
const getPasswordFirstInvalidRule = () => {
  // 返回第一条无效的规则
  const invalidRule = passwordRules.value.find(rule => !rule.valid)
  return invalidRule ? [invalidRule] : []
}

// 组件挂载
onMounted(() => {
  // 使用 composable 的 fetchSiteKey
  fetchTurnstileSiteKey('/api/turnstile/config/').then(key => {
    if (!key) {
      ElMessage.error('获取验证码配置失败')
    }
  })
})
</script>

<style scoped>
/* ========== 背景容器 ========== */
.auth-container {
  position: relative;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  overflow: hidden;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

/* 渐变网格覆盖 */
.auth-container::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background:
    radial-gradient(circle at 20% 80%, rgba(240, 147, 251, 0.3) 0%, transparent 50%),
    radial-gradient(circle at 80% 20%, rgba(102, 126, 234, 0.3) 0%, transparent 50%),
    radial-gradient(circle at 40% 40%, rgba(168, 85, 247, 0.2) 0%, transparent 50%);
  opacity: 0.8;
  z-index: 1;
}

/* 浮动光球 */
.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.4;
  z-index: 1;
  pointer-events: none;
}

.orb-1 {
  width: 500px;
  height: 500px;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.6), rgba(168, 85, 247, 0.6));
  top: -10%;
  left: -10%;
  animation: orbFloat1 20s ease-in-out infinite;
}

.orb-2 {
  width: 400px;
  height: 400px;
  background: linear-gradient(135deg, rgba(240, 147, 251, 0.5), rgba(245, 87, 108, 0.5));
  bottom: -10%;
  right: -10%;
  animation: orbFloat2 18s ease-in-out infinite 7s;
}

.orb-3 {
  width: 350px;
  height: 350px;
  background: linear-gradient(135deg, rgba(168, 85, 247, 0.4), rgba(102, 126, 234, 0.4));
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  animation: orbFloat3 22s ease-in-out infinite 14s;
}

@keyframes orbFloat1 {
  0%, 100% {
    transform: translate(0, 0);
  }
  33% {
    transform: translate(50px, -50px);
  }
  66% {
    transform: translate(-50px, 50px);
  }
}

@keyframes orbFloat2 {
  0%, 100% {
    transform: translate(0, 0);
  }
  33% {
    transform: translate(-60px, 40px);
  }
  66% {
    transform: translate(40px, -60px);
  }
}

@keyframes orbFloat3 {
  0%, 100% {
    transform: translate(-50%, -50%);
  }
  33% {
    transform: translate(calc(-50% + 30px), calc(-50% - 40px));
  }
  66% {
    transform: translate(calc(-50% - 40px), calc(-50% + 30px));
  }
}

/* ========== 毛玻璃卡片 ========== */
.auth-card {
  position: relative;
  z-index: 10;
  width: 100%;
  max-width: 520px;
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(30px) saturate(180%);
  -webkit-backdrop-filter: blur(30px) saturate(180%);
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-radius: 32px;
  overflow: hidden;
  box-shadow:
    0 20px 60px rgba(0, 0, 0, 0.3),
    inset 0 1px 0 rgba(255, 255, 255, 0.2);
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  animation: cardEntrance 0.8s ease-out;
}

@keyframes cardEntrance {
  from {
    opacity: 1;
    transform: translateY(30px) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.auth-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg,
    transparent,
    rgba(255, 255, 255, 0.4),
    transparent
  );
}

.auth-card:hover {
  transform: translateY(-5px) scale(1.01);
  box-shadow:
    0 30px 80px rgba(0, 0, 0, 0.35),
    inset 0 1px 0 rgba(255, 255, 255, 0.3);
  border-color: rgba(255, 255, 255, 0.3);
}

/* ========== 卡片头部 ========== */
.auth-header {
  background: transparent;
  padding: 40px 30px;
  text-align: center;
  color: white;
  position: relative;
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
  margin-top: 20px;
}

.auth-button {
  width: 100%;
  height: 50px;
  font-size: 1.1rem;
  font-weight: 600;
  border-radius: 12px;
}

.login-link {
  text-align: center;
  margin-top: 20px;
  color: #666;
}

.login-link-text {
  color: #667eea;
  text-decoration: none;
  font-weight: 500;
  margin-left: 5px;
}

.login-link-text:hover {
  color: #764ba2;
}

/* 字段提示样式 */
.field-hint {
  color: rgba(255, 255, 255, 0.7);
  font-size: 0.85rem;
  margin-top: 5px;
  margin-left: 4px;
  font-style: italic;
}

/* 字段错误样式 */
.field-error {
  color: #f56c6c;
  font-size: 0.85rem;
  margin-top: 5px;
  display: flex;
  align-items: center;
  gap: 4px;
}

/* 验证规则样式 - 统一为灰白色 */
.validation-rules {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.validation-rule {
  font-size: 0.85rem;
  display: flex;
  align-items: center;
  gap: 4px;
  color: rgba(255, 255, 255, 0.7);
  font-style: italic;
  transition: color 0.3s ease;
}

.rule-valid {
  color: #4caf50;
}

.rule-invalid {
  color: rgba(255, 255, 255, 0.7);
}

/* 内联验证错误样式 - 确保文字在红色边框内 */
.inline-validation-error {
  margin-top: 8px;
  padding: 8px 12px;
  background: rgba(245, 108, 108, 0.1);
  border: 1px solid rgba(245, 108, 108, 0.3);
  border-radius: 6px;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  word-wrap: break-word;
  word-break: break-word;
  overflow-wrap: break-word;
}

.inline-validation-error .error-icon {
  color: #f56c6c;
  font-size: 0.85rem;
  flex-shrink: 0;
  line-height: 1.4;
}

.inline-validation-error .error-text {
  color: #f56c6c;
  font-size: 0.85rem;
  line-height: 1.4;
  flex: 1;
  word-wrap: break-word;
  word-break: break-word;
  overflow-wrap: break-word;
  white-space: normal;
}

/* 输入框容器样式 */
.input-wrapper {
  position: relative;
  width: 100%;
}

/* 带错误状态的输入框 */
.input-wrapper :deep(.el-input.has-error .el-input__wrapper) {
  box-shadow: 0 0 0 1px rgba(245, 108, 108, 0.5) inset;
}

/* 密码强度样式 */
.password-strength {
  margin-top: 8px;
}

.strength-bars {
  display: flex;
  gap: 4px;
  margin-bottom: 5px;
}

.strength-bar {
  flex: 1;
  height: 4px;
  background: #e0e0e0;
  border-radius: 2px;
  transition: background-color 0.3s ease;
}

.strength-weak {
  background: #f56c6c;
}

.strength-medium {
  background: #e6a23c;
}

.strength-strong {
  background: #67c23a;
}

.strength-very-strong {
  background: #4caf50;
}

.strength-text {
  font-size: 0.85rem;
  font-weight: 500;
}

.strength-0 { color: #999; }
.strength-1 { color: #f56c6c; }
.strength-2 { color: #e6a23c; }
.strength-3 { color: #67c23a; }
.strength-4 { color: #4caf50; }

/* 邮箱验证码样式 */
.email-code-container {
  display: flex;
  gap: 10px;
}

.email-code-input {
  flex: 1;
}

.email-code-button {
  min-width: 120px;
  white-space: nowrap;
}


/* 服务条款样式 */
.terms-checkbox {
  margin-top: 10px;
}

.terms-link {
  color: #667eea;
  text-decoration: none;
}

.terms-link:hover {
  text-decoration: underline;
}

/* 服务器错误样式 */
.server-errors {
  margin-bottom: 20px;
}

/* 提示框样式 */
.prompt-content {
  text-align: center;
  padding: 20px 0;
}

.prompt-icon {
  font-size: 3rem;
  margin-bottom: 15px;
}

.prompt-icon.success {
  color: #67c23a;
}

.prompt-icon.error {
  color: #f56c6c;
}

.prompt-message {
  font-size: 1.1rem;
  color: #333;
  margin: 0;
}

/* 完全隐藏Element Plus的错误信息，避免重复显示 */
.auth-form :deep(.el-form-item__error) {
  display: none !important;
  visibility: hidden !important;
  opacity: 0 !important;
  height: 0 !important;
  margin: 0 !important;
  padding: 0 !important;
  overflow: hidden !important;
}

/* 修复全局overflow冲突 - 使用更强的选择器确保验证提示能够显示 */
.auth-form :deep(.el-form-item) {
  overflow: visible !important;
}

.auth-form :deep(.el-form-item__content) {
  overflow: visible !important;
  position: relative !important;
}

.auth-form .custom-validation {
  display: block !important;
  visibility: visible !important;
  overflow: visible !important;
  position: relative !important;
  z-index: 99999 !important;
  opacity: 1 !important;
  height: auto !important;
  max-height: none !important;
  pointer-events: auto !important;
  transform: none !important;
}

.auth-form .custom-validation .validation-rule {
  display: flex !important;
  visibility: visible !important;
  opacity: 1 !important;
  pointer-events: auto !important;
}

/* 额外的兜底样式 - 针对所有可能的情况 */
.auth-card :deep(.el-form-item),
.auth-card :deep(.el-form-item__content) {
  overflow: visible !important;
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

  .email-code-container {
    flex-direction: column;
    gap: 10px;
  }

  .email-code-button {
    min-width: auto;
  }

  .validation-rules {
    flex-direction: column;
    gap: 5px;
  }

  .auth-button {
    height: 45px;
    font-size: 1rem;
  }
}
</style>
