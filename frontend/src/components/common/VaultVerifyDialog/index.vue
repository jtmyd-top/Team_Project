<template>
  <el-dialog
    v-model="dialogVisible"
    title=""
    width="450px"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    append-to-body
    modal-class="vault-verify-overlay"
    align-center
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

        <!-- 解锁时长选择 -->
        <div class="duration-selector">
          <label class="duration-label">保密柜保持解锁时长</label>
          <el-select
            v-model="durationMinutes"
            class="duration-select"
            popper-class="vault-duration-select-popper"
            placeholder="选择解锁时长"
            :disabled="isVerifying"
          >
            <el-option
              v-for="option in durationOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
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
import { ref } from 'vue'
import { ElDialog, ElButton, ElCheckbox, ElSelect, ElOption } from 'element-plus'
import CaptchaWidget from '@components/common/CaptchaWidget/index.vue'
import { useVaultVerifyDialog } from '@composables/useVaultVerifyDialog'
import '@/assets/styles/components/vault-verify-dialog.css'

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

const captchaWidgetRef = ref(null)

const {
  code,
  useBackup,
  isVerifying,
  errorMessage,
  sendingCode,
  countdown,
  hasError,
  isShaking,
  failCount,
  requireCaptcha,
  captchaLoadError,
  codeInputRef,
  isLocked,
  lockRemaining,
  dialogVisible,
  canVerify,
  durationMinutes,
  durationOptions,
  formatLockTime,
  onCaptchaChange,
  onCaptchaError,
  retryCaptcha,
  handleCodeInput,
  handleBackupToggle,
  handleSendEmailCode,
  handleVerify,
  handleClose
} = useVaultVerifyDialog(props, emit, captchaWidgetRef)
</script>
