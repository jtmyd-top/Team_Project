// composables/usePrivateVault.js - 保密柜自动锁定功能
import { ref, onMounted, onUnmounted, watch } from 'vue'

// 默认锁定时间：5分钟
const DEFAULT_LOCK_TIMEOUT = 5 * 60 * 1000

export function usePrivateVault(options = {}) {
  const {
    lockTimeout = DEFAULT_LOCK_TIMEOUT,
    onLock = null,
    onUnlock = null
  } = options

  // 状态
  const isUnlocked = ref(false)
  const lastActivityTime = ref(Date.now())
  const remainingTime = ref(lockTimeout)

  let activityTimer = null
  let countdownInterval = null

  // 更新活动时间
  const updateActivity = () => {
    if (isUnlocked.value) {
      lastActivityTime.value = Date.now()
      remainingTime.value = lockTimeout
    }
  }

  // 锁定保密柜
  const lock = () => {
    isUnlocked.value = false
    remainingTime.value = 0
    clearTimer()
    if (onLock) onLock()
  }

  // 解锁保密柜
  const unlock = () => {
    isUnlocked.value = true
    lastActivityTime.value = Date.now()
    remainingTime.value = lockTimeout
    startTimer()
    if (onUnlock) onUnlock()
  }

  // 清除定时器
  const clearTimer = () => {
    if (activityTimer) {
      clearTimeout(activityTimer)
      activityTimer = null
    }
    if (countdownInterval) {
      clearInterval(countdownInterval)
      countdownInterval = null
    }
  }

  // 启动自动锁定定时器
  const startTimer = () => {
    clearTimer()

    // 倒计时更新
    countdownInterval = setInterval(() => {
      const elapsed = Date.now() - lastActivityTime.value
      remainingTime.value = Math.max(0, lockTimeout - elapsed)

      if (remainingTime.value <= 0) {
        lock()
      }
    }, 1000)

    // 主定时器
    activityTimer = setTimeout(() => {
      lock()
    }, lockTimeout)
  }

  // 格式化剩余时间
  const formatRemainingTime = () => {
    const minutes = Math.floor(remainingTime.value / 60000)
    const seconds = Math.floor((remainingTime.value % 60000) / 1000)
    return `${minutes}:${seconds.toString().padStart(2, '0')}`
  }

  // 活动事件监听
  const activityEvents = ['mousedown', 'mousemove', 'keydown', 'scroll', 'touchstart']

  const handleActivity = () => {
    updateActivity()
    // 重置定时器
    if (isUnlocked.value) {
      clearTimer()
      startTimer()
    }
  }

  // 生命周期
  onMounted(() => {
    // 添加活动事件监听
    activityEvents.forEach(event => {
      window.addEventListener(event, handleActivity, { passive: true })
    })

    // 监听页面可见性变化
    document.addEventListener('visibilitychange', () => {
      if (document.hidden && isUnlocked.value) {
        // 页面隐藏时立即锁定（可选）
        // lock()
      }
    })
  })

  onUnmounted(() => {
    clearTimer()
    activityEvents.forEach(event => {
      window.removeEventListener(event, handleActivity)
    })
  })

  // 监听解锁状态变化
  watch(isUnlocked, (newVal) => {
    if (newVal) {
      startTimer()
    } else {
      clearTimer()
    }
  })

  return {
    isUnlocked,
    remainingTime,
    lock,
    unlock,
    updateActivity,
    formatRemainingTime
  }
}

// 保密柜密码验证工具
export function useVaultPassword() {
  const isVerifying = ref(false)
  const error = ref('')

  const verifyPassword = async (password) => {
    isVerifying.value = true
    error.value = ''

    try {
      // 这里应该调用后端 API 验证密码
      const response = await fetch('/api/vault/verify/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({ password })
      })

      const data = await response.json()

      if (data.success) {
        return true
      } else {
        error.value = data.message || '密码错误'
        return false
      }
    } catch (e) {
      error.value = '验证失败，请重试'
      return false
    } finally {
      isVerifying.value = false
    }
  }

  return {
    isVerifying,
    error,
    verifyPassword
  }
}

// 获取 CSRF Token
function getCsrfToken() {
  const cookieValue = document.cookie
    .split('; ')
    .find(row => row.startsWith('csrftoken='))
    ?.split('=')[1]
  return cookieValue || ''
}
