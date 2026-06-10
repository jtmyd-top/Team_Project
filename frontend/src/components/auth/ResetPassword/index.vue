<template>
  <div class="auth-page">
    <!-- 浮动光球背景 -->
    <div class="bg-orbs">
      <div class="orb orb-1"></div>
      <div class="orb orb-2"></div>
      <div class="orb orb-3"></div>
    </div>

    <!-- 错误状态 -->
    <div v-if="error || !isValidRequest" class="auth-content">
      <div class="error-state">
        <div class="error-icon">
          <i class="fas fa-exclamation-circle"></i>
        </div>
        <h2 class="error-title">链接已失效</h2>
        <p class="error-message">{{ error || '重置链接无效，请重新获取' }}</p>
        <a href="/forgot-password/" class="primary-link-btn">
          <i class="fas fa-redo-alt"></i>
          <span>重新获取链接</span>
        </a>
      </div>
    </div>

    <!-- 主表单 - 毛玻璃卡片 -->
    <div v-else class="auth-content" :class="{ 'shake': isShaking }">
      <!-- 品牌标识 -->
      <div class="brand-section">
        <div class="brand-icon">
          <i class="fas fa-lock-open"></i>
        </div>
        <h1 class="brand-title">重置密码</h1>
        <p class="brand-subtitle">
          您好，<span class="username-highlight">{{ username }}</span>
        </p>
        <p class="brand-desc">请输入您的新密码</p>
      </div>

      <!-- 表单 -->
      <el-form
        ref="resetFormRef"
        :model="resetForm"
        :rules="resetRules"
        class="auth-form"
        @submit.prevent="submitForm"
      >
        <!-- 新密码 -->
        <div class="form-section">
          <el-form-item prop="password" class="form-item">
            <el-input
              v-model="resetForm.password"
              type="password"
              name="new-password"
              autocomplete="new-password"
              placeholder="请输入新密码（至少8位）"
              size="large"
              show-password
              class="auth-input"
              @input="checkPasswordStrength"
              @keyup.enter="submitForm"
            >
              <template #prefix>
                <i class="fas fa-key input-icon"></i>
              </template>
            </el-input>
          </el-form-item>

          <!-- 密码强度指示器 -->
          <transition name="fade">
            <div v-if="resetForm.password" class="password-strength">
              <div class="strength-bars">
                <div
                  v-for="i in 4"
                  :key="i"
                  class="strength-bar"
                  :class="{ 'active': i <= passwordStrength, [`level-${passwordStrength}`]: i <= passwordStrength }"
                ></div>
              </div>
              <span class="strength-label" :class="`level-${passwordStrength}`">
                {{ getStrengthText() }}
              </span>
            </div>
          </transition>

          <!-- 密码复杂度提示 -->
          <div v-if="shouldShowPasswordError" class="validation-rules custom-validation">
            <div class="validation-rule rule-invalid">
              <span class="error-dot">●</span>
              <span>{{ getPasswordErrorMessage() }}</span>
            </div>
          </div>

          <!-- 确认密码 -->
          <el-form-item prop="confirmPassword" class="form-item">
            <el-input
              v-model="resetForm.confirmPassword"
              type="password"
              name="confirm-password"
              autocomplete="new-password"
              placeholder="请再次输入新密码"
              size="large"
              show-password
              class="auth-input"
              @keyup.enter="submitForm"
            >
              <template #prefix>
                <i class="fas fa-shield-alt input-icon"></i>
              </template>
            </el-input>
          </el-form-item>
        </div>

        <!-- 提交按钮 -->
        <div class="action-section">
          <el-button
            type="primary"
            size="large"
            :loading="isLoading"
            :disabled="isLoading"
            @click="submitForm"
            class="primary-btn"
          >
            <i class="fas fa-check-circle btn-icon"></i>
            {{ isLoading ? '正在重置...' : '确认重置密码' }}
          </el-button>
        </div>

        <!-- 消息提示 -->
        <transition name="fade">
          <div v-if="message.text" class="message-box" :class="`message-${message.type}`">
            <i class="fas" :class="getMessageIcon()"></i>
            <span>{{ message.text }}</span>
          </div>
        </transition>
      </el-form>

      <!-- 成功覆盖层 -->
      <transition name="overlay-fade">
        <div v-if="showSuccess" class="success-overlay">
          <div class="success-content">
            <div class="success-checkmark">
              <svg class="checkmark" viewBox="0 0 52 52">
                <circle class="checkmark-circle" cx="26" cy="26" r="25" fill="none"/>
                <path class="checkmark-check" fill="none" d="M14.1 27.2l7.1 7.2 16.7-16.8"/>
              </svg>
            </div>
            <h2 class="success-title">重置成功！</h2>
            <p class="success-subtitle">您的密码已成功更新</p>
            <p class="success-redirect">正在跳转到登录页面...</p>
          </div>
        </div>
      </transition>
    </div>
  </div>
</template>

<script setup>
import { useResetPassword } from '@composables/useResetPassword'
import '@/assets/styles/components/reset-password.css'

const {
  // Refs
  resetFormRef,

  // 状态
  isLoading,
  isShaking,
  showSuccess,
  error,
  username,
  isValidRequest,

  // 表单数据
  resetForm,

  // 消息
  message,

  // 计算属性
  passwordStrength,
  shouldShowPasswordError,

  // 表单规则
  resetRules,

  // 方法
  getPasswordErrorMessage,
  checkPasswordStrength,
  getStrengthText,
  getMessageIcon,
  submitForm
} = useResetPassword()
</script>
