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
import { ref, computed, watch, onMounted } from 'vue'
import { ElNotification } from 'element-plus'
import Turnstile from './Turnstile.vue'
import ImageCaptcha from './ImageCaptcha.vue'
import { useCaptcha, CAPTCHA_TYPE } from '@/composables/useCaptcha'

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

// 使用 useCaptcha composable
const {
  captchaType,
  turnstileEnabled,
  turnstileSiteKey,
  turnstileToken,
  imageCaptchaCode,
  isLoading,
  isTurnstileVerified,
  turnstileLoadFailed,
  turnstileVerifyFailed,
  canUseImageCaptcha,
  isUsingTurnstile,
  isUsingImageCaptcha,
  isVerified,
  captchaParams,
  error,  // 添加 error 状态
  initialize,
  onTurnstileVerified: handleTurnstileVerified,
  onTurnstileError: handleTurnstileError,
  onTurnstileExpired: handleTurnstileExpired,
  reset,
  fullReset,
  validate
} = useCaptcha({
  turnstileTimeout: props.turnstileTimeout
})

// 重试初始化
const retryInit = () => {
  initialize()
}

const turnstileRef = ref(null)
const imageCaptchaRef = ref(null)

// 包装 Turnstile 回调以触发事件
const onTurnstileVerified = (token) => {
  handleTurnstileVerified(token)
  emit('verified', { type: CAPTCHA_TYPE.TURNSTILE, token })
  emit('change', captchaParams.value)
}

const onTurnstileError = (err) => {
  handleTurnstileError(err)
  emit('error', err)
  emit('change', captchaParams.value)
}

const onTurnstileExpired = () => {
  handleTurnstileExpired()
  emit('change', captchaParams.value)
}

// 监听图形验证码输入
watch(imageCaptchaCode, () => {
  emit('change', captchaParams.value)
})

// 监听验证码类型变化（Turnstile 加载失败降级时触发）
watch(captchaType, (newType, oldType) => {
  if (newType !== oldType) {
    console.log('[CaptchaWidget] captchaType changed:', oldType, '->', newType)
    emit('change', captchaParams.value)
  }
})

// 监听加载状态变化，初始化完成后触发一次 change
watch(isLoading, (loading, wasLoading) => {
  if (wasLoading && !loading) {
    // 加载完成，通知父组件当前状态
    emit('change', captchaParams.value)
  }
})

// 监听错误状态，发出 error 事件
watch(error, (err) => {
  if (err) {
    console.error('[CaptchaWidget] Error:', err)
    emit('error', err)
  }
})

// 暴露方法给父组件
defineExpose({
  // 获取验证参数
  getCaptchaParams: () => captchaParams.value,
  // 是否已验证
  isVerified: () => isVerified.value,
  // 验证
  validate,
  // 重置（保留失败状态）
  reset: () => {
    reset()
    if (turnstileRef.value && turnstileRef.value.reset) {
      turnstileRef.value.reset()
    }
    if (imageCaptchaRef.value) {
      imageCaptchaRef.value.reset()
    }
  },
  // 完全重置（清除失败状态，尝试恢复 Turnstile）
  fullReset: () => {
    fullReset()
    if (turnstileRef.value && turnstileRef.value.reset) {
      turnstileRef.value.reset()
    }
  },
  // 刷新图形验证码
  refreshImageCaptcha: () => {
    if (imageCaptchaRef.value) {
      imageCaptchaRef.value.refresh()
    }
  },
  // 当前验证类型
  getCaptchaType: () => captchaType.value,
  // 是否可以使用图形验证码
  canUseImageCaptcha: () => canUseImageCaptcha.value
})
</script>

<style scoped>
.captcha-widget {
  width: 100%;
  min-height: 65px;
}

.captcha-loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 20px;
  color: #606266;
  font-size: 14px;
  background: linear-gradient(135deg, #f5f7fa 0%, #e8ebf0 100%);
  border-radius: 12px;
  border: 1px dashed #dcdfe6;
}

.loading-spinner {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: pulse-rotate 1.5s ease-in-out infinite;
}

.loading-spinner i {
  font-size: 24px;
  color: var(--el-color-primary, #409eff);
}

@keyframes pulse-rotate {
  0% {
    transform: scale(1) rotate(0deg);
    opacity: 1;
  }
  50% {
    transform: scale(1.1) rotate(180deg);
    opacity: 0.7;
  }
  100% {
    transform: scale(1) rotate(360deg);
    opacity: 1;
  }
}

.captcha-error-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 20px;
  background: linear-gradient(135deg, #fef0f0 0%, #fde2e2 100%);
  border-radius: 12px;
  border: 1px solid #fbc4c4;
  color: #f56c6c;
  font-size: 14px;
}

.captcha-error-state i {
  font-size: 20px;
}

.retry-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: linear-gradient(135deg, #409eff 0%, #66b1ff 100%);
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.retry-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.4);
}

.retry-btn i {
  font-size: 12px;
  color: #fff;
}

.captcha-fallback-hint {
  margin-bottom: 12px;
  padding: 10px 14px;
  background: linear-gradient(135deg, #fdf6ec 0%, #fef9f0 100%);
  border: 1px solid #faecd8;
  border-radius: 8px;
  font-size: 13px;
  color: #e6a23c;
  display: flex;
  align-items: center;
  gap: 8px;
}

.captcha-fallback-hint i {
  font-size: 16px;
  flex-shrink: 0;
}

/* 暗色模式 */
@media (prefers-color-scheme: dark) {
  .captcha-loading-state {
    background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
    border-color: #475569;
    color: #a3a6ad;
  }

  .captcha-error-state {
    background: linear-gradient(135deg, #3f1d1d 0%, #4a2424 100%);
    border-color: #7f1d1d;
  }

  .captcha-fallback-hint {
    background: linear-gradient(135deg, #2b2614 0%, #332d1f 100%);
    border-color: #4d4d4d;
    color: #e6a23c;
  }
}
</style>
