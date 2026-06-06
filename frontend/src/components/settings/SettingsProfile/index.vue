<template>
  <div class="profile-settings-container">
    <!-- 封面/横幅区域 -->
    <div class="profile-cover-section">
      <div class="profile-cover-media">
        <img
          v-if="userStore.banner && !userStore.bannerIsVideo"
          :src="userStore.banner"
          alt="封面"
          class="cover-img">
        <video
          v-if="userStore.banner && userStore.bannerIsVideo"
          ref="bannerVideoRef"
          :src="userStore.banner"
          class="cover-img"
          autoplay loop playsinline
          :muted="videoMuted"
          @loadedmetadata="checkVideoAudio">
        </video>
        <div v-if="!userStore.banner" class="cover-gradient"></div>

        <!-- 视频控件：左下角（仅视频显示） -->
        <div v-if="userStore.bannerIsVideo" class="cover-video-controls">
          <!-- 播放/暂停 -->
          <button class="cover-ctrl-btn" @click.stop="toggleVideoPlay"
                  :title="videoPaused ? '播放' : '暂停'">
            <i :class="playIconClass"></i>
          </button>

          <!-- 音量 -->
          <div class="cover-volume-ctrl"
               @mouseenter.stop="volumeSliderVisible = true"
               @mouseleave.stop="volumeSliderVisible = false">
            <button class="cover-ctrl-btn" @click.stop="toggleVideoMute"
                    :title="videoMuted ? '开启声音' : '静音'">
              <i :class="volumeIconClass" :key="volumeIconClass"></i>
            </button>
            <div class="cover-volume-slider" :class="{ visible: volumeSliderVisible }">
              <input type="range" min="0" max="1" step="0.01"
                     v-model.number="videoVolume" @input="updateVideoVolume">
            </div>
          </div>
        </div>

        <!-- 更改封面按钮：右下角 -->
        <div class="cover-upload-wrap">
          <el-upload
            :action="API_ENDPOINTS.uploadAvatar"
            name="banner"
            :headers="csrfHeader"
            :show-file-list="false"
            :on-success="handleBannerSuccess"
            :on-error="() => ElMessage.error('封面上传失败')"
            accept="image/jpeg,image/png,image/webp,image/gif,video/mp4,video/webm">
            <button class="cover-change-btn">
              <i class="fas fa-camera"></i>
              <span>更改封面</span>
            </button>
          </el-upload>
        </div>
      </div>
    </div>

    <!-- 区域 1: 账户信息 (用户名和邮箱) -->
    <div class="form-section account-info-section">
      <div class="form-row account-form-row">
        <!-- 用户名修改 -->
        <el-form label-position="top" class="account-edit-card">
          <div class="account-card-head">
            <div class="account-card-head__icon">
              <i class="fas fa-signature"></i>
            </div>
            <div class="account-card-head__text">
              <strong>用户名</strong>
              <span>修改后会同步到你的个人资料展示</span>
            </div>
          </div>
          <el-form-item label="用户名">
            <div class="account-input-row">
              <el-input
                v-model="userStore.nickname"
                class="account-main-input"
                placeholder="至少6位，以小写字母开头" />
              <el-button
                class="account-action-btn"
                type="primary"
                :disabled="!nicknameDirty || profileSaving"
                :loading="profileSaving"
                @click="saveProfile">
                <i class="fas fa-check"></i>
                保存
              </el-button>
            </div>
            <div class="form-hint">
              <span v-if="nicknameDirty">
                <i class="fas fa-pen"></i> 已检测到修改，点击右侧按钮即可保存
              </span>
              <span v-else>用户名至少6位，以小写字母开头，只能包含字母、数字和下划线</span>
            </div>
          </el-form-item>
        </el-form>

        <!-- 邮箱设置 -->
        <el-form label-position="top" class="account-edit-card">
          <div class="account-card-head">
            <div class="account-card-head__icon account-card-head__icon--email">
              <i class="fas fa-envelope-open-text"></i>
            </div>
            <div class="account-card-head__text">
              <strong>邮箱</strong>
              <span>邮箱修改需要进行一次安全验证</span>
            </div>
            <span class="account-card-head__badge" :class="{ 'is-active': !emailDirty }">
              {{ emailDirty ? '待验证' : '已绑定' }}
            </span>
          </div>
          <el-form-item label="邮箱">
            <div class="account-input-row">
              <el-input
                v-model="tempEmail"
                class="account-main-input"
                placeholder="请输入新的邮箱地址" />
              <el-button
                class="account-action-btn account-action-btn--email"
                type="primary"
                :disabled="!emailDirty"
                @click="openEmailChangeDialog">
                <i class="fas fa-wand-magic-sparkles"></i>
                修改
              </el-button>
            </div>
            <div class="form-hint">
              <span v-if="!emailDirty">当前邮箱：{{ userStore.email }}</span>
              <span v-else-if="emailChanged" style="color: #409EFF;">
                <i class="fas fa-info-circle"></i> 修改邮箱需要进行安全验证
              </span>
              <span v-else style="color: #E6A23C;">
                <i class="fas fa-exclamation-circle"></i> 请输入正确的邮箱格式后再继续
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
                  :disabled="emailTwoFaCountdown.counting"
                  :loading="emailForm.twoFaCodeSending"
                  @click="sendEmail2faCode">
                  <i :class="emailTwoFaCountdown.counting ? 'fas fa-clock' : 'fas fa-redo'"></i>
                  {{ emailTwoFaCountdown.counting ? `${emailTwoFaCountdown.seconds}秒后重试` : '重新发送验证码' }}
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
import { ElMessage, ElUpload } from 'element-plus';
import CaptchaWidget from '@components/common/CaptchaWidget/index.vue';
import { useSettingsProfile } from '@composables/useSettingsProfile.js';
import '@/assets/styles/components/settings-profile.css';

const {
  userStore,
  API_ENDPOINTS,
  csrfHeader,
  bioSaving,
  profileSaving,
  bioEditing,
  bioDraft,
  showEmailDialog,
  emailCountdown,
  emailTwoFaCountdown,
  captchaWidgetRef,
  onCaptchaChange,
  emailForm,
  emailCheck,
  tempEmail,
  nicknameDirty,
  emailDirty,
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
  toggleEmailBackupCode,
  // 封面/横幅
  bannerVideoRef,
  videoHasAudio,
  videoMuted,
  videoPaused,
  videoVolume,
  volumeSliderVisible,
  volumeIconClass,
  playIconClass,
  handleBannerSuccess,
  checkVideoAudio,
  toggleVideoMute,
  toggleVideoPlay,
  updateVideoVolume,
} = useSettingsProfile();
</script>
