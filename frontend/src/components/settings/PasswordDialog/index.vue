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
import { usePasswordDialog } from '@composables/usePasswordDialog.js';
import '@/assets/styles/components/password-dialog.css';

// Props
const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  }
});

// Emits
const emit = defineEmits(['update:modelValue', 'submit']);

const {
  visible,
  form,
  passwordStrength,
  canSubmit,
  checkPasswordStrength,
  resetForm,
  handleSubmit
} = usePasswordDialog(props, emit);
</script>
