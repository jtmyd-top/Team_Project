<template>
  <div class="vault-lock-overlay" v-if="!isUnlocked">
    <div class="vault-lock-modal">
      <!-- 锁定图标 -->
      <div class="lock-icon">
        <i class="fas fa-lock"></i>
      </div>

      <!-- 标题 -->
      <h2 class="lock-title">保密柜已锁定</h2>
      <p class="lock-description">请输入密码以访问保密柜内容</p>

      <!-- 密码输入 -->
      <div class="password-input-wrapper">
        <div class="input-group">
          <i class="fas fa-key"></i>
          <input
            ref="passwordInput"
            :type="showPassword ? 'text' : 'password'"
            v-model="password"
            placeholder="输入保密柜密码"
            @keyup.enter="handleUnlock"
            :disabled="isVerifying"
          />
          <button
            type="button"
            class="toggle-password"
            @click="showPassword = !showPassword"
          >
            <i :class="showPassword ? 'fas fa-eye-slash' : 'fas fa-eye'"></i>
          </button>
        </div>
        <p v-if="error" class="error-message">{{ error }}</p>
      </div>

      <!-- 操作按钮 -->
      <div class="lock-actions">
        <button
          class="unlock-btn"
          @click="handleUnlock"
          :disabled="!password || isVerifying"
        >
          <i v-if="isVerifying" class="fas fa-spinner fa-spin"></i>
          <i v-else class="fas fa-unlock"></i>
          <span>{{ isVerifying ? '验证中...' : '解锁' }}</span>
        </button>
        <button class="cancel-btn" @click="handleCancel">
          <span>取消</span>
        </button>
      </div>

      <!-- 忘记密码提示 -->
      <p class="forgot-hint">
        <a href="#" @click.prevent="handleForgotPassword">忘记密码?</a>
      </p>
    </div>
  </div>

  <!-- 已解锁状态显示倒计时 -->
  <div v-else-if="showTimer" class="vault-timer">
    <i class="fas fa-lock-open"></i>
    <span>{{ formattedTime }}</span>
    <button class="lock-now-btn" @click="handleLockNow" title="立即锁定">
      <i class="fas fa-lock"></i>
    </button>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'

const props = defineProps({
  isUnlocked: {
    type: Boolean,
    default: false
  },
  remainingTime: {
    type: Number,
    default: 0
  },
  showTimer: {
    type: Boolean,
    default: true
  },
  isVerifying: {
    type: Boolean,
    default: false
  },
  error: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['unlock', 'lock', 'cancel', 'forgot-password'])

const password = ref('')
const showPassword = ref(false)
const passwordInput = ref(null)

// 格式化剩余时间
const formattedTime = computed(() => {
  const minutes = Math.floor(props.remainingTime / 60000)
  const seconds = Math.floor((props.remainingTime % 60000) / 1000)
  return `${minutes}:${seconds.toString().padStart(2, '0')}`
})

// 解锁
const handleUnlock = () => {
  if (!password.value || props.isVerifying) return
  emit('unlock', password.value)
}

// 立即锁定
const handleLockNow = () => {
  emit('lock')
}

// 取消
const handleCancel = () => {
  password.value = ''
  emit('cancel')
}

// 忘记密码
const handleForgotPassword = () => {
  emit('forgot-password')
}

// 监听解锁状态，自动聚焦密码输入框
watch(() => props.isUnlocked, (newVal) => {
  if (!newVal) {
    password.value = ''
    nextTick(() => {
      passwordInput.value?.focus()
    })
  }
})
</script>

<style scoped>
.vault-lock-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(8px);
}

.vault-lock-modal {
  background: var(--bg-secondary, #16213e);
  border-radius: 16px;
  padding: 40px;
  width: 100%;
  max-width: 400px;
  text-align: center;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
}

.lock-icon {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 24px;
}

.lock-icon i {
  font-size: 32px;
  color: white;
}

.lock-title {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary, #fff);
  margin: 0 0 8px;
}

.lock-description {
  font-size: 14px;
  color: var(--text-secondary, rgba(255, 255, 255, 0.6));
  margin: 0 0 32px;
}

.password-input-wrapper {
  margin-bottom: 24px;
}

.input-group {
  position: relative;
  display: flex;
  align-items: center;
}

.input-group > i {
  position: absolute;
  left: 16px;
  color: var(--text-secondary, rgba(255, 255, 255, 0.4));
  font-size: 14px;
}

.input-group input {
  width: 100%;
  padding: 14px 48px;
  border-radius: 8px;
  border: 1px solid var(--border-color, rgba(255, 255, 255, 0.1));
  background: var(--input-bg, rgba(255, 255, 255, 0.05));
  color: var(--text-primary, #fff);
  font-size: 16px;
  outline: none;
  transition: all 0.2s ease;
}

.input-group input::placeholder {
  color: var(--text-secondary, rgba(255, 255, 255, 0.4));
}

.input-group input:focus {
  border-color: var(--primary-color, #409eff);
  background: var(--input-bg-focus, rgba(255, 255, 255, 0.08));
}

.toggle-password {
  position: absolute;
  right: 12px;
  padding: 8px;
  background: transparent;
  border: none;
  color: var(--text-secondary, rgba(255, 255, 255, 0.4));
  cursor: pointer;
  transition: color 0.2s ease;
}

.toggle-password:hover {
  color: var(--text-primary, #fff);
}

.error-message {
  margin-top: 8px;
  font-size: 13px;
  color: #f56c6c;
  text-align: left;
}

.lock-actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.unlock-btn {
  width: 100%;
  padding: 14px 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  border-radius: 8px;
  color: white;
  font-size: 16px;
  font-weight: 500;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: all 0.2s ease;
}

.unlock-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(102, 126, 234, 0.4);
}

.unlock-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.cancel-btn {
  width: 100%;
  padding: 12px 24px;
  background: transparent;
  border: 1px solid var(--border-color, rgba(255, 255, 255, 0.2));
  border-radius: 8px;
  color: var(--text-secondary, rgba(255, 255, 255, 0.6));
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.cancel-btn:hover {
  background: var(--hover-bg, rgba(255, 255, 255, 0.08));
  color: var(--text-primary, #fff);
}

.forgot-hint {
  margin-top: 24px;
  font-size: 13px;
}

.forgot-hint a {
  color: var(--primary-color, #409eff);
  text-decoration: none;
}

.forgot-hint a:hover {
  text-decoration: underline;
}

/* 倒计时显示 */
.vault-timer {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: var(--hover-bg, rgba(255, 255, 255, 0.08));
  border-radius: 6px;
  font-size: 12px;
  color: var(--text-secondary, rgba(255, 255, 255, 0.6));
}

.vault-timer i {
  color: #67c23a;
}

.lock-now-btn {
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: var(--text-secondary, rgba(255, 255, 255, 0.4));
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.lock-now-btn:hover {
  background: var(--hover-bg, rgba(255, 255, 255, 0.08));
  color: var(--text-primary, #fff);
}
</style>
