<template>
  <el-dialog
    v-model="dialogVisible"
    title=""
    width="450px"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    @close="handleClose"
    class="vault-verify-dialog"
  >
    <div class="vault-verify-content" :class="{ 'shake': isShaking }">
      <!-- 锁定图标 -->
      <div class="lock-icon" :class="{ 'locked': isLocked }">
        <i :class="isLocked ? 'fas fa-lock' : 'fas fa-shield-halved'"></i>
      </div>

      <!-- 标题 -->
      <h3 class="verify-title">安全验证</h3>

      <!-- 锁定状态提示 -->
      <div v-if="isLocked" class="locked-notice">
        <i class="fas fa-clock"></i>
        <div class="locked-text">
          <span>错误次数过多，请等待 <strong>{{ formatLockTime(lockRemaining) }}</strong> 后重试</span>
          <span class="locked-hint">或通过 <a href="/forgot-password/" class="reset-link">重置密码</a> 解除锁定</span>
        </div>
      </div>

      <!-- 正常验证流程 -->
      <template v-else>
        <!-- 验证方式提示 -->
        <p class="verify-description">
          {{ useBackup ? '请输入 8 位备用验证码' : '请输入 6 位动态密码' }}
        </p>

        <!-- 邮箱验证码发送按钮 -->
        <div v-if="twoFaMethod === 'email' && !useBackup" class="email-code-section">
          <el-button
            type="primary"
            :loading="sendingCode"
            :disabled="countdown > 0"
            @click="handleSendEmailCode"
            class="send-code-btn"
          >
            <i v-if="!sendingCode" :class="countdown > 0 ? 'fas fa-clock' : 'fas fa-paper-plane'"></i>
            {{ countdown > 0 ? `${countdown}s` : '发送验证码' }}
          </el-button>
        </div>

        <!-- 验证码输入 -->
        <div class="code-input-wrapper" :class="{ 'error': hasError }">
          <input
            ref="codeInputRef"
            v-model="code"
            type="tel"
            inputmode="numeric"
            pattern="\d*"
            autocomplete="one-time-code"
            :placeholder="useBackup ? '输入备用码' : '● ● ● ● ● ●'"
            :maxlength="useBackup ? 8 : 6"
            :disabled="isVerifying"
            @input="handleCodeInput"
            @keyup.enter="handleVerify"
            class="code-input"
          />
          <div v-if="isVerifying" class="verifying-indicator">
            <i class="fas fa-spinner fa-spin"></i>
          </div>
        </div>

        <!-- 错误提示 -->
        <transition name="fade">
          <div v-if="errorMessage" class="error-message">
            <i class="fas fa-exclamation-circle"></i>
            <span>{{ errorMessage }}</span>
            <span v-if="failCount > 0" class="fail-count">（已失败 {{ failCount }} 次）</span>
          </div>
        </transition>

        <!-- CAPTCHA 验证区域（第3次失败后显示） -->
        <transition name="fade">
          <div v-if="requireCaptcha" class="captcha-section">
            <div class="captcha-header">
              <i class="fas fa-robot"></i>
              <span>请完成人机验证后继续</span>
            </div>
            <CaptchaWidget
              ref="captchaWidgetRef"
              :turnstile-timeout="8000"
              @change="onCaptchaChange"
              @error="onCaptchaError"
            />
            <!-- 加载失败时的备用提示 -->
            <div v-if="captchaLoadError" class="captcha-fallback-notice">
              <i class="fas fa-exclamation-triangle"></i>
              <span>验证码加载失败，请刷新页面重试</span>
              <el-button size="small" @click="retryCaptcha" class="retry-captcha-btn">
                <i class="fas fa-redo"></i> 重试
              </el-button>
            </div>
          </div>
        </transition>

        <!-- 使用备用码切换 -->
        <div class="backup-toggle">
          <el-checkbox v-model="useBackup" @change="handleBackupToggle">
            使用备用验证码
          </el-checkbox>
        </div>
      </template>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleClose" class="cancel-btn">
          <i class="fas fa-times"></i>
          取消
        </el-button>
        <el-button
          v-if="!isLocked"
          type="primary"
          :loading="isVerifying"
          :disabled="!canVerify"
          @click="handleVerify"
          class="verify-btn"
        >
          <i v-if="!isVerifying" class="fas fa-check"></i>
          验证
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch, computed, nextTick, onUnmounted } from 'vue'
import { ElMessage, ElDialog, ElButton, ElCheckbox } from 'element-plus'
import CaptchaWidget from './CaptchaWidget.vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  twoFaMethod: {
    type: String,
    default: 'totp'
  }
})

const emit = defineEmits(['update:modelValue', 'verified', 'cancel'])

const dialogVisible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

// 状态
const code = ref('')
const useBackup = ref(false)
const isVerifying = ref(false)
const errorMessage = ref('')
const sendingCode = ref(false)
const countdown = ref(0)
const hasError = ref(false)
const isShaking = ref(false)
const failCount = ref(0)
const requireCaptcha = ref(false)
const captchaLoadError = ref(false)
const codeInputRef = ref(null)
const captchaWidgetRef = ref(null)

// CAPTCHA 参数
const captchaParams = ref({
  captcha_type: 'turnstile',
  turnstile_token: '',
  image_captcha: ''
})

// 锁定状态
const isLocked = ref(false)
const lockRemaining = ref(0)
let lockTimer = null
let countdownTimer = null

// 计算属性：是否可以验证
const canVerify = computed(() => {
  if (isLocked.value || isVerifying.value) return false

  // 检查验证码长度
  const codeValid = useBackup.value
    ? code.value.length === 8
    : code.value.length === 6

  if (!codeValid) return false

  // 如果需要CAPTCHA，检查是否已验证
  if (requireCaptcha.value) {
    const params = captchaParams.value
    if (params.captcha_type === 'turnstile') {
      return !!params.turnstile_token
    }
    return params.image_captcha && params.image_captcha.length >= 4
  }

  return true
})

// 格式化锁定时间
const formatLockTime = (seconds) => {
  if (seconds >= 3600) {
    const hours = Math.floor(seconds / 3600)
    const mins = Math.floor((seconds % 3600) / 60)
    return `${hours}小时${mins}分钟`
  } else if (seconds >= 60) {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}分${secs}秒`
  }
  return `${seconds}秒`
}

// CAPTCHA 变化回调
const onCaptchaChange = (params) => {
  captchaParams.value = params
  captchaLoadError.value = false
}

// CAPTCHA 加载错误回调
const onCaptchaError = (err) => {
  console.error('CAPTCHA加载错误:', err)
  captchaLoadError.value = true
}

// 重试加载CAPTCHA
const retryCaptcha = () => {
  captchaLoadError.value = false
  if (captchaWidgetRef.value && captchaWidgetRef.value.fullReset) {
    captchaWidgetRef.value.fullReset()
  }
}

// 处理验证码输入
const handleCodeInput = (e) => {
  // 只允许数字
  code.value = code.value.replace(/\D/g, '')
  hasError.value = false
  errorMessage.value = ''

  // 自动提交：当输入满6位（普通验证码）或8位（备用码）时自动验证
  // 但如果需要CAPTCHA且未验证，则不自动提交
  const targetLength = useBackup.value ? 8 : 6
  if (code.value.length === targetLength && !isVerifying.value && !isLocked.value) {
    if (!requireCaptcha.value || canVerify.value) {
      handleVerify()
    }
  }
}

// 切换备用码模式
const handleBackupToggle = () => {
  code.value = ''
  hasError.value = false
  errorMessage.value = ''
  nextTick(() => {
    codeInputRef.value?.focus()
  })
}

// 触发抖动动画
const triggerShake = () => {
  isShaking.value = true
  hasError.value = true
  setTimeout(() => {
    isShaking.value = false
  }, 500)
}

// 发送邮箱验证码
const handleSendEmailCode = async () => {
  if (sendingCode.value || countdown.value > 0) return

  sendingCode.value = true
  errorMessage.value = ''

  try {
    const response = await fetch('/api/vault/send-email-code/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
      }
    })
    const data = await response.json()

    if (data.status === 'success') {
      ElMessage.success('验证码已发送')
      startCountdown()
      nextTick(() => {
        codeInputRef.value?.focus()
      })
    } else {
      errorMessage.value = data.message || '发送失败'
    }
  } catch (e) {
    errorMessage.value = '发送失败，请稍后重试'
  } finally {
    sendingCode.value = false
  }
}

// 开始倒计时
const startCountdown = () => {
  countdown.value = 60
  countdownTimer = setInterval(() => {
    countdown.value--
    if (countdown.value <= 0) {
      clearInterval(countdownTimer)
    }
  }, 1000)
}

// 开始锁定倒计时
const startLockCountdown = (seconds) => {
  isLocked.value = true
  lockRemaining.value = seconds

  if (lockTimer) clearInterval(lockTimer)
  lockTimer = setInterval(() => {
    lockRemaining.value--
    if (lockRemaining.value <= 0) {
      clearInterval(lockTimer)
      isLocked.value = false
      failCount.value = 0
      errorMessage.value = ''
      requireCaptcha.value = false
    }
  }, 1000)
}

// 验证
const handleVerify = async () => {
  if (!canVerify.value || isVerifying.value) return

  isVerifying.value = true
  errorMessage.value = ''
  hasError.value = false

  try {
    // 构建请求体
    const requestBody = {
      code: code.value,
      use_backup: useBackup.value
    }

    // 如果需要CAPTCHA，添加验证参数
    if (requireCaptcha.value) {
      Object.assign(requestBody, captchaParams.value)
    }

    const response = await fetch('/api/vault/verify/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
      },
      body: JSON.stringify(requestBody)
    })
    const data = await response.json()

    if (data.status === 'success') {
      ElMessage.success('验证成功')
      emit('verified', {
        expireTime: data.expire_time,
        remainingSeconds: data.remaining_seconds
      })
      dialogVisible.value = false
    } else if (data.status === 'locked') {
      // 账户被锁定
      failCount.value = data.fail_count || 0
      startLockCountdown(data.lock_seconds || 60)
      triggerShake()
      errorMessage.value = data.message || '错误次数过多'
    } else if (data.status === 'require_captcha') {
      // 需要人机验证
      requireCaptcha.value = true
      failCount.value = data.fail_count || 0
      triggerShake()
      errorMessage.value = data.message || '请完成人机验证'
      code.value = ''
      // 重置CAPTCHA
      if (captchaWidgetRef.value) {
        captchaWidgetRef.value.reset()
      }
    } else {
      // 普通验证失败
      failCount.value = data.fail_count || failCount.value + 1
      triggerShake()
      errorMessage.value = data.message || '验证码错误'
      code.value = ''

      // 检查是否需要显示CAPTCHA
      if (data.require_captcha) {
        requireCaptcha.value = true
      }

      // 重置CAPTCHA
      if (requireCaptcha.value && captchaWidgetRef.value) {
        captchaWidgetRef.value.reset()
      }

      nextTick(() => {
        codeInputRef.value?.focus()
      })
    }
  } catch (e) {
    triggerShake()
    errorMessage.value = '验证失败，请稍后重试'
    code.value = ''
  } finally {
    isVerifying.value = false
  }
}

// 关闭对话框
const handleClose = () => {
  code.value = ''
  useBackup.value = false
  errorMessage.value = ''
  hasError.value = false
  isShaking.value = false
  requireCaptcha.value = false
  captchaLoadError.value = false
  captchaParams.value = {
    captcha_type: 'turnstile',
    turnstile_token: '',
    image_captcha: ''
  }
  dialogVisible.value = false
  emit('cancel')
}

// 对话框打开时聚焦输入框
watch(dialogVisible, (val) => {
  if (val) {
    // 检查锁定状态
    checkLockStatus()
    nextTick(() => {
      codeInputRef.value?.focus()
    })
  } else {
    if (countdownTimer) {
      clearInterval(countdownTimer)
      countdown.value = 0
    }
  }
})

// 检查锁定状态
const checkLockStatus = async () => {
  try {
    const response = await fetch('/api/vault/lock-status/')
    const data = await response.json()
    if (data.is_locked) {
      startLockCountdown(data.remaining_seconds)
      failCount.value = data.fail_count || 0
    } else {
      isLocked.value = false
      failCount.value = data.fail_count || 0
      // 如果失败次数 >= 3，显示CAPTCHA
      if (failCount.value >= 3) {
        requireCaptcha.value = true
      }
    }
  } catch (e) {
    console.error('检查锁定状态失败:', e)
  }
}

// 清理
onUnmounted(() => {
  if (countdownTimer) clearInterval(countdownTimer)
  if (lockTimer) clearInterval(lockTimer)
})
</script>

<style scoped>
/* 对话框背景模糊 */
:deep(.el-overlay) {
  backdrop-filter: blur(6px);
  background-color: rgba(0, 0, 0, 0.5);
}

:deep(.vault-verify-dialog) {
  border-radius: 20px;
  overflow: hidden;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.4);
}

:deep(.vault-verify-dialog .el-dialog__header) {
  display: none;
}

:deep(.vault-verify-dialog .el-dialog__body) {
  padding: 0;
}

:deep(.vault-verify-dialog .el-dialog__footer) {
  padding: 20px 32px 28px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border-top: 1px solid rgba(0, 0, 0, 0.05);
}

.vault-verify-content {
  text-align: center;
  padding: 40px 32px 24px;
  background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%);
}

/* 抖动动画 */
.vault-verify-content.shake {
  animation: shake 0.5s cubic-bezier(0.36, 0.07, 0.19, 0.97);
}

@keyframes shake {
  0%, 100% { transform: translateX(0); }
  10%, 30%, 50%, 70%, 90% { transform: translateX(-8px); }
  20%, 40%, 60%, 80% { transform: translateX(8px); }
}

/* 锁定图标 */
.lock-icon {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 24px;
  box-shadow: 0 10px 30px rgba(102, 126, 234, 0.4);
  transition: all 0.3s ease;
}

.lock-icon.locked {
  background: linear-gradient(135deg, #f56c6c 0%, #e74c3c 100%);
  box-shadow: 0 10px 30px rgba(245, 108, 108, 0.4);
}

.lock-icon i {
  font-size: 32px;
  color: white;
}

/* 标题 */
.verify-title {
  font-size: 22px;
  font-weight: 700;
  color: #303133;
  margin: 0 0 8px;
}

/* 描述 */
.verify-description {
  font-size: 14px;
  color: #909399;
  margin-bottom: 24px;
}

/* 锁定提示 */
.locked-notice {
  background: linear-gradient(135deg, #fef0f0 0%, #fde2e2 100%);
  border: 1px solid rgba(245, 108, 108, 0.3);
  border-radius: 12px;
  padding: 20px;
  margin: 20px 0;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  color: #f56c6c;
  font-size: 14px;
  text-align: left;
}

.locked-notice > i {
  font-size: 20px;
  animation: pulse 1.5s ease-in-out infinite;
  flex-shrink: 0;
  margin-top: 2px;
}

.locked-text {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.locked-notice strong {
  color: #e74c3c;
  font-size: 16px;
}

.locked-hint {
  font-size: 13px;
  color: #909399;
}

.reset-link {
  color: #409eff;
  text-decoration: none;
  font-weight: 600;
}

.reset-link:hover {
  text-decoration: underline;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* 发送验证码按钮 */
.email-code-section {
  margin-bottom: 20px;
}

.send-code-btn {
  border-radius: 10px;
  padding: 12px 24px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

/* 验证码输入框 */
.code-input-wrapper {
  position: relative;
  margin-bottom: 16px;
}

.code-input {
  width: 100%;
  height: 56px;
  border: 2px solid #e4e7ed;
  border-radius: 14px;
  font-size: 24px;
  font-weight: 600;
  text-align: center;
  letter-spacing: 8px;
  color: #303133;
  background: #fff;
  outline: none;
  transition: all 0.3s ease;
  padding: 0 20px;
  box-sizing: border-box;
}

.code-input::placeholder {
  color: #c0c4cc;
  letter-spacing: 4px;
  font-size: 18px;
}

.code-input:focus {
  border-color: #667eea;
  box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.15);
}

.code-input-wrapper.error .code-input {
  border-color: #f56c6c;
  box-shadow: 0 0 0 4px rgba(245, 108, 108, 0.15);
}

.code-input:disabled {
  background: #f5f7fa;
  cursor: not-allowed;
}

/* 验证中指示器 */
.verifying-indicator {
  position: absolute;
  right: 16px;
  top: 50%;
  transform: translateY(-50%);
  color: #667eea;
  font-size: 20px;
}

/* 错误消息 */
.error-message {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px 16px;
  background: linear-gradient(135deg, #fef0f0 0%, #fde2e2 100%);
  border: 1px solid rgba(245, 108, 108, 0.3);
  border-radius: 10px;
  color: #f56c6c;
  font-size: 13px;
  margin-bottom: 16px;
}

.error-message i {
  font-size: 16px;
}

.fail-count {
  color: #e74c3c;
  font-weight: 600;
}

/* CAPTCHA 区域 */
.captcha-section {
  margin-bottom: 16px;
  padding: 16px;
  background: linear-gradient(135deg, #f5f7fa 0%, #e8ebf0 100%);
  border-radius: 12px;
  border: 1px dashed #dcdfe6;
}

.captcha-header {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-bottom: 12px;
  color: #606266;
  font-size: 13px;
}

.captcha-header i {
  color: #e6a23c;
  font-size: 16px;
}

/* CAPTCHA 加载失败提示 */
.captcha-fallback-notice {
  margin-top: 12px;
  padding: 12px 16px;
  background: linear-gradient(135deg, #fef0f0 0%, #fde2e2 100%);
  border: 1px solid rgba(245, 108, 108, 0.3);
  border-radius: 10px;
  display: flex;
  align-items: center;
  gap: 10px;
  color: #f56c6c;
  font-size: 13px;
}

.captcha-fallback-notice i {
  font-size: 16px;
  flex-shrink: 0;
}

.retry-captcha-btn {
  margin-left: auto;
  background: linear-gradient(135deg, #409eff 0%, #66b1ff 100%);
  border: none;
  color: #fff;
  border-radius: 6px;
}

.retry-captcha-btn:hover {
  opacity: 0.9;
}

/* 备用码切换 */
.backup-toggle {
  margin-top: 8px;
}

.backup-toggle :deep(.el-checkbox__label) {
  color: #909399;
  font-size: 13px;
}

/* 底部按钮 */
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.cancel-btn,
.verify-btn {
  border-radius: 10px;
  padding: 12px 28px;
  font-weight: 600;
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.3s ease;
}

.cancel-btn {
  background: #f5f7fa;
  border: 1px solid #e4e7ed;
  color: #606266;
}

.cancel-btn:hover {
  background: #e4e7ed;
  color: #303133;
}

.verify-btn {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  color: #fff;
  box-shadow: 0 4px 15px rgba(102, 126, 234, 0.35);
}

.verify-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.45);
}

.verify-btn:disabled {
  background: #e4e7ed;
  color: #a8abb2;
  box-shadow: none;
  cursor: not-allowed;
}

/* 动画 */
.fade-enter-active,
.fade-leave-active {
  transition: all 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

/* 响应式 */
@media (max-width: 480px) {
  .vault-verify-content {
    padding: 32px 20px 20px;
  }

  .code-input {
    font-size: 20px;
    letter-spacing: 6px;
  }

  .dialog-footer {
    flex-direction: column-reverse;
  }

  .cancel-btn,
  .verify-btn {
    width: 100%;
    justify-content: center;
  }
}

/* 暗色模式 */
@media (prefers-color-scheme: dark) {
  .vault-verify-content {
    background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%);
  }

  .verify-title {
    color: #f1f5f9;
  }

  .verify-description {
    color: #94a3b8;
  }

  .code-input {
    background: #1e293b;
    border-color: #475569;
    color: #f1f5f9;
  }

  .code-input:focus {
    border-color: #667eea;
  }

  :deep(.vault-verify-dialog .el-dialog__footer) {
    background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
  }

  .cancel-btn {
    background: #334155;
    border-color: #475569;
    color: #e2e8f0;
  }

  .captcha-section {
    background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
    border-color: #475569;
  }

  .captcha-header {
    color: #94a3b8;
  }
}
</style>
