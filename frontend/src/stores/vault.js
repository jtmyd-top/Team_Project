/**
 * Vault Store - 保险柜状态管理
 *
 * 功能：
 * - 管理 DEK 缓存状态
 * - 管理待处理操作（加入保密柜需要验证时）
 * - 处理验证后的自动重试逻辑
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useVaultStore = defineStore('vault', () => {
  // ==================== State ====================

  // DEK（数据加密密钥）缓存
  const dek = ref(null)
  const keyExpireTime = ref(null)

  // 是否已解锁的计算属性
  const isUnlocked = computed(() => {
    return dek.value && keyExpireTime.value && keyExpireTime.value > Date.now()
  })

  // 待处理操作：用户点击"加入保密柜"但需要先验证时
  const pendingOperation = ref(null)
  // pendingOperation 结构：{
  //   noteId: number,
  //   noteContent: string,
  //   callback: () => Promise<void>  // 验证成功后执行的回调
  // }

  // 2FA 验证对话框的可见性
  const show2FADialog = ref(false)

  // Vault 初始化状态
  const vaultInitialized = ref(false)
  const vaultInitializing = ref(false)
  const vaultInitError = ref(null)

  // ==================== Actions ====================

  /**
   * 保存 DEK 到本地存储
   */
  function setDEK(dekValue, expireTime) {
    dek.value = dekValue
    keyExpireTime.value = expireTime
  }

  /**
   * 清除 DEK（登出或密钥过期时调用）
   */
  function clearDEK() {
    dek.value = null
    keyExpireTime.value = null
  }

  /**
   * 设置待处理操作
   * 当用户需要先进行 2FA 验证才能完成加密时，先保存操作信息
   */
  function setPendingOperation(noteId, noteContent, callback) {
    pendingOperation.value = {
      noteId,
      noteContent,
      callback
    }
  }

  /**
   * 清除待处理操作
   */
  function clearPendingOperation() {
    pendingOperation.value = null
  }

  /**
   * 执行待处理操作
   * 在用户完成 2FA 验证后调用此函数
   */
  async function executePendingOperation() {
    if (!pendingOperation.value) {
      return false
    }

    try {
      await pendingOperation.value.callback()
      clearPendingOperation()
      return true
    } catch (e) {
      console.error('[Vault] Failed to execute pending operation:', e)
      // 保留 pendingOperation，以便用户可以重试
      throw e
    }
  }

  /**
   * 显示 2FA 验证对话框
   */
  function show2FADialogModal() {
    show2FADialog.value = true
  }

  /**
   * 隐藏 2FA 验证对话框
   */
  function hide2FADialogModal() {
    show2FADialog.value = false
  }

  /**
   * 获取 CSRF Token
   */
  function getCsrfToken() {
    const cookieValue = document.cookie
      .split('; ')
      .find(row => row.startsWith('csrftoken='))
      ?.split('=')[1]
    return cookieValue || ''
  }

  /**
   * 懒加载初始化保密柜
   * 如果用户已启用 2FA 但保密柜未初始化，尝试初始化
   * 忽略"已初始化"的错误，作为成功处理
   */
  async function checkAndInitVault() {
    if (vaultInitializing.value) {
      return // 避免并发请求
    }

    vaultInitializing.value = true
    vaultInitError.value = null

    try {
      // 1. 获取保密柜状态
      const statusResponse = await fetch('/api/vault/status/', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken()
        }
      })

      const statusData = await statusResponse.json()

      if (!statusData.two_fa_enabled) {
        // 用户未启用 2FA，不需要初始化
        vaultInitialized.value = true
        return
      }

      // 2. 尝试初始化保密柜
      const initResponse = await fetch('/api/vault/init/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken()
        }
      })

      if (initResponse.ok) {
        const initData = await initResponse.json()
        if (initData.status === 'success') {
          vaultInitialized.value = true
        }
      } else if (initResponse.status === 400) {
        // 400 = 保密柜已初始化，忽略此错误
        const errorData = await initResponse.json()
        if (errorData.message && errorData.message.includes('已初始化')) {
          vaultInitialized.value = true
        } else {
          vaultInitError.value = errorData.message
        }
      } else {
        // 其他错误
        const errorData = await initResponse.json()
        vaultInitError.value = errorData.message || 'Failed to initialize vault'
      }
    } catch (e) {
      vaultInitError.value = e.message
    } finally {
      vaultInitializing.value = false
    }
  }

  return {
    // State
    dek,
    keyExpireTime,
    pendingOperation,
    show2FADialog,
    vaultInitialized,
    vaultInitializing,
    vaultInitError,

    // Computed
    isUnlocked,

    // Actions
    setDEK,
    clearDEK,
    setPendingOperation,
    clearPendingOperation,
    executePendingOperation,
    show2FADialogModal,
    hide2FADialogModal,
    checkAndInitVault
  }
})
