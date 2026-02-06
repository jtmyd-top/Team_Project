import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'

/**
 * TurnstileWidget composable - 用于 Turnstile 组件内部逻辑
 * @param {Object} props - Component props
 * @param {Function} emit - Emit function
 * @returns {Object} - Composable state and methods
 */
export function useTurnstileWidget(props, emit) {
  const turnstileElement = ref(null)
  const turnstileToken = ref('')
  const error = ref('')
  const isLoaded = ref(false)
  const isLoading = ref(true)
  const widgetId = ref(null)
  const retryCount = ref(0)
  const maxRetries = 1  // 优化：只重试1次，快速降级到图形验证码

  // 加载 Turnstile 脚本
  const loadTurnstileScript = () => {
    return new Promise((resolve, reject) => {
      // 已经加载完成
      if (window.turnstile) {
        isLoaded.value = true
        resolve()
        return
      }

      // 检查是否已存在脚本标签
      const existingScript = document.querySelector('script[src*="challenges.cloudflare.com/turnstile"]')
      if (existingScript) {
        // 等待已有脚本加载
        const checkInterval = setInterval(() => {
          if (window.turnstile) {
            clearInterval(checkInterval)
            isLoaded.value = true
            resolve()
          }
        }, 100)
        return
      }

      // 创建新的脚本标签
      const script = document.createElement('script')
      script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit'
      script.async = true
      script.defer = true

      script.onload = () => {
        console.log('Turnstile script loaded')
        isLoaded.value = true
        resolve()
      }

      script.onerror = () => {
        console.error('Turnstile script load error')
        error.value = '验证码脚本加载失败，请刷新页面重试'
        reject(new Error('Failed to load Turnstile script'))
      }

      document.head.appendChild(script)
    })
  }

  // 渲染 Turnstile widget
  const renderWidget = async () => {
    await nextTick()

    if (!window.turnstile || !turnstileElement.value || !props.siteKey) {
      return false
    }

    // 清理已有 widget
    if (widgetId.value !== null) {
      try {
        window.turnstile.remove(widgetId.value)
      } catch (e) {
        // 忽略移除错误
      }
      widgetId.value = null
    }

    // 渲染新的 widget
    try {
      widgetId.value = window.turnstile.render(turnstileElement.value, {
        sitekey: props.siteKey,
        callback: (token) => {
          console.log('Turnstile verification succeeded')
          turnstileToken.value = token
          error.value = ''
          retryCount.value = 0  // 重置重试计数
          emit('verified', token)
        },
        'error-callback': (errorCode) => {
          console.error('Turnstile error:', errorCode)
          // 自动重试机制
          if (retryCount.value < maxRetries) {
            retryCount.value++
            console.log(`Turnstile 自动重试 (${retryCount.value}/${maxRetries})...`)
            // 优化：缩短重试间隔到500ms，加快降级速度
            setTimeout(() => {
              if (window.turnstile && widgetId.value !== null) {
                try {
                  window.turnstile.reset(widgetId.value)
                } catch (e) {
                  renderWidget()
                }
              } else {
                renderWidget()
              }
            }, 500)
          } else {
            error.value = '验证码加载失败，请刷新页面重试'
            emit('error', error.value)
          }
        },
        'expired-callback': () => {
          console.log('Turnstile token expired')
          turnstileToken.value = ''
          emit('expired')
        },
        theme: 'auto',
        size: 'normal',
        language: props.language
      })
      return true
    } catch (e) {
      console.error('Failed to render Turnstile widget:', e)
      error.value = '验证码渲染失败，请刷新页面重试'
      return false
    }
  }

  // 重置验证码
  const reset = () => {
    turnstileToken.value = ''
    error.value = ''
    retryCount.value = 0  // 重置重试计数

    if (window.turnstile && widgetId.value !== null) {
      try {
        window.turnstile.reset(widgetId.value)
      } catch (e) {
        // 忽略重置错误
      }
    }
  }

  // 获取 token
  const getToken = () => turnstileToken.value

  // 检查是否已验证
  const isVerified = () => !!turnstileToken.value

  // 监听 siteKey 变化
  watch(() => props.siteKey, (newKey, oldKey) => {
    if (newKey && newKey !== oldKey && isLoaded.value) {
      renderWidget()
    }
  })

  onMounted(async () => {
    isLoading.value = true
    error.value = ''

    try {
      await loadTurnstileScript()
      await renderWidget()
    } catch (err) {
      console.error('Failed to initialize Turnstile:', err)
      error.value = '验证码初始化失败，请刷新页面重试'
    } finally {
      isLoading.value = false
    }
  })

  onUnmounted(() => {
    if (window.turnstile && widgetId.value !== null) {
      try {
        window.turnstile.remove(widgetId.value)
      } catch (e) {
        // 忽略移除错误
      }
    }
    widgetId.value = null
  })

  return {
    turnstileElement,
    error,
    isLoading,
    reset,
    getToken,
    isVerified,
    renderWidget
  }
}
