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

        <el-form-item label="图片验证码" class="form-item-enhanced">
          <div class="captcha-container">
            <el-input
              v-model="emailForm.imageCaptcha"
              placeholder="请输入图片验证码"
              size="large"
              maxlength="4"
              clearable
              class="enhanced-input captcha-input">
              <template #prefix>
                <i class="fas fa-shield-alt input-icon"></i>
              </template>
              <template #suffix>
                <el-tooltip content="区分大小写" placement="top">
                  <i class="fas fa-info-circle tooltip-icon"></i>
                </el-tooltip>
              </template>
            </el-input>
            <div class="captcha-image-wrapper" @click="refreshCaptcha">
              <img :src="captchaUrl" class="captcha-image" alt="验证码">
              <div class="captcha-overlay">
                <i class="fas fa-sync-alt"></i>
                <span>点击刷新</span>
              </div>
            </div>
          </div>
          <div class="form-hint-enhanced">
            <i class="fas fa-lightbulb"></i>
            点击图片可刷新验证码
          </div>
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
import { ref, reactive, computed } from 'vue';
import { useUserStore } from '../../stores/user.js';
import { apiService } from '../../services/apiService.js';
import { createDebouncedRequest, useCountdown } from '../../utils/request.js';
import { ElMessage } from 'element-plus';

const userStore = useUserStore();

// 对话框显示状态
const showEmailDialog = ref(false);

// 倒计时（两个独立的倒计时）
const emailCountdown = useCountdown();  // 新邮箱验证码倒计时
const twoFaCountdown = useCountdown();  // 2FA验证码倒计时

// 图片验证码URL
const captchaUrl = ref('/captcha/?_=' + Date.now());

// 邮箱表单
const emailForm = reactive({
  new_email: '',
  password: '',
  imageCaptcha: '',
  code: '',
  codeSending: false,
  show2FA: false,
  twoFaMethod: '',
  twoFaCode: '',
  useBackup: false,
  twoFaCodeSending: false,
});

// 邮箱检查状态
const emailCheck = reactive({
  status: null,
  message: ''
});

// 邮箱正则
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/**
 * 刷新图片验证码
 */
const refreshCaptcha = () => {
  captchaUrl.value = '/captcha/?_=' + Date.now();
};

/**
 * 邮箱检查核心逻辑
 */
const checkEmailAvailabilityCore = async (signal) => {
  const email = emailForm.new_email.trim();
  if (!email) {
    emailCheck.status = null;
    emailCheck.message = '';
    return;
  }
  
  if (!EMAIL_REGEX.test(email)) {
    emailCheck.status = 'invalid';
    emailCheck.message = '邮箱格式不正确';
    return;
  }

  try {
    const data = await apiService.checkEmail(email, true);
    if (data.is_taken) {
      emailCheck.status = 'taken';
      emailCheck.message = '该邮箱已被绑定';
    } else {
      emailCheck.status = 'ok';
      emailCheck.message = '该邮箱可用';
    }
  } catch (error) {
    if (error.name === 'AbortError') return;
    emailCheck.status = 'invalid';
    emailCheck.message = '邮箱检查失败，请稍后再试';
  }
};

/**
 * 防抖的邮箱检查
 */
const checkEmailAvailability = createDebouncedRequest(checkEmailAvailabilityCore, 400);

/**
 * 是否可以发送验证码
 */
const canSendCode = computed(() => {
  return EMAIL_REGEX.test(emailForm.new_email.trim()) && 
         emailCheck.status === 'ok' && 
         emailForm.imageCaptcha.trim().length > 0;
});

/**
 * 是否可以提交表单
 */
const canSubmitEmail = computed(() => {
  if (!EMAIL_REGEX.test(emailForm.new_email.trim())) return false;
  if (emailCheck.status !== 'ok') return false;
  if (!emailForm.password.trim()) return false;
  if (!emailForm.code.trim()) return false;
  
  // 如果2FA已显示，则必须输入2FA代码
  if (emailForm.show2FA && !emailForm.twoFaCode.trim()) return false;

  return true;
});

/**
 * 发送邮箱验证码
 */
const sendEmailCode = async () => {
  const email = emailForm.new_email.trim();
  if (!EMAIL_REGEX.test(email)) return ElMessage.warning("请输入正确邮箱");
  if (emailCheck.status !== 'ok') return ElMessage.warning(emailCheck.message || "该邮箱不可用");
  if (!emailForm.imageCaptcha) return ElMessage.warning("请输入图片验证码");

  emailForm.codeSending = true;
  try {
    const data = await apiService.sendEmailCode({
      email,
      image_captcha_code: emailForm.imageCaptcha,
      purpose: "email_change"
    });
    
    if (data.status === "success") {
      ElMessage.success({
        message: `验证码已发送至新邮箱 ${emailForm.new_email}，请查收`,
        duration: 4000
      });
      emailCountdown.start(120);
      refreshCaptcha();
      emailForm.imageCaptcha = "";
    } else {
      ElMessage.error(data.message || "发送验证码失败");
      refreshCaptcha();
      emailForm.imageCaptcha = "";
    }
  } catch (error) {
    ElMessage.error(error.message || "网络错误");
    refreshCaptcha();
    emailForm.imageCaptcha = "";
  } finally {
    emailForm.codeSending = false;
  }
};

/**
 * 修改邮箱
 */
const changeEmail = async () => {
  // 基础客户端验证
  if (emailCheck.status !== 'ok') return ElMessage.warning(emailCheck.message || "该邮箱不可用");
  if (!emailForm.password) return ElMessage.warning("请输入当前密码");
  if (!emailForm.code) return ElMessage.warning("请输入新邮箱的验证码");

  // 如果2FA输入框可见，则验证2FA代码
  if (emailForm.show2FA && !emailForm.twoFaCode) {
    return ElMessage.warning("请输入两因素验证码");
  }

  try {
    // 构建请求体
    const requestBody = {
      password: emailForm.password,
      new_email: emailForm.new_email.trim(),
      code: emailForm.code.trim(),  // 确保验证码被正确发送
    };

    // 如果是第二步，则添加2FA详情
    if (emailForm.show2FA) {
      requestBody.two_fa_code = emailForm.twoFaCode.trim();
      requestBody.use_backup = emailForm.useBackup;
    }

    const data = await apiService.updateEmail(requestBody);

    if (data.status === "require_2fa") {
      // 后端要求2FA，进入第二步
      emailForm.show2FA = true;
      emailForm.twoFaMethod = data.method;

      // 根据2FA方法通知用户
      if (data.method === 'email') {
        ElMessage.info({
          message: "为保证安全，验证码已自动发送至您的原邮箱（非新邮箱），请查收",
          duration: 5000
        });
        // 启动2FA倒计时
        twoFaCountdown.start(120);
      } else { // totp
        ElMessage.info("请输入验证器应用中的验证码以完成操作");
      }
    } else if (data.status === "success") {
      // 成功！
      userStore.updateEmail(data.email);
      showEmailDialog.value = false;
      resetEmailForm();
      ElMessage.success("邮箱修改成功");
    } else {
      // 处理后端返回的其他错误
      ElMessage.error(data.message || "邮箱修改失败");
      // 如果是第一步出错，刷新图片验证码以便重试
      if (!emailForm.show2FA) {
        refreshCaptcha();
        emailForm.imageCaptcha = '';
      }
    }
  } catch (error) {
    ElMessage.error(error.message || "网络错误");
    // 网络错误时也刷新图片验证码
    if (!emailForm.show2FA) {
      refreshCaptcha();
      emailForm.imageCaptcha = '';
    }
  }
};

/**
 * 重新发送2FA验证码（修改邮箱场景）
 */
const resend2FACode = async () => {
  if (twoFaCountdown.counting) return;
  
  emailForm.twoFaCodeSending = true;
  try {
    const data = await apiService.sendOperation2FACode();
    
    if (data.status === 'success') {
      ElMessage.success({
        message: '2FA验证码已重新发送至您的原邮箱',
        duration: 3000
      });
      twoFaCountdown.start(120);
    } else {
      ElMessage.error(data.message || '发送失败');
    }
  } catch (error) {
    ElMessage.error(error.message || '网络错误');
  } finally {
    emailForm.twoFaCodeSending = false;
  }
};

/**
 * 切换备用验证码（邮箱修改）
 */
const toggleEmailBackupCode = () => {
  emailForm.useBackup = !emailForm.useBackup;
  emailForm.twoFaCode = '';
  const message = emailForm.useBackup
    ? "已切换到备用验证码模式"
    : `已切换回${emailForm.twoFaMethod === 'totp' ? '验证器' : '邮箱'}验证模式`;
  ElMessage.info(message);
};

/**
 * 重置邮箱表单
 */
const resetEmailForm = () => {
  emailForm.new_email = '';
  emailForm.password = '';
  emailForm.imageCaptcha = '';
  emailForm.code = '';
  emailForm.show2FA = false;
  emailForm.twoFaCode = '';
  emailForm.twoFaMethod = '';
  emailForm.useBackup = false;
  emailCheck.status = null;
  emailCheck.message = '';
  emailCountdown.stop();
  twoFaCountdown.stop();
  refreshCaptcha();
};
</script>

<style scoped>
/* ==================== 主要区域样式 ==================== */
.form-section {
  padding: 24px;
  border-radius: 12px;
  transition: all 0.3s ease;
}

.form-section:nth-of-type(odd) {
  background-color: #fff;
}

.form-section:nth-of-type(even) {
  background-color: #f9f9fa;
}

.form-section-title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.form-section-title i {
  color: #409eff;
}

.email-display {
  display: flex;
  align-items: center;
  justify-content: space-between;
  max-width: 600px;
  padding: 20px;
  background: linear-gradient(135deg, #f5f7fa 0%, #e8ebf0 100%);
  border-radius: 12px;
  border: 1px solid #e4e7ed;
  transition: all 0.3s ease;
}

.email-display:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  transform: translateY(-2px);
}

.email-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.email-info label {
  font-weight: 600;
  color: #606266;
  font-size: 14px;
}

.email-value {
  color: #303133;
  font-family: 'Courier New', monospace;
  font-weight: 500;
  padding: 4px 12px;
  background: rgba(255, 255, 255, 0.8);
  border-radius: 6px;
}

/* ==================== 对话框样式 ==================== */
:deep(.email-change-dialog) {
  border-radius: 16px;
  overflow: hidden;
}

:deep(.email-change-dialog .el-dialog__header) {
  padding: 0;
  margin: 0;
  background: linear-gradient(135deg, #409eff 0%, #66b1ff 100%);
}

:deep(.email-change-dialog .el-dialog__body) {
  padding: 32px;
  background: #fafbfc;
}

:deep(.email-change-dialog .el-dialog__footer) {
  padding: 20px 32px;
  background: #fff;
  border-top: 1px solid #e4e7ed;
}

.dialog-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 24px 32px;
  color: #fff;
}

.header-icon {
  font-size: 24px;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.05); }
}

.header-title {
  font-size: 20px;
  font-weight: 600;
  letter-spacing: 0.5px;
}

/* ==================== 表单样式 ==================== */
.email-form {
  padding-top: 8px;
}

.form-item-enhanced {
  margin-bottom: 24px;
}

.input-wrapper {
  position: relative;
}

.enhanced-input :deep(.el-input__wrapper) {
  border-radius: 10px;
  padding: 12px 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  border: 2px solid #e4e7ed;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  background: #fff;
}

.enhanced-input :deep(.el-input__wrapper:hover) {
  border-color: #c0c4cc;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.enhanced-input :deep(.el-input__wrapper.is-focus) {
  border-color: #409eff;
  box-shadow: 0 4px 16px rgba(64, 158, 255, 0.2);
  transform: translateY(-1px);
}

.input-icon {
  color: #909399;
  font-size: 16px;
  margin-right: 4px;
}

.enhanced-input :deep(.el-input__wrapper.is-focus) .input-icon {
  color: #409eff;
}

.status-icon {
  font-size: 18px;
  animation: fadeIn 0.3s ease;
}

.status-success {
  color: #67c23a;
}

.status-error {
  color: #f56c6c;
}

.status-warning {
  color: #e6a23c;
}

/* 状态消息样式 */
.status-message {
  margin-top: 8px;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 8px;
  animation: slideDown 0.3s ease;
}

.status-message-success {
  background: #f0f9ff;
  color: #67c23a;
  border: 1px solid #c2e7b0;
}

.status-message-error {
  background: #fef0f0;
  color: #f56c6c;
  border: 1px solid #fbc4c4;
}

/* ==================== 验证码区域样式 ==================== */
.captcha-container {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.captcha-input {
  flex: 1;
}

.captcha-image-wrapper {
  position: relative;
  height: 48px;
  width: 140px;
  cursor: pointer;
  border-radius: 8px;
  overflow: hidden;
  border: 2px solid #e4e7ed;
  transition: all 0.3s ease;
  flex-shrink: 0;
}

.captcha-image-wrapper:hover {
  border-color: #409eff;
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.2);
  transform: translateY(-2px);
}

.captcha-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.captcha-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(64, 158, 255, 0.9);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.3s ease;
  gap: 4px;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
}

.captcha-image-wrapper:hover .captcha-overlay {
  opacity: 1;
}

.captcha-overlay i {
  font-size: 18px;
  animation: rotate 1s ease-in-out infinite;
}

@keyframes rotate {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.form-hint-enhanced {
  margin-top: 8px;
  padding: 6px 12px;
  background: #f4f4f5;
  border-radius: 6px;
  font-size: 12px;
  color: #606266;
  display: flex;
  align-items: center;
  gap: 6px;
}

.form-hint-enhanced i {
  color: #e6a23c;
  font-size: 13px;
}

.tooltip-icon {
  color: #909399;
  cursor: help;
  transition: color 0.3s;
}

.tooltip-icon:hover {
  color: #409eff;
}

/* ==================== 验证码输入和按钮 ==================== */
.code-input-container {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.code-input {
  flex: 1;
}

.send-code-btn {
  border-radius: 10px;
  padding: 0 24px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.3s ease;
  min-width: 140px;
  justify-content: center;
}

.send-code-btn:not(.is-disabled):hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(64, 158, 255, 0.3);
}

.send-code-btn i {
  font-size: 14px;
}

.countdown-hint {
  margin-top: 8px;
  padding: 10px 14px;
  background: linear-gradient(135deg, #fff7e6 0%, #ffe7ba 100%);
  border-radius: 8px;
  font-size: 13px;
  color: #e6a23c;
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1px solid #f5dab1;
  animation: slideDown 0.3s ease;
}

.countdown-hint strong {
  color: #d48806;
  font-size: 15px;
  font-weight: 700;
}

.countdown-hint i {
  animation: spin 2s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

/* ==================== 2FA区域样式 ==================== */
.two-fa-section {
  margin-top: 24px;
  padding: 20px;
  background: #fff;
  border-radius: 12px;
  border: 2px dashed #409eff;
  animation: fadeIn 0.4s ease;
}

.divider-enhanced {
  margin: 0 0 20px 0;
}

.divider-enhanced :deep(.el-divider__text) {
  background: #fff;
  padding: 0 16px;
  font-weight: 600;
  color: #409eff;
  display: flex;
  align-items: center;
  gap: 8px;
}

.divider-enhanced i {
  font-size: 16px;
}

.alert-enhanced {
  margin-bottom: 20px;
  border-radius: 10px;
  padding: 12px 16px;
}

.alert-content {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
}

.alert-content i {
  font-size: 20px;
  flex-shrink: 0;
}

.two-fa-actions {
  display: flex;
  gap: 16px;
  align-items: center;
  flex-wrap: wrap;
}

.resend-link,
.backup-code-toggle {
  color: #409eff;
  font-weight: 500;
  padding: 8px 16px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  transition: all 0.3s ease;
}

.resend-link:hover,
.backup-code-toggle:hover {
  background: #ecf5ff;
  color: #66b1ff;
}

.resend-link i,
.backup-code-toggle i {
  font-size: 14px;
}

/* ==================== 对话框底部按钮 ==================== */
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.cancel-btn,
.submit-btn {
  border-radius: 10px;
  padding: 0 32px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.3s ease;
  min-width: 120px;
  justify-content: center;
}

.cancel-btn {
  border: 2px solid #dcdfe6;
}

.cancel-btn:hover {
  background: #f5f7fa;
  border-color: #c0c4cc;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.submit-btn:not(.is-disabled) {
  background: linear-gradient(135deg, #409eff 0%, #66b1ff 100%);
  border: none;
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.3);
}

.submit-btn:not(.is-disabled):hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(64, 158, 255, 0.4);
}

.submit-btn.is-disabled {
  opacity: 0.6;
  cursor: not-allowed;
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
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.slide-fade-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 1, 1);
}

.slide-fade-enter-from {
  transform: translateY(-10px);
  opacity: 0;
}

.slide-fade-leave-to {
  transform: translateY(10px);
  opacity: 0;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: scale(0.95);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* ==================== 响应式设计 ==================== */
@media (max-width: 768px) {
  .dialog-header {
    padding: 20px 24px;
  }

  :deep(.email-change-dialog .el-dialog__body) {
    padding: 24px 20px;
  }

  .captcha-container,
  .code-input-container {
    flex-direction: column;
  }

  .captcha-image-wrapper {
    width: 100%;
  }

  .send-code-btn {
    width: 100%;
  }

  .dialog-footer {
    flex-direction: column-reverse;
  }

  .cancel-btn,
  .submit-btn {
    width: 100%;
  }
  
  .two-fa-actions {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
