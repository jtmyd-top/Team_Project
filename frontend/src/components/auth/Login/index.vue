<template>
  <div class="auth-page">
    <!-- 浮动光球背景 -->
    <div class="bg-orbs">
      <div class="orb orb-1"></div>
      <div class="orb orb-2"></div>
      <div class="orb orb-3"></div>
    </div>

    <!-- 主内容区 - 去容器化设计 -->
    <div class="auth-content">
      <!-- 品牌标识 -->
      <div class="brand-section">
        <div class="brand-icon">
          <i class="fas fa-book-open"></i>
        </div>
        <h1 class="brand-title">欢迎回来</h1>
        <p class="brand-subtitle">登录您的知识管理账户</p>
      </div>

      <!-- 第一步：用户名密码登录表单 -->
      <el-form
        v-if="!require2fa"
        ref="loginFormRef"
        :model="loginForm"
        :rules="loginRules"
        @submit.prevent="handleLogin"
        class="auth-form"
      >
        <div class="form-section">
          <el-form-item prop="username" class="form-item">
            <el-input
              v-model="loginForm.username"
              placeholder="请输入用户名"
              size="large"
              clearable
              class="auth-input"
            >
              <template #prefix>
                <i class="fas fa-user input-icon"></i>
              </template>
            </el-input>
          </el-form-item>

          <el-form-item prop="password" class="form-item">
            <el-input
              v-model="loginForm.password"
              type="password"
              placeholder="请输入密码"
              size="large"
              show-password
              class="auth-input"
              @keyup.enter="handleLogin"
            >
              <template #prefix>
                <i class="fas fa-lock input-icon"></i>
              </template>
            </el-input>
          </el-form-item>
        </div>

        <!-- 验证码组件 -->
        <div class="captcha-section">
          <CaptchaWidget
            ref="captchaWidgetRef"
            :turnstile-timeout="8000"
            @change="onCaptchaChange"
            @enter="handleLogin"
          />
        </div>

        <!-- 登录按钮 -->
        <div class="action-section">
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            @click="handleLogin"
            class="primary-btn"
          >
            <i class="fas fa-sign-in-alt btn-icon"></i>
            {{ loading ? '登录中...' : '登录' }}
          </el-button>
        </div>

        <!-- 底部链接 -->
        <div class="footer-links">
          <a href="/forgot-password/" class="link-item">
            <i class="fas fa-key"></i>
            <span>忘记密码？</span>
          </a>
        </div>
      </el-form>

      <!-- 第二步：2FA验证表单 -->
      <div v-if="require2fa" class="twofa-content">
        <!-- 2FA信息提示 - 优化样式 -->
        <div class="twofa-notice">
          <div class="notice-icon">
            <i class="fas fa-shield-alt"></i>
          </div>
          <div class="notice-text">
            <strong>两因素认证</strong>
            <p v-if="!useBackupCode && twoFaMethod === 'totp'">
              请打开您的身份验证器应用，输入显示的6位数字验证码
            </p>
            <p v-if="!useBackupCode && twoFaMethod === 'email'">
              验证码已发送到您的邮箱，请查收并输入
            </p>
            <p v-if="useBackupCode">
              请输入您的8位备用验证码
            </p>
          </div>
        </div>

        <!-- 2FA验证表单 -->
        <el-form
          ref="twoFaFormRef"
          :model="twoFaForm"
          :rules="twoFaRules"
          @submit.prevent="verifyTwoFA"
          class="auth-form"
        >
          <div class="form-section">
            <el-form-item prop="code" class="form-item">
              <el-input
                v-model="twoFaForm.code"
                :placeholder="useBackupCode ? '请输入8位备用验证码' : '请输入6位验证码'"
                size="large"
                :maxlength="useBackupCode ? 8 : 6"
                class="auth-input code-input"
                @keyup.enter="verifyTwoFA"
                @input="handleVerificationCodeInput"
              >
                <template #prefix>
                  <i class="fas fa-key input-icon"></i>
                </template>
              </el-input>
            </el-form-item>
          </div>

          <!-- 邮箱2FA倒计时和重发 -->
          <div v-if="twoFaMethod === 'email' && !useBackupCode" class="resend-section">
            <div v-if="countdown > 0" class="countdown-text">
              <i class="fas fa-clock"></i>
              <span>{{ countdown }}秒后可重新发送</span>
            </div>
            <button
              v-else
              type="button"
              @click="resendTwoFACode"
              :disabled="resendLoading"
              class="resend-btn"
            >
              <i class="fas fa-redo"></i>
              <span>{{ resendLoading ? '发送中...' : '重新发送验证码' }}</span>
            </button>
          </div>

          <!-- 操作按钮区 -->
          <div class="twofa-actions">
            <!-- 主按钮：验证 -->
            <el-button
              type="primary"
              size="large"
              :loading="twoFaLoading"
              @click="verifyTwoFA"
              class="primary-btn"
            >
              <i class="fas fa-check-circle btn-icon"></i>
              {{ twoFaLoading ? '验证中...' : '验证' }}
            </el-button>

            <!-- 次要按钮：使用备用验证码 -->
            <el-button
              v-if="!useBackupCode"
              type="primary"
              size="large"
              @click="useBackupCode = true"
              class="primary-btn secondary-btn"
            >
              <i class="fas fa-key btn-icon"></i>
              使用备用验证码
            </el-button>

            <!-- 返回按钮 -->
            <el-button
              type="primary"
              size="large"
              @click="useBackupCode ? (useBackupCode = false) : backToPassword()"
              class="primary-btn secondary-btn"
            >
              <i class="fas fa-arrow-left btn-icon"></i>
              {{ useBackupCode ? '返回2FA验证' : '返回密码验证' }}
            </el-button>
          </div>
        </el-form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import CaptchaWidget from '@components/common/CaptchaWidget/index.vue'
import { useLogin } from '@composables/useLogin'
import '@/assets/styles/components/login.css'

const captchaWidgetRef = ref(null)

const {
  loginFormRef,
  twoFaFormRef,
  loginForm,
  loginRules,
  twoFaForm,
  twoFaRules,
  captchaParams,
  loading,
  require2fa,
  twoFaLoading,
  twoFaMethod,
  useBackupCode,
  countdown,
  resendLoading,
  onCaptchaChange,
  handleLogin,
  verifyTwoFA,
  resendTwoFACode,
  startCountdown,
  backToPassword,
  handleVerificationCodeInput
} = useLogin(captchaWidgetRef)

onMounted(() => {
  // CaptchaWidget 会自动初始化验证码
})
</script>
