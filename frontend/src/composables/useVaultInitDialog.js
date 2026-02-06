/**
 * VaultInitDialog 逻辑层
 * 处理保险柜初始化对话框的逻辑
 */

import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useVaultEncryption } from '@/composables/useVaultEncryption'

export function useVaultInitDialog(emit) {
  const { initializeVault } = useVaultEncryption()

  // ==================== 状态 ====================
  const showInitDialog = ref(false)
  const initializing = ref(false)

  // ==================== 方法 ====================
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

  // ==================== 返回 ====================
  return {
    showInitDialog,
    initializing,
    handleInit,
    resetForm,
    openInitDialog
  }
}
