/**
 * Login 逻辑层
 * 处理登录、2FA验证、表单验证等功能
 */

import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { extractApiErrorMessage } from '@utils/apiError'

const resolveLoginErrorMessage = (error) => {
  if (error.response?.data) {
    return extractApiErrorMessage(error.response.data, '')
  }
  if (error.message && error.message !== '请求失败') {
    return error.message
  }
  return ''
}

const getSafeRedirectUrl = () => {
  const next = new URLSearchParams(window.location.search).get('next')
  if (next && next.startsWith('/') && !next.startsWith('//')) {
    return next
  }
  return '/'
}

export function useLogin(captchaWidgetRef) {
  // ==================== 状态管理 ====================
  const loginFormRef = ref()
  const twoFaFormRef = ref()

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

  const captchaReady = computed(() => {
    const widget = captchaWidgetRef.value
    if (!widget) return false
    if (typeof widget.isLoading === 'function' && widget.isLoading()) return false
    if (typeof widget.isVerified === 'function') {
      return widget.isVerified()
    }
    return false
  })

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
  const trustDevice = ref(false)  // 信任设备选项
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

    if (!captchaWidgetRef.value) {
      ElMessage.warning('\u4eba\u673a\u9a8c\u8bc1\u6b63\u5728\u52a0\u8f7d\uff0c\u8bf7\u7a0d\u540e\u518d\u8bd5')
      return
    }

    if (typeof captchaWidgetRef.value.isLoading === 'function' && captchaWidgetRef.value.isLoading()) {
      ElMessage.warning('\u4eba\u673a\u9a8c\u8bc1\u6b63\u5728\u52a0\u8f7d\uff0c\u8bf7\u7a0d\u540e\u518d\u8bd5')
      return
    }

    if (!captchaWidgetRef.value.validate()) {
      ElMessage.warning('\u8bf7\u5b8c\u6210\u4eba\u673a\u9a8c\u8bc1')
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
          window.location.href = getSafeRedirectUrl()
        }, 1000)
      }
    } catch (error) {
      const errorMessage = resolveLoginErrorMessage(error)

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
        use_backup: useBackupCode.value,
        trust_device: trustDevice.value,  // 传递信任设备选项
        temporary_token: temporaryToken.value
      })

      ElMessage.success('登录成功！')
      setTimeout(() => {
        window.location.href = getSafeRedirectUrl()
      }, 1000)
    } catch (error) {
      const errorMessage = resolveLoginErrorMessage(error)

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
      const errorMessage = resolveLoginErrorMessage(error)

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
    trustDevice.value = false  // 重置信任设备选项
    countdown.value = 0
    refreshCaptcha()
  }

  const handleVerificationCodeInput = () => {
    const expectedLength = useBackupCode.value ? 8 : 6
    const currentLength = twoFaForm.code.length

    if (currentLength === expectedLength) {
      setTimeout(() => {
        verifyTwoFA()
      }, 20)
    }
  }

  // ==================== 返回 ====================
  return {
    loginFormRef,
    twoFaFormRef,
    loginForm,
    loginRules,
    twoFaForm,
    twoFaRules,
    captchaParams,
    loading,
    require2fa,
    twoFaLoading,
    twoFaMethod,
    useBackupCode,
    trustDevice,
    countdown,
    resendLoading,
    captchaReady,
    onCaptchaChange,
    handleLogin,
    verifyTwoFA,
    resendTwoFACode,
    startCountdown,
    backToPassword,
    handleVerificationCodeInput
  }
}
