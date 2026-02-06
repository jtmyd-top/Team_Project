<template>
  <div class="auth-container">
    <!-- 浮动光球 -->
    <div class="orb orb-1"></div>
    <div class="orb orb-2"></div>
    <div class="orb orb-3"></div>

    <div class="auth-card">
      <!-- 卡片头部 -->
      <div class="auth-header">
        <div class="auth-logo">
          <i class="fas fa-user-plus"></i>
        </div>
        <h2 class="auth-title">创建新账户</h2>
        <p class="auth-subtitle">加入知识管理平台</p>
      </div>

      <!-- 卡片内容 -->
      <div class="auth-body">
        <!-- 后端错误显示 -->
        <div v-if="serverErrors.length > 0" class="server-errors">
          <el-alert
            v-for="error in serverErrors"
            :key="error"
            :title="error"
            type="error"
            :closable="false"
            style="margin-bottom: 10px;"
          />
        </div>

        <!-- 注册表单 -->
        <el-form
          ref="signupFormRef"
          :model="signupForm"
          :rules="signupRules"
          @submit.prevent="submitForm"
          class="auth-form"
        >
          <!-- 用户名 -->
          <el-form-item prop="username">
            <el-input
              v-model.trim="signupForm.username"
              placeholder="请输入用户名"
              size="large"
              clearable
              :prefix-icon="User"
              @focus="handleUsernameFocus"
              @blur="[handleUsernameBlur, checkUsernameOnServer]"
              :loading="usernameCheckLoading"
            />
          <!-- 显示用户名验证提示 - 统一为红色边框样式 -->
            <div v-if="shouldShowUsernameError" class="validation-rules custom-validation"
                 style="display: block !important; visibility: visible !important; overflow: visible !important; margin-top: 8px; padding: 8px 12px; background: rgba(245, 108, 108, 0.1); border: 1px solid rgba(245, 108, 108, 0.3); border-radius: 6px; position: relative; z-index: 1000; max-width: 100%; box-sizing: border-box;">
              <div class="validation-rule rule-invalid"
                   style="color: #f56c6c !important; font-size: 14px; display: flex; align-items: center; gap: 6px; overflow: visible !important; word-wrap: break-word; word-break: break-all; line-height:0%;height: 100%;">
                <span style="color: #f56c6c; flex-shrink: 0;">●</span>
                <span style="flex: 1; min-width: 0;">{{ getUsernameErrorMessage() }}</span>
              </div>
            </div>
            <div v-if="usernameError" class="field-error">
              <i class="fas fa-exclamation-circle"></i>
              {{ usernameError }}
            </div>
          </el-form-item>

          <!-- 邮箱 -->
          <el-form-item prop="email">
            <el-input
              v-model.trim="signupForm.email"
              placeholder="请输入邮箱地址"
              size="large"
              clearable
              :prefix-icon="Message"
              @input="validateEmail"
              @blur="checkEmailOnServer"
              :loading="emailCheckLoading"
            />
            <!-- 显示邮箱验证提示 - 统一为红色边框样式 -->
            <div v-if="shouldShowEmailError" class="validation-rules custom-validation"
                 style="display: block !important; visibility: visible !important; overflow: visible !important; margin-top: 8px; padding: 8px 12px; background: rgba(245, 108, 108, 0.1); border: 1px solid rgba(245, 108, 108, 0.3); border-radius: 6px; position: relative; z-index: 1000; max-width: 100%; box-sizing: border-box;">
              <div class="validation-rule rule-invalid"
                   style="color: #f56c6c !important; font-size: 14px; display: flex; align-items: center; gap: 6px; overflow: visible !important; word-wrap: break-word; word-break: break-all; line-height: 0%; min-height: auto;">
                <span style="color: #f56c6c; flex-shrink: 0;">●</span>
                <span style="flex: 1; min-width: 0;">{{ getEmailErrorMessage() }}</span>
              </div>
            </div>
            <div v-if="emailError" class="field-error">
              <i class="fas fa-exclamation-circle"></i>
              {{ emailError }}
            </div>
          </el-form-item>


          <!-- 密码 -->
          <el-form-item prop="password">
            <el-input
              v-model="signupForm.password"
              type="password"
              placeholder="请输入密码"
              size="large"
              show-password
              :prefix-icon="Lock"
              @focus="handlePasswordFocus"
              @blur="handlePasswordBlur"
              @input="validatePassword"
            />
            <!-- 显示密码验证提示 - 统一为红色边框样式 -->
            <div v-if="shouldShowPasswordError" class="validation-rules custom-validation"
                 style="display: block !important; visibility: visible !important; overflow: visible !important; margin-top: 8px; padding: 8px 12px; background: rgba(245, 108, 108, 0.1); border: 1px solid rgba(245, 108, 108, 0.3); border-radius: 6px; position: relative; z-index: 1000; max-width: 100%; box-sizing: border-box;">
              <div class="validation-rule rule-invalid"
                   style="color: #f56c6c !important; font-size: 14px; display: flex; align-items: center; gap: 6px; overflow: visible !important; word-wrap: break-word; word-break: break-all; line-height: 0%; min-height: auto;">
                <span style="color: #f56c6c; flex-shrink: 0;">●</span>
                <span style="flex: 1; min-width: 0;">{{ getPasswordErrorMessage() }}</span>
              </div>
            </div>
          </el-form-item>

          <!-- 确认密码 -->
          <el-form-item prop="confirmPassword">
            <el-input
              v-model="signupForm.confirmPassword"
              type="password"
              placeholder="请再次输入密码"
              size="large"
              show-password
              :prefix-icon="Lock"
              @input="validateConfirmPassword"
            />
            <!-- 显示确认密码验证提示 - 统一为红色边框样式 -->
            <div v-if="shouldShowConfirmPasswordError" class="validation-rules custom-validation"
                 style="display: block !important; visibility: visible !important; overflow: visible !important; margin-top: 8px; padding: 8px 12px; background: rgba(245, 108, 108, 0.1); border: 1px solid rgba(245, 108, 108, 0.3); border-radius: 6px; position: relative; z-index: 1000; max-width: 100%; box-sizing: border-box;">
              <div class="validation-rule rule-invalid"
                   style="color: #f56c6c !important; font-size: 14px; display: flex; align-items: center; gap: 6px; overflow: visible !important; word-wrap: break-word; word-break: break-all; line-height:0%;height: 100%;">
                <span style="color: #f56c6c; flex-shrink: 0;">●</span>
                <span style="flex: 1; min-width: 0;">{{ getConfirmPasswordErrorMessage() }}</span>
              </div>
            </div>
          </el-form-item>

          <!-- 验证码组件 -->
          <div class="captcha-section">
            <CaptchaWidget
              ref="captchaWidgetRef"
              :turnstile-timeout="8000"
              @change="onCaptchaChange"
            />
          </div>

          <!-- 邮箱验证码 -->
          <el-form-item prop="emailCode">
            <div class="email-code-container">
              <el-input
                v-model="signupForm.emailCode"
                placeholder="请输入邮箱验证码"
                size="large"
                :prefix-icon="Key"
                maxlength="6"
                class="email-code-input"
              />
              <el-button
                :disabled="countdown > 0 || !isEmailValid || emailCodeLoading || emailCheckLoading || !isCaptchaVerified"
                :loading="emailCodeLoading || emailCheckLoading"
                @click="handleSendVerificationCode"
                class="email-code-button"
                size="large"
              >
                {{ emailCheckLoading ? '检查中...' : emailCodeButtonText }}
              </el-button>
            </div>
          </el-form-item>

          <!-- 服务条款 -->
          <el-form-item prop="agreeTerms">
            <el-checkbox v-model="signupForm.agreeTerms" class="terms-checkbox">
              我已阅读并同意
              <a href="#" class="terms-link" @click.prevent>服务条款</a>
              和
              <a href="#" class="terms-link" @click.prevent>隐私政策</a>
            </el-checkbox>
          </el-form-item>

          <!-- 提交按钮 -->
          <el-form-item>
            <el-button
              type="primary"
              size="large"
              :loading="submitLoading"
              :disabled="!canSubmit"
              @click="submitForm"
              class="auth-button"
            >
              <i class="fas fa-user-plus" style="margin-right: 8px;"></i>
              {{ submitLoading ? '注册中...' : '创建账户' }}
            </el-button>
          </el-form-item>

          <!-- 登录链接 -->
          <div class="login-link">
            已有账户？
            <a href="/login/" class="login-link-text" @click="addRippleEffect">
              立即登录
            </a>
          </div>
        </el-form>
      </div>
    </div>

    <!-- 成功/错误提示模态框 -->
    <el-dialog
      v-model="showPrompt"
      :title="promptTitle"
      width="400px"
      :before-close="closePrompt"
      center
    >
      <div class="prompt-content">
        <div class="prompt-icon" :class="promptType">
          <i :class="promptType === 'success' ? 'fas fa-check-circle' : 'fas fa-times-circle'"></i>
        </div>
        <p class="prompt-message">{{ promptMessage }}</p>
      </div>
      <template #footer>
        <el-button @click="closePrompt" type="primary">确定</el-button>
      </template>
    </el-dialog>

    </div>
</template>

<script setup>
import { User, Lock, Message, Key } from '@element-plus/icons-vue'
import CaptchaWidget from '@components/common/CaptchaWidget/index.vue'
import { useSignup } from '@composables/useSignup'
import '@/assets/styles/components/signup.css'

const {
  // Refs
  signupFormRef,
  captchaWidgetRef,

  // 表单数据
  signupForm,

  // 加载状态
  usernameCheckLoading,
  emailCheckLoading,
  emailCodeLoading,
  submitLoading,

  // 错误状态
  serverErrors,
  usernameError,
  emailError,

  // 验证码
  countdown,
  isEmailValid,
  isCaptchaVerified,
  emailCodeButtonText,

  // 提示框
  showPrompt,
  promptType,
  promptTitle,
  promptMessage,

  // 验证规则显示
  shouldShowUsernameError,
  shouldShowEmailError,
  shouldShowPasswordError,
  shouldShowConfirmPasswordError,

  // 表单规则
  signupRules,

  // 计算属性
  canSubmit,

  // 方法
  onCaptchaChange,
  validatePassword,
  validateEmail,
  validateConfirmPassword,
  getUsernameErrorMessage,
  getEmailErrorMessage,
  getPasswordErrorMessage,
  getConfirmPasswordErrorMessage,
  checkUsernameOnServer,
  checkEmailOnServer,
  handleSendVerificationCode,
  submitForm,
  closePrompt,
  handlePasswordFocus,
  handlePasswordBlur,
  handleUsernameFocus,
  handleUsernameBlur,
  addRippleEffect
} = useSignup()
</script>
