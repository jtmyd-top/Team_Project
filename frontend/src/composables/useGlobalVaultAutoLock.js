/**
 * useGlobalVaultAutoLock - 全局保密柜自动锁定
 *
 * 职责：
 * - 监听用户活动（mousemove/keydown/click/scroll/touchstart），节流到 30s 重置一次倒计时
 * - 主倒计时到 keyExpireTime 时触发 clearDEK，全局锁定
 * - beforeunload 强制清 DEK
 *
 * 用法：在顶层组件（KnowledgeList/index.vue 等各入口根组件）onMounted 里调用一次。
 */

import { onMounted, onUnmounted, watch } from 'vue'
import { useVaultStore } from '@/stores/vault'

const ACTIVITY_THROTTLE_MS = 30 * 1000

export function useGlobalVaultAutoLock() {
  const vaultStore = useVaultStore()

  let mainCountdownTimer = null
  let lastActivityReset = 0

  const ACTIVITY_EVENTS = ['mousemove', 'keydown', 'click', 'scroll', 'touchstart']

  function clearTimers() {
    if (mainCountdownTimer) { clearTimeout(mainCountdownTimer); mainCountdownTimer = null }
  }

  function armCountdown() {
    if (mainCountdownTimer) { clearTimeout(mainCountdownTimer); mainCountdownTimer = null }
    const expire = vaultStore.keyExpireTime
    if (!vaultStore.isUnlocked || !expire) return
    if (!Number.isFinite(expire)) return
    const remaining = expire - Date.now()
    if (remaining <= 0) {
      lock()
      return
    }
    mainCountdownTimer = setTimeout(() => {
      lock()
    }, remaining)
  }

  function lock() {
    clearTimers()
    if (vaultStore.isUnlocked) {
      vaultStore.clearDEK()
    }
  }

  function resetOnActivity() {
    if (!vaultStore.isUnlocked) return
    const now = Date.now()
    if (now - lastActivityReset < ACTIVITY_THROTTLE_MS) return
    lastActivityReset = now
    armCountdown()
  }

  function onBeforeUnload() {
    // 页面卸载时兜底清理密钥（虽然进程也会释放，但主动清可降低浏览器缓存残留风险）
    lock()
  }

  // 监听解锁/锁定状态变化：解锁时启动倒计时，锁定时清除
  let stopWatch = null

  onMounted(() => {
    ACTIVITY_EVENTS.forEach(ev =>
      window.addEventListener(ev, resetOnActivity, { passive: true })
    )
    window.addEventListener('beforeunload', onBeforeUnload)

    stopWatch = watch(
      () => vaultStore.isUnlocked,
      (unlocked) => {
        if (unlocked) {
          armCountdown()
        } else {
          clearTimers()
        }
      },
      { immediate: true }
    )
  })

  onUnmounted(() => {
    ACTIVITY_EVENTS.forEach(ev =>
      window.removeEventListener(ev, resetOnActivity)
    )
    window.removeEventListener('beforeunload', onBeforeUnload)
    clearTimers()
    if (stopWatch) stopWatch()
  })

  return { lock }
}
