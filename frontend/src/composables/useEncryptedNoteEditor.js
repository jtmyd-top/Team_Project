import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useVaultEncryption } from '@/composables/useVaultEncryption'
import { getCsrfToken } from '@utils/csrf'
import { extractApiErrorMessage } from '@utils/apiError'

export function useEncryptedNoteEditor(props, emit) {
  const { isKeyValid } = useVaultEncryption()

  const showEncryptionDialog = ref(false)
  const rememberChoice = ref(false)

  async function handleToggleSecret() {
    if (props.isSecret) {
      // 已加密，要移出
      try {
        await ElMessageBox.confirm(
          '确定要将此笔记移出保险柜吗？',
          '移出保险柜',
          {
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            type: 'warning'
          }
        )
      } catch {
        return
      }
    } else {
      // 未加密，要加密
      // 检查是否已初始化和验证
      if (!isKeyValid.value) {
        ElMessage.warning('请先完成 2FA 验证')
        return
      }

      showEncryptionDialog.value = true
      return
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
        ElMessage.error(extractApiErrorMessage(data, '操作失败'))
      }
    } catch (e) {
      console.error('Toggle encryption error:', e)
      ElMessage.error('操作失败')
    }
  }

  function closeEncryptionDialog() {
    showEncryptionDialog.value = false
  }

  return {
    showEncryptionDialog,
    rememberChoice,
    handleToggleSecret,
    confirmEncryption,
    closeEncryptionDialog
  }
}
