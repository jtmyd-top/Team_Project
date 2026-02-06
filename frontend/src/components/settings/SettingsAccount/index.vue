<template>
  <div>
    <!-- 邮箱设置 -->
    <div class="form-section">
      <h3 class="form-section-title">
        <i class="fas fa-envelope"></i> 邮箱地址
      </h3>

      <div class="email-display">
        <div class="email-info">
          <label>当前邮箱：</label>
          <span class="email-value">{{ userStore.email }}</span>
        </div>
        <el-button type="primary" @click="showEmailDialog = true">
          修改邮箱
        </el-button>
      </div>
    </div>

    <!-- 修改邮箱对话框 -->
    <el-dialog
      v-model="showEmailDialog"
      title="修改邮箱"
      width="540px"
      :close-on-click-modal="false"
      class="email-change-dialog"
      @close="resetEmailForm">

      <template #header>
        <div class="dialog-header">
          <i class="fas fa-envelope-open-text header-icon"></i>
          <span class="header-title">修改邮箱地址</span>
        </div>
      </template>

      <el-form label-position="top" class="email-form">
        <el-form-item label="新邮箱地址" class="form-item-enhanced">
          <div class="input-wrapper">
            <el-input
              v-model="emailForm.new_email"
              placeholder="请输入新的邮箱地址"
              @input="checkEmailAvailability"
              size="large"
              clearable
              class="enhanced-input">
              <template #prefix>
                <i class="fas fa-envelope input-icon"></i>
              </template>
              <template #suffix>
                <transition name="fade">
                  <i v-if="emailCheck.status === 'ok'" class="fas fa-check-circle status-icon status-success"></i>
                  <i v-else-if="emailCheck.status === 'taken'" class="fas fa-times-circle status-icon status-error"></i>
                  <i v-else-if="emailCheck.status === 'invalid'" class="fas fa-exclamation-circle status-icon status-warning"></i>
                </transition>
              </template>
            </el-input>
            <transition name="slide-fade">
              <div v-if="emailCheck.message"
                   class="status-message"
                   :class="{
                     'status-message-success': emailCheck.status === 'ok',
                     'status-message-error': emailCheck.status === 'taken' || emailCheck.status === 'invalid'
                   }">
                <i class="fas fa-info-circle"></i>
                {{ emailCheck.message }}
              </div>
            </transition>
          </div>
        </el-form-item>

        <el-form-item label="当前密码" class="form-item-enhanced">
          <el-input
            v-model="emailForm.password"
            type="password"
            placeholder="请输入当前密码以验证身份"
            show-password
            size="large"
            clearable
            class="enhanced-input">
            <template #prefix>
              <i class="fas fa-lock input-icon"></i>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item label="验证码" class="form-item-enhanced">
          <CaptchaWidget
            ref="captchaWidgetRef"
            :turnstile-timeout="8000"
            @change="onCaptchaChange"
          />
        </el-form-item>

        <el-form-item class="form-item-enhanced">
          <template #label>
            <span>新邮箱验证码</span>
            <el-tooltip placement="top" effect="light">
              <template #content>
                <div style="max-width: 250px;">
                  验证码将发送至您填写的<strong>新邮箱</strong>地址，<br/>
                  用于验证新邮箱的所有权
                </div>
              </template>
              <i class="fas fa-question-circle" style="margin-left: 6px; color: #909399; cursor: help;"></i>
            </el-tooltip>
          </template>
          <div class="code-input-container">
            <el-input
              v-model="emailForm.code"
              placeholder="请输入发送到新邮箱的6位验证码"
              size="large"
              maxlength="6"
              clearable
              class="enhanced-input code-input">
              <template #prefix>
                <i class="fas fa-key input-icon"></i>
              </template>
            </el-input>
            <el-button
              :disabled="!canSendCode || emailCountdown.counting"
              :loading="emailForm.codeSending"
              @click="sendEmailCode"
              size="large"
              class="send-code-btn"
              :type="emailCountdown.counting ? 'info' : 'primary'">
              <template v-if="!emailForm.codeSending">
                <i v-if="!emailCountdown.counting" class="fas fa-paper-plane"></i>
                <i v-else class="fas fa-clock"></i>
              </template>
              <span>{{ emailCountdown.counting ? `${emailCountdown.seconds}秒后重试` : '发送验证码' }}</span>
            </el-button>
          </div>
          <transition name="slide-fade">
            <div v-if="emailCountdown.counting" class="countdown-hint">
              <i class="fas fa-hourglass-half"></i>
              <span>请等待 <strong>{{ emailCountdown.seconds }}</strong> 秒后重新发送</span>
            </div>
          </transition>
        </el-form-item>

        <!-- 2FA验证（如果需要） -->
        <transition name="slide-fade">
          <div v-if="emailForm.show2FA" class="two-fa-section">
            <el-divider class="divider-enhanced">
              <i class="fas fa-shield-alt"></i>
              <span>需要两因素验证</span>
            </el-divider>

            <el-alert
              type="info"
              :closable="false"
              class="alert-enhanced">
              <template #default>
                <div class="alert-content">
                  <i :class="emailForm.twoFaMethod === 'totp' ? 'fas fa-mobile-alt' : 'fas fa-envelope'"></i>
                  <span>{{ emailForm.twoFaMethod === 'totp'
                    ? '请输入验证器应用中的6位验证码'
                    : '验证码已自动发送至您的原邮箱，请查收（用于安全验证）' }}</span>
                </div>
              </template>
            </el-alert>

            <el-form-item class="form-item-enhanced">
              <template #label>
                <span>{{ emailForm.useBackup ? '备用验证码' : '2FA验证码' }}</span>
                <el-tooltip placement="top" effect="light">
                  <template #content>
                    <div style="max-width: 280px;">
                      此验证码发送至您的<strong>原邮箱</strong>（当前绑定邮箱），<br/>
                      用于二次身份验证，确保是您本人操作
                    </div>
                  </template>
                  <i class="fas fa-question-circle" style="margin-left: 6px; color: #909399; cursor: help;"></i>
                </el-tooltip>
              </template>
              <div class="code-input-container">
                <el-input
                  v-model="emailForm.twoFaCode"
                  :placeholder="emailForm.useBackup ? '请输入8位备用码' : '请输入发送到原邮箱的6位验证码'"
                  :maxlength="emailForm.useBackup ? 8 : 6"
                  size="large"
                  clearable
                  class="enhanced-input code-input">
                  <template #prefix>
                    <i :class="emailForm.useBackup ? 'fas fa-key' : 'fas fa-qrcode'" class="input-icon"></i>
                  </template>
                </el-input>

                <!-- 仅在邮箱2FA且未使用备用码时显示重发按钮 -->
                <el-button
                  v-if="emailForm.twoFaMethod === 'email' && !emailForm.useBackup"
                  :disabled="twoFaCountdown.counting"
                  :loading="emailForm.twoFaCodeSending"
                  @click="resend2FACode"
                  size="large"
                  class="send-code-btn"
                  :type="twoFaCountdown.counting ? 'info' : 'primary'">
                  <template v-if="!emailForm.twoFaCodeSending">
                    <i v-if="!twoFaCountdown.counting" class="fas fa-paper-plane"></i>
                    <i v-else class="fas fa-clock"></i>
                  </template>
                  <span>{{ twoFaCountdown.counting ? `${twoFaCountdown.seconds}秒后重试` : '重新发送' }}</span>
                </el-button>
              </div>

              <!-- 倒计时提示 -->
              <transition name="slide-fade">
                <div v-if="twoFaCountdown.counting && emailForm.twoFaMethod === 'email' && !emailForm.useBackup" class="countdown-hint">
                  <i class="fas fa-hourglass-half"></i>
                  <span>请等待 <strong>{{ twoFaCountdown.seconds }}</strong> 秒后重新发送</span>
                </div>
              </transition>
            </el-form-item>

            <!-- 切换验证方式按钮 -->
            <div class="two-fa-actions">
              <!-- 重新发送验证码链接（仅邮箱2FA且未使用备用码时显示） -->
              <el-button
                v-if="emailForm.twoFaMethod === 'email' && !emailForm.useBackup"
                type="text"
                size="small"
                :disabled="twoFaCountdown.counting"
                @click="resend2FACode"
                class="resend-link">
                <i class="fas fa-redo"></i>
                重新发送验证码
              </el-button>

              <!-- 切换备用码链接 -->
              <el-button
                type="text"
                size="small"
                @click="toggleEmailBackupCode"
                class="backup-code-toggle">
                <i :class="emailForm.useBackup ? 'fas fa-mobile-alt' : 'fas fa-key'"></i>
                {{ emailForm.useBackup ? '使用验证器' : '使用备用验证码' }}
              </el-button>
            </div>
          </div>
        </transition>
      </el-form>

      <template #footer>
        <div class="dialog-footer">
          <el-button
            @click="showEmailDialog = false"
            size="large"
            class="cancel-btn">
            <i class="fas fa-times"></i>
            <span>取消</span>
          </el-button>
          <el-button
            type="primary"
            :disabled="!canSubmitEmail"
            @click="changeEmail"
            size="large"
            class="submit-btn">
            <i class="fas fa-check"></i>
            <span>确认修改</span>
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import CaptchaWidget from '@components/common/CaptchaWidget/index.vue';
import { useSettingsAccount } from '@composables/useSettingsAccount.js';
import '@/assets/styles/components/settings-account.css';

const {
  userStore,
  showEmailDialog,
  emailCountdown,
  twoFaCountdown,
  captchaWidgetRef,
  onCaptchaChange,
  emailForm,
  emailCheck,
  checkEmailAvailability,
  canSendCode,
  canSubmitEmail,
  sendEmailCode,
  changeEmail,
  resend2FACode,
  toggleEmailBackupCode,
  resetEmailForm
} = useSettingsAccount();
</script>
