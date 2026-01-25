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
import { ref, onMounted, watch } from 'vue'
import { useProofOfWork } from '@/composables/useProofOfWork'

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

const captchaSrc = ref('')
const captchaInput = ref(props.modelValue)
const isLoading = ref(false)
const error = ref('')
const powProgress = ref(0)  // PoW 计算进度

// 初始化 PoW composable
const { isComputing, progress, getInitToken: solvePow, cancel: cancelPow } = useProofOfWork()

// 监听 PoW 进度
watch(progress, (val) => {
  powProgress.value = val
})

// 生成带 init_token 的验证码URL
const getCaptchaUrl = (token) => {
  return `/api/captcha/?token=${encodeURIComponent(token)}&t=${Date.now()}`
}

// 获取 init_token（通过 PoW）
const getInitToken = async () => {
  return await solvePow('/api/captcha/init/')
}

// 刷新验证码
const refreshCaptcha = async () => {
  if (isLoading.value) return

  isLoading.value = true
  error.value = ''
  captchaInput.value = ''
  emit('update:modelValue', '')

  try {
    // 第一步：获取 init_token
    const initToken = await getInitToken()

    // 第二步：使用 token 获取验证码图片
    const response = await fetch(getCaptchaUrl(initToken), {
      credentials: 'include'  // 携带 cookie
    })

    if (!response.ok) {
      // 尝试解析错误信息
      const contentType = response.headers.get('content-type')
      if (contentType && contentType.includes('application/json')) {
        const errorData = await response.json()
        throw new Error(errorData.error || '验证码加载失败')
      }
      throw new Error('验证码加载失败')
    }

    const blob = await response.blob()

    // 释放之前的 URL
    if (captchaSrc.value && captchaSrc.value.startsWith('blob:')) {
      URL.revokeObjectURL(captchaSrc.value)
    }

    captchaSrc.value = URL.createObjectURL(blob)
    emit('loaded')
  } catch (err) {
    console.error('Failed to load captcha:', err)
    error.value = err.message || '验证码加载失败，请点击刷新'
    emit('error', err)
  } finally {
    isLoading.value = false
  }
}

// 处理输入
const handleInput = (value) => {
  // 转大写，只允许字母和数字
  const filtered = value.toUpperCase().replace(/[^A-Z0-9]/g, '')
  captchaInput.value = filtered
  emit('update:modelValue', filtered)
}

// 监听 modelValue 变化
watch(() => props.modelValue, (newVal) => {
  if (newVal !== captchaInput.value) {
    captchaInput.value = newVal
  }
})

// 暴露方法
defineExpose({
  refresh: refreshCaptcha,
  reset: () => {
    captchaInput.value = ''
    emit('update:modelValue', '')
    refreshCaptcha()
  }
})

onMounted(() => {
  if (props.autoLoad) {
    refreshCaptcha()
  }
})
</script>

<style scoped>
.image-captcha-container {
  width: 100%;
}

/* 输入框样式 */
.captcha-input {
  width: 100%;
}

.captcha-input :deep(.el-input__wrapper) {
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(102, 126, 234, 0.2);
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  transition: all 0.3s ease;
  padding: 4px 8px 4px 12px;
}

.captcha-input :deep(.el-input__wrapper:hover) {
  border-color: rgba(102, 126, 234, 0.4);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.1);
}

.captcha-input :deep(.el-input__wrapper.is-focus) {
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.captcha-input :deep(.el-input__inner) {
  text-transform: uppercase;
  letter-spacing: 3px;
  font-weight: 600;
  font-size: 15px;
  color: #1f2937;
}

.captcha-input :deep(.el-input__inner::placeholder) {
  letter-spacing: normal;
  font-weight: 400;
  color: #9ca3af;
}

.captcha-icon {
  color: #667eea;
  font-size: 14px;
}

/* append 插槽样式 - 去除默认背景和边框 */
.captcha-input :deep(.el-input-group__append) {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  padding: 0 !important;
  margin-left: 12px;
  display: flex;
  align-items: stretch;
}

/* 验证码图片容器 - 占满整个 append 容器 */
.captcha-image-box {
  width: 100px;
  height: 100%;
  min-height: 40px;
  border-radius: 12px;
  overflow: hidden;
  cursor: pointer;
  position: relative;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border: 1px solid rgba(102, 126, 234, 0.2);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  align-items: center;
  justify-content: center;
}

.captcha-image-box:hover {
  border-color: rgba(102, 126, 234, 0.4);
  opacity: 0.9;
}

.captcha-image-box:active {
  opacity: 0.8;
}

.captcha-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: all 0.3s ease;
}

.captcha-image.loading {
  opacity: 0.4;
  filter: blur(2px);
}

/* 加载状态 */
.captcha-loading {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.9);
}

.captcha-loading i {
  color: #667eea;
  font-size: 14px;
}

/* 占位符 */
.captcha-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  color: #9ca3af;
  font-size: 14px;
}

/* PoW 计算进度显示 */
.captcha-pow-progress {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.pow-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: pow-spin 0.8s linear infinite;
}

.pow-text {
  font-size: 9px;
  font-weight: 600;
  color: white;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
}

@keyframes pow-spin {
  to {
    transform: rotate(360deg);
  }
}

/* 错误提示 */
.captcha-error {
  margin-top: 8px;
  padding: 8px 12px;
  font-size: 13px;
  color: #ef4444;
  background: rgba(239, 68, 68, 0.08);
  border-radius: 8px;
  border-left: 3px solid #ef4444;
  display: flex;
  align-items: center;
  gap: 6px;
}

/* 提示文字 */
.captcha-tip {
  margin-top: 8px;
  font-size: 12px;
  color: rgba(107, 114, 128, 0.7);
  text-align: center;
}

/* 过渡动画 */
.fade-enter-active,
.fade-leave-active {
  transition: all 0.25s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

/* 响应式设计 */
@media (max-width: 400px) {
  .captcha-image-box {
    width: 75px;
    height: 28px;
  }

  .captcha-input :deep(.el-input__inner) {
    letter-spacing: 2px;
    font-size: 14px;
  }
}
</style>
