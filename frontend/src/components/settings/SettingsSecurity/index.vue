<template>
  <div class="settings-security">
    <!-- 修改密码 -->
    <div class="form-section">
      <h3 class="form-section-title">
        <i class="fas fa-key"></i> 修改密码
      </h3>
      <el-button type="primary" @click="showPasswordDialog = true" size="large">
        <i class="fas fa-key"></i> 修改密码
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
            show-password
            maxlength="50">
            <template #prefix>
              <i class="fas fa-lock"></i>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item label="新密码">
          <el-input
            v-model="passwordForm.new"
            type="password"
            placeholder="至少8位字符"
            show-password
            maxlength="50">
            <template #prefix>
              <i class="fas fa-key"></i>
            </template>
          </el-input>
          <div class="form-hint" style="color: #909399;">
            密码至少8位，建议包含字母、数字和特殊字符
          </div>
        </el-form-item>

        <el-form-item label="确认新密码">
          <el-input
            v-model="passwordForm.confirm"
            type="password"
            placeholder="再次输入新密码"
            show-password
            maxlength="50">
            <template #prefix>
              <i class="fas fa-key"></i>
            </template>
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
            <div style="display: flex; gap: 12px;">
              <el-input
                v-model="passwordForm.twoFaCode"
                :placeholder="passwordForm.useBackup ? '请输入8位备用码' : '请输入6位验证码'"
                :maxlength="passwordForm.useBackup ? 8 : 6">
              </el-input>
              <el-button
                v-if="passwordForm.twoFaMethod === 'email' && !passwordForm.useBackup"
                :disabled="passwordCountdown.counting"
                :loading="passwordForm.twoFaCodeSending"
                @click="sendPassword2faCode"
                :type="passwordCountdown.counting ? 'info' : 'primary'">
                {{ passwordCountdown.counting ? `${passwordCountdown.seconds}秒` : '重发' }}
              </el-button>
            </div>
            <div v-if="passwordCountdown.counting && passwordForm.twoFaMethod === 'email'"
                 class="form-hint" style="color: #E6A23C; margin-top: 4px;">
              <i class="fas fa-clock"></i> 请等待 {{ passwordCountdown.seconds }} 秒后重新发送
            </div>
          </el-form-item>

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
        <el-button
          type="primary"
          @click="changePassword"
          :loading="passwordForm.submitting">
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
import { useSettingsSecurity } from '@composables/useSettingsSecurity.js';
import '@/assets/styles/components/settings-security.css';

const {
  // Store
  userStore,

  // Countdown
  passwordCountdown,

  // Dialog states
  showPasswordDialog,
  show2faSetupDialog,
  show2faDisableDialog,
  showBackupCodesDialog,

  // Form states
  passwordForm,
  twoFaSetup,
  twoFaDisable,
  backupCodes,

  // Methods
  changePassword,
  resetPasswordForm,
  sendPassword2faCode,
  togglePasswordBackupCode,
  start2faSetup,
  verify2faSetup,
  finish2faSetup,
  cancel2faSetup,
  copyBackupCodes,
  disable2fa,
  regenerateBackupCodes,
  copyNewBackupCodes,
  closeBackupCodesDialog,
} = useSettingsSecurity();
</script>
