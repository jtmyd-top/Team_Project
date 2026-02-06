<template>
  <div class="profile-settings-container">
    <!-- 区域 1: 账户信息 (用户名和邮箱) -->
    <div class="form-section">
      <h3 class="form-section-title">账户信息</h3>
      <div class="form-row">
        <!-- 用户名修改 -->
        <el-form label-position="top">
          <el-form-item label="用户名">
            <el-input
              v-model="userStore.nickname"
              placeholder="至少6位，以小写字母开头">
              <template #prefix>
                <i class="fas fa-user"></i>
              </template>
              <template #append>
                <el-button
                  type="primary"
                  :loading="profileSaving"
                  @click="saveProfile">
                  保存
                </el-button>
              </template>
            </el-input>
            <div class="form-hint">
              用户名至少6位，以小写字母开头，只能包含字母、数字和下划线
            </div>
          </el-form-item>
        </el-form>

        <!-- 邮箱设置 -->
        <el-form label-position="top">
          <el-form-item label="邮箱">
            <el-input
              v-model="tempEmail"
              placeholder="请输入新的邮箱地址">
              <template #prefix>
                <i class="fas fa-envelope"></i>
              </template>
              <template #append>
                <el-button
                  type="primary"
                  @click="openEmailChangeDialog">
                  修改
                </el-button>
              </template>
            </el-input>
            <div class="form-hint">
              <span v-if="!emailChanged">当前邮箱：{{ userStore.email }}</span>
              <span v-else style="color: #409EFF;">
                <i class="fas fa-info-circle"></i> 修改邮箱需要进行安全验证
              </span>
            </div>
          </el-form-item>
        </el-form>
      </div>
    </div>

    <!-- 区域 2: 个性签名 -->
    <div class="form-section">
      <h3 class="form-section-title">个性签名</h3>
      <div v-if="!bioEditing" class="bio-display">
        <p>{{ userStore.bio || '这个人很懒，什么都没写...' }}</p>
        <div style="margin-top: 12px;">
          <el-button type="primary" @click="editBio">
            <i class="fas fa-edit"></i> 编辑签名
          </el-button>
        </div>
      </div>
      <div v-else class="bio-edit">
        <el-input
          v-model="bioDraft"
          type="textarea"
          :rows="3"
          maxlength="200"
          show-word-limit
          placeholder="介绍一下自己吧...">
          <template #prefix>
            <i class="fas fa-pen"></i>
          </template>
        </el-input>
        <div style="margin-top: 12px;">
          <el-button @click="cancelBio">取消</el-button>
          <el-button type="primary" :loading="bioSaving" @click="saveBio">保存签名</el-button>
        </div>
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
          <div class="header-icon-wrapper">
            <i class="fas fa-envelope-open-text"></i>
          </div>
          <div class="header-text">
            <span class="header-title">修改邮箱地址</span>
            <span class="header-subtitle">请完成以下验证步骤</span>
          </div>
        </div>
      </template>

      <div class="dialog-body">
        <el-form label-position="top" class="email-form">
          <el-form-item label="新邮箱地址" class="form-item-enhanced">
            <el-input
              v-model="emailForm.new_email"
              placeholder="请输入新的邮箱地址"
              size="large"
              clearable
              class="enhanced-input"
              @input="checkEmailAvailability">
              <template #prefix>
                <i class="fas fa-envelope input-icon"></i>
              </template>
              <template #suffix>
                <i v-if="emailCheck.status === 'ok'" class="fas fa-check-circle status-icon status-success"></i>
                <i v-else-if="emailCheck.status === 'taken'" class="fas fa-times-circle status-icon status-error"></i>
                <i v-else-if="emailCheck.status === 'invalid'" class="fas fa-exclamation-circle status-icon status-warning"></i>
              </template>
            </el-input>
            <div v-if="emailCheck.message" class="status-message" :class="emailCheck.status === 'ok' ? 'status-success-msg' : 'status-error-msg'">
              <i :class="emailCheck.status === 'ok' ? 'fas fa-check-circle' : 'fas fa-info-circle'"></i>
              {{ emailCheck.message }}
            </div>
          </el-form-item>

          <el-form-item label="当前密码" class="form-item-enhanced">
            <el-input
              v-model="emailForm.password"
              type="password"
              placeholder="请输入当前密码验证身份"
              size="large"
              show-password
              clearable
              class="enhanced-input">
              <template #prefix>
                <i class="fas fa-lock input-icon"></i>
              </template>
            </el-input>
          </el-form-item>

          <!-- 人机验证 -->
          <el-form-item label="安全验证" class="form-item-enhanced">
            <div class="captcha-container">
              <CaptchaWidget
                ref="captchaWidgetRef"
                :turnstile-timeout="8000"
                @change="onCaptchaChange"
              />
            </div>
          </el-form-item>

          <el-form-item label="邮箱验证码" class="form-item-enhanced">
            <div class="code-input-container">
              <el-input
                v-model="emailForm.code"
                placeholder="请输入6位验证码"
                size="large"
                maxlength="6"
                clearable
                class="enhanced-input code-input">
                <template #prefix>
                  <i class="fas fa-key input-icon"></i>
                </template>
              </el-input>
              <el-button
                type="primary"
                size="large"
                :disabled="!canSendCode || emailCountdown.counting"
                :loading="emailForm.codeSending"
                class="send-code-btn"
                @click="sendEmailCode">
                <i v-if="!emailForm.codeSending && !emailCountdown.counting" class="fas fa-paper-plane"></i>
                <i v-else-if="emailCountdown.counting" class="fas fa-clock"></i>
                {{ emailCountdown.counting ? `${emailCountdown.seconds}秒` : '发送验证码' }}
              </el-button>
            </div>
          </el-form-item>

          <!-- 2FA验证（如果需要） -->
          <transition name="slide-fade">
            <div v-if="emailForm.show2FA" class="two-fa-section">
              <el-divider class="divider-enhanced">
                <i class="fas fa-shield-alt"></i>
                <span>两因素验证</span>
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
                      : '验证码已发送到您的邮箱，请查收' }}</span>
                  </div>
                </template>
              </el-alert>

              <el-form-item :label="emailForm.useBackup ? '备用验证码' : '验证码'" class="form-item-enhanced">
                <el-input
                  v-model="emailForm.twoFaCode"
                  :placeholder="emailForm.useBackup ? '请输入8位备用码' : '请输入6位验证码'"
                  size="large"
                  maxlength="8"
                  clearable
                  class="enhanced-input">
                  <template #prefix>
                    <i class="fas fa-mobile-alt input-icon"></i>
                  </template>
                </el-input>
              </el-form-item>

              <div class="two-fa-actions">
                <el-button
                  v-if="emailForm.twoFaMethod === 'email'"
                  type="text"
                  size="small"
                  :loading="emailForm.twoFaCodeSending"
                  @click="sendEmail2faCode">
                  <i class="fas fa-redo"></i> 重新发送验证码
                </el-button>

                <el-button
                  type="text"
                  size="small"
                  @click="toggleEmailBackupCode">
                  <i :class="emailForm.useBackup ? 'fas fa-mobile-alt' : 'fas fa-key'"></i>
                  {{ emailForm.useBackup ? '使用验证器' : '使用备用验证码' }}
                </el-button>
              </div>
            </div>
          </transition>
        </el-form>
      </div>

      <template #footer>
        <div class="dialog-footer">
          <el-button size="large" class="cancel-btn" @click="showEmailDialog = false">
            <i class="fas fa-times"></i> 取消
          </el-button>
          <el-button
            type="primary"
            size="large"
            class="submit-btn"
            :disabled="!canSubmitEmail"
            @click="changeEmail">
            <i class="fas fa-check"></i> 确认修改
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import CaptchaWidget from '@components/common/CaptchaWidget/index.vue';
import { useSettingsProfile } from '@composables/useSettingsProfile.js';
import '@/assets/styles/components/settings-profile.css';

const {
  userStore,
  bioSaving,
  profileSaving,
  bioEditing,
  bioDraft,
  showEmailDialog,
  emailCountdown,
  captchaWidgetRef,
  onCaptchaChange,
  emailForm,
  emailCheck,
  tempEmail,
  emailChanged,
  openEmailChangeDialog,
  editBio,
  cancelBio,
  saveBio,
  saveProfile,
  checkEmailAvailability,
  canSendCode,
  canSubmitEmail,
  sendEmailCode,
  changeEmail,
  resetEmailForm,
  sendEmail2faCode,
  toggleEmailBackupCode
} = useSettingsProfile();
</script>
