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
import { computed } from 'vue'
import { ElDialog, ElButton } from 'element-plus'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue', 'go-to-settings', 'cancel'])

const dialogVisible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const handleGoToSettings = () => {
  emit('go-to-settings')
  dialogVisible.value = false
}

const handleClose = () => {
  emit('cancel')
}
</script>

<style scoped>
.setup-content {
  text-align: center;
  padding: 20px 0;
}

.setup-icon {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 20px;
}

.setup-icon i {
  font-size: 28px;
  color: white;
}

.setup-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary, #303133);
  margin: 0 0 12px;
}

.setup-description {
  font-size: 14px;
  color: var(--text-secondary, #909399);
  line-height: 1.6;
  margin-bottom: 24px;
}

.features-list {
  text-align: left;
  background: var(--bg-secondary, #f5f7fa);
  border-radius: 8px;
  padding: 16px;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  font-size: 13px;
  color: var(--text-primary, #303133);
}

.feature-item i {
  color: #67c23a;
  font-size: 14px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.dialog-footer .el-button i {
  margin-right: 6px;
}
</style>
