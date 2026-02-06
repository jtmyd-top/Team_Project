import { ref, computed, watch, nextTick } from 'vue'

export function usePrivateVaultLock(props, emit) {
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

  return {
    password,
    showPassword,
    passwordInput,
    formattedTime,
    handleUnlock,
    handleLockNow,
    handleCancel,
    handleForgotPassword
  }
}
