/**
 * useVaultEncryption.js - 保险柜加密 Composable
 *
 * 功能：
 * - 管理保险柜状态和密钥缓存
 * - 与后端通信获取 DEK
 * - 前端加密/解密笔记数据
 * - 处理 2FA 验证和密钥恢复
 */

import { ref, computed, onMounted } from 'vue'
import { useVaultStore } from '@/stores/vault'

export function useVaultEncryption() {
  // ==================== State ====================
  const dek = ref(null)  // 数据加密密钥 (Base64)
  const vaultKey = ref(null)  // 原始 DEK bytes (for crypto operations)
  const keyExpireTime = ref(null)  // 密钥过期时间戳
  const isKeyValid = computed(() => {
    return dek.value && keyExpireTime.value && keyExpireTime.value > Date.now()
  })

  // 2FA 验证状态
  const verificationPending = ref(false)
  const verificationError = ref(null)

  // 获取 vaultStore 实例
  const vaultStore = useVaultStore()

  // ==================== 密钥管理 ====================

  /**
   * 尝试从 Redis session 中无感恢复密钥
   * 这样用户在刷新页面后不需要重新进行 2FA 验证
   */
  async function tryRecoverKeyFromSession() {
    try {
      const response = await fetch('/api/vault/key/', {
        method: 'GET',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
        }
      })

      if (response.ok) {
        const data = await response.json()
        if (data.dek) {
          dek.value = data.dek
          keyExpireTime.value = Date.now() + (data.expire_time * 1000)
          // 【新增】同时更新 vaultStore
          vaultStore.setDEK(data.dek, keyExpireTime.value)
          return true
        }
      }
      return false
    } catch (e) {
      console.warn('Session recovery failed:', e)
      return false
    }
  }

  /**
   * 验证 2FA 并获取密钥
   * 调用 vault/verify API，成功后返回 DEK
   */
  async function verify2FAAndGetKey(code, useBackup = false) {
    verificationPending.value = true
    verificationError.value = null

    try {
      const response = await fetch('/api/vault/verify/', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify({
          code: code,
          use_backup: useBackup
        })
      })

      const data = await response.json()

      if (!response.ok) {
        verificationError.value = data.message || '验证失败'
        return {
          success: false,
          message: data.message,
          failCount: data.fail_count
        }
      }

      // 验证成功，保存 DEK
      if (data.dek) {
        const expireTime = Date.now() + (data.expire_time * 1000)
        dek.value = data.dek
        keyExpireTime.value = expireTime
        // 【新增】同时更新 vaultStore，确保跨组件数据一致
        vaultStore.setDEK(data.dek, expireTime)
      }

      return {
        success: true,
        message: data.message,
        expireTime: data.expire_time
      }
    } catch (e) {
      console.error('2FA verification error:', e)
      verificationError.value = '验证请求失败'
      return {
        success: false,
        message: '验证请求失败'
      }
    } finally {
      verificationPending.value = false
    }
  }

  /**
   * 检查密钥有效性，如果过期则需要重新验证
   */
  function needsReVerification() {
    return !isKeyValid.value
  }

  // ==================== 加密/解密操作 ====================

  // 所有加密解密现在在前端进行，使用 useClientCrypto.js
  // encryptNoteForStorage 和 decryptNoteFromBackend 已废弃

  /**
   * Base64 转 Uint8Array
   */
  function base64ToBytes(base64) {
    const binary = atob(base64)
    const bytes = new Uint8Array(binary.length)
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i)
    }
    return bytes
  }

  /**
   * Uint8Array 转 Base64
   */
  function bytesToBase64(bytes) {
    let binary = ''
    for (let i = 0; i < bytes.byteLength; i++) {
      binary += String.fromCharCode(bytes[i])
    }
    return btoa(binary)
  }

  // ==================== 工具函数 ====================

  /**
   * 从 Cookie 获取 CSRF Token
   */
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

  /**
   * 清除本地缓存的密钥
   */
  function clearKey() {
    dek.value = null
    vaultKey.value = null
    keyExpireTime.value = null
    verificationError.value = null
  }

  /**
   * 初始化保险柜
   */
  async function initializeVault() {
    try {
      const response = await fetch('/api/vault/init/', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
        }
      })

      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.message || '初始化失败')
      }

      return {
        success: true,
        message: data.message
      }
    } catch (e) {
      console.error('Vault initialization error:', e)
      return {
        success: false,
        message: e.message
      }
    }
  }

  // ==================== Lifecycle ====================

  /**
   * 组件挂载时尝试恢复密钥
   */
  onMounted(async () => {
    // 尝试从 Redis 恢复密钥
    await tryRecoverKeyFromSession()
  })

  return {
    // State
    dek,
    isKeyValid,
    keyExpireTime,
    verificationPending,
    verificationError,

    // Methods
    verify2FAAndGetKey,
    tryRecoverKeyFromSession,
    needsReVerification,
    clearKey,
    initializeVault,
    getCsrfToken,

    // Utilities
    base64ToBytes,
    bytesToBase64
  }
}
