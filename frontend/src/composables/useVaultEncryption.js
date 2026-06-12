/**
 * useVaultEncryption.js - 保险柜加密 Composable
 *
 * 说明：
 * - 所有 DEK 存储转移到 vaultStore（内部走 vaultKey 闭包 + 非导出 CryptoKey）
 * - 本 composable 不再持有 dek/keyExpireTime 本地引用
 * - 对外仍暴露 isKeyValid 等 computed，实际代理 vaultStore.isUnlocked
 */

import { computed, ref, onMounted } from 'vue'
import { useVaultStore } from '@/stores/vault'
import { getCsrfToken } from '@utils/csrf'
import { extractApiErrorMessage } from '@utils/apiError'

export function useVaultEncryption() {
  const vaultStore = useVaultStore()

  // 代理 store 的解锁状态
  const isKeyValid = computed(() => vaultStore.isUnlocked)
  const keyExpireTime = computed(() => vaultStore.keyExpireTime)

  // 2FA 验证状态
  const verificationPending = ref(false)
  const verificationError = ref(null)

  // ==================== 密钥管理 ====================

  /**
   * 尝试从 Redis session 中无感恢复密钥
   * 委托到 vaultStore.recoverKey（Pinia 单例锁，多个组件并发调用只发一个 /api/vault/key/ 请求）
   */
  async function tryRecoverKeyFromSession() {
    return vaultStore.recoverKey()
  }

  /**
   * 验证 2FA 并获取密钥（方案 C：ECDH 握手）
   */
  async function verify2FAAndGetKey(code, useBackup = false) {
    verificationPending.value = true
    verificationError.value = null

    try {
      const { clientPrivateKey, clientPubB64 } = await vaultStore.beginHandshake()

      const response = await fetch('/api/vault/verify/', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({ code, use_backup: useBackup, client_pub: clientPubB64 })
      })

      const data = await response.json().catch(() => ({}))

      if (!response.ok) {
        const message = extractApiErrorMessage(data, '验证失败')
        verificationError.value = message
        return {
          success: false,
          message,
          failCount: data.fail_count
        }
      }

      if (data.server_pub && data.iv && data.ct) {
        const ttl = data.session_scoped ? 0 : (data.remaining_seconds ?? data.expire_time)
        if (data.session_scoped || ttl > 0) {
          await vaultStore.completeHandshake({
            serverPubB64: data.server_pub,
            ivB64: data.iv,
            ctB64: data.ct,
            clientPrivateKey
          }, ttl)
        }
      }

      return {
        success: true,
        message: data.message,
        expireTime: data.expire_time
      }
    } catch (e) {
      console.error('2FA verification error:', e)
      const message = e.message && e.message !== '请求失败' ? e.message : '验证请求失败'
      verificationError.value = message
      return { success: false, message }
    } finally {
      verificationPending.value = false
    }
  }

  function needsReVerification() {
    return !isKeyValid.value
  }

  function clearKey() {
    vaultStore.clearDEK()
    verificationError.value = null
  }

  async function initializeVault() {
    try {
      const response = await fetch('/api/vault/init/', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken()
        }
      })

      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(extractApiErrorMessage(data, '初始化失败'))

      return { success: true, message: data.message }
    } catch (e) {
      console.error('Vault initialization error:', e)
      return { success: false, message: e.message }
    }
  }

  onMounted(async () => {
    if (!vaultStore.isUnlocked) {
      await tryRecoverKeyFromSession()
    }
  })

  return {
    // State / Computed
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
  }
}
