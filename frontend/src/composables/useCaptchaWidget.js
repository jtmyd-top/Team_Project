import { ref, watch } from 'vue'
import { useCaptcha, CAPTCHA_TYPE } from '@/composables/useCaptcha'

export function useCaptchaWidget(props, emit) {
  // 使用 useCaptcha composable
  const {
    captchaType,
    turnstileEnabled,
    turnstileSiteKey,
    turnstileToken,
    imageCaptchaCode,
    isLoading,
    isTurnstileVerified,
    turnstileLoadFailed,
    turnstileVerifyFailed,
    canUseImageCaptcha,
    isUsingTurnstile,
    isUsingImageCaptcha,
    isVerified,
    captchaParams,
    error,
    initialize,
    onTurnstileVerified: handleTurnstileVerified,
    onTurnstileError: handleTurnstileError,
    onTurnstileExpired: handleTurnstileExpired,
    reset,
    fullReset,
    validate
  } = useCaptcha({
    turnstileTimeout: props.turnstileTimeout
  })

  // 重试初始化
  const retryInit = () => {
    initialize()
  }

  const turnstileRef = ref(null)
  const imageCaptchaRef = ref(null)

  // 包装 Turnstile 回调以触发事件
  const onTurnstileVerified = (token) => {
    handleTurnstileVerified(token)
    emit('verified', { type: CAPTCHA_TYPE.TURNSTILE, token })
    emit('change', captchaParams.value)
  }

  const onTurnstileError = (err) => {
    handleTurnstileError(err)
    emit('error', err)
    emit('change', captchaParams.value)
  }

  const onTurnstileExpired = () => {
    handleTurnstileExpired()
    emit('change', captchaParams.value)
  }

  // 监听图形验证码输入
  watch(imageCaptchaCode, () => {
    emit('change', captchaParams.value)
  })

  // 监听验证码类型变化（Turnstile 加载失败降级时触发）
  watch(captchaType, (newType, oldType) => {
    if (newType !== oldType) {
      console.log('[CaptchaWidget] captchaType changed:', oldType, '->', newType)
      emit('change', captchaParams.value)
    }
  })

  // 监听加载状态变化，初始化完成后触发一次 change
  watch(isLoading, (loading, wasLoading) => {
    if (wasLoading && !loading) {
      // 加载完成，通知父组件当前状态
      emit('change', captchaParams.value)
    }
  })

  // 监听错误状态，发出 error 事件
  watch(error, (err) => {
    if (err) {
      console.error('[CaptchaWidget] Error:', err)
      emit('error', err)
    }
  })

  // 重置方法（保留失败状态）
  const resetCaptcha = () => {
    reset()
    if (turnstileRef.value && turnstileRef.value.reset) {
      turnstileRef.value.reset()
    }
    if (imageCaptchaRef.value) {
      imageCaptchaRef.value.reset()
    }
  }

  // 完全重置（清除失败状态，尝试恢复 Turnstile）
  const fullResetCaptcha = () => {
    fullReset()
    if (turnstileRef.value && turnstileRef.value.reset) {
      turnstileRef.value.reset()
    }
  }

  // 刷新图形验证码
  const refreshImageCaptcha = () => {
    if (imageCaptchaRef.value) {
      imageCaptchaRef.value.refresh()
    }
  }

  return {
    // 状态
    captchaType,
    turnstileSiteKey,
    imageCaptchaCode,
    isLoading,
    isUsingTurnstile,
    isUsingImageCaptcha,
    isVerified,
    captchaParams,
    canUseImageCaptcha,
    // refs
    turnstileRef,
    imageCaptchaRef,
    // 方法
    retryInit,
    onTurnstileVerified,
    onTurnstileError,
    onTurnstileExpired,
    resetCaptcha,
    fullResetCaptcha,
    refreshImageCaptcha,
    validate,
    // 常量
    CAPTCHA_TYPE
  }
}
