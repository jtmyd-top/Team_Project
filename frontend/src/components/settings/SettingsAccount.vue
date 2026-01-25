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
import { ref, reactive, computed } from 'vue';
import { useUserStore } from '../../stores/user.js';
import { apiService } from '../../services/apiService.js';
import { createDebouncedRequest, useCountdown } from '../../utils/request.js';
import { ElMessage } from 'element-plus';
import CaptchaWidget from '../common/CaptchaWidget.vue';

const userStore = useUserStore();

// 对话框显示状态
const showEmailDialog = ref(false);

// 倒计时（两个独立的倒计时）
const emailCountdown = useCountdown();  // 新邮箱验证码倒计时
const twoFaCountdown = useCountdown();  // 2FA验证码倒计时

// 验证码组件引用
const captchaWidgetRef = ref(null);

// 验证码参数（由 CaptchaWidget 更新）
const captchaParams = ref({
  captcha_type: 'turnstile',
  turnstile_token: '',
  image_captcha: ''
});

// 监听验证码变化
const onCaptchaChange = (params) => {
  captchaParams.value = params;
};

// 判断验证码是否已验证
const isCaptchaVerified = computed(() => {
  const params = captchaParams.value;
  if (params.captcha_type === 'turnstile') {
    return !!params.turnstile_token;
  }
  return params.image_captcha && params.image_captcha.length >= 4;
});

// 邮箱表单
const emailForm = reactive({
  new_email: '',
  password: '',
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
 * 刷新验证码
 */
const refreshCaptcha = () => {
  if (captchaWidgetRef.value) {
    captchaWidgetRef.value.reset();
  }
};

/**
 * 邮箱检查核心逻辑
 */
const checkEmailAvailabilityCore = async (signal) => {
  const email = (emailForm.new_email || '').trim();
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
  return EMAIL_REGEX.test((emailForm.new_email || '').trim()) &&
         emailCheck.status === 'ok' &&
         isCaptchaVerified.value;
});

/**
 * 是否可以提交表单
 */
const canSubmitEmail = computed(() => {
  if (!EMAIL_REGEX.test((emailForm.new_email || '').trim())) return false;
  if (emailCheck.status !== 'ok') return false;
  if (!(emailForm.password || '').trim()) return false;
  if (!(emailForm.code || '').trim()) return false;

  // 如果2FA已显示，则必须输入2FA代码
  if (emailForm.show2FA && !(emailForm.twoFaCode || '').trim()) return false;

  return true;
});

/**
 * 发送邮箱验证码
 */
const sendEmailCode = async () => {
  const email = (emailForm.new_email || '').trim();
  if (!EMAIL_REGEX.test(email)) return ElMessage.warning("请输入正确邮箱");
  if (emailCheck.status !== 'ok') return ElMessage.warning(emailCheck.message || "该邮箱不可用");

  // 验证验证码
  if (captchaWidgetRef.value && !captchaWidgetRef.value.validate()) {
    return;
  }

  emailForm.codeSending = true;
  try {
    const data = await apiService.sendEmailCode({
      email,
      purpose: "email_change",
      ...captchaParams.value  // 展开验证码参数
    });

    if (data.status === "success") {
      ElMessage.success({
        message: `验证码已发送至新邮箱 ${emailForm.new_email}，请查收`,
        duration: 4000
      });
      emailCountdown.start(120);
      refreshCaptcha();
    } else {
      ElMessage.error(data.message || "发送验证码失败");
      refreshCaptcha();
    }
  } catch (error) {
    ElMessage.error(error.message || "网络错误");
    refreshCaptcha();
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
      new_email: (emailForm.new_email || '').trim(),
      code: (emailForm.code || '').trim(),  // 确保验证码被正确发送
    };

    // 如果是第二步，则添加2FA详情
    if (emailForm.show2FA) {
      requestBody.two_fa_code = (emailForm.twoFaCode || '').trim();
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
      // 如果是第一步出错，刷新验证码以便重试
      if (!emailForm.show2FA) {
        refreshCaptcha();
      }
    }
  } catch (error) {
    ElMessage.error(error.message || "网络错误");
    // 网络错误时也刷新验证码
    if (!emailForm.show2FA) {
      refreshCaptcha();
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
  border-radius: 20px;
  overflow: hidden;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
}

:deep(.email-change-dialog .el-dialog__header) {
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

:deep(.email-change-dialog .el-dialog__body) {
  padding: 0;
  background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%);
}

:deep(.email-change-dialog .el-dialog__footer) {
  padding: 24px 32px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border-top: 1px solid rgba(0, 0, 0, 0.05);
}

:deep(.email-change-dialog .el-dialog__headerbtn) {
  top: 20px;
  right: 20px;
  width: 36px;
  height: 36px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 50%;
  transition: all 0.3s ease;
}

:deep(.email-change-dialog .el-dialog__headerbtn:hover) {
  background: rgba(255, 255, 255, 0.3);
  transform: rotate(90deg);
}

:deep(.email-change-dialog .el-dialog__headerbtn .el-dialog__close) {
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
.email-form {
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

.status-warning {
  color: #f59e0b;
}

/* 状态消息样式 */
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

.status-message-success {
  background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
  color: #059669;
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.status-message-error {
  background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
  color: #dc2626;
  border: 1px solid rgba(239, 68, 68, 0.3);
}

/* ==================== 验证码区域样式 ==================== */
.captcha-section {
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border-radius: 16px;
  padding: 20px;
  border: 1px solid rgba(0, 0, 0, 0.05);
  margin-bottom: 24px;
}

/* ==================== 验证码输入和按钮 ==================== */
.code-input-container {
  display: flex;
  gap: 14px;
  align-items: flex-start;
}

.code-input {
  flex: 1;
}

.send-code-btn {
  border-radius: 12px;
  padding: 0 28px;
  height: 50px;
  font-weight: 600;
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 10px;
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  min-width: 150px;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  color: #fff;
  position: relative;
  overflow: hidden;
}

.send-code-btn::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
  transition: left 0.5s ease;
}

.send-code-btn:not(.is-disabled):hover::before {
  left: 100%;
}

.send-code-btn:not(.is-disabled):hover {
  transform: translateY(-3px);
  box-shadow: 0 10px 30px rgba(102, 126, 234, 0.4);
}

.send-code-btn:not(.is-disabled):active {
  transform: translateY(-1px);
}

.send-code-btn.is-disabled {
  background: linear-gradient(135deg, #94a3b8 0%, #cbd5e1 100%);
  cursor: not-allowed;
}

.send-code-btn i {
  font-size: 16px;
}

.countdown-hint {
  margin-top: 12px;
  padding: 14px 18px;
  background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
  border-radius: 12px;
  font-size: 13px;
  color: #92400e;
  display: flex;
  align-items: center;
  gap: 10px;
  border: 1px solid rgba(245, 158, 11, 0.3);
  animation: slideUp 0.3s ease;
}

.countdown-hint strong {
  color: #b45309;
  font-size: 16px;
  font-weight: 700;
  background: linear-gradient(135deg, #f59e0b, #d97706);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.countdown-hint i {
  animation: spin 2s linear infinite;
  color: #f59e0b;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

/* ==================== 2FA区域样式 ==================== */
.two-fa-section {
  margin-top: 28px;
  padding: 24px;
  background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
  border-radius: 16px;
  border: 2px solid transparent;
  background-clip: padding-box;
  position: relative;
  animation: fadeInScale 0.4s ease;
}

.two-fa-section::before {
  content: '';
  position: absolute;
  inset: -2px;
  border-radius: 18px;
  background: linear-gradient(135deg, #667eea, #764ba2, #f093fb);
  z-index: -1;
  animation: borderGlow 3s ease infinite;
}

@keyframes borderGlow {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}

@keyframes fadeInScale {
  from { opacity: 0; transform: scale(0.95); }
  to { opacity: 1; transform: scale(1); }
}

.divider-enhanced {
  margin: 0 0 24px 0;
}

.divider-enhanced :deep(.el-divider__text) {
  background: linear-gradient(135deg, #f8fafc 0%, #ffffff 100%);
  padding: 0 20px;
  font-weight: 700;
  font-size: 15px;
  background: linear-gradient(135deg, #667eea, #764ba2);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  display: flex;
  align-items: center;
  gap: 10px;
}

.divider-enhanced :deep(.el-divider__text) i {
  -webkit-text-fill-color: #667eea;
}

.divider-enhanced i {
  font-size: 18px;
}

.alert-enhanced {
  margin-bottom: 24px;
  border-radius: 12px;
  padding: 16px 20px;
  background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
  border: 1px solid rgba(59, 130, 246, 0.3);
}

.alert-content {
  display: flex;
  align-items: center;
  gap: 14px;
  font-size: 14px;
  color: #1e40af;
}

.alert-content i {
  font-size: 24px;
  flex-shrink: 0;
  color: #3b82f6;
}

.two-fa-actions {
  display: flex;
  gap: 16px;
  align-items: center;
  flex-wrap: wrap;
  margin-top: 16px;
}

.resend-link,
.backup-code-toggle {
  color: #667eea;
  font-weight: 600;
  padding: 10px 18px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  transition: all 0.3s ease;
  background: transparent;
  border: 1px solid transparent;
}

.resend-link:hover,
.backup-code-toggle:hover {
  background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
  color: #764ba2;
  border-color: rgba(102, 126, 234, 0.3);
  transform: translateX(3px);
}

.resend-link i,
.backup-code-toggle i {
  font-size: 15px;
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
    padding: 24px 28px;
  }

  .header-icon {
    font-size: 26px;
    padding: 12px;
  }

  .header-title {
    font-size: 20px;
  }

  .email-form {
    padding: 24px 20px;
  }

  :deep(.email-change-dialog .el-dialog__body) {
    padding: 0;
  }

  .code-input-container {
    flex-direction: column;
  }

  .send-code-btn {
    width: 100%;
    height: 48px;
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

  .two-fa-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .resend-link,
  .backup-code-toggle {
    justify-content: center;
  }
}

/* ==================== 暗色模式支持 ==================== */
@media (prefers-color-scheme: dark) {
  :deep(.email-change-dialog .el-dialog__body) {
    background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%);
  }

  :deep(.email-change-dialog .el-dialog__footer) {
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

  .two-fa-section {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
  }

  .alert-enhanced {
    background: linear-gradient(135deg, #1e3a5f 0%, #1e293b 100%);
    border-color: rgba(59, 130, 246, 0.4);
  }

  .alert-content {
    color: #93c5fd;
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
