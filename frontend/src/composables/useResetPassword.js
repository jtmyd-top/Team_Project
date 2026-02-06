/**
 * ResetPassword 逻辑层
 * 处理密码重置流程、表单验证、密码强度检测等功能
 */

import { ref, reactive, computed, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { usePasswordStrength } from '@composables/usePasswordStrength'

export function useResetPassword() {
  // ==================== Composables ====================
  const passwordRef = ref('')
  const {
    strength,
    rules: passwordRulesData,
    isValid: isPasswordStrongEnough,
    strengthText,
    strengthLevel
  } = usePasswordStrength(passwordRef)

  // ==================== 状态管理 ====================
  const resetFormRef = ref(null)
  const isLoading = ref(false)
  const isShaking = ref(false)
  const showSuccess = ref(false)

  // 初始数据
  const initialData = window.RESET_PASSWORD_INITIAL || {}
  const error = ref(initialData.error)
  const userId = ref(initialData.userId)
  const token = ref(initialData.token)
  const username = ref(initialData.username || '用户')

  const isValidRequest = ref(!!userId.value && !!token.value && !error.value)

  // 表单数据
  const resetForm = reactive({
    password: '',
    confirmPassword: ''
  })

  // 消息状态
  const message = reactive({
    text: '',
    type: 'info'
  })

  // ==================== 监听器 ====================
  watch(() => resetForm.password, (newVal) => {
    passwordRef.value = newVal
  })

  // ==================== 计算属性 ====================
  const passwordStrength = computed(() => strengthLevel.value)

  const shouldShowPasswordError = computed(() => {
    const password = resetForm.password
    if (!password) return false

    const hasMinLength = password.length >= 8
    const hasUpperCase = /[A-Z]/.test(password)
    const hasLowerCase = /[a-z]/.test(password)
    const hasNumber = /\d/.test(password)

    return !(hasMinLength && hasUpperCase && hasLowerCase && hasNumber && strengthLevel.value >= 2)
  })

  const isPasswordValid = computed(() => {
    const password = resetForm.password
    if (!password) return false

    const hasMinLength = password.length >= 8
    const hasUpperCase = /[A-Z]/.test(password)
    const hasLowerCase = /[a-z]/.test(password)
    const hasNumber = /\d/.test(password)

    return hasMinLength && hasUpperCase && hasLowerCase && hasNumber && strengthLevel.value >= 2
  })

  // ==================== 表单验证规则 ====================
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

  // ==================== 方法定义 ====================
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

    // 检查密码复杂度
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

  // ==================== 生命周期 ====================
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

  // ==================== 返回 ====================
  return {
    // Refs
    resetFormRef,

    // 状态
    isLoading,
    isShaking,
    showSuccess,
    error,
    userId,
    token,
    username,
    isValidRequest,

    // 表单数据
    resetForm,

    // 消息
    message,

    // 计算属性
    passwordStrength,
    shouldShowPasswordError,
    isPasswordValid,

    // 表单规则
    resetRules,

    // 方法
    getPasswordErrorMessage,
    checkPasswordStrength,
    getStrengthText,
    getMessageIcon,
    triggerShake,
    submitForm
  }
}
