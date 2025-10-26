<template>
  <div class="settings-content-card">
    <!-- 用户名和邮箱并排 -->
    <div class="form-row">
      <!-- 用户名修改 -->
      <div class="form-section">
        <h3 class="form-section-title">用户名</h3>
        <el-form label-position="left" label-width="100px">
          <el-form-item label="用户名">
            <el-input 
              v-model="userStore.nickname" 
              placeholder="至少6位，以小写字母开头">
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
      </div>

      <!-- 邮箱设置 -->
      <div class="form-section">
        <h3 class="form-section-title">邮箱地址</h3>
        <el-form label-position="left" label-width="100px">
          <el-form-item label="邮箱">
            <el-input 
              v-model="tempEmail" 
              placeholder="请输入新的邮箱地址">
              <template #append>
                <el-button 
                  type="primary" 
                  :disabled="!emailChanged"
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

    <!-- 个性签名 -->
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
      width="500px"
      @close="resetEmailForm">
      
      <el-form label-position="top">
        <el-form-item label="新邮箱地址">
          <el-input
            v-model="emailForm.new_email"
            placeholder="请输入新的邮箱地址"
            @input="checkEmailAvailability">
            <template #suffix>
              <i v-if="emailCheck.status === 'ok'" class="fas fa-check-circle" style="color: #67C23A;"></i>
              <i v-else-if="emailCheck.status === 'taken'" class="fas fa-times-circle" style="color: #F56C6C;"></i>
              <i v-else-if="emailCheck.status === 'invalid'" class="fas fa-exclamation-circle" style="color: #E6A23C;"></i>
            </template>
          </el-input>
          <div v-if="emailCheck.message" class="form-hint" :style="{ color: emailCheck.status === 'ok' ? '#67C23A' : '#F56C6C' }">
            {{ emailCheck.message }}
          </div>
        </el-form-item>

        <el-form-item label="当前密码">
          <el-input
            v-model="emailForm.password"
            type="password"
            placeholder="请输入当前密码"
            show-password>
          </el-input>
        </el-form-item>

        <el-form-item label="图片验证码">
          <div style="display: flex; gap: 12px;">
            <el-input
              v-model="emailForm.imageCaptcha"
              placeholder="请输入图片验证码"
              style="flex: 1;">
            </el-input>
            <img 
              :src="captchaUrl" 
              @click="refreshCaptcha" 
              style="height: 40px; cursor: pointer; border-radius: 4px;">
          </div>
        </el-form-item>

        <el-form-item label="邮箱验证码">
          <div style="display: flex; gap: 12px;">
            <el-input
              v-model="emailForm.code"
              placeholder="请输入邮箱验证码"
              style="flex: 1;">
            </el-input>
            <el-button
              type="primary"
              :disabled="!canSendCode || emailCountdown.counting"
              :loading="emailForm.codeSending"
              @click="sendEmailCode">
              {{ emailCountdown.counting ? `${emailCountdown.seconds}秒` : '发送验证码' }}
            </el-button>
          </div>
        </el-form-item>

        <!-- 2FA验证（如果需要） -->
        <div v-if="emailForm.show2FA">
          <el-divider>需要两因素验证</el-divider>
          
          <el-alert
            type="info"
            :closable="false"
            style="margin-bottom: 16px;">
            {{ emailForm.twoFaMethod === 'totp' 
              ? '请输入验证器应用中的6位验证码' 
              : '验证码已发送到您的邮箱，请查收' }}
          </el-alert>

          <el-form-item :label="emailForm.useBackup ? '备用验证码' : '验证码'">
            <el-input
              v-model="emailForm.twoFaCode"
              :placeholder="emailForm.useBackup ? '请输入8位备用码' : '请输入6位验证码'"
              maxlength="8">
            </el-input>
          </el-form-item>

          <el-button
            v-if="emailForm.twoFaMethod === 'email'"
            type="text"
            size="small"
            :loading="emailForm.twoFaCodeSending"
            @click="sendEmail2faCode">
            重新发送验证码
          </el-button>

          <el-button
            type="text"
            size="small"
            @click="toggleEmailBackupCode">
            {{ emailForm.useBackup ? '使用验证器' : '使用备用验证码' }}
          </el-button>
        </div>
      </el-form>

      <template #footer>
        <el-button @click="showEmailDialog = false">取消</el-button>
        <el-button 
          type="primary" 
          :disabled="!canSubmitEmail"
          @click="changeEmail">
          确认修改
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, nextTick, onUnmounted } from 'vue';
import { useUserStore } from '../../stores/user.js';
import { apiService } from '../../services/apiService.js';
import { createDebouncedRequest, useCountdown } from '../../utils/request.js';
import { ElMessage } from 'element-plus';

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

// 临时邮箱（用于输入新邮箱）
const tempEmail = ref(userStore.email);

// 邮箱是否改变
const emailChanged = computed(() => {
  return tempEmail.value.trim() !== userStore.email && 
         EMAIL_REGEX.test(tempEmail.value.trim());
});

/**
 * 打开邮箱修改对话框
 */
const openEmailChangeDialog = async () => {
  if (emailChanged.value) {
    emailForm.new_email = tempEmail.value.trim();
    showEmailDialog.value = true;
    // 立即触发邮箱可用性检查（不使用防抖）
    await checkEmailAvailabilityCore();
  }
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
    const data = await apiService.updateProfile({ bio: bioDraft.value });
    if (data.status === "success") {
      userStore.updateBio(data.bio);
      bioDraft.value = data.bio;
      bioEditing.value = false;
      ElMessage.success("个性签名已保存");
    } else {
      ElMessage.error(data.message || "保存失败");
    }
  } catch (error) {
    ElMessage.error(error.message || "网络错误");
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
    const data = await apiService.checkUsername(nickname);
    if (data.is_taken) {
      ElMessage.error("用户名已被占用，请换一个");
      return false;
    }
  } catch (err) {
    ElMessage.error("无法检查用户名，请稍后再试");
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
    const data = await apiService.updateProfile({ nickname: userStore.nickname });
    if (data.status === "success") {
      userStore.updateNickname(data.nickname);
      ElMessage.success("用户名修改成功");
    } else {
      ElMessage.error(data.message || "更新失败");
    }
  } catch (error) {
    ElMessage.error(error.message || "网络错误");
  } finally {
    profileSaving.value = false;
  }
};

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
  if (!emailForm.imageCaptcha.trim()) return false;
  if (!emailForm.code.trim()) return false;
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
      ElMessage.success("验证码已发送到新邮箱");
      emailCountdown.start(60);
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
  if (emailCheck.status !== 'ok') return ElMessage.warning(emailCheck.message || "该邮箱不可用");
  if (!emailForm.password) return ElMessage.warning("请输入当前密码");
  if (!emailForm.imageCaptcha) return ElMessage.warning("请输入图片验证码");
  if (!emailForm.code) return ElMessage.warning("请输入邮箱验证码");

  if (emailForm.show2FA && !emailForm.twoFaCode) {
    return ElMessage.warning("请输入两因素验证码");
  }

  try {
    const requestBody = {
      password: emailForm.password,
      new_email: emailForm.new_email.trim(),
      code: emailForm.code.trim(),
      image_captcha_code: emailForm.imageCaptcha.trim(),
    };

    if (emailForm.show2FA) {
      requestBody.two_fa_code = emailForm.twoFaCode;
      requestBody.use_backup = emailForm.useBackup;
    }

    const data = await apiService.updateEmail(requestBody);

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
    ElMessage.error(error.message || "网络错误");
  } finally {
    if (!emailForm.show2FA) {
      refreshCaptcha();
      emailForm.imageCaptcha = "";
    }
  }
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
  tempEmail.value = userStore.email; // 重置为当前邮箱
  refreshCaptcha();
};

/**
 * 发送邮箱修改2FA验证码
 */
const sendEmail2faCode = async () => {
  emailForm.twoFaCodeSending = true;
  try {
    const data = await apiService.sendOperation2FA();
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
.settings-content-card {
  background: white;
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

/* 表单行 - 并排布局 */
.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  margin-bottom: 24px;
}

@media (max-width: 768px) {
  .form-row {
    grid-template-columns: 1fr;
  }
}

/* 表单区域 */
.form-section {
  margin-bottom: 32px;
}

.form-section-title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 16px;
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
</style>
