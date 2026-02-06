<template>
  <div class="auth-page">
    <!-- 浮动光球背景 -->
    <div class="bg-orbs">
      <div class="orb orb-1"></div>
      <div class="orb orb-2"></div>
      <div class="orb orb-3"></div>
    </div>

    <!-- 主内容区 - 毛玻璃卡片 -->
    <div class="auth-content" :class="{ 'shake': isShaking }">
      <!-- 品牌标识 -->
      <div class="brand-section">
        <div class="brand-icon">
          <i class="fas fa-key"></i>
        </div>
        <h1 class="brand-title">重置密码</h1>
        <p class="brand-subtitle">输入您的邮箱地址，我们将发送重置链接</p>
      </div>

      <!-- 表单 -->
      <el-form
        ref="forgotFormRef"
        :model="forgotForm"
        :rules="forgotRules"
        class="auth-form"
        @submit.prevent="submitForm"
      >
        <div class="form-section">
          <el-form-item prop="email" class="form-item">
            <el-input
              v-model="forgotForm.email"
              type="email"
              placeholder="请输入您的邮箱地址"
              size="large"
              clearable
              class="auth-input"
              @input="handleEmailInput"
            >
              <template #prefix>
                <i class="fas fa-envelope input-icon"></i>
              </template>
            </el-input>
          </el-form-item>
        </div>

        <!-- 验证码 -->
        <div class="captcha-section">
          <CaptchaWidget
            ref="captchaWidgetRef"
            :turnstile-timeout="5000"
            @change="onCaptchaChange"
          />
        </div>

        <!-- 提交按钮 -->
        <div class="action-section">
          <el-button
            type="primary"
            size="large"
            :loading="isLoading"
            :disabled="isLoading || isCountingDown"
            @click="submitForm"
            class="primary-btn"
          >
            <template v-if="!isLoading && !isCountingDown">
              <i class="fas fa-paper-plane btn-icon"></i>
              发送重置链接
            </template>
            <template v-else-if="isLoading">
              <i class="fas fa-spinner fa-spin btn-icon"></i>
              发送中...
            </template>
            <template v-else>
              <i class="fas fa-clock btn-icon"></i>
              {{ countdown }}秒后可重新发送
            </template>
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

      <!-- 返回链接 -->
      <div class="footer-links">
        <a href="/login" class="back-link">
          <i class="fas fa-arrow-left"></i>
          <span>返回登录</span>
        </a>
      </div>
    </div>
  </div>
</template>

<script setup>
import CaptchaWidget from '@components/common/CaptchaWidget/index.vue'
import { useForgotPassword } from '@composables/useForgotPassword'
import '@/assets/styles/components/forgot-password.css'

const {
  // Refs
  forgotFormRef,
  captchaWidgetRef,

  // 状态
  isLoading,
  isCountingDown,
  countdown,
  isShaking,

  // 表单数据
  forgotForm,

  // 消息
  message,

  // 表单规则
  forgotRules,

  // 方法
  onCaptchaChange,
  handleEmailInput,
  getMessageIcon,
  submitForm
} = useForgotPassword()
</script>
