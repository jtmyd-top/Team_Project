<template>
  <Teleport to="body">
    <TransitionGroup name="notification" tag="div" class="notification-container">
      <div
        v-for="notification in notifications"
        :key="notification.id"
        class="notification"
        :class="[notification.type, { 'with-icon': notification.showIcon }]"
        @click="closeNotification(notification.id)"
      >
        <i v-if="notification.showIcon" class="notification-icon" :class="getIconClass(notification.type)"></i>
        <span class="notification-message">{{ notification.message }}</span>
        <button class="notification-close" @click.stop="closeNotification(notification.id)">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>
    </TransitionGroup>
  </Teleport>
</template>

<script setup>
import { ref, onUnmounted } from 'vue'

// Props
const props = defineProps({
  // 默认显示时长(ms)
  duration: {
    type: Number,
    default: 3000
  },
  // 最大同时显示数量
  maxCount: {
    type: Number,
    default: 5
  },
  // 是否显示图标
  showIcon: {
    type: Boolean,
    default: true
  },
  // 位置
  position: {
    type: String,
    default: 'top-right',
    validator: (v) => ['top-right', 'top-left', 'top-center', 'bottom-right', 'bottom-left', 'bottom-center'].includes(v)
  }
})

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

// 暴露方法
defineExpose({
  show,
  success,
  error,
  warning,
  info,
  close: closeNotification,
  closeAll
})
</script>

<style scoped>
.notification-container {
  position: fixed;
  top: 80px;
  right: 20px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 10px;
  pointer-events: none;
}

.notification {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-radius: 8px;
  color: white;
  font-size: 14px;
  font-weight: 500;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  pointer-events: auto;
  cursor: pointer;
  max-width: 360px;
  min-width: 200px;
  backdrop-filter: blur(8px);
}

.notification-icon {
  font-size: 16px;
  flex-shrink: 0;
}

.notification-message {
  flex: 1;
  line-height: 1.4;
}

.notification-close {
  background: transparent;
  border: none;
  color: inherit;
  opacity: 0.7;
  cursor: pointer;
  padding: 2px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: opacity 0.2s;
}

.notification-close:hover {
  opacity: 1;
}

/* 类型样式 */
.notification.success {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
}

.notification.error {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
}

.notification.warning {
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
}

.notification.info {
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
}

/* 动画 */
.notification-enter-active {
  animation: slideInRight 0.3s ease-out;
}

.notification-leave-active {
  animation: slideOutRight 0.3s ease-in;
}

.notification-move {
  transition: transform 0.3s ease;
}

@keyframes slideInRight {
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

@keyframes slideOutRight {
  from {
    transform: translateX(0);
    opacity: 1;
  }
  to {
    transform: translateX(100%);
    opacity: 0;
  }
}

/* 响应式 */
@media (max-width: 480px) {
  .notification-container {
    left: 10px;
    right: 10px;
    top: 70px;
  }

  .notification {
    max-width: 100%;
    min-width: 0;
  }
}
</style>
