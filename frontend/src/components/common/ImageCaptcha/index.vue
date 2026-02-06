<template>
  <div class="image-captcha-container">
    <!-- 输入框 + 验证码图片在同一行 -->
    <el-input
      v-model="captchaInput"
      placeholder="请输入验证码"
      class="captcha-input"
      size="large"
      maxlength="4"
      @input="handleInput"
      @keyup.enter="$emit('enter')"
    >
      <template #prefix>
        <i class="fas fa-shield-alt captcha-icon"></i>
      </template>
      <!-- 验证码图片作为输入框的附加内容（与输入框分离） -->
      <template #append>
        <div class="captcha-image-box" @click.stop="refreshCaptcha" title="点击刷新验证码">
          <img
            v-if="captchaSrc && !isComputing"
            :src="captchaSrc"
            alt="验证码"
            class="captcha-image"
            :class="{ 'loading': isLoading }"
          />
          <!-- PoW 计算中的进度显示 -->
          <div v-if="isComputing" class="captcha-pow-progress">
            <div class="pow-spinner"></div>
            <span class="pow-text">{{ powProgress }}%</span>
          </div>
          <div v-else-if="isLoading" class="captcha-loading">
            <i class="fas fa-spinner fa-spin"></i>
          </div>
          <div v-if="!captchaSrc && !isLoading && !isComputing" class="captcha-placeholder">
            <i class="fas fa-image"></i>
          </div>
        </div>
      </template>
    </el-input>
    <!-- 错误提示 -->
    <transition name="fade">
      <div v-if="error" class="captcha-error">
        <i class="fas fa-exclamation-circle"></i>
        {{ error }}
      </div>
    </transition>
    <!-- 提示文字 -->
    <div class="captcha-tip">
      {{ isComputing ? '正在验证环境...' : '点击图片刷新验证码' }}
    </div>
  </div>
</template>

<script setup>
import { useImageCaptcha } from '@/composables/useImageCaptcha'
import '@/assets/styles/components/image-captcha.css'

const props = defineProps({
  modelValue: {
    type: String,
    default: ''
  },
  autoLoad: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['update:modelValue', 'loaded', 'error', 'enter'])

const {
  captchaSrc,
  captchaInput,
  isLoading,
  error,
  powProgress,
  isComputing,
  refreshCaptcha,
  handleInput,
  reset
} = useImageCaptcha(props, emit)

// 暴露方法
defineExpose({
  refresh: refreshCaptcha,
  reset
})
</script>
