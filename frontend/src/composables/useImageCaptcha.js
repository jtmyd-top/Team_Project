import { ref, watch, onMounted } from 'vue'
import { useProofOfWork } from '@/composables/useProofOfWork'

export function useImageCaptcha(props, emit) {
  const captchaSrc = ref('')
  const captchaInput = ref(props.modelValue)
  const isLoading = ref(false)
  const error = ref('')
  const powProgress = ref(0)  // PoW 计算进度

  // 初始化 PoW composable
  const { isComputing, progress, getInitToken: solvePow, cancel: cancelPow } = useProofOfWork()

  // 监听 PoW 进度
  watch(progress, (val) => {
    powProgress.value = val
  })

  // 生成带 init_token 的验证码URL
  const getCaptchaUrl = (token) => {
    return `/api/captcha/?token=${encodeURIComponent(token)}&t=${Date.now()}`
  }

  // 获取 init_token（通过 PoW）
  const getInitToken = async () => {
    return await solvePow('/api/captcha/init/')
  }

  // 刷新验证码
  const refreshCaptcha = async () => {
    if (isLoading.value) return

    isLoading.value = true
    error.value = ''
    captchaInput.value = ''
    emit('update:modelValue', '')

    try {
      // 第一步：获取 init_token
      const initToken = await getInitToken()

      // 第二步：使用 token 获取验证码图片
      const response = await fetch(getCaptchaUrl(initToken), {
        credentials: 'include'  // 携带 cookie
      })

      if (!response.ok) {
        // 尝试解析错误信息
        const contentType = response.headers.get('content-type')
        if (contentType && contentType.includes('application/json')) {
          const errorData = await response.json()
          throw new Error(errorData.message || errorData.error || '验证码加载失败')
        }
        throw new Error('验证码加载失败')
      }

      const blob = await response.blob()

      // 释放之前的 URL
      if (captchaSrc.value && captchaSrc.value.startsWith('blob:')) {
        URL.revokeObjectURL(captchaSrc.value)
      }

      captchaSrc.value = URL.createObjectURL(blob)
      emit('loaded')
    } catch (err) {
      console.error('Failed to load captcha:', err)
      error.value = err.message || '验证码加载失败，请点击刷新'
      emit('error', err)
    } finally {
      isLoading.value = false
    }
  }

  // 处理输入
  const handleInput = (value) => {
    // 转大写，只允许字母和数字
    const filtered = value.toUpperCase().replace(/[^A-Z0-9]/g, '')
    captchaInput.value = filtered
    emit('update:modelValue', filtered)
  }

  // 监听 modelValue 变化
  watch(() => props.modelValue, (newVal) => {
    if (newVal !== captchaInput.value) {
      captchaInput.value = newVal
    }
  })

  // 重置方法
  const reset = () => {
    captchaInput.value = ''
    emit('update:modelValue', '')
    refreshCaptcha()
  }

  onMounted(() => {
    if (props.autoLoad) {
      refreshCaptcha()
    }
  })

  return {
    captchaSrc,
    captchaInput,
    isLoading,
    error,
    powProgress,
    isComputing,
    refreshCaptcha,
    handleInput,
    reset
  }
}
