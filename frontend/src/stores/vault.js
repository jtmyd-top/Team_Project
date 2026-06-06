/**
 * Vault Store - 保险柜状态管理
 *
 * 职责：
 * - 封装 vaultKey 闭包模块的调用（DEK 不再存于 Pinia 响应式状态）
 * - 管理待处理操作、2FA 对话框可见性、vault 初始化状态
 * - 通过 lockStateTick 订阅 vaultKey 的锁定事件，让 isUnlocked computed 响应式
 */

import { defineStore } from 'pinia'
import { ref, computed, onScopeDispose } from 'vue'
import { getCsrfToken } from '@utils/csrf'
import { extractApiErrorMessage } from '@utils/apiError'
import * as vaultKey from '@/stores/vaultKey'

export const useVaultStore = defineStore('vault', () => {
  // 用于触发响应式 tick 的计数器：vaultKey 状态变化时递增
  const lockStateTick = ref(0)

  const unsubscribe = vaultKey.onLockStateChange(() => {
    lockStateTick.value++
  })

  // Pinia store 长驻不卸载，但以防万一
  onScopeDispose(() => {
    try { unsubscribe() } catch (e) { /* noop */ }
  })

  // isUnlocked 依赖 tick，锁定/解锁时自动重算
  const isUnlocked = computed(() => {
    void lockStateTick.value
    return vaultKey.hasKey()
  })

  const keyExpireTime = computed(() => {
    void lockStateTick.value
    return vaultKey.getExpireTime()
  })

  // 待处理操作（加入保密柜需要先验证时）
  const pendingOperation = ref(null)

  // 2FA 验证对话框的可见性
  const show2FADialog = ref(false)

  // Vault 初始化状态
  const vaultInitialized = ref(false)
  const vaultInitializing = ref(false)
  const vaultInitError = ref(null)

  // ==================== Actions ====================

  /**
   * 导入 DEK（base64），内部 importKey 成非导出 CryptoKey 存入闭包
   * 【已弃用：方案 C 改用 beginHandshake + completeHandshake】
   */
  async function setDEK(dekBase64, ttlSeconds) {
    await vaultKey.importDekBase64(dekBase64, ttlSeconds)
  }

  /**
   * 方案 C：开始 ECDH 握手，得到客户端公钥和非导出临时私钥
   */
  async function beginHandshake() {
    return vaultKey.beginHandshake()
  }

  /**
   * 方案 C：完成握手，解包服务端返回的 wrapped DEK 并写入闭包
   */
  async function completeHandshake(params, ttlSeconds) {
    await vaultKey.completeHandshakeImport({ ...params, ttlSeconds })
  }

  function clearDEK() {
    vaultKey.clearKey()
  }

  function extendExpire(ttlSeconds) {
    const ok = vaultKey.extendExpire(ttlSeconds)
    if (ok) lockStateTick.value++
    return ok
  }

  async function encrypt(plaintext) {
    return vaultKey.encrypt(plaintext)
  }

  async function decrypt(ciphertextBase64) {
    return vaultKey.decrypt(ciphertextBase64)
  }

  function onLockStateChange(fn) {
    return vaultKey.onLockStateChange(fn)
  }

  function setPendingOperation(noteId, noteContent, callback) {
    pendingOperation.value = { noteId, noteContent, callback }
  }

  function clearPendingOperation() {
    pendingOperation.value = null
  }

  async function executePendingOperation() {
    if (!pendingOperation.value) return false
    try {
      await pendingOperation.value.callback()
      clearPendingOperation()
      return true
    } catch (e) {
      console.error('[Vault] Failed to execute pending operation:', e)
      throw e
    }
  }

  function show2FADialogModal() { show2FADialog.value = true }
  function hide2FADialogModal() { show2FADialog.value = false }

  async function checkAndInitVault() {
    // 仅检查状态，不再自动 POST /api/vault/init/。
    // vault_init 必须由用户显式动作（"创建保密柜"按钮）触发，避免页面加载就发非幂等的初始化请求。
    if (vaultInitializing.value) return vaultInitialized.value
    vaultInitializing.value = true
    vaultInitError.value = null
    try {
      const statusResponse = await fetch('/api/vault/status/', {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
      })
      if (!statusResponse.ok) {
        vaultInitialized.value = false
        return false
      }
      const statusData = await statusResponse.json()
      if (!statusData.two_fa_enabled) {
        // 没开 2FA 视为不需要 vault；不去触发 init
        vaultInitialized.value = false
        return false
      }
      vaultInitialized.value = !!statusData.vault_initialized
      return vaultInitialized.value
    } catch (e) {
      vaultInitError.value = e.message
      vaultInitialized.value = false
      return false
    } finally {
      vaultInitializing.value = false
    }
  }

  /**
   * 显式初始化保密柜（只能由用户主动点击"创建"触发）
   */
  async function initVault() {
    const initResponse = await fetch('/api/vault/init/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken()
      }
    })
    const data = await initResponse.json().catch(() => ({}))
    if (initResponse.ok && data.status === 'success') {
      vaultInitialized.value = true
      return { success: true }
    }
    if (initResponse.status === 400 && data.message?.includes('已初始化')) {
      vaultInitialized.value = true
      return { success: true, alreadyInitialized: true }
    }
    return { success: false, message: extractApiErrorMessage(data, '初始化失败') }
  }

  // ==================== 单例锁：自动恢复 DEK ====================
  // 多个 composable 在 onMounted 同时调用 recoverKey 会并发轰炸 /api/vault/key/。
  // Pinia store 是单例，把 in-flight Promise 放在闭包里，重复调用直接复用。
  let fetchKeyPromise = null

  /**
   * 走握手从后端无感恢复 DEK。已解锁直接返回；in-flight 请求复用同一个 Promise。
   */
  async function recoverKey() {
    if (isUnlocked.value) return true
    if (fetchKeyPromise) return fetchKeyPromise

    fetchKeyPromise = (async () => {
      try {
        const statusResponse = await fetch('/api/vault/status/', {
          method: 'GET',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' }
        })
        if (!statusResponse.ok) return false

        const statusData = await statusResponse.json()
        vaultInitialized.value = !!statusData.vault_initialized

        if (!statusData.two_fa_enabled || !statusData.vault_initialized || !statusData.is_verified) {
          return false
        }

        const { clientPrivateKey, clientPubB64 } = await vaultKey.beginHandshake()
        const response = await fetch('/api/vault/key/', {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
          },
          body: JSON.stringify({ client_pub: clientPubB64 })
        })
        if (!response.ok) return false
        const data = await response.json()
        const ttl = data.remaining_seconds || data.expire_time
        if (data.server_pub && data.iv && data.ct && ttl) {
          await vaultKey.completeHandshakeImport({
            serverPubB64: data.server_pub,
            ivB64: data.iv,
            ctB64: data.ct,
            clientPrivateKey,
            ttlSeconds: ttl
          })
          return true
        }
        return false
      } catch (e) {
        console.warn('[Vault] recoverKey failed:', e)
        return false
      } finally {
        fetchKeyPromise = null
      }
    })()

    return fetchKeyPromise
  }

  return {
    // State
    pendingOperation,
    show2FADialog,
    vaultInitialized,
    vaultInitializing,
    vaultInitError,

    // Computed（代理 vaultKey 闭包）
    isUnlocked,
    keyExpireTime,

    // Actions
    setDEK,
    beginHandshake,
    completeHandshake,
    clearDEK,
    extendExpire,
    encrypt,
    decrypt,
    onLockStateChange,
    setPendingOperation,
    clearPendingOperation,
    executePendingOperation,
    show2FADialogModal,
    hide2FADialogModal,
    checkAndInitVault,
    initVault,
    recoverKey
  }
})
