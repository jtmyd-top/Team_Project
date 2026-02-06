<template>
  <div class="turnstile-container">
    <!-- 加载状态 -->
    <div v-if="isLoading" class="turnstile-loading">
      <i class="fas fa-spinner fa-spin"></i>
      <span>正在加载验证码...</span>
    </div>

    <!-- Turnstile Widget -->
    <div
      v-show="!isLoading && !error"
      ref="turnstileElement"
      class="cf-turnstile"
    ></div>

    <!-- 错误状态 -->
    <div v-if="error" class="turnstile-error">
      <i class="fas fa-exclamation-triangle"></i>
      <span>{{ error }}</span>
    </div>
  </div>
</template>

<script setup>
import { useTurnstileWidget } from '@/composables/useTurnstileWidget'
import '@/assets/styles/components/turnstile.css'

const props = defineProps({
  language: {
    type: String,
    default: 'zh-cn'
  },
  siteKey: {
    type: String,
    required: true
  }
})

const emit = defineEmits(['verified', 'error', 'expired'])

const {
  turnstileElement,
  error,
  isLoading,
  reset,
  getToken,
  isVerified,
  renderWidget
} = useTurnstileWidget(props, emit)

// 暴露方法给父组件
defineExpose({
  reset,
  getToken,
  isVerified,
  renderWidget
})
</script>
