/**
 * useCaptcha - 统一的验证码管理 Composable
 *
 * 逻辑：
 * - 默认强制使用 Turnstile
 * - 只有当 Turnstile 加载超时或验证失败时，才允许降级到图形验证码
 * - 用户不能主动选择图形验证码
 */

import { ref, computed, onMounted, onUnmounted } from 'vue'

// 验证类型常量
export const CAPTCHA_TYPE = {
  TURNSTILE: 'turnstile',
  IMAGE: 'image'
}

// 默认配置
const DEFAULT_CONFIG = {
  // Turnstile 脚本加载超时时间（毫秒）- 优化：从8秒减少到5秒
  turnstileTimeout: 5000,
  // Turnstile 渲染超时时间（毫秒）- 新增：渲染超时独立控制
  turnstileRenderTimeout: 3000,
  // 后端配置 API
  configApiUrl: '/api/turnstile/config/',
  // 是否显示降级提示
  showFallbackMessage: true,
  // 消息处理函数
  messageHandler: null
}

/**
 * 默认消息处理器
 */
function defaultMessageHandler(type, message) {
  if (typeof window !== 'undefined' && window.ElMessage) {
    window.ElMessage[type](message)
    return
  }
  const methods = { success: 'log', error: 'error', warning: 'warn', info: 'info' }
  console[methods[type] || 'log'](`[Captcha] ${message}`)
}

/**
 * useCaptcha Composable
 */
export function useCaptcha(options = {}) {
  const config = { ...DEFAULT_CONFIG, ...options }

  // ========== 状态 ==========
  const captchaType = ref(CAPTCHA_TYPE.TURNSTILE)  // 当前验证类型
  const turnstileEnabled = ref(false)               // 后端是否启用 Turnstile
  const turnstileSiteKey = ref('')                  // Turnstile site key
  const turnstileToken = ref('')                    // Turnstile token
  const imageCaptchaCode = ref('')                  // 图形验证码输入值
  const isLoading = ref(true)                       // 是否正在加载
  const isTurnstileVerified = ref(false)            // Turnstile 是否已验证
  const turnstileLoadFailed = ref(false)            // Turnstile 脚本是否加载失败
  const turnstileVerifyFailed = ref(false)          // Turnstile 验证是否失败（多次）
  const error = ref(null)                           // 错误信息
  const turnstileErrorCount = ref(0)                // Turnstile 错误次数

  // ========== 计算属性 ==========
  // 是否允许使用图形验证码（只有 Turnstile 失败后才允许）
  const canUseImageCaptcha = computed(() => {
    return turnstileLoadFailed.value || turnstileVerifyFailed.value || !turnstileEnabled.value
  })

  // 当前是否使用 Turnstile
  const isUsingTurnstile = computed(() => captchaType.value === CAPTCHA_TYPE.TURNSTILE)

  // 当前是否使用图形验证码
  const isUsingImageCaptcha = computed(() => captchaType.value === CAPTCHA_TYPE.IMAGE)

  // 是否已通过验证
  const isVerified = computed(() => {
    if (isUsingTurnstile.value) {
      return isTurnstileVerified.value && !!turnstileToken.value
    }
    // 图形验证码只检查是否有输入，实际验证在服务端
    return imageCaptchaCode.value.length >= 4
  })

  // 获取提交时需要的参数
  const captchaParams = computed(() => {
    if (isUsingTurnstile.value) {
      return {
        captcha_type: CAPTCHA_TYPE.TURNSTILE,
        turnstile_token: turnstileToken.value,
        image_captcha: ''
      }
    }
    return {
      captcha_type: CAPTCHA_TYPE.IMAGE,
      turnstile_token: '',
      image_captcha: imageCaptchaCode.value
    }
  })

  // ========== 消息处理 ==========
  const showMessage = (type, message) => {
    if (config.messageHandler) {
      config.messageHandler(type, message)
    } else {
      defaultMessageHandler(type, message)
    }
  }

  // ========== 方法 ==========

  /**
   * 获取后端配置
   */
  const fetchConfig = async () => {
    try {
      const response = await fetch(config.configApiUrl)
      if (!response.ok) {
        throw new Error(`Config API error: ${response.status}`)
      }
      const data = await response.json()

      if (data.status === 'success') {
        turnstileEnabled.value = data.enabled === true
        turnstileSiteKey.value = data.site_key || ''
        return { enabled: data.enabled, siteKey: data.site_key }
      }
      return { enabled: false, siteKey: null }
    } catch (err) {
      console.error('Failed to fetch captcha config:', err)
      return { enabled: false, siteKey: null }
    }
  }

  /**
   * 加载 Turnstile 脚本
   */
  const loadTurnstileScript = () => {
    return new Promise((resolve, reject) => {
      // 已经加载
      if (window.turnstile) {
        resolve()
        return
      }

      // 检查是否已有脚本标签
      const existingScript = document.querySelector('script[src*="challenges.cloudflare.com/turnstile"]')
      if (existingScript) {
        const checkInterval = setInterval(() => {
          if (window.turnstile) {
            clearInterval(checkInterval)
            resolve()
          }
        }, 100)

        // 超时检查
        setTimeout(() => {
          clearInterval(checkInterval)
          if (!window.turnstile) {
            reject(new Error('Turnstile script load timeout'))
          }
        }, config.turnstileTimeout)
        return
      }

      // 创建脚本
      const script = document.createElement('script')
      script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit'
      script.async = true
      script.defer = true

      // 设置超时
      const timeoutId = setTimeout(() => {
        script.onload = null
        script.onerror = null
        reject(new Error('Turnstile script load timeout'))
      }, config.turnstileTimeout)

      script.onload = () => {
        clearTimeout(timeoutId)
        resolve()
      }

      script.onerror = () => {
        clearTimeout(timeoutId)
        reject(new Error('Turnstile script load error'))
      }

      document.head.appendChild(script)
    })
  }

  /**
   * 初始化验证码系统
   * 优化：并行获取配置和预加载脚本，减少等待时间
   */
  const initialize = async () => {
    isLoading.value = true
    error.value = null
    turnstileLoadFailed.value = false
    turnstileVerifyFailed.value = false
    turnstileErrorCount.value = 0

    try {
      // 优化：并行获取配置和预加载 Turnstile 脚本
      const [configResult, scriptResult] = await Promise.allSettled([
        fetchConfig(),
        loadTurnstileScript()
      ])

      // 检查配置获取结果
      const configData = configResult.status === 'fulfilled' ? configResult.value : { enabled: false }

      // 如果后端禁用了 Turnstile，直接使用图形验证码
      if (!configData.enabled) {
        console.log('[Captcha] Turnstile disabled by server, using image captcha')
        captchaType.value = CAPTCHA_TYPE.IMAGE
        isLoading.value = false
        return
      }

      // 检查脚本加载结果
      if (scriptResult.status === 'rejected') {
        console.warn('[Captcha] Turnstile load failed:', scriptResult.reason?.message)
        turnstileLoadFailed.value = true
        captchaType.value = CAPTCHA_TYPE.IMAGE

        if (config.showFallbackMessage) {
          showMessage('warning', '智能验证加载失败，已切换为图形验证码')
        }
      } else {
        console.log('[Captcha] Turnstile loaded successfully')
        captchaType.value = CAPTCHA_TYPE.TURNSTILE
      }
    } catch (err) {
      console.error('[Captcha] Initialize error:', err)
      error.value = err
      captchaType.value = CAPTCHA_TYPE.IMAGE
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Turnstile 验证成功回调
   */
  const onTurnstileVerified = (token) => {
    turnstileToken.value = token
    isTurnstileVerified.value = true
    error.value = null
    turnstileErrorCount.value = 0  // 重置错误计数
  }

  /**
   * Turnstile 验证失败回调
   * 优化：Turnstile 组件内部已有重试机制，当收到 error 事件时说明重试已用完
   * 此时应立即降级到图形验证码，无需额外等待
   */
  const onTurnstileError = (err) => {
    console.error('[Captcha] Turnstile verification error:', err)
    turnstileToken.value = ''
    isTurnstileVerified.value = false

    // 立即降级到图形验证码（Turnstile 组件内部已完成重试）
    turnstileVerifyFailed.value = true
    captchaType.value = CAPTCHA_TYPE.IMAGE

    if (config.showFallbackMessage) {
      showMessage('warning', '智能验证失败，已切换为图形验证码')
    }
  }

  /**
   * Turnstile token 过期回调
   */
  const onTurnstileExpired = () => {
    turnstileToken.value = ''
    isTurnstileVerified.value = false
    showMessage('warning', '验证已过期，请重新验证')
  }

  /**
   * 切换到图形验证码（仅在允许时有效）
   */
  const switchToImageCaptcha = () => {
    if (!canUseImageCaptcha.value) {
      showMessage('info', '请先完成智能验证')
      return false
    }
    captchaType.value = CAPTCHA_TYPE.IMAGE
    imageCaptchaCode.value = ''
    return true
  }

  /**
   * 切换回 Turnstile（如果可用）
   */
  const switchToTurnstile = () => {
    if (turnstileLoadFailed.value) {
      showMessage('error', '智能验证不可用')
      return false
    }
    captchaType.value = CAPTCHA_TYPE.TURNSTILE
    turnstileToken.value = ''
    isTurnstileVerified.value = false
    return true
  }

  /**
   * 重置验证码
   */
  const reset = () => {
    turnstileToken.value = ''
    isTurnstileVerified.value = false
    imageCaptchaCode.value = ''
    error.value = null
    // 注意：不重置 turnstileLoadFailed 和 turnstileVerifyFailed
    // 因为这些状态表示已经发生过的失败
  }

  /**
   * 完全重置（包括错误状态）
   */
  const fullReset = () => {
    reset()
    turnstileErrorCount.value = 0
    // 如果之前是验证失败降级的，尝试恢复到 Turnstile
    if (turnstileVerifyFailed.value && !turnstileLoadFailed.value && turnstileEnabled.value) {
      turnstileVerifyFailed.value = false
      captchaType.value = CAPTCHA_TYPE.TURNSTILE
    }
  }

  /**
   * 验证是否可提交
   */
  const validate = () => {
    if (isUsingTurnstile.value) {
      if (!turnstileToken.value) {
        showMessage('warning', '请完成人机验证')
        return false
      }
    } else {
      if (!imageCaptchaCode.value || imageCaptchaCode.value.length < 4) {
        showMessage('warning', '请输入验证码')
        return false
      }
    }
    return true
  }

  // ========== 生命周期 ==========
  onMounted(() => {
    initialize()
  })

  // ========== 返回 ==========
  return {
    // 状态
    captchaType,
    turnstileEnabled,
    turnstileSiteKey,
    turnstileToken,
    imageCaptchaCode,
    isLoading,
    isTurnstileVerified,
    turnstileLoadFailed,
    turnstileVerifyFailed,
    error,

    // 计算属性
    canUseImageCaptcha,
    isUsingTurnstile,
    isUsingImageCaptcha,
    isVerified,
    captchaParams,

    // Turnstile 回调
    onTurnstileVerified,
    onTurnstileError,
    onTurnstileExpired,

    // 方法
    initialize,
    switchToImageCaptcha,
    switchToTurnstile,
    reset,
    fullReset,
    validate,

    // 常量
    CAPTCHA_TYPE
  }
}

export default useCaptcha
