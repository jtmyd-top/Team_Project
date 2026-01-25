<template>
  <el-dialog
    v-model="visible"
    title="修改密码"
    width="540px"
    :close-on-click-modal="false"
    class="password-change-dialog"
    @close="resetForm">

    <template #header>
      <div class="dialog-header">
        <i class="fas fa-key header-icon"></i>
        <span class="header-title">修改密码</span>
      </div>
    </template>

    <el-form label-position="top" class="password-form">
      <el-form-item label="当前密码" class="form-item-enhanced">
        <el-input
          v-model="form.current"
          type="password"
          show-password
          placeholder="请输入当前密码以验证身份"
          size="large"
          clearable
          class="enhanced-input">
          <template #prefix>
            <i class="fas fa-lock input-icon"></i>
          </template>
        </el-input>
      </el-form-item>

      <el-form-item label="新密码" class="form-item-enhanced">
        <div class="input-wrapper">
          <el-input
            v-model="form.new"
            type="password"
            show-password
            placeholder="请输入新密码（至少8位字符）"
            size="large"
            clearable
            class="enhanced-input"
            @input="checkPasswordStrength">
            <template #prefix>
              <i class="fas fa-shield-alt input-icon"></i>
            </template>
          </el-input>
          <transition name="slide-fade">
            <div v-if="form.new && passwordStrength.level" class="password-strength">
              <div class="strength-bar">
                <div
                  class="strength-fill"
                  :class="passwordStrength.level"
                  :style="{ width: passwordStrength.percent + '%' }">
                </div>
              </div>
              <span class="strength-text" :class="passwordStrength.level">
                {{ passwordStrength.text }}
              </span>
            </div>
          </transition>
        </div>
      </el-form-item>

      <el-form-item label="确认新密码" class="form-item-enhanced">
        <div class="input-wrapper">
          <el-input
            v-model="form.confirm"
            type="password"
            show-password
            placeholder="请再次输入新密码"
            size="large"
            clearable
            class="enhanced-input">
            <template #prefix>
              <i class="fas fa-check-double input-icon"></i>
            </template>
            <template #suffix>
              <transition name="fade">
                <i v-if="form.confirm && form.new === form.confirm"
                   class="fas fa-check-circle status-icon status-success"></i>
                <i v-else-if="form.confirm && form.new !== form.confirm"
                   class="fas fa-times-circle status-icon status-error"></i>
              </transition>
            </template>
          </el-input>
          <transition name="slide-fade">
            <div v-if="form.confirm && form.new !== form.confirm" class="status-message status-message-error">
              <i class="fas fa-exclamation-circle"></i>
              两次输入的密码不一致
            </div>
          </transition>
        </div>
      </el-form-item>
    </el-form>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="visible = false" size="large" class="cancel-btn">
          <i class="fas fa-times"></i>
          <span>取消</span>
        </el-button>
        <el-button
          type="primary"
          :disabled="!canSubmit"
          @click="handleSubmit"
          size="large"
          class="submit-btn">
          <i class="fas fa-check"></i>
          <span>确认修改</span>
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'

// Props
const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  }
})

// Emits
const emit = defineEmits(['update:modelValue', 'submit'])

// Local state
const visible = ref(props.modelValue)
const form = ref({
  current: '',
  new: '',
  confirm: ''
})

// Password strength
const passwordStrength = ref({
  level: '',
  text: '',
  percent: 0
})

// Check password strength
const checkPasswordStrength = () => {
  const password = form.value.new
  if (!password) {
    passwordStrength.value = { level: '', text: '', percent: 0 }
    return
  }

  let score = 0

  // Length check
  if (password.length >= 8) score += 1
  if (password.length >= 12) score += 1
  if (password.length >= 16) score += 1

  // Character variety
  if (/[a-z]/.test(password)) score += 1
  if (/[A-Z]/.test(password)) score += 1
  if (/[0-9]/.test(password)) score += 1
  if (/[^a-zA-Z0-9]/.test(password)) score += 1

  if (score <= 2) {
    passwordStrength.value = { level: 'weak', text: '弱', percent: 25 }
  } else if (score <= 4) {
    passwordStrength.value = { level: 'medium', text: '中等', percent: 50 }
  } else if (score <= 5) {
    passwordStrength.value = { level: 'strong', text: '强', percent: 75 }
  } else {
    passwordStrength.value = { level: 'very-strong', text: '非常强', percent: 100 }
  }
}

// Can submit
const canSubmit = computed(() => {
  return form.value.current &&
         form.value.new &&
         form.value.new.length >= 8 &&
         form.value.new === form.value.confirm
})

// Watch for prop changes
watch(() => props.modelValue, (newValue) => {
  visible.value = newValue
})

// Watch for visibility changes
watch(visible, (newValue) => {
  emit('update:modelValue', newValue)
})

// Reset form
const resetForm = () => {
  form.value = {
    current: '',
    new: '',
    confirm: ''
  }
  passwordStrength.value = { level: '', text: '', percent: 0 }
}

// Handle submit
const handleSubmit = () => {
  // Validation
  if (!form.value.current) {
    ElMessage.warning('请输入当前密码')
    return
  }
  if (!form.value.new) {
    ElMessage.warning('请输入新密码')
    return
  }
  if (!form.value.confirm) {
    ElMessage.warning('请确认新密码')
    return
  }
  if (form.value.new !== form.value.confirm) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }
  if (form.value.new.length < 8) {
    ElMessage.warning('新密码至少8位')
    return
  }

  // Emit submit event with form data
  emit('submit', {
    current_password: form.value.current,
    new_password: form.value.new,
    confirm_password: form.value.confirm
  })
}
</script>

<style scoped>
/* ==================== 对话框样式 ==================== */
:deep(.password-change-dialog) {
  border-radius: 20px;
  overflow: hidden;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
}

:deep(.password-change-dialog .el-dialog__header) {
  padding: 0;
  margin: 0;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
  background-size: 200% 200%;
  animation: gradientShift 8s ease infinite;
}

@keyframes gradientShift {
  0%, 100% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
}

:deep(.password-change-dialog .el-dialog__body) {
  padding: 0;
  background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%);
}

:deep(.password-change-dialog .el-dialog__footer) {
  padding: 24px 32px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border-top: 1px solid rgba(0, 0, 0, 0.05);
}

:deep(.password-change-dialog .el-dialog__headerbtn) {
  top: 20px;
  right: 20px;
  width: 36px;
  height: 36px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 50%;
  transition: all 0.3s ease;
}

:deep(.password-change-dialog .el-dialog__headerbtn:hover) {
  background: rgba(255, 255, 255, 0.3);
  transform: rotate(90deg);
}

:deep(.password-change-dialog .el-dialog__headerbtn .el-dialog__close) {
  color: #fff;
  font-size: 18px;
}

.dialog-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 32px 40px;
  color: #fff;
  position: relative;
  overflow: hidden;
}

.dialog-header::before {
  content: '';
  position: absolute;
  top: -50%;
  left: -50%;
  width: 200%;
  height: 200%;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.1) 0%, transparent 60%);
  animation: shimmer 3s ease-in-out infinite;
}

@keyframes shimmer {
  0%, 100% { transform: translateX(-50%) translateY(-50%) rotate(0deg); }
  50% { transform: translateX(-30%) translateY(-30%) rotate(180deg); }
}

.header-icon {
  font-size: 32px;
  background: rgba(255, 255, 255, 0.2);
  padding: 16px;
  border-radius: 16px;
  backdrop-filter: blur(10px);
  animation: iconFloat 3s ease-in-out infinite;
  position: relative;
  z-index: 1;
}

@keyframes iconFloat {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-5px); }
}

.header-title {
  font-size: 24px;
  font-weight: 700;
  letter-spacing: 0.5px;
  text-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
  position: relative;
  z-index: 1;
}

/* ==================== 表单样式 ==================== */
.password-form {
  padding: 32px 40px;
}

.form-item-enhanced {
  margin-bottom: 28px;
}

.form-item-enhanced :deep(.el-form-item__label) {
  font-weight: 600;
  color: #303133;
  font-size: 14px;
  margin-bottom: 8px;
}

.input-wrapper {
  position: relative;
}

.enhanced-input :deep(.el-input__wrapper) {
  border-radius: 12px;
  padding: 14px 18px;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
  border: 2px solid transparent;
  background: linear-gradient(#fff, #fff) padding-box,
              linear-gradient(135deg, #e4e7ed, #f5f7fa) border-box;
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.enhanced-input :deep(.el-input__wrapper:hover) {
  background: linear-gradient(#fff, #fff) padding-box,
              linear-gradient(135deg, #c0c4cc, #e4e7ed) border-box;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.08);
  transform: translateY(-2px);
}

.enhanced-input :deep(.el-input__wrapper.is-focus) {
  background: linear-gradient(#fff, #fff) padding-box,
              linear-gradient(135deg, #667eea, #764ba2) border-box;
  box-shadow: 0 8px 25px rgba(102, 126, 234, 0.25);
  transform: translateY(-2px);
}

.input-icon {
  color: #909399;
  font-size: 18px;
  margin-right: 6px;
  transition: all 0.3s ease;
}

.enhanced-input :deep(.el-input__wrapper.is-focus) .input-icon {
  color: #667eea;
  transform: scale(1.1);
}

/* ==================== 密码强度指示器 ==================== */
.password-strength {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.strength-bar {
  flex: 1;
  height: 6px;
  background: #e4e7ed;
  border-radius: 3px;
  overflow: hidden;
}

.strength-fill {
  height: 100%;
  border-radius: 3px;
  transition: all 0.4s ease;
}

.strength-fill.weak {
  background: linear-gradient(90deg, #f56c6c, #e6a23c);
}

.strength-fill.medium {
  background: linear-gradient(90deg, #e6a23c, #f7ba2a);
}

.strength-fill.strong {
  background: linear-gradient(90deg, #67c23a, #85ce61);
}

.strength-fill.very-strong {
  background: linear-gradient(90deg, #409eff, #67c23a);
}

.strength-text {
  font-size: 12px;
  font-weight: 600;
  min-width: 60px;
}

.strength-text.weak {
  color: #f56c6c;
}

.strength-text.medium {
  color: #e6a23c;
}

.strength-text.strong {
  color: #67c23a;
}

.strength-text.very-strong {
  color: #409eff;
}

/* ==================== 状态图标和消息 ==================== */
.status-icon {
  font-size: 20px;
  animation: popIn 0.3s cubic-bezier(0.68, -0.55, 0.265, 1.55);
}

@keyframes popIn {
  0% { transform: scale(0); opacity: 0; }
  100% { transform: scale(1); opacity: 1; }
}

.status-success {
  color: #10b981;
}

.status-error {
  color: #ef4444;
}

.status-message {
  margin-top: 10px;
  padding: 12px 16px;
  border-radius: 10px;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 10px;
  animation: slideUp 0.3s ease;
  backdrop-filter: blur(10px);
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.status-message-error {
  background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
  color: #dc2626;
  border: 1px solid rgba(239, 68, 68, 0.3);
}

/* ==================== 对话框底部按钮 ==================== */
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 16px;
}

.cancel-btn,
.submit-btn {
  border-radius: 12px;
  padding: 0 36px;
  height: 48px;
  font-weight: 600;
  font-size: 15px;
  display: flex;
  align-items: center;
  gap: 10px;
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  min-width: 130px;
  justify-content: center;
  position: relative;
  overflow: hidden;
}

.cancel-btn {
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border: 2px solid #e2e8f0;
  color: #64748b;
}

.cancel-btn:hover {
  background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%);
  border-color: #cbd5e1;
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.1);
  color: #475569;
}

.submit-btn:not(.is-disabled) {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  color: #fff;
  box-shadow: 0 8px 25px rgba(102, 126, 234, 0.35);
}

.submit-btn:not(.is-disabled)::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
  transition: left 0.5s ease;
}

.submit-btn:not(.is-disabled):hover::before {
  left: 100%;
}

.submit-btn:not(.is-disabled):hover {
  transform: translateY(-3px);
  box-shadow: 0 12px 35px rgba(102, 126, 234, 0.45);
}

.submit-btn:not(.is-disabled):active {
  transform: translateY(-1px);
}

.submit-btn.is-disabled {
  background: linear-gradient(135deg, #e2e8f0 0%, #cbd5e1 100%);
  color: #94a3b8;
  cursor: not-allowed;
  box-shadow: none;
}

/* ==================== 动画效果 ==================== */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-fade-enter-active {
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.slide-fade-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 1, 1);
}

.slide-fade-enter-from {
  transform: translateY(-15px);
  opacity: 0;
}

.slide-fade-leave-to {
  transform: translateY(15px);
  opacity: 0;
}

/* ==================== 响应式设计 ==================== */
@media (max-width: 768px) {
  .dialog-header {
    padding: 24px 28px;
  }

  .header-icon {
    font-size: 26px;
    padding: 12px;
  }

  .header-title {
    font-size: 20px;
  }

  .password-form {
    padding: 24px 20px;
  }

  .dialog-footer {
    flex-direction: column-reverse;
    gap: 12px;
  }

  .cancel-btn,
  .submit-btn {
    width: 100%;
    height: 50px;
  }
}

/* ==================== 暗色模式支持 ==================== */
@media (prefers-color-scheme: dark) {
  :deep(.password-change-dialog .el-dialog__body) {
    background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%);
  }

  :deep(.password-change-dialog .el-dialog__footer) {
    background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
    border-top-color: rgba(255, 255, 255, 0.1);
  }

  .form-item-enhanced :deep(.el-form-item__label) {
    color: #e2e8f0;
  }

  .enhanced-input :deep(.el-input__wrapper) {
    background: linear-gradient(#1e293b, #1e293b) padding-box,
                linear-gradient(135deg, #475569, #334155) border-box;
  }

  .enhanced-input :deep(.el-input__wrapper:hover) {
    background: linear-gradient(#1e293b, #1e293b) padding-box,
                linear-gradient(135deg, #64748b, #475569) border-box;
  }

  .enhanced-input :deep(.el-input__wrapper.is-focus) {
    background: linear-gradient(#1e293b, #1e293b) padding-box,
                linear-gradient(135deg, #667eea, #764ba2) border-box;
  }

  .strength-bar {
    background: #475569;
  }

  .cancel-btn {
    background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
    border-color: #475569;
    color: #e2e8f0;
  }

  .cancel-btn:hover {
    background: linear-gradient(135deg, #334155 0%, #475569 100%);
    color: #f8fafc;
  }
}
</style>
