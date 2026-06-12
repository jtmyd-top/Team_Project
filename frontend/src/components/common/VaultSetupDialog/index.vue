<template>
  <el-dialog
    v-model="dialogVisible"
    title="需要设置两因素认证"
    width="420px"
    :close-on-click-modal="false"
    @close="handleClose"
    class="vault-setup-dialog"
  >
    <div class="setup-content">
      <!-- 图标 -->
      <div class="setup-icon">
        <i class="fas fa-lock"></i>
      </div>

      <h3 class="setup-title">保密柜需要两因素认证</h3>

      <p class="setup-description">
        为了保护您的私密笔记，保密柜功能需要先启用两因素认证（2FA）。
        启用后，每次访问保密柜都需要进行身份验证。
      </p>

      <div class="features-list">
        <div class="feature-item">
          <i class="fas fa-check-circle"></i>
          <span>支持验证器应用（如 Google Authenticator）</span>
        </div>
        <div class="feature-item">
          <i class="fas fa-check-circle"></i>
          <span>支持邮箱验证码</span>
        </div>
        <div class="feature-item">
          <i class="fas fa-check-circle"></i>
          <span>验证后30分钟内无需重复验证</span>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleClose">稍后设置</el-button>
        <el-button type="primary" @click="handleGoToSettings">
          <i class="fas fa-cog"></i>
          前往设置
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ElDialog, ElButton } from 'element-plus'
import 'element-plus/es/components/dialog/style/css'
import 'element-plus/es/components/button/style/css'
import { useVaultSetupDialog } from '@/composables/useVaultSetupDialog'
import '@/assets/styles/components/vault-setup-dialog.css'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue', 'go-to-settings', 'cancel'])

const {
  dialogVisible,
  handleGoToSettings,
  handleClose
} = useVaultSetupDialog(props, emit)
</script>
