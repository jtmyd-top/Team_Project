/**
 * useTurnstile - Cloudflare Turnstile 验证码集成
 *
 * 统一了 Login.vue, Signup.vue, ForgotPassword.vue 中的 Turnstile 集成逻辑
 */

import { ref, onMounted, onUnmounted } from 'vue'

// 默认配置
const DEFAULT_CONFIG = {
  // 验证成功后的消息
  successMessage: '人机验证通过',
  // 验证失败后的消息
  errorMessage: '人机验证失败，请重试',
  // 验证过期后的消息
  expiredMessage: '验证已过期，请重新验证',
  // 是否显示消息提示
  showMessage: true,
  // 消息提示函数（可自定义）
  messageHandler: null
}

/**
 * 默认消息处理器（使用 Element Plus）
 */
function defaultMessageHandler(type, message) {
  // 尝试使用 Element Plus 的 ElMessage
  if (typeof window !== 'undefined' && window.ElMessage) {
    window.ElMessage[type](message)
    return
  }

  // 降级到 console
  const methods = { success: 'log', error: 'error', warning: 'warn', info: 'info' }
  console[methods[type] || 'log'](`[Turnstile] ${message}`)
}

/**
 * Vue Composable: useTurnstile
 *
 * 用法:
 * ```js
 * import { useTurnstile } from '@/composables/useTurnstile'
 *
 * const {
 *   token,
 *   siteKey,
 *   isVerified,
 *   isLoading,
 *   onVerified,
 *   onError,
 *   onExpired,
 *   fetchSiteKey,
 *   reset
 * } = useTurnstile()
 *
 * // 在模板中使用
 * <Turnstile
 *   v-if="siteKey"
 *   :site-key="siteKey"
 *   @verified="onVerified"
 *   @error="onError"
 *   @expired="onExpired"
 * />
 * ```
 */
export function useTurnstile(options = {}) {
  const config = { ...DEFAULT_CONFIG, ...options }

  // 状态
  const token = ref('')
  const siteKey = ref('')
  const isVerified = ref(false)
  const isLoading = ref(false)
  const error = ref(null)

  // 消息处理
  const showMessage = (type, message) => {
    if (!config.showMessage) return

    if (config.messageHandler) {
      config.messageHandler(type, message)
    } else {
      defaultMessageHandler(type, message)
    }
  }

  /**
   * 验证成功回调
   * @param {string} verifiedToken - Turnstile 返回的 token
   */
  const onVerified = (verifiedToken) => {
    token.value = verifiedToken
    isVerified.value = true
    error.value = null
    showMessage('success', config.successMessage)
  }

  /**
   * 验证失败回调
   * @param {Error} err - 错误信息
   */
  const onError = (err) => {
    token.value = ''
    isVerified.value = false
    error.value = err
    showMessage('error', config.errorMessage)
  }

  /**
   * 验证过期回调
   */
  const onExpired = () => {
    token.value = ''
    isVerified.value = false
    showMessage('warning', config.expiredMessage)
  }

  /**
   * 从后端获取 Turnstile site key
   * @param {string} url - API 地址，默认 /api/turnstile-site-key/
   * @returns {Promise<string>} site key
   */
  const fetchSiteKey = async (url = '/api/turnstile-site-key/') => {
    isLoading.value = true
    error.value = null

    try {
      const response = await fetch(url)
      if (!response.ok) {
        throw new Error(`Failed to fetch site key: ${response.status}`)
      }

      const data = await response.json()

      // 支持多种响应格式
      // 格式1: {status: 'success', site_key: '...'}
      // 格式2: {site_key: '...'}
      // 格式3: {siteKey: '...'}
      let key = null
      if (data.status === 'success' && data.site_key) {
        key = data.site_key
      } else if (data.site_key) {
        key = data.site_key
      } else if (data.siteKey) {
        key = data.siteKey
      }

      if (key) {
        siteKey.value = key
        return key
      } else {
        throw new Error('Site key not found in response')
      }
    } catch (err) {
      error.value = err
      console.error('Failed to fetch Turnstile site key:', err)
      return null
    } finally {
      isLoading.value = false
    }
  }

  /**
   * 重置状态
   */
  const reset = () => {
    token.value = ''
    isVerified.value = false
    error.value = null
  }

  /**
   * 验证 token 是否有效（非空）
   * @returns {boolean}
   */
  const validate = () => {
    if (!token.value) {
      showMessage('warning', '请完成人机验证')
      return false
    }
    return true
  }

  return {
    // 状态
    token,
    siteKey,
    isVerified,
    isLoading,
    error,

    // 回调函数（用于绑定到 Turnstile 组件）
    onVerified,
    onError,
    onExpired,

    // 方法
    fetchSiteKey,
    reset,
    validate
  }
}

/**
 * 创建 Turnstile 验证规则（用于 Element Plus 表单验证）
 * @param {Ref} tokenRef - token 的 ref
 * @param {string} message - 验证失败时的消息
 * @returns {Object} 验证规则
 */
export function createTurnstileRule(tokenRef, message = '请完成人机验证') {
  return {
    validator: (rule, value, callback) => {
      if (!tokenRef.value) {
        callback(new Error(message))
      } else {
        callback()
      }
    },
    trigger: 'change'
  }
}

/**
 * Turnstile 组件的 props 类型定义（用于 TypeScript）
 */
export const turnstileProps = {
  siteKey: {
    type: String,
    required: true
  },
  theme: {
    type: String,
    default: 'auto',
    validator: (v) => ['auto', 'light', 'dark'].includes(v)
  },
  size: {
    type: String,
    default: 'normal',
    validator: (v) => ['normal', 'compact'].includes(v)
  }
}

export default useTurnstile
