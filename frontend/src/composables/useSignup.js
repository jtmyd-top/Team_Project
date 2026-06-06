/**
 * Signup 逻辑层
 * 处理用户注册流程、表单验证、CAPTCHA、邮箱验证码等功能
 */

import { ref, reactive, computed, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { User, Lock, Message, Key } from '@element-plus/icons-vue'
import { usePasswordStrength } from '@composables/usePasswordStrength'
import { extractApiErrorMessage } from '@utils/apiError'

const resolveSignupErrorMessages = (error) => {
  const message = error.response?.data
    ? extractApiErrorMessage(error.response.data, '')
    : (error.message && error.message !== '请求失败' ? error.message : '')

  if (!message) return []
  if (message.includes('人机验证')) {
    return ['人机验证已过期，请重新完成验证后重试']
  }
  return message.split(/;\s*/).filter(Boolean)
}

export function useSignup() {
  // ==================== Composables ====================
  const {
    strength: passwordStrengthData,
    updateStrength: updatePasswordStrength
  } = usePasswordStrength()

  // ==================== 验证码状态管理 ====================
  const captchaWidgetRef = ref()
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

  // ==================== 表单状态 ====================
  const signupFormRef = ref()

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

  // ==================== 验证规则 ====================
  const usernameRules = ref([
    { text: '至少6个字符', valid: false },
    { text: '以小写字母开头', valid: false },
    { text: '只能包含小写字母、数字、下划线', valid: false }
  ])

  const passwordRules = ref([
    { text: '至少8个字符', valid: false },
    { text: '包含大写字母', valid: false },
    { text: '包含小写字母', valid: false },
    { text: '包含数字', valid: false }
  ])

  const emailRules = ref([
    { text: '请输入邮箱地址', valid: false },
    { text: '邮箱格式不正确', valid: false }
  ])

  const confirmPasswordRules = ref([
    { text: '请再次输入密码', valid: false },
    { text: '两次输入的密码不一致', valid: false }
  ])

  const passwordStrength = ref({
    level: 0,
    text: '请输入密码'
  })

  const signupRules = {
    username: [],
    email: [],
    password: [],
    confirmPassword: [],
    emailCode: [],
    agreeTerms: []
  }

  // ==================== 计算属性 ====================
  const isEmailValid = computed(() => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    return emailRegex.test(signupForm.email)
  })

  const isCaptchaVerified = computed(() => {
    const params = captchaParams.value
    if (params.captcha_type === 'turnstile') {
      return !!params.turnstile_token
    }
    return params.image_captcha && params.image_captcha.length >= 4
  })

  const emailCodeButtonText = computed(() => {
    if (countdown.value > 0) {
      return `${countdown.value}秒后重发`
    }
    return '发送验证码'
  })

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

  const shouldShowUsernameError = computed(() => {
    const username = signupForm.username
    if (!username) return false
    const hasMinLength = username.length >= 6
    const startsWithLower = /^[a-z]/.test(username)
    const validChars = /^[a-z0-9_]*$/.test(username)
    return !(hasMinLength && startsWithLower && validChars)
  })

  const shouldShowEmailError = computed(() => {
    const email = signupForm.email
    if (!email) return false
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    return !emailRegex.test(email)
  })

  const shouldShowPasswordError = computed(() => {
    const password = signupForm.password
    if (!password) return false
    const hasMinLength = password.length >= 8
    const hasUpperCase = /[A-Z]/.test(password)
    const hasLowerCase = /[a-z]/.test(password)
    const hasNumber = /\d/.test(password)
    return !(hasMinLength && hasUpperCase && hasLowerCase && hasNumber && passwordStrength.value.level >= 2)
  })

  const shouldShowConfirmPasswordError = computed(() => {
    const confirmPassword = signupForm.confirmPassword
    if (!confirmPassword) return false
    return confirmPassword !== signupForm.password
  })

  // ==================== 验证函数 ====================
  const validatePassword = () => {
    passwordStrengthData.value = signupForm.password
    updatePasswordStrength()

    const password = signupForm.password
    const isValidLength = password.length >= 8
    const hasUpperCase = /[A-Z]/.test(password)
    const hasLowerCase = /[a-z]/.test(password)
    const hasNumber = /\d/.test(password)

    passwordRules.value = [
      { text: '至少8个字符', valid: isValidLength },
      { text: '包含大写字母', valid: hasUpperCase },
      { text: '包含小写字母', valid: hasLowerCase },
      { text: '包含数字', valid: hasNumber }
    ]

    if (isValidLength && hasUpperCase && hasLowerCase && hasNumber) {
      showPasswordRules.value = false
    } else if (password.length > 0) {
      showPasswordRules.value = true
    }

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

  const validateEmail = () => {
    const email = signupForm.email
    const hasValue = email.length > 0
    const isValidFormat = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
    emailRules.value = [
      { text: '请输入邮箱地址', valid: hasValue },
      { text: '邮箱格式不正确', valid: isValidFormat }
    ]
  }

  const validateConfirmPassword = () => {
    const confirmPassword = signupForm.confirmPassword
    const password = signupForm.password
    const hasValue = confirmPassword.length > 0
    const isMatch = confirmPassword === password && password.length > 0
    confirmPasswordRules.value = [
      { text: '请再次输入密码', valid: hasValue },
      { text: '两次输入的密码不一致', valid: isMatch }
    ]
  }

  const getUsernameErrorMessage = () => {
    const username = signupForm.username
    if (!username) return '请输入用户名'
    if (username.length < 6) return '用户名至少6位'
    if (!/^[a-z]/.test(username)) return '用户名必须以小写字母开头'
    if (!/^[a-z0-9_]*$/.test(username)) return '用户名只能包含小写字母、数字、下划线'
    return ''
  }

  const getEmailErrorMessage = () => {
    const email = signupForm.email
    if (!email) return '请输入邮箱地址'
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!emailRegex.test(email)) return '请输入正确的邮箱格式'
    return ''
  }

  const getPasswordErrorMessage = () => {
    const password = signupForm.password
    if (!password) return '请输入密码'
    if (password.length < 8) return '密码至少8位'
    if (!/[A-Z]/.test(password)) return '密码必须包含大写字母'
    if (!/[a-z]/.test(password)) return '密码必须包含小写字母'
    if (!/\d/.test(password)) return '密码必须包含数字'
    if (passwordStrength.value.level < 2) return '密码强度太弱，请增加复杂度'
    return ''
  }

  const getConfirmPasswordErrorMessage = () => {
    const confirmPassword = signupForm.confirmPassword
    if (!confirmPassword) return '请再次输入密码'
    if (confirmPassword !== signupForm.password) return '两次输入的密码不一致'
    return ''
  }

  // ==================== API 调用 ====================
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
      // 静默处理
    } finally {
      usernameCheckLoading.value = false
    }
  }

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
      // 静默处理
    } finally {
      emailCheckLoading.value = false
    }
  }

  const handleSendVerificationCode = async () => {
    if (!isEmailValid.value) return

    if (captchaWidgetRef.value && !captchaWidgetRef.value.validate()) {
      return
    }

    emailCheckLoading.value = true
    emailError.value = ''

    try {
      const response = await window.apiService.auth.checkEmail(signupForm.email)
      if (response.is_taken) {
        emailError.value = '该邮箱已被绑定'
        return
      }

      const data = await window.apiService.auth.sendEmailCode({
        email: signupForm.email,
        purpose: 'register',
        ...captchaParams.value
      })

      ElMessage.success('验证码已发送到您的邮箱，请查收')
      emailCodeSent.value = true
      startCountdown()
    } catch (error) {
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
      refreshCaptcha()
    } finally {
      emailCheckLoading.value = false
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

  const submitForm = async () => {
    if (!signupFormRef.value) return

    const customValidationErrors = []

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
      customValidationErrors.forEach(error => ElMessage.error(error))
      return
    }

    if (captchaWidgetRef.value && !captchaWidgetRef.value.validate()) {
      return
    }

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
        ...captchaParams.value
      }

      await window.apiService.auth.register(formData)
      showPromptMessage('success', '注册成功！', '您的账户已创建成功，请登录')
    } catch (error) {
      const errors = resolveSignupErrorMessages(error)
      serverErrors.value = errors.length > 0 ? errors : ['网络错误，请稍后重试']
      refreshCaptcha()
    } finally {
      submitLoading.value = false
    }
  }

  // ==================== 提示框 ====================
  const showPromptMessage = (type, title, message) => {
    promptType.value = type
    promptTitle.value = title
    promptMessage.value = message
    showPrompt.value = true
  }

  const closePrompt = () => {
    showPrompt.value = false
    if (promptType.value === 'success') {
      window.location.href = '/login/'
    }
  }

  // ==================== 焦点事件处理 ====================
  const handlePasswordFocus = () => {
    showPasswordRules.value = true
  }

  const handlePasswordBlur = () => {
    if (!signupForm.password) {
      showPasswordRules.value = false
    }
  }

  const handleUsernameFocus = () => {
    showUsernameRules.value = true
  }

  const handleUsernameBlur = () => {
    if (!signupForm.username) {
      showUsernameRules.value = false
    }
  }

  // ==================== 涟漪效果 ====================
  const addRippleEffect = (event) => {
    event.preventDefault()
    const link = event.currentTarget
    const rect = link.getBoundingClientRect()
    const x = event.clientX - rect.left
    const y = event.clientY - rect.top

    link.classList.remove('ripple-effect')
    void link.offsetWidth
    link.style.setProperty('--ripple-x', `${x}px`)
    link.style.setProperty('--ripple-y', `${y}px`)
    link.classList.add('ripple-effect')

    setTimeout(() => {
      window.location.href = link.href
    }, 300)
  }

  // ==================== 监听器 ====================
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

      if (isValidLength && isValidStart && isValidChars) {
        showUsernameRules.value = false
      } else {
        showUsernameRules.value = true
      }
    } else {
      usernameRules.value.forEach(rule => rule.valid = false)
      showUsernameRules.value = false
    }
  })

  watch(() => signupForm.email, () => {
    emailError.value = ''
  })

  // ==================== 生命周期 ====================
  onMounted(() => {
    // CaptchaWidget 会自动初始化验证码
  })

  // ==================== 返回 ====================
  return {
    // Refs
    signupFormRef,
    captchaWidgetRef,

    // 表单数据
    signupForm,

    // 加载状态
    usernameCheckLoading,
    emailCheckLoading,
    emailCodeLoading,
    submitLoading,

    // 错误状态
    serverErrors,
    usernameError,
    emailError,

    // 验证码
    countdown,
    emailCodeSent,
    isEmailValid,
    isCaptchaVerified,
    emailCodeButtonText,

    // 提示框
    showPrompt,
    promptType,
    promptTitle,
    promptMessage,

    // 验证规则显示
    showPasswordRules,
    showUsernameRules,
    usernameRules,
    passwordRules,
    emailRules,
    confirmPasswordRules,
    passwordStrength,

    // 表单规则
    signupRules,

    // 计算属性
    canSubmit,
    shouldShowUsernameError,
    shouldShowEmailError,
    shouldShowPasswordError,
    shouldShowConfirmPasswordError,

    // 方法
    onCaptchaChange,
    validatePassword,
    validateEmail,
    validateConfirmPassword,
    getUsernameErrorMessage,
    getEmailErrorMessage,
    getPasswordErrorMessage,
    getConfirmPasswordErrorMessage,
    checkUsernameOnServer,
    checkEmailOnServer,
    handleSendVerificationCode,
    submitForm,
    closePrompt,
    handlePasswordFocus,
    handlePasswordBlur,
    handleUsernameFocus,
    handleUsernameBlur,
    addRippleEffect
  }
}
