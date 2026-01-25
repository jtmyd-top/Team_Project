<template>
  <div class="encrypted-note-editor">
    <!-- 加密状态指示器 -->
    <div v-if="props.isSecret" class="encryption-badge">
      <el-icon><Lock /></el-icon>
      <span>此笔记已加密</span>
    </div>

    <!-- 加密切换对话框 -->
    <el-dialog
      title="加密笔记"
      v-model="showEncryptionDialog"
      width="500px"
    >
      <el-alert
        title="确认加密"
        type="warning"
        description="将此笔记加入保险柜后，内容将被加密存储。您必须通过 2FA 验证才能查看。"
        closable
        :closable="false"
      />

      <div style="margin-top: 20px; color: #666;">
        <p>
          <el-checkbox v-model="rememberChoice">记住我的选择</el-checkbox>
        </p>
      </div>

      <template #footer>
        <el-button @click="showEncryptionDialog = false">取消</el-button>
        <el-button type="primary" @click="confirmEncryption">
          加入保险柜
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Lock } from '@element-plus/icons-vue'
import { ElMessage, ElConfirm } from 'element-plus'
import { useVaultEncryption } from '@/composables/useVaultEncryption'

const props = defineProps({
  noteId: {
    type: Number,
    required: true
  },
  isSecret: {
    type: Boolean,
    default: false
  },
  content: {
    type: String,
    default: ''
  }
})

const { isKeyValid, verify2FAAndGetKey } = useVaultEncryption()

const showEncryptionDialog = ref(false)
const rememberChoice = ref(false)

async function handleToggleSecret() {
  if (props.isSecret) {
    // 已加密，要移出
    const confirmed = await ElConfirm({
      title: '移出保险柜',
      message: '确定要将此笔记移出保险柜吗？',
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
      .then(() => true)
      .catch(() => false)

    if (!confirmed) return
  } else {
    // 未加密，要加密
    // 检查是否已初始化和验证
    if (!isKeyValid.value) {
      ElMessage.warning('请先完成 2FA 验证')
      return
    }

    showEncryptionDialog.value = true
  }
}

async function confirmEncryption() {
  // 实际的加密由后端处理
  // 这里只是发送切换请求
  try {
    const response = await fetch(`/api/notes/${props.noteId}/toggle-secret/`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken()
      }
    })

    const data = await response.json()

    if (response.ok) {
      ElMessage.success(data.message)
      showEncryptionDialog.value = false
      emit('toggle-success', data)
    } else {
      ElMessage.error(data.message || '操作失败')
    }
  } catch (e) {
    console.error('Toggle encryption error:', e)
    ElMessage.error('操作失败')
  }
}

function getCsrfToken() {
  const name = 'csrftoken'
  let cookieValue = null
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';')
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim()
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1))
        break
      }
    }
  }
  return cookieValue
}

defineExpose({
  handleToggleSecret
})

const emit = defineEmits(['toggle-success'])
</script>

<style scoped>
.encrypted-note-editor {
  width: 100%;
}

.encryption-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background-color: #f0f9ff;
  border: 1px solid #b3d8ff;
  border-radius: 4px;
  color: #0084f4;
  font-size: 14px;
  margin-bottom: 10px;
}

.encryption-badge :deep(.el-icon) {
  width: 1em;
  height: 1em;
}
</style>
