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
import { useBaseNotification } from '@/composables/useBaseNotification'
import '@/assets/styles/components/base-notification.css'

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

const {
  notifications,
  getIconClass,
  show,
  success,
  error,
  warning,
  info,
  closeNotification,
  closeAll
} = useBaseNotification(props)

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
