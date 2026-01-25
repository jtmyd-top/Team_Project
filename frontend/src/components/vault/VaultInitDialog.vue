<template>
  <div class="vault-integration">
    <!-- 保险柜初始化对话框 -->
    <el-dialog
      title="初始化保险柜"
      v-model="showInitDialog"
      width="500px"
      @close="resetForm"
    >
      <div class="init-content">
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
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useVaultEncryption } from '@/composables/useVaultEncryption'

const { initializeVault } = useVaultEncryption()

const showInitDialog = ref(false)
const initializing = ref(false)

async function handleInit() {
  initializing.value = true

  try {
    const result = await initializeVault()

    if (result.success) {
      ElMessage.success('保险柜初始化成功！')
      showInitDialog.value = false
      emit('init-success')
    } else {
      ElMessage.error(result.message || '初始化失败')
    }
  } catch (e) {
    console.error('Initialization error:', e)
    ElMessage.error('初始化出错')
  } finally {
    initializing.value = false
  }
}

function resetForm() {
  initializing.value = false
}

function openInitDialog() {
  showInitDialog.value = true
}

defineExpose({
  openInitDialog
})

const emit = defineEmits(['init-success'])
</script>

<style scoped>
.vault-integration {
  /* Placeholder for vault UI elements */
}

.init-content {
  padding: 10px 0;
}
</style>
