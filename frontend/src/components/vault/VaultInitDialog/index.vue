<template>
  <div class="vault-integration">
    <!-- 保险柜初始化对话框 -->
    <el-dialog
      title="初始化保险柜"
      v-model="showInitDialog"
      width="500px"
      @close="resetForm"
    >
      <div class="vault-init-content">
        <el-alert
          title="保险柜信息"
          type="info"
          description="初始化后，您的笔记内容将被加密存储。只有通过 2FA 验证后才能查看。"
          closable
        />

        <div style="margin-top: 20px;">
          <p style="color: #666; font-size: 14px;">
            这个过程会：
            <br />• 生成一个加密密钥（DEK）
            <br />• 用系统密钥（KEK）加密存储
            <br />• 未来笔记内容都会用这个密钥加密
          </p>
        </div>
      </div>

      <template #footer>
        <el-button @click="showInitDialog = false">取消</el-button>
        <el-button type="primary" :loading="initializing" @click="handleInit">
          确认初始化
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { useVaultInitDialog } from '@/composables/useVaultInitDialog'
import '@/assets/styles/components/vault-init-dialog.css'

const emit = defineEmits(['init-success'])

const {
  showInitDialog,
  initializing,
  handleInit,
  resetForm,
  openInitDialog
} = useVaultInitDialog(emit)

defineExpose({
  openInitDialog
})
</script>
