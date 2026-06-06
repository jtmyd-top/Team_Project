/**
 * ForgotPassword 逻辑层
 * 处理忘记密码流程、邮箱验证、验证码发送等功能
 */

import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { extractApiErrorMessage } from '@utils/apiError'

export function useForgotPassword() {
  // ==================== 状态管理 ====================
  const forgotFormRef = ref(null)
  const captchaWidgetRef = ref(null)
  const isLoading = ref(false)
  const isCountingDown = ref(false)
  const countdown = ref(60)
  const isShaking = ref(false)

  // 验证码参数
  const captchaParams = ref({
    captcha_type: 'turnstile',
    turnstile_token: '',
    image_captcha: ''
  })

  // 表单数据
  const forgotForm = reactive({
    email: ''
  })

  // 消息状态
  const message = reactive({
    text: '',
    type: 'info'
  })

  // ==================== 验证函数 ====================
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

  // 表单验证规则
  const forgotRules = {
    email: [
      { required: true, message: '请输入邮箱地址', trigger: 'blur' },
      { validator: validateEmail, trigger: 'blur' }
    ]
  }

  // ==================== 方法定义 ====================
  const onCaptchaChange = (params) => {
    captchaParams.value = params
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
        message.text = extractApiErrorMessage(data, '发送失败，请稍后重试')
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

  // ==================== 生命周期 ====================
  onMounted(() => {
    const initialData = window.FORGOT_PASSWORD_INITIAL || {}
    if (initialData.user_is_authenticated) {
      window.location.href = '/'
    }
  })

  // ==================== 返回 ====================
  return {
    // Refs
    forgotFormRef,
    captchaWidgetRef,

    // 状态
    isLoading,
    isCountingDown,
    countdown,
    isShaking,

    // 表单数据
    forgotForm,

    // 消息
    message,

    // 表单规则
    forgotRules,

    // 方法
    onCaptchaChange,
    handleEmailInput,
    getMessageIcon,
    submitForm
  }
}
