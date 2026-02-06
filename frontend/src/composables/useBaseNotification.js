import { ref, onUnmounted } from 'vue'

/**
 * BaseNotification composable
 * @param {Object} props - Component props
 * @returns {Object} - Composable state and methods
 */
export function useBaseNotification(props) {
  // 通知列表
  const notifications = ref([])
  const timers = new Map()
  let idCounter = 0

  /**
   * 获取图标类名
   */
  function getIconClass(type) {
    const icons = {
      success: 'fas fa-check-circle',
      error: 'fas fa-times-circle',
      warning: 'fas fa-exclamation-triangle',
      info: 'fas fa-info-circle'
    }
    return icons[type] || icons.info
  }

  /**
   * 添加通知
   * @param {Object|string} options - 通知配置或消息文本
   * @returns {number} 通知ID
   */
  function show(options) {
    const id = ++idCounter

    // 支持简单字符串参数
    const config = typeof options === 'string'
      ? { message: options }
      : options

    const notification = {
      id,
      message: config.message || '',
      type: config.type || 'info',
      duration: config.duration ?? props.duration,
      showIcon: config.showIcon ?? props.showIcon
    }

    // 限制最大数量
    if (notifications.value.length >= props.maxCount) {
      const oldest = notifications.value[0]
      closeNotification(oldest.id)
    }

    notifications.value.push(notification)

    // 自动关闭
    if (notification.duration > 0) {
      const timer = setTimeout(() => {
        closeNotification(id)
      }, notification.duration)
      timers.set(id, timer)
    }

    return id
  }

  /**
   * 快捷方法
   */
  function success(message, options = {}) {
    return show({ ...options, message, type: 'success' })
  }

  function error(message, options = {}) {
    return show({ ...options, message, type: 'error' })
  }

  function warning(message, options = {}) {
    return show({ ...options, message, type: 'warning' })
  }

  function info(message, options = {}) {
    return show({ ...options, message, type: 'info' })
  }

  /**
   * 关闭通知
   * @param {number} id - 通知ID
   */
  function closeNotification(id) {
    const index = notifications.value.findIndex(n => n.id === id)
    if (index > -1) {
      notifications.value.splice(index, 1)
    }

    // 清除定时器
    if (timers.has(id)) {
      clearTimeout(timers.get(id))
      timers.delete(id)
    }
  }

  /**
   * 关闭所有通知
   */
  function closeAll() {
    notifications.value = []
    timers.forEach(timer => clearTimeout(timer))
    timers.clear()
  }

  // 清理
  onUnmounted(() => {
    timers.forEach(timer => clearTimeout(timer))
    timers.clear()
  })

  return {
    notifications,
    getIconClass,
    show,
    success,
    error,
    warning,
    info,
    closeNotification,
    closeAll
  }
}
