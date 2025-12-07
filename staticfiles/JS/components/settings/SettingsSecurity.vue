<template>
  <div>
    <!-- 修改密码 -->
    <div class="form-section">
      <h3 class="form-section-title">
        <i class="fas fa-key"></i> 修改密码
      </h3>
      <el-button type="primary" @click="showPasswordDialog = true">
        修改密码
      </el-button>
    </div>

    <!-- 两因素认证 -->
    <div class="form-section">
      <h3 class="form-section-title">
        <i class="fas fa-shield-alt"></i> 两因素认证
      </h3>
      
      <div v-if="!userStore.two_fa_enabled" class="security-status">
        <el-alert type="warning" :closable="false">
          <template #title>
            两因素认证未启用
          </template>
          <p>启用两因素认证可以为您的账户提供额外的安全保护</p>
        </el-alert>
        
        <div class="security-actions">
          <el-button type="primary" @click="show2faSetupDialog = true">
            启用两因素认证
          </el-button>
        </div>
      </div>

      <div v-else class="security-status">
        <el-alert type="success" :closable="false">
          <template #title>
            两因素认证已启用
          </template>
          <p>
            当前使用的方式：
            <strong>{{ userStore.two_fa_method === 'totp' ? '验证器应用' : '邮箱验证' }}</strong>
          </p>
        </el-alert>

        <div class="security-actions">
          <el-button @click="showBackupCodesDialog = true">
            管理备用验证码
          </el-button>
          <el-button type="danger" @click="show2faDisableDialog = true">
            禁用两因素认证
          </el-button>
        </div>
      </div>
    </div>

    <!-- 修改密码对话框 -->
    <el-dialog
      v-model="showPasswordDialog"
      title="修改密码"
      width="500px"
      @close="resetPasswordForm">
      
      <el-form label-position="top">
        <el-form-item label="当前密码">
          <el-input
            v-model="passwordForm.current"
            type="password"
            placeholder="请输入当前密码"
            show-password>
          </el-input>
        </el-form-item>

        <el-form-item label="新密码">
          <el-input
            v-model="passwordForm.new"
            type="password"
            placeholder="至少8位字符"
            show-password>
          </el-input>
        </el-form-item>

        <el-form-item label="确认新密码">
          <el-input
            v-model="passwordForm.confirm"
            type="password"
            placeholder="再次输入新密码"
            show-password>
          </el-input>
        </el-form-item>

        <!-- 2FA验证（如果需要） -->
        <div v-if="passwordForm.show2FA">
          <el-divider>需要两因素验证</el-divider>
          
          <el-alert
            type="info"
            :closable="false"
            style="margin-bottom: 16px;">
            {{ passwordForm.twoFaMethod === 'totp' 
              ? '请输入验证器应用中的6位验证码' 
              : '验证码已发送到您的邮箱，请查收' }}
          </el-alert>

          <el-form-item :label="passwordForm.useBackup ? '备用验证码' : '验证码'">
            <el-input
              v-model="passwordForm.twoFaCode"
              :placeholder="passwordForm.useBackup ? '请输入8位备用码' : '请输入6位验证码'"
              maxlength="8">
            </el-input>
          </el-form-item>

          <el-button
            v-if="passwordForm.twoFaMethod === 'email'"
            type="text"
            size="small"
            :loading="passwordForm.twoFaCodeSending"
            @click="sendPassword2faCode">
            重新发送验证码
          </el-button>

          <el-button
            type="text"
            size="small"
            @click="togglePasswordBackupCode">
            {{ passwordForm.useBackup ? '使用验证器' : '使用备用验证码' }}
          </el-button>
        </div>
      </el-form>

      <template #footer>
        <el-button @click="showPasswordDialog = false">取消</el-button>
        <el-button type="primary" @click="changePassword">
          确认修改
        </el-button>
      </template>
    </el-dialog>

    <!-- 启用2FA对话框 -->
    <el-dialog
      v-model="show2faSetupDialog"
      title="启用两因素认证"
      width="500px"
      @close="cancel2faSetup">
      
      <!-- 选择2FA方式 -->
      <div v-if="!twoFaSetup.step">
        <p style="margin-bottom: 24px; color: #606266;">
          选择您希望使用的两因素认证方式：
        </p>
        
        <div class="twofa-method-grid">
          <div class="twofa-method-card" @click="start2faSetup('totp')">
            <i class="fas fa-mobile-alt"></i>
            <h4>验证器应用</h4>
            <p>使用 Google Authenticator、Authy 等应用</p>
          </div>
          
          <div class="twofa-method-card" @click="start2faSetup('email')">
            <i class="fas fa-envelope"></i>
            <h4>邮箱验证</h4>
            <p>通过邮箱接收验证码</p>
          </div>
        </div>
      </div>

      <!-- TOTP设置流程 -->
      <div v-if="twoFaSetup.step === 'totp-scan'">
        <el-steps :active="0" finish-status="success" style="margin-bottom: 24px;">
          <el-step title="扫描二维码"></el-step>
          <el-step title="验证"></el-step>
          <el-step title="保存备用码"></el-step>
        </el-steps>

        <div class="qr-code-section">
          <p style="margin-bottom: 16px;">
            使用验证器应用扫描下方二维码：
          </p>
          <div class="qr-code-container">
            <img :src="twoFaSetup.qrCode" alt="QR Code">
          </div>
          <p style="margin-top: 16px; color: #909399; font-size: 13px;">
            密钥：<code>{{ twoFaSetup.secret }}</code>
          </p>
        </div>

        <el-form style="margin-top: 24px;">
          <el-form-item label="验证码">
            <el-input
              v-model="twoFaSetup.verifyCode"
              placeholder="请输入6位验证码"
              maxlength="6">
            </el-input>
          </el-form-item>
        </el-form>
      </div>

      <!-- 备用验证码 -->
      <div v-if="twoFaSetup.step === 'backup-codes'">
        <el-steps :active="2" finish-status="success" style="margin-bottom: 24px;">
          <el-step title="扫描二维码"></el-step>
          <el-step title="验证"></el-step>
          <el-step title="保存备用码"></el-step>
        </el-steps>

        <el-alert type="warning" :closable="false" style="margin-bottom: 16px;">
          <template #title>
            请妥善保存备用验证码
          </template>
          <p>这些备用码只会显示一次，请将它们保存在安全的地方</p>
        </el-alert>

        <div class="backup-codes-container">
          <div v-for="code in twoFaSetup.backupCodes" :key="code" class="backup-code">
            {{ code }}
          </div>
        </div>

        <div style="margin-top: 16px; text-align: center;">
          <el-button type="primary" @click="copyBackupCodes">
            <i class="fas fa-copy"></i> 复制备用码
          </el-button>
        </div>
      </div>

      <!-- Footer必须是el-dialog的直接子元素 -->
      <template #footer>
        <div v-if="!twoFaSetup.step">
          <el-button @click="cancel2faSetup">取消</el-button>
        </div>
        <div v-else-if="twoFaSetup.step === 'totp-scan'">
          <el-button @click="cancel2faSetup">取消</el-button>
          <el-button type="primary" @click="verify2faSetup">
            验证并继续
          </el-button>
        </div>
        <div v-else-if="twoFaSetup.step === 'backup-codes'">
          <el-button type="primary" @click="finish2faSetup">
            我已保存，完成设置
          </el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 禁用2FA对话框 -->
    <el-dialog
      v-model="show2faDisableDialog"
      title="禁用两因素认证"
      width="400px">
      
      <el-alert type="warning" :closable="false" style="margin-bottom: 16px;">
        禁用两因素认证将降低您账户的安全性
      </el-alert>

      <el-form label-position="top">
        <el-form-item label="请输入密码确认">
          <el-input
            v-model="twoFaDisable.password"
            type="password"
            placeholder="请输入您的密码"
            show-password>
          </el-input>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="show2faDisableDialog = false">取消</el-button>
        <el-button type="danger" @click="disable2fa">
          确认禁用
        </el-button>
      </template>
    </el-dialog>

    <!-- 备用码管理对话框 -->
    <el-dialog
      v-model="showBackupCodesDialog"
      title="管理备用验证码"
      width="500px"
      @close="closeBackupCodesDialog">
      
      <div v-if="!backupCodes.newCodes">
        <p style="margin-bottom: 16px; color: #606266;">
          重新生成备用验证码将使旧的备用码失效
        </p>

        <el-form label-position="top">
          <el-form-item label="请输入密码确认">
            <el-input
              v-model="backupCodes.password"
              type="password"
              placeholder="请输入您的密码"
              show-password>
            </el-input>
          </el-form-item>
        </el-form>

        <el-button type="primary" @click="regenerateBackupCodes">
          重新生成备用码
        </el-button>
      </div>

      <div v-else>
        <el-alert type="success" :closable="false" style="margin-bottom: 16px;">
          备用验证码已重新生成
        </el-alert>

        <div class="backup-codes-container">
          <div v-for="code in backupCodes.newCodes" :key="code" class="backup-code">
            {{ code }}
          </div>
        </div>

        <div style="margin-top: 16px; text-align: center;">
          <el-button type="primary" @click="copyNewBackupCodes">
            <i class="fas fa-copy"></i> 复制备用码
          </el-button>
        </div>
      </div>

      <template #footer>
        <el-button @click="closeBackupCodesDialog">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue';
import { useUserStore } from '../../stores/user.js';
import { apiService } from '../../services/apiService.js';
import { ElMessage } from 'element-plus';

const userStore = useUserStore();

// 添加调试日志
onMounted(() => {
  console.log('=== 安全设置页面调试信息 ===');
  console.log('window.SETTINGS_INITIAL:', window.SETTINGS_INITIAL);
  console.log('userStore.two_fa_enabled:', userStore.two_fa_enabled);
  console.log('userStore.two_fa_method:', userStore.two_fa_method);
  console.log('============================');
});

// 对话框显示状态
const showPasswordDialog = ref(false);
const show2faSetupDialog = ref(false);
const show2faDisableDialog = ref(false);
const showBackupCodesDialog = ref(false);

// 修改密码表单
const passwordForm = reactive({
  current: '',
  new: '',
  confirm: '',
  show2FA: false,
  twoFaMethod: '',
  twoFaCode: '',
  useBackup: false,
  twoFaCodeSending: false,
});

// 2FA设置
const twoFaSetup = reactive({
  step: null,
  method: null,
  qrCode: '',
  secret: '',
  verifyCode: '',
  backupCodes: [],
});

// 2FA禁用
const twoFaDisable = reactive({
  password: '',
});

// 备用码管理
const backupCodes = reactive({
  password: '',
  newCodes: null,
});

/**
 * 修改密码
 */
const changePassword = async () => {
  if (!passwordForm.current) return ElMessage.warning("请输入当前密码");
  if (!passwordForm.new) return ElMessage.warning("请输入新密码");
  if (!passwordForm.confirm) return ElMessage.warning("请确认新密码");
  if (passwordForm.new !== passwordForm.confirm) return ElMessage.warning("两次输入的密码不一致");
  if (passwordForm.new.length < 8) return ElMessage.warning("新密码至少8位");
  
  // 检查新密码是否与旧密码相同
  if (passwordForm.current === passwordForm.new) {
    return ElMessage.warning("新密码不能与旧密码一致");
  }

  if (passwordForm.show2FA && !passwordForm.twoFaCode) {
    return ElMessage.warning("请输入两因素验证码");
  }

  try {
    const requestBody = {
      current_password: passwordForm.current,
      new_password: passwordForm.new,
      confirm_password: passwordForm.confirm,
    };

    if (passwordForm.show2FA) {
      requestBody.two_fa_code = passwordForm.twoFaCode;
      requestBody.use_backup = passwordForm.useBackup;
    }

    const data = await apiService.changePassword(requestBody);

    if (data.status === "require_2fa") {
      passwordForm.show2FA = true;
      passwordForm.twoFaMethod = data.method;

      if (data.method === 'email') {
        await sendPassword2faCode();
      } else {
        ElMessage.info("请输入验证器应用中的验证码");
      }
    } else if (data.status === "success") {
      ElMessage.success("密码修改成功");
      showPasswordDialog.value = false;
      resetPasswordForm();
    } else {
      ElMessage.error(data.message || "密码修改失败");
    }
  } catch (error) {
    ElMessage.error(error.message || "网络错误");
  }
};

/**
 * 重置密码表单
 */
const resetPasswordForm = () => {
  passwordForm.current = '';
  passwordForm.new = '';
  passwordForm.confirm = '';
  passwordForm.show2FA = false;
  passwordForm.twoFaCode = '';
  passwordForm.twoFaMethod = '';
  passwordForm.useBackup = false;
};

/**
 * 发送密码修改2FA验证码
 */
const sendPassword2faCode = async () => {
  passwordForm.twoFaCodeSending = true;
  try {
    const data = await apiService.sendOperation2FA();
    if (data.status === "success" && data.requires_2fa) {
      ElMessage.success("验证码已发送至您的邮箱");
    }
  } catch (error) {
    ElMessage.error(error.message || "发送验证码失败");
  } finally {
    passwordForm.twoFaCodeSending = false;
  }
};

/**
 * 切换备用验证码（密码修改）
 */
const togglePasswordBackupCode = () => {
  passwordForm.useBackup = !passwordForm.useBackup;
  passwordForm.twoFaCode = '';
  ElMessage.info(passwordForm.useBackup 
    ? "已切换到备用验证码模式，请输入8位备用码" 
    : "已切换回验证器模式，请输入6位验证码");
};

/**
 * 开始2FA设置
 */
const start2faSetup = async (method) => {
  twoFaSetup.method = method;

  try {
    const data = await apiService.enable2FA(method);
    if (data.status === "success") {
      if (method === 'totp') {
        twoFaSetup.step = 'totp-scan';
        twoFaSetup.qrCode = data.qr_code;
        twoFaSetup.secret = data.secret;
      } else {
        if (data.two_fa_enabled === true) {
          userStore.update2FAStatus(true, 'email');
          show2faSetupDialog.value = false;
          ElMessage.success("邮箱两因素认证已启用");
        } else {
          ElMessage.error("启用邮箱两因素认证失败，请重试");
        }
      }
    } else {
      ElMessage.error(data.message || "启用失败");
    }
  } catch (error) {
    ElMessage.error(error.message || "网络错误");
  }
};

/**
 * 验证2FA设置
 */
const verify2faSetup = async () => {
  if (!twoFaSetup.verifyCode) return ElMessage.warning("请输入验证码");

  try {
    const data = await apiService.verify2FASetup(twoFaSetup.verifyCode);
    if (data.status === "success") {
      twoFaSetup.step = 'backup-codes';
      twoFaSetup.backupCodes = data.backup_codes || [];
      ElMessage.success("验证成功，请保存备用验证码");
    } else {
      ElMessage.error(data.message || "验证失败");
    }
  } catch (error) {
    ElMessage.error(error.message || "网络错误");
  }
};

/**
 * 完成2FA设置
 */
const finish2faSetup = () => {
  userStore.update2FAStatus(true, twoFaSetup.method);
  show2faSetupDialog.value = false;
  twoFaSetup.step = null;
  twoFaSetup.verifyCode = '';
  twoFaSetup.backupCodes = [];
  ElMessage.success("两因素认证已成功启用");
};

/**
 * 取消2FA设置
 */
const cancel2faSetup = () => {
  show2faSetupDialog.value = false;
  twoFaSetup.step = null;
  twoFaSetup.verifyCode = '';
  twoFaSetup.backupCodes = [];
};

/**
 * 复制备用码
 */
const copyBackupCodes = () => {
  const text = twoFaSetup.backupCodes.join('\n');
  copyToClipboard(text);
};

/**
 * 禁用2FA
 */
const disable2fa = async () => {
  if (!twoFaDisable.password) return ElMessage.warning("请输入密码");

  try {
    const data = await apiService.disable2FA(twoFaDisable.password);
    if (data.status === "success") {
      userStore.update2FAStatus(false);
      show2faDisableDialog.value = false;
      twoFaDisable.password = '';
      ElMessage.success("两因素认证已禁用");
    } else {
      ElMessage.error(data.message || "禁用失败");
    }
  } catch (error) {
    ElMessage.error(error.message || "网络错误");
  }
};

/**
 * 重新生成备用码
 */
const regenerateBackupCodes = async () => {
  if (!backupCodes.password) return ElMessage.warning("请输入密码");

  try {
    const data = await apiService.regenerateBackupCodes(backupCodes.password);
    if (data.status === "success") {
      backupCodes.newCodes = data.backup_codes || [];
      ElMessage.success("备用验证码已重新生成");
    } else {
      ElMessage.error(data.message || "生成失败");
    }
  } catch (error) {
    ElMessage.error(error.message || "网络错误");
  }
};

/**
 * 复制新备用码
 */
const copyNewBackupCodes = () => {
  const text = backupCodes.newCodes.join('\n');
  copyToClipboard(text);
};

/**
 * 关闭备用码对话框
 */
const closeBackupCodesDialog = () => {
  showBackupCodesDialog.value = false;
  backupCodes.password = '';
  backupCodes.newCodes = null;
};

/**
 * 复制到剪贴板
 */
const copyToClipboard = (text) => {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(() => {
      ElMessage.success("已复制到剪贴板");
    }).catch(() => {
      fallbackCopyText(text);
    });
  } else {
    fallbackCopyText(text);
  }
};

/**
 * 备用复制方法
 */
const fallbackCopyText = (text) => {
  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.style.position = 'fixed';
  textarea.style.opacity = '0';
  document.body.appendChild(textarea);
  textarea.select();

  try {
    const successful = document.execCommand('copy');
    if (successful) {
      ElMessage.success("已复制到剪贴板");
    } else {
      ElMessage.error("复制失败，请手动复制");
    }
  } catch (err) {
    ElMessage.error("复制失败，请手动复制");
  } finally {
    document.body.removeChild(textarea);
  }
};
</script>

<style scoped>
.form-section {
  padding: 24px;
  border-radius: 8px;
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
}

.security-status {
  max-width: 600px;
}

.security-actions {
  display: flex;
  gap: 12px;
  margin-top: 16px;
}

.twofa-method-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.twofa-method-card {
  padding: 24px;
  border: 2px solid #dcdfe6;
  border-radius: 8px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s;
}

.twofa-method-card:hover {
  border-color: #409eff;
  box-shadow: 0 2px 12px rgba(64, 158, 255, 0.2);
}

.twofa-method-card i {
  font-size: 48px;
  color: #409eff;
  margin-bottom: 12px;
}

.twofa-method-card h4 {
  margin: 0 0 8px 0;
  font-size: 16px;
  color: #303133;
}

.twofa-method-card p {
  margin: 0;
  font-size: 13px;
  color: #909399;
}

.qr-code-section {
  text-align: center;
}

.qr-code-container {
  display: inline-block;
  padding: 16px;
  background: white;
  border: 2px solid #dcdfe6;
  border-radius: 8px;
}

.qr-code-container img {
  display: block;
  width: 200px;
  height: 200px;
}

.backup-codes-container {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
  max-height: 300px;
  overflow-y: auto;
}

.backup-code {
  padding: 12px;
  background: white;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  text-align: center;
  font-family: 'Courier New', monospace;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}
</style>
