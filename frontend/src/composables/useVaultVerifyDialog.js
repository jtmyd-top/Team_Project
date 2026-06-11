/**
 * VaultVerifyDialog 逻辑层
 * 处理 2FA 验证、锁定状态、CAPTCHA 验证等功能
 */

import { ref, watch, computed, nextTick, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useVaultStore } from '@/stores/vault'
import { extractApiErrorMessage } from '@utils/apiError'

export function useVaultVerifyDialog(props, emit, captchaWidgetRef) {
  const vaultStore = useVaultStore()

  // ==================== 状态 ====================
  const code = ref('')
  const useBackup = ref(false)
  const isVerifying = ref(false)
  const errorMessage = ref('')
  const sendingCode = ref(false)
  const countdown = ref(0)
  const hasError = ref(false)
  const isShaking = ref(false)
  const failCount = ref(0)
  const requireCaptcha = ref(false)
  const captchaLoadError = ref(false)
  const codeInputRef = ref(null)
  const isVerificationSuccess = ref(false)

  // 解锁时长选择
  const DEFAULT_DURATION_MINUTES = 30
  const durationMinutes = ref(DEFAULT_DURATION_MINUTES)
  const durationOptions = [
    { label: '30 分钟 (默认)', value: 30 },
    { label: '1 小时', value: 60 },
    { label: '3 小时', value: 180 },
    { label: '6 小时', value: 360 },
    { label: '直到关闭浏览器为止', value: 0 }
  ]

  // CAPTCHA 参数
  const captchaParams = ref({
    captcha_type: 'turnstile',
    turnstile_token: '',
    image_captcha: ''
  })

  // 锁定状态
  const isLocked = ref(false)
  const lockRemaining = ref(0)
  let lockTimer = null
  let countdownTimer = null

  // ==================== 计算属性 ====================
  const dialogVisible = computed({
    get: () => props.modelValue,
    set: (val) => emit('update:modelValue', val)
  })

  const canVerify = computed(() => {
    if (isLocked.value || isVerifying.value) return false

    const codeValid = useBackup.value
      ? code.value.length === 8
      : code.value.length === 6

    if (!codeValid) return false

    if (requireCaptcha.value) {
      const params = captchaParams.value
      if (params.captcha_type === 'turnstile') {
        return !!params.turnstile_token
      }
      return params.image_captcha && params.image_captcha.length >= 4
    }

    return true
  })

  // ==================== 工具函数 ====================
  const formatLockTime = (seconds) => {
    if (seconds >= 3600) {
      const hours = Math.floor(seconds / 3600)
      const mins = Math.floor((seconds % 3600) / 60)
      return `${hours}小时${mins}分钟`
    } else if (seconds >= 60) {
      const mins = Math.floor(seconds / 60)
      const secs = seconds % 60
      return `${mins}分${secs}秒`
    }
    return `${seconds}秒`
  }

  // ==================== CAPTCHA 处理 ====================
  const onCaptchaChange = (params) => {
    captchaParams.value = params
    captchaLoadError.value = false
  }

  const onCaptchaError = (err) => {
    console.error('CAPTCHA加载错误:', err)
    captchaLoadError.value = true
  }

  const retryCaptcha = () => {
    captchaLoadError.value = false
    if (captchaWidgetRef.value && captchaWidgetRef.value.fullReset) {
      captchaWidgetRef.value.fullReset()
    }
  }

  // ==================== 输入处理 ====================
  const handleCodeInput = (e) => {
    code.value = code.value.replace(/\D/g, '')
    hasError.value = false
    errorMessage.value = ''

    // Keep the duration selector effective by submitting only from the
    // verify button or Enter, instead of racing as soon as the code is complete.
  }

  const handleBackupToggle = () => {
    code.value = ''
    hasError.value = false
    errorMessage.value = ''
    nextTick(() => {
      codeInputRef.value?.focus()
    })
  }

  // ==================== 动画效果 ====================
  const triggerShake = () => {
    isShaking.value = true
    hasError.value = true
    setTimeout(() => {
      isShaking.value = false
    }, 500)
  }

  // ==================== 邮箱验证码 ====================
  const handleSendEmailCode = async () => {
    if (sendingCode.value || countdown.value > 0) return

    sendingCode.value = true
    errorMessage.value = ''

    try {
      const response = await fetch('/api/vault/send-email-code/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
        }
      })
      const data = await response.json().catch(() => ({}))

      if (response.ok && data.status === 'success') {
        ElMessage.success('验证码已发送')
        startCountdown()
        nextTick(() => {
          codeInputRef.value?.focus()
        })
      } else {
        errorMessage.value = extractApiErrorMessage(data, '发送失败')
      }
    } catch (e) {
      errorMessage.value = e.message || '发送失败，请稍后重试'
    } finally {
      sendingCode.value = false
    }
  }

  const startCountdown = () => {
    countdown.value = 60
    countdownTimer = setInterval(() => {
      countdown.value--
      if (countdown.value <= 0) {
        clearInterval(countdownTimer)
      }
    }, 1000)
  }

  // ==================== 锁定倒计时 ====================
  const startLockCountdown = (seconds) => {
    isLocked.value = true
    lockRemaining.value = seconds

    if (lockTimer) clearInterval(lockTimer)
    lockTimer = setInterval(() => {
      lockRemaining.value--
      if (lockRemaining.value <= 0) {
        clearInterval(lockTimer)
        isLocked.value = false
        failCount.value = 0
        errorMessage.value = ''
        requireCaptcha.value = false
      }
    }, 1000)
  }

  // ==================== 验证逻辑 ====================
  const handleVerify = async () => {
    if (!canVerify.value || isVerifying.value) return

    isVerifying.value = true
    errorMessage.value = ''
    hasError.value = false

    try {
      // 方案 C：开启 ECDH 握手，携带临时公钥
      const { clientPrivateKey, clientPubB64 } = await vaultStore.beginHandshake()

      const requestBody = {
        code: code.value,
        use_backup: useBackup.value,
        duration: durationMinutes.value,
        client_pub: clientPubB64
      }

      if (requireCaptcha.value) {
        Object.assign(requestBody, captchaParams.value)
      }

      const response = await fetch('/api/vault/verify/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
        },
        body: JSON.stringify(requestBody)
      })
      const data = await response.json().catch(() => ({}))

      if (!response.ok) {
        triggerShake()
        errorMessage.value = extractApiErrorMessage(data, '验证失败，请稍后重试')
        code.value = ''
        return
      }

      if (data.status === 'success') {
        ElMessage.success('验证成功')
        isVerificationSuccess.value = true

        // 方案 C：用握手响应解包 DEK 并导入非导出 CryptoKey
        // 注意：用 remaining_seconds（TTL 秒数），expire_time 是 Unix 时间戳，直接当 TTL 会让
        // setTimeout 收到 1e15 级别的延时被浏览器钳为 1ms，立刻触发自动锁定
        const ttl = data.remaining_seconds || data.expire_time
        if (data.server_pub && data.iv && data.ct && ttl) {
          try {
            await vaultStore.completeHandshake({
              serverPubB64: data.server_pub,
              ivB64: data.iv,
              ctB64: data.ct,
              clientPrivateKey
            }, ttl)
          } catch (e) {
            console.error('[Vault] Failed to complete handshake:', e)
          }
        }

        emit('verified', {
          expireTime: data.expire_time,
          remainingSeconds: data.remaining_seconds
        })

        // 通知事件订阅者：vault 已解锁（不再广播原始 DEK）
        window.dispatchEvent(new CustomEvent('vault-verification-success', {
          detail: {
            expireTime: data.expire_time
          }
        }))

        dialogVisible.value = false
      } else if (data.status === 'locked') {
        failCount.value = data.fail_count || 0
        startLockCountdown(data.lock_seconds || 60)
        triggerShake()
        errorMessage.value = extractApiErrorMessage(data, '错误次数过多')
      } else if (data.status === 'require_captcha') {
        requireCaptcha.value = true
        failCount.value = data.fail_count || 0
        triggerShake()
        errorMessage.value = extractApiErrorMessage(data, '请完成人机验证')
        code.value = ''
        if (captchaWidgetRef.value) {
          captchaWidgetRef.value.reset()
        }
      } else {
        failCount.value = data.fail_count || failCount.value + 1
        triggerShake()
        errorMessage.value = extractApiErrorMessage(data, '验证码错误')
        code.value = ''

        if (data.require_captcha) {
          requireCaptcha.value = true
        }

        if (requireCaptcha.value && captchaWidgetRef.value) {
          captchaWidgetRef.value.reset()
        }

        nextTick(() => {
          codeInputRef.value?.focus()
        })
      }
    } catch (e) {
      triggerShake()
      errorMessage.value = '验证失败，请稍后重试'
      code.value = ''
    } finally {
      isVerifying.value = false
    }
  }

  // ==================== 关闭对话框 ====================
  const handleClose = () => {
    code.value = ''
    useBackup.value = false
    errorMessage.value = ''
    hasError.value = false
    isShaking.value = false
    requireCaptcha.value = false
    captchaLoadError.value = false
    durationMinutes.value = DEFAULT_DURATION_MINUTES
    captchaParams.value = {
      captcha_type: 'turnstile',
      turnstile_token: '',
      image_captcha: ''
    }
    dialogVisible.value = false

    if (!isVerificationSuccess.value) {
      emit('cancel')
    }

    isVerificationSuccess.value = false
  }

  // ==================== 锁定状态检查 ====================
  const checkLockStatus = async () => {
    try {
      const response = await fetch('/api/vault/lock-status/')
      const data = await response.json()
      if (data.is_locked) {
        startLockCountdown(data.remaining_seconds)
        failCount.value = data.fail_count || 0
      } else {
        isLocked.value = false
        failCount.value = data.fail_count || 0
        if (failCount.value >= 3) {
          requireCaptcha.value = true
        }
      }
    } catch (e) {
      console.error('检查锁定状态失败:', e)
    }
  }

  // ==================== 监听器 ====================
  watch(dialogVisible, (val) => {
    if (val) {
      checkLockStatus()
      nextTick(() => {
        codeInputRef.value?.focus()
      })
    } else {
      if (countdownTimer) {
        clearInterval(countdownTimer)
        countdown.value = 0
      }
    }
  })

  // ==================== 生命周期 ====================
  onUnmounted(() => {
    if (countdownTimer) clearInterval(countdownTimer)
    if (lockTimer) clearInterval(lockTimer)
  })

  // ==================== 返回 ====================
  return {
    // 状态
    code,
    useBackup,
    isVerifying,
    errorMessage,
    sendingCode,
    countdown,
    hasError,
    isShaking,
    failCount,
    requireCaptcha,
    captchaLoadError,
    codeInputRef,
    isLocked,
    lockRemaining,
    dialogVisible,
    canVerify,
    durationMinutes,
    durationOptions,

    // 方法
    formatLockTime,
    onCaptchaChange,
    onCaptchaError,
    retryCaptcha,
    handleCodeInput,
    handleBackupToggle,
    handleSendEmailCode,
    handleVerify,
    handleClose
  }
}
