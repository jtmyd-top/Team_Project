/**
 * useConfirm - 确认对话框 Composable
 *
 * 提供简单的确认对话框功能
 */

import { ref } from 'vue'

const state = ref({
  visible: false,
  title: '确认',
  message: '',
  confirmText: '确定',
  cancelText: '取消',
  type: 'primary',
  resolve: null
})

/**
 * 显示确认对话框
 * @param {string} message - 确认消息
 * @param {Object} options - 配置选项
 * @returns {Promise<boolean>} 用户是否确认
 */
export function showConfirm(message, options = {}) {
  return new Promise((resolve) => {
    state.value = {
      visible: true,
      title: options.title || '确认',
      message,
      confirmText: options.confirmText || '确定',
      cancelText: options.cancelText || '取消',
      type: options.type || 'primary',
      resolve
    }
  })
}

/**
 * 确认对话框 Composable
 * @returns {Object} 对话框状态和方法
 */
export function useConfirm() {
  const handleConfirm = () => {
    if (state.value.resolve) {
      state.value.resolve(true)
    }
    state.value.visible = false
  }

  const handleCancel = () => {
    if (state.value.resolve) {
      state.value.resolve(false)
    }
    state.value.visible = false
  }

  return {
    state,
    showConfirm,
    handleConfirm,
    handleCancel
  }
}

// 导出供直接使用的函数
export { showConfirm }
