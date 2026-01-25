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
import { ref, reactive, computed, nextTick, onUnmounted } from 'vue';
import { useUserStore } from '../../stores/user.js';
// apiService 已经挂载到 window 对象上
import { createDebouncedRequest, useCountdown } from '../../utils/request.js';
import { ElMessage } from 'element-plus';
import CaptchaWidget from '../common/CaptchaWidget.vue';

const userStore = useUserStore();

// API端点和CSRF令牌
const API_ENDPOINTS = window.API_ENDPOINTS || {};
const csrfHeader = { "X-CSRFToken": window.SETTINGS_INITIAL?.csrfToken || "" };

// 加载状态
const bioSaving = ref(false);
const profileSaving = ref(false);

// 个性签名编辑
const bioEditing = ref(false);
const bioDraft = ref(userStore.bio || "");

// 邮箱对话框
const showEmailDialog = ref(false);

// 倒计时
const emailCountdown = useCountdown();

// 验证码组件引用
const captchaWidgetRef = ref(null);

// 验证码参数
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

// 刷新验证码
const refreshCaptcha = () => {
  if (captchaWidgetRef.value) {
    captchaWidgetRef.value.reset();
  }
};


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

// 临时邮箱（用于输入新邮箱）
const tempEmail = ref(userStore.email);

// 邮箱是否改变
const emailChanged = computed(() => {
  return (tempEmail.value || '').trim() !== userStore.email &&
         EMAIL_REGEX.test((tempEmail.value || '').trim());
});

/**
 * 打开邮箱修改对话框
 */
const openEmailChangeDialog = async () => {
  // 检查邮箱是否有效改变
  if (!emailChanged.value) {
    ElMessage.warning('请先输入新的邮箱地址');
    return;
  }

  emailForm.new_email = (tempEmail.value || '').trim();
  showEmailDialog.value = true;
  // 立即触发邮箱可用性检查（不使用防抖）
  await checkEmailAvailabilityCore();
};

/**
 * 编辑个性签名
 */
const editBio = () => {
  bioDraft.value = userStore.bio || "";
  bioEditing.value = true;
};

/**
 * 取消编辑
 */
const cancelBio = () => {
  bioDraft.value = userStore.bio || "";
  bioEditing.value = false;
};

/**
 * 保存个性签名
 */
const saveBio = async () => {
  if (bioSaving.value) return;

  bioSaving.value = true;
  try {
    const data = await window.apiService.updateProfile({ bio: bioDraft.value });
    if (data.status === "success") {
      userStore.updateBio(data.bio);
      bioDraft.value = data.bio;
      bioEditing.value = false;
      ElMessage.success("个性签名已保存");
    } else {
      ElMessage.error(data.message || "保存失败");
    }
  } catch (error) {
    console.error('操作失败:', error);
    // 更全面的错误处理
    if (error.response?.data) {
      const data = error.response.data;
      if (data.error) {
        ElMessage.error(data.error);
      } else if (data.message) {
        ElMessage.error(data.message);
      } else if (typeof data === 'object' && data !== null) {
        // 处理字段验证错误
        const errors = [];
        for (const [field, messages] of Object.entries(data)) {
          if (Array.isArray(messages)) {
            errors.push(`${field}: ${messages.join(', ')}`);
          } else {
            errors.push(`${field}: ${messages}`);
          }
        }
        ElMessage.error(errors.join('; '));
      } else {
        ElMessage.error("操作失败");
      }
    } else {
      ElMessage.error(error.message || "网络错误");
    }
  } finally {
    bioSaving.value = false;
  }
};

/**
 * 验证用户名
 */
const validateUsername = async (nickname) => {
  const usernameRegex = /^[a-z][a-z0-9_]{5,}$/;
  if (!usernameRegex.test(nickname)) {
    ElMessage.warning("用户名至少6位，以小写字母开头，只能包含字母、数字和下划线");
    return false;
  }

  try {
    const data = await window.apiService.auth.checkUsername(nickname);
    if (data.is_taken) {
      ElMessage.error("用户名已被占用，请换一个");
      return false;
    }
  } catch (err) {
    console.error('检查用户名失败:', err);
    ElMessage.error(err.message || "无法检查用户名，请稍后再试");
    return false;
  }

  return true;
};

/**
 * 保存用户名
 */
const saveProfile = async () => {
  if (!await validateUsername(userStore.nickname)) return;
  if (profileSaving.value) return;

  profileSaving.value = true;
  try {
    const data = await window.apiService.updateProfile({ nickname: userStore.nickname });
    if (data.status === "success") {
      userStore.updateNickname(data.nickname);
      ElMessage.success("用户名修改成功");
    } else {
      ElMessage.error(data.message || "更新失败");
    }
  } catch (error) {
    console.error('操作失败:', error);
    // 更全面的错误处理
    if (error.response?.data) {
      const data = error.response.data;
      if (data.error) {
        ElMessage.error(data.error);
      } else if (data.message) {
        ElMessage.error(data.message);
      } else if (typeof data === 'object' && data !== null) {
        // 处理字段验证错误
        const errors = [];
        for (const [field, messages] of Object.entries(data)) {
          if (Array.isArray(messages)) {
            errors.push(`${field}: ${messages.join(', ')}`);
          } else {
            errors.push(`${field}: ${messages}`);
          }
        }
        ElMessage.error(errors.join('; '));
      } else {
        ElMessage.error("操作失败");
      }
    } else {
      ElMessage.error(error.message || "网络错误");
    }
  } finally {
    profileSaving.value = false;
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
    const data = await window.apiService.auth.checkEmail(email, true);
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
  return true;
});

/**
 * 发送邮箱验证码
 */
const sendEmailCode = async () => {
  const email = (emailForm.new_email || '').trim();
  if (!EMAIL_REGEX.test(email)) return ElMessage.warning("请输入正确邮箱");
  if (emailCheck.status !== 'ok') return ElMessage.warning(emailCheck.message || "该邮箱不可用");

  // 验证人机验证
  if (captchaWidgetRef.value && !captchaWidgetRef.value.validate()) {
    return;
  }

  emailForm.codeSending = true;
  try {
    const data = await window.apiService.auth.sendEmailCode({
      email,
      purpose: "email_change",
      ...captchaParams.value  // 展开验证码参数
    });

    if (data.status === "success") {
      ElMessage.success("验证码已发送到新邮箱");
      emailCountdown.start(60);
      refreshCaptcha();  // 发送成功后刷新验证码
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
  if (emailCheck.status !== 'ok') return ElMessage.warning(emailCheck.message || "该邮箱不可用");
  if (!emailForm.password) return ElMessage.warning("请输入当前密码");
  if (!emailForm.code) return ElMessage.warning("请输入邮箱验证码");

  if (emailForm.show2FA && !emailForm.twoFaCode) {
    return ElMessage.warning("请输入两因素验证码");
  }

  try {
    const requestBody = {
      password: emailForm.password,
      new_email: (emailForm.new_email || '').trim(),
      code: (emailForm.code || '').trim(),
    };

    if (emailForm.show2FA) {
      requestBody.two_fa_code = emailForm.twoFaCode;
      requestBody.use_backup = emailForm.useBackup;
    }

    const data = await window.apiService.updateEmail(requestBody);

    if (data.status === "require_2fa") {
      emailForm.show2FA = true;
      emailForm.twoFaMethod = data.method;

      if (data.method === 'email') {
        await sendEmail2faCode();
      } else {
        ElMessage.info("请输入验证器应用中的验证码");
      }
    } else if (data.status === "success") {
      userStore.updateEmail(data.email);
      tempEmail.value = data.email; // 更新临时邮箱为新邮箱
      showEmailDialog.value = false;
      resetEmailForm();
      ElMessage.success("邮箱修改成功");
    } else {
      ElMessage.error(data.message || "邮箱修改失败");
    }
  } catch (error) {
    console.error('操作失败:', error);
    // 更全面的错误处理
    if (error.response?.data) {
      const data = error.response.data;
      if (data.error) {
        ElMessage.error(data.error);
      } else if (data.message) {
        ElMessage.error(data.message);
      } else if (typeof data === 'object' && data !== null) {
        // 处理字段验证错误
        const errors = [];
        for (const [field, messages] of Object.entries(data)) {
          if (Array.isArray(messages)) {
            errors.push(`${field}: ${messages.join(', ')}`);
          } else {
            errors.push(`${field}: ${messages}`);
          }
        }
        ElMessage.error(errors.join('; '));
      } else {
        ElMessage.error("操作失败");
      }
    } else {
      ElMessage.error(error.message || "网络错误");
    }
  }
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
  tempEmail.value = userStore.email; // 重置为当前邮箱
  refreshCaptcha();  // 重置验证码
};

/**
 * 发送邮箱修改2FA验证码
 */
const sendEmail2faCode = async () => {
  emailForm.twoFaCodeSending = true;
  try {
    const data = await window.apiService.auth.sendOperation2FA();
    if (data.status === "success" && data.requires_2fa) {
      ElMessage.success("验证码已发送至您的邮箱");
    }
  } catch (error) {
    ElMessage.error(error.message || "发送验证码失败");
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
  ElMessage.info(emailForm.useBackup 
    ? "已切换到备用验证码模式，请输入8位备用码" 
    : "已切换回验证器模式，请输入6位验证码");
};
</script>

<style scoped>
.profile-settings-container {
  /* 移除 flex 布局，让 form-section 自然堆叠 */
}

/* 表单区域 - 这是分层卡片的核心 */
.form-section {
  padding: 24px;
  border-radius: 8px;
}

/* 奇数区域为白色，偶数区域为浅灰 */
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
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e4e7ed;
}

/* 表单行 - 并排布局 */
.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}

@media (max-width: 768px) {
  .form-row {
    grid-template-columns: 1fr;
  }
}

.form-hint {
  color: #909399;
  font-size: 12px;
  margin-top: 4px;
}

/* 邮箱显示 */
.email-display {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
}

.email-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.email-info label {
  font-weight: 500;
  color: #606266;
}

.email-value {
  color: #303133;
  font-family: monospace;
  word-break: break-all;
}

/* 个性签名显示 */
.bio-display {
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
}

.bio-display p {
  margin: 0 0 12px 0;
  color: #606266;
  line-height: 1.6;
}

.bio-edit {
  max-width: 100%;
}

/* 强制覆盖 Element Plus 输入框组的 append 按钮样式 */
.form-section :deep(.el-input-group__append) {
  background-color: transparent !important;
  border: none !important;
  padding: 0 !important;
}

.form-section :deep(.el-input-group__append .el-button) {
  background-color: #409EFF !important;
  color: #ffffff !important;
  border-color: #409EFF !important;
  margin: 0 !important;
}

.form-section :deep(.el-input-group__append .el-button:hover) {
  background-color: #66b1ff !important;
  border-color: #66b1ff !important;
}

/* 增加输入框高度 */
.form-section :deep(.el-input__wrapper) {
  min-height: 48px !important;
  padding: 8px 12px !important;

}

.form-section :deep(.el-input__inner) {
  height: 32px !important;
  line-height: 32px !important;
}

/* 确保 textarea 也有合适的高度 */
.form-section :deep(.el-textarea__inner) {
  min-height: 100px !important;
  padding: 12px !important;
}

/* 输入框动画效果 */
.form-section :deep(.el-input__wrapper) {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
  border: 1px solid #dcdfe6 !important;
}

.form-section :deep(.el-input__wrapper:hover) {
  border-color: #c0c4cc !important;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08) !important;
  transform: translateY(-1px);
}

.form-section :deep(.el-input__wrapper.is-focus) {
  border-color: #409EFF !important;
  box-shadow: 0 0 0 3px rgba(64, 158, 255, 0.15) !important;
  transform: translateY(-1px);
}

/* Textarea 动画效果 */
.form-section :deep(.el-textarea__inner) {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
  border: 1px solid #dcdfe6 !important;
}

.form-section :deep(.el-textarea__inner:hover) {
  border-color: #c0c4cc !important;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08) !important;
}

.form-section :deep(.el-textarea__inner:focus) {
  border-color: #409EFF !important;
  box-shadow: 0 0 0 3px rgba(64, 158, 255, 0.15) !important;
}

/* 按钮悬停动画 */
.form-section :deep(.el-button) {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

.form-section :deep(.el-button:hover) {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.3) !important;
}

.form-section :deep(.el-button:active) {
  transform: translateY(0);
  box-shadow: 0 2px 4px rgba(64, 158, 255, 0.2) !important;
}

/* ==================== 邮箱修改弹窗样式 ==================== */
:deep(.email-change-dialog) {
  border-radius: 20px;
  overflow: hidden;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
}

:deep(.email-change-dialog .el-dialog__header) {
  padding: 0;
  margin: 0;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

:deep(.email-change-dialog .el-dialog__body) {
  padding: 0;
  background: #f8fafc;
}

:deep(.email-change-dialog .el-dialog__footer) {
  padding: 20px 32px 24px;
  background: #fff;
  border-top: 1px solid #e4e7ed;
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

/* 弹窗头部 */
.dialog-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 28px 32px;
  color: #fff;
}

.header-icon-wrapper {
  width: 56px;
  height: 56px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(10px);
}

.header-icon-wrapper i {
  font-size: 26px;
}

.header-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.header-title {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: 0.5px;
}

.header-subtitle {
  font-size: 13px;
  opacity: 0.85;
}

/* 弹窗内容 */
.dialog-body {
  padding: 28px 32px;
}

.email-form {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.form-item-enhanced {
  margin-bottom: 20px;
}

.form-item-enhanced :deep(.el-form-item__label) {
  font-weight: 600;
  color: #303133;
  font-size: 14px;
  margin-bottom: 8px;
}

/* 增强输入框 */
.enhanced-input :deep(.el-input__wrapper) {
  border-radius: 12px;
  padding: 14px 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  border: 2px solid #e4e7ed;
  transition: all 0.3s ease;
  background: #fff;
}

.enhanced-input :deep(.el-input__wrapper:hover) {
  border-color: #c0c4cc;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.enhanced-input :deep(.el-input__wrapper.is-focus) {
  border-color: #667eea;
  box-shadow: 0 4px 16px rgba(102, 126, 234, 0.2);
}

.input-icon {
  color: #909399;
  font-size: 16px;
  margin-right: 4px;
}

/* 状态图标 */
.status-icon {
  font-size: 18px;
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

/* 状态消息 */
.status-message {
  margin-top: 8px;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-success-msg {
  background: linear-gradient(135deg, #f0f9eb 0%, #e1f3d8 100%);
  color: #67c23a;
  border: 1px solid #c2e7b0;
}

.status-error-msg {
  background: linear-gradient(135deg, #fef0f0 0%, #fde2e2 100%);
  color: #f56c6c;
  border: 1px solid #fbc4c4;
}

/* 验证码容器 */
.captcha-container {
  background: linear-gradient(135deg, #f5f7fa 0%, #e8ebf0 100%);
  border-radius: 12px;
  padding: 16px;
  border: 1px dashed #dcdfe6;
}

/* 验证码输入容器 */
.code-input-container {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.code-input {
  flex: 1;
}

/* 发送验证码按钮 */
.send-code-btn {
  border-radius: 12px;
  padding: 0 24px;
  height: 50px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.3s ease;
  min-width: 130px;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
}

.send-code-btn:not(.is-disabled):hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(102, 126, 234, 0.4);
}

.send-code-btn.is-disabled {
  background: linear-gradient(135deg, #a0a0a0 0%, #c0c0c0 100%);
}

/* 2FA 区域 */
.two-fa-section {
  margin-top: 20px;
  padding: 20px;
  background: #fff;
  border-radius: 12px;
  border: 2px solid #667eea;
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-10px); }
  to { opacity: 1; transform: translateY(0); }
}

.divider-enhanced {
  margin: 0 0 20px 0;
}

.divider-enhanced :deep(.el-divider__text) {
  background: #fff;
  padding: 0 16px;
  font-weight: 600;
  color: #667eea;
  display: flex;
  align-items: center;
  gap: 8px;
}

.alert-enhanced {
  margin-bottom: 20px;
  border-radius: 10px;
}

.alert-content {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
}

.alert-content i {
  font-size: 20px;
}

.two-fa-actions {
  display: flex;
  gap: 16px;
  align-items: center;
  flex-wrap: wrap;
}

/* 弹窗底部 */
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.cancel-btn,
.submit-btn {
  border-radius: 12px;
  padding: 0 28px;
  height: 46px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.3s ease;
}

.cancel-btn {
  background: #f5f7fa;
  border: 2px solid #dcdfe6;
  color: #606266;
}

.cancel-btn:hover {
  background: #e9ecef;
  border-color: #c0c4cc;
  transform: translateY(-2px);
}

.submit-btn:not(.is-disabled) {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  color: #fff;
  box-shadow: 0 4px 15px rgba(102, 126, 234, 0.35);
}

.submit-btn:not(.is-disabled):hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(102, 126, 234, 0.45);
}

.submit-btn.is-disabled {
  background: #e4e7ed;
  color: #a8abb2;
}

/* 动画 */
.slide-fade-enter-active {
  transition: all 0.3s ease;
}

.slide-fade-leave-active {
  transition: all 0.2s ease;
}

.slide-fade-enter-from,
.slide-fade-leave-to {
  transform: translateY(-10px);
  opacity: 0;
}

/* 响应式 */
@media (max-width: 768px) {
  .dialog-header {
    padding: 20px 24px;
  }

  .dialog-body {
    padding: 20px 24px;
  }

  .code-input-container {
    flex-direction: column;
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
}
</style>
