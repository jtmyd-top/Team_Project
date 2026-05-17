<template>
  <div class="captcha-widget">
    <!-- 加载状态 - 优化：显示更友好的加载提示 -->
    <div v-if="isLoading" class="captcha-loading-state">
      <div class="loading-spinner">
        <i class="fas fa-shield-alt"></i>
      </div>
      <span>正在加载智能验证...</span>
    </div>

    <!-- Turnstile 验证 -->
    <template v-else-if="isUsingTurnstile">
      <Turnstile
        v-if="turnstileSiteKey"
        ref="turnstileRef"
        :site-key="turnstileSiteKey"
        @verified="onTurnstileVerified"
        @error="onTurnstileError"
        @expired="onTurnstileExpired"
      />
      <!-- 等待 siteKey 加载的状态 -->
      <div v-else class="captcha-loading-state">
        <div class="loading-spinner">
          <i class="fas fa-spinner fa-spin"></i>
        </div>
        <span>正在初始化验证码...</span>
      </div>
    </template>

    <!-- 图形验证码（仅在 Turnstile 失败后显示） -->
    <template v-else-if="isUsingImageCaptcha">
      <ImageCaptcha
        ref="imageCaptchaRef"
        v-model="imageCaptchaCode"
        @enter="$emit('enter')"
      />
    </template>

    <!-- 备用状态：如果所有条件都不满足 -->
    <div v-else class="captcha-error-state">
      <i class="fas fa-exclamation-triangle"></i>
      <span>验证码加载失败</span>
      <button @click="retryInit" class="retry-btn">
        <i class="fas fa-redo"></i> 重试
      </button>
    </div>
  </div>
</template>

<script setup>
import Turnstile from '@components/common/Turnstile/index.vue'
import ImageCaptcha from '@components/common/ImageCaptcha/index.vue'
import { useCaptchaWidget } from '@composables/useCaptchaWidget'
import '@/assets/styles/components/captcha-widget.css'

const props = defineProps({
  // 是否显示降级提示
  showFallbackHint: {
    type: Boolean,
    default: true
  },
  // Turnstile 加载超时时间（优化：从8秒减少到5秒）
  turnstileTimeout: {
    type: Number,
    default: 5000
  }
})

const emit = defineEmits(['verified', 'error', 'change', 'enter'])

const {
  captchaType,
  turnstileSiteKey,
  imageCaptchaCode,
  isLoading,
  isUsingTurnstile,
  isUsingImageCaptcha,
  isVerified,
  captchaParams,
  canUseImageCaptcha,
  turnstileRef,
  imageCaptchaRef,
  retryInit,
  onTurnstileVerified,
  onTurnstileError,
  onTurnstileExpired,
  resetCaptcha,
  fullResetCaptcha,
  refreshImageCaptcha,
  validate
} = useCaptchaWidget(props, emit)

// 暴露方法给父组件
defineExpose({
  // 获取验证参数
  getCaptchaParams: () => captchaParams.value,
  // 是否已验证
  isVerified: () => isVerified.value,
  isLoading: () => isLoading.value,
  // 验证
  validate,
  // 重置（保留失败状态）
  reset: resetCaptcha,
  // 完全重置（清除失败状态，尝试恢复 Turnstile）
  fullReset: fullResetCaptcha,
  // 刷新图形验证码
  refreshImageCaptcha,
  // 当前验证类型
  getCaptchaType: () => captchaType.value,
  // 是否可以使用图形验证码
  canUseImageCaptcha: () => canUseImageCaptcha.value
})
</script>
