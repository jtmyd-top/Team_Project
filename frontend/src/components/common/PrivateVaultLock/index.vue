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
import { usePrivateVaultLock } from '@/composables/usePrivateVaultLock'
import '@/assets/styles/components/private-vault-lock.css'

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

const {
  password,
  showPassword,
  passwordInput,
  formattedTime,
  handleUnlock,
  handleLockNow,
  handleCancel,
  handleForgotPassword
} = usePrivateVaultLock(props, emit)
</script>
