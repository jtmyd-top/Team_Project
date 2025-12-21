<template>
  <div class="auth-container">
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
            <div class="validation-rules" :class="{ show: showUsernameRules }" v-show="showUsernameRules && signupForm.username">
              <!-- 只显示第一条错误的规则 -->
              <div
                v-for="rule in getUsernameFirstInvalidRule()"
                :key="rule.text"
                :class="{ 'rule-invalid': !rule.valid }"
                class="validation-rule"
              >
                <i class="fas fa-exclamation-circle"></i>
                {{ rule.text }}
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
              @blur="checkEmailOnServer"
              :loading="emailCheckLoading"
            />
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
            <div class="password-strength" v-show="showPasswordRules && signupForm.password">
              <div class="strength-bars">
                <div
                  v-for="level in 4"
                  :key="level"
                  :class="{
                    'strength-bar': true,
                    'strength-weak': passwordStrength.level === 1 && level <= 1,
                    'strength-medium': passwordStrength.level === 2 && level <= 2,
                    'strength-strong': passwordStrength.level === 3 && level <= 3,
                    'strength-very-strong': passwordStrength.level === 4 && level <= 4
                  }"
                ></div>
              </div>
              <div class="strength-text" :class="`strength-${passwordStrength.level}`">
                {{ passwordStrength.text }}
              </div>
            </div>
            <div class="validation-rules" :class="{ show: showPasswordRules }">
              <!-- 只显示第一条错误的规则 -->
              <div
                v-for="rule in getPasswordFirstInvalidRule()"
                :key="rule.text"
                :class="{ 'rule-invalid': !rule.valid }"
                class="validation-rule"
              >
                <i class="fas fa-exclamation-circle"></i>
                {{ rule.text }}
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
                :disabled="countdown > 0 || !isEmailValid || emailCodeLoading || emailCheckLoading"
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

    <!-- 图形验证码弹窗 -->
    <el-dialog
      v-model="showCaptchaDialog"
      title="安全验证"
      width="380px"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      center
      class="captcha-dialog"
    >
      <div class="captcha-dialog-content">
        <div class="captcha-header">
          <div class="captcha-icon">
            <i class="fas fa-shield-alt"></i>
          </div>
          <h3>请完成人机验证</h3>
          <p>为确保账户安全，请输入下方验证码</p>
        </div>

        <div class="captcha-body">
          <div class="captcha-input-group">
            <el-input
              v-model.trim="captchaDialogForm.captcha"
              placeholder="请输入验证码"
              size="large"
              maxlength="5"
              class="captcha-input"
              :prefix-icon="Key"
              @keyup.enter="submitCaptcha"
              @input="handleCaptchaInput"
              ref="captchaInputRef"
            />
          </div>

          <div class="captcha-image-container">
            <img
              :src="captchaUrl"
              alt="验证码"
              class="captcha-display"
              @click="() => refreshCaptcha(true)"
            />
            <div class="captcha-refresh-hint" @click="() => refreshCaptcha(true)">
              <i class="fas fa-sync-alt"></i>
              <span>点击刷新验证码</span>
            </div>
          </div>

          <div v-if="captchaDialogError" class="captcha-error">
            <i class="fas fa-exclamation-triangle"></i>
            <span class="error-text">{{ captchaDialogError }}</span>
            <button class="error-clear-btn" @click="captchaDialogError = ''" title="清空错误">
              <i class="fas fa-times"></i>
            </button>
          </div>
        </div>
      </div>

      <template #footer>
        <div class="captcha-dialog-footer">
          <el-button
            @click="cancelCaptcha"
            size="large"
            class="captcha-cancel-btn"
          >
            取消
          </el-button>
          <el-button
            type="primary"
            @click="submitCaptcha"
            size="large"
            :loading="captchaSubmitting"
            class="captcha-submit-btn"
          >
            <i class="fas fa-check"></i>
            验证并发送
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { User, Lock, Message, Key } from '@element-plus/icons-vue'
// apiService 已经挂载到 window 对象上

// ==================== 状态管理 ====================
const signupFormRef = ref()

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

// 验证码弹窗状态
const showCaptchaDialog = ref(false)
const captchaSubmitting = ref(false)
const captchaDialogError = ref('')
const captchaDialogForm = reactive({
  captcha: ''
})
const captchaInputRef = ref(null)

// 验证码相关
const captchaUrl = ref('')
const currentCaptchaId = ref('')
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

// 验证确认密码
const validateConfirmPassword = (rule, value, callback) => {
  if (value !== signupForm.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

// ==================== 验证规则 ====================
// 用户名验证规则
const usernameRules = ref([
  { text: '至少6个字符', valid: false },
  { text: '以小写字母开头', valid: false },
  { text: '只能包含字母、数字、下划线', valid: false }
])

// 密码验证规则
const passwordRules = ref([
  { text: '至少8个字符', valid: false },
  { text: '包含大写字母', valid: false },
  { text: '包含小写字母', valid: false },
  { text: '包含数字', valid: false }
])

// 密码强度
const passwordStrength = ref({
  level: 0,
  text: '请输入密码'
})

// 表单验证规则
const signupRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 6, message: '用户名至少6位', trigger: 'blur' },
    { pattern: /^[a-z][a-z0-9_]*$/, message: '用户名必须以小写字母开头，只能包含字母数字下划线', trigger: 'blur' }
  ],
  email: [
    { required: true, message: '请输入邮箱地址', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 8, message: '密码至少8位', trigger: 'blur' },
    { validator: validatePasswordRule, trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' }
  ],
  emailCode: [
    { required: true, message: '请输入邮箱验证码', trigger: 'blur' },
    { len: 6, message: '验证码为6位', trigger: 'blur' }
  ],
  agreeTerms: [
    { required: true, message: '请同意服务条款和隐私政策', trigger: 'change' }
  ]
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

// ==================== 方法定义 ====================
// 验证密码
const validatePassword = () => {
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
    console.error('检查用户名失败:', error)
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
    console.error('检查邮箱失败:', error)
  } finally {
    emailCheckLoading.value = false
  }
}

// 发送验证码前的验证和弹窗显示
const handleSendVerificationCode = async () => {
  if (!isEmailValid.value) return

  // 先检查邮箱是否可用
  emailCheckLoading.value = true
  emailError.value = ''

  try {
    const response = await window.apiService.auth.checkEmail(signupForm.email)
    if (response.is_taken) {
      emailError.value = '该邮箱已被绑定'
      return
    }

    // 邮箱可用，显示验证码弹窗
    showCaptchaDialog.value = true
    // 清空之前的错误信息
    captchaDialogForm.captcha = ''
    captchaDialogError.value = ''
    refreshCaptcha()
    // 聚焦到验证码输入框
    setTimeout(() => {
      captchaInputRef.value?.focus()
    }, 100)
  } catch (error) {
    console.error('检查邮箱失败:', error)
  } finally {
    emailCheckLoading.value = false
  }
}


// 弹窗验证码相关方法
const refreshCaptcha = async (clearError = false) => {
  try {
    const response = await fetch('/api/captcha/', {
      method: 'GET',
      headers: {
        'X-CSRFToken': window.SETTINGS_INITIAL?.csrfToken || ''
      }
    })

    const data = await response.json()

    if (data.status === 'success') {
      captchaUrl.value = data.captcha_image
      currentCaptchaId.value = data.captcha_id
      captchaDialogForm.captcha = ''
      // 根据参数决定是否清空错误信息
      if (clearError) {
        captchaDialogError.value = ''
      }
    } else {
      captchaDialogError.value = data.message || '验证码生成失败'
    }
  } catch (error) {
    console.error('获取验证码失败:', error)
    captchaDialogError.value = '网络错误，请稍后重试'
  }
}

const cancelCaptcha = () => {
  showCaptchaDialog.value = false
  captchaDialogForm.captcha = ''
  captchaDialogError.value = ''
}

const submitCaptcha = async () => {
  if (!captchaDialogForm.captcha || captchaDialogForm.captcha.trim().length !== 5) {
    captchaDialogError.value = '请输入5位验证码'
    // 不刷新验证码，让用户看到错误提示
    return
  }

  captchaSubmitting.value = true

  try {
    // 验证图形验证码
    const response = await fetch('/api/validate-captcha/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        captcha_id: currentCaptchaId.value,
        captcha_code: captchaDialogForm.captcha
      })
    })

    const data = await response.json()

    if (data.status === 'success') {
      // 验证码正确，发送邮箱验证码
      try {
        await window.apiService.auth.sendEmailCode(signupForm.email, 'register', true)
        ElMessage.success('验证码已发送到您的邮箱，请查收')
        emailCodeSent.value = true
        startCountdown()
        // 关闭弹窗
        showCaptchaDialog.value = false
        captchaDialogForm.captcha = ''
        captchaDialogError.value = ''
      } catch (emailError) {
        console.error('发送邮箱验证码失败:', emailError)
        // 发送邮箱验证码失败，显示错误信息
        if (emailError.message) {
          captchaDialogError.value = emailError.message
        } else {
          captchaDialogError.value = '发送验证码失败，请稍后重试'
        }
      }
    } else {
      captchaDialogError.value = data.message || '验证码错误'
      // 不刷新验证码，让错误信息持续显示
    }
  } catch (error) {
    console.error('发送验证码失败:', error)
    // 优先使用错误对象的message属性
    if (error.message) {
      captchaDialogError.value = error.message
    } else if (error.response?.data?.error) {
      captchaDialogError.value = error.response.data.error
    } else if (error.response?.data?.message) {
      captchaDialogError.value = error.response.data.message
    } else {
      captchaDialogError.value = '发送失败，请稍后重试'
    }
    // 不刷新验证码，让错误信息持续显示
  } finally {
    captchaSubmitting.value = false
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

// 处理验证码输入
const handleCaptchaInput = (value) => {
  // 当用户开始输入时，清空错误信息
  if (captchaDialogError.value && value && value.length > 0) {
    captchaDialogError.value = ''
  }
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

  try {
    const valid = await signupFormRef.value.validate()
    if (!valid) return

    submitLoading.value = true
    serverErrors.value = []

    const formData = {
      username: signupForm.username,
      email: signupForm.email,
      password: signupForm.password,
      confirm_password: signupForm.confirmPassword,
      email_code: signupForm.emailCode,
      agree_terms: signupForm.agreeTerms
    }

    await window.apiService.auth.register(formData)

    showPromptMessage('success', '注册成功！', '您的账户已创建成功，请登录')
  } catch (error) {
    console.error('注册失败:', error)
    if (error.response?.data) {
      const data = error.response.data
      if (typeof data === 'string') {
        serverErrors.value = [data]
      } else if (data.errors) {
        serverErrors.value = Object.values(data.errors).flat()
      } else if (data.error) {
        serverErrors.value = [data.error]
      } else if (typeof data === 'object' && data !== null) {
        // 处理 {password: ["此字段不能为空"]} 格式
        const errors = []
        for (const [field, messages] of Object.entries(data)) {
          if (Array.isArray(messages)) {
            errors.push(...messages)
          } else {
            errors.push(messages)
          }
        }
        serverErrors.value = errors
      } else {
        serverErrors.value = ['注册失败，请检查信息后重试']
      }
    } else if (error.message) {
      serverErrors.value = [error.message]
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

/* 验证规则样式 */
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
  color: #999;
  transition: color 0.3s ease;
}

.rule-valid {
  color: #4caf50;
}

.rule-invalid {
  color: #999;
}

.field-error {
  color: #f56c6c;
  font-size: 0.85rem;
  margin-top: 5px;
  display: flex;
  align-items: center;
  gap: 4px;
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

/* 弹窗式验证码样式 */
.captcha-dialog .el-dialog {
  border-radius: 16px;
  overflow: hidden;
}

.captcha-dialog .el-dialog__header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 0;
  margin: 0;
  border-radius: 16px 16px 0 0;
}

.captcha-dialog .el-dialog__header .el-dialog__title {
  color: white;
  font-weight: 600;
  font-size: 18px;
  padding: 20px 24px;
}

.captcha-dialog .el-dialog__headerbtn .el-dialog__close {
  color: white;
  font-size: 20px;
}

.captcha-dialog-content {
  padding: 0;
}

.captcha-header {
  background: linear-gradient(135deg, #f8f9ff 0%, #e8f4ff 100%);
  padding: 32px 24px;
  text-align: center;
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
}

.captcha-icon {
  width: 60px;
  height: 60px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
  box-shadow: 0 8px 24px rgba(102, 126, 234, 0.3);
}

.captcha-icon i {
  color: white;
  font-size: 24px;
}

.captcha-header h3 {
  margin: 0 0 8px 0;
  color: #2c3e50;
  font-size: 20px;
  font-weight: 600;
}

.captcha-header p {
  margin: 0;
  color: #64748b;
  font-size: 14px;
  line-height: 1.5;
}

.captcha-body {
  padding: 32px 24px;
}

.captcha-input-group {
  margin-bottom: 24px;
}

.captcha-input {
  width: 100%;
}

.captcha-input .el-input__wrapper {
  background: rgba(255, 255, 255, 0.9);
  border: 2px solid #e2e8f0;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  transition: all 0.3s ease;
}

.captcha-input .el-input__wrapper:hover {
  border-color: #cbd5e0;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.captcha-input .el-input__wrapper.is-focus {
  border-color: #667eea;
  box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.15);
}

.captcha-image-container {
  position: relative;
  margin-bottom: 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.captcha-display {
  width: 100%;
  max-width: 200px;
  height: 70px;
  border: 2px solid #e2e8f0;
  border-radius: 12px;
  object-fit: cover;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.captcha-display:hover {
  border-color: #667eea;
  box-shadow: 0 8px 24px rgba(102, 126, 234, 0.2);
  transform: scale(1.02);
}

.captcha-refresh-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #64748b;
  font-size: 12px;
  cursor: pointer;
  transition: color 0.2s ease;
}

.captcha-refresh-hint:hover {
  color: #667eea;
}

.captcha-refresh-hint i {
  font-size: 14px;
}

.captcha-error {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  color: #dc2626;
  font-size: 14px;
  margin-top: 12px;
  animation: slideInUp 0.3s ease;
  position: relative;
}

.captcha-error i {
  font-size: 16px;
  flex-shrink: 0;
}

.captcha-error .error-text {
  flex: 1;
  line-height: 1.4;
}

.captcha-error .error-clear-btn {
  background: none;
  border: none;
  color: #dc2626;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  transition: background-color 0.2s;
  flex-shrink: 0;
}

.captcha-error .error-clear-btn:hover {
  background: rgba(220, 38, 38, 0.1);
}

.captcha-dialog-footer {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 24px 24px 32px 24px;
  background: #f8fafc;
  border-top: 1px solid rgba(0, 0, 0, 0.05);
}

.captcha-cancel-btn {
  background: white;
  border: 2px solid #e2e8f0;
  color: #64748b;
  font-weight: 500;
}

.captcha-cancel-btn:hover {
  background: #f8fafc;
  border-color: #cbd5e0;
  color: #475569;
}

.captcha-submit-btn {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  color: white;
  font-weight: 600;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
  display: flex;
  align-items: center;
  gap: 6px;
}

.captcha-submit-btn:hover {
  background: linear-gradient(135deg, #5a67d8 0%, #6b4b8d 100%);
  box-shadow: 0 6px 16px rgba(102, 126, 234, 0.4);
  transform: translateY(-1px);
}

.captcha-submit-btn i {
  font-size: 14px;
}

@keyframes slideInUp {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
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