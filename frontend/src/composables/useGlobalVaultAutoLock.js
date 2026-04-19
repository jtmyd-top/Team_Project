/**
 * useGlobalVaultAutoLock - 全局保密柜自动锁定
 *
 * 职责：
 * - 监听用户活动（mousemove/keydown/click/scroll/touchstart），节流到 30s 重置一次倒计时
 * - 主倒计时到 keyExpireTime 时触发 clearDEK，全局锁定
 * - visibilitychange 隐藏时启动 60s 短倒计时；回到可见取消
 * - beforeunload 强制清 DEK
 *
 * 用法：在顶层组件（KnowledgeList/index.vue 等各入口根组件）onMounted 里调用一次。
 */

import { onMounted, onUnmounted, watch } from 'vue'
import { useVaultStore } from '@/stores/vault'

const ACTIVITY_THROTTLE_MS = 30 * 1000
const HIDDEN_LOCK_DELAY_MS = 60 * 1000

export function useGlobalVaultAutoLock() {
  const vaultStore = useVaultStore()

  let mainCountdownTimer = null
  let hiddenTimer = null
  let lastActivityReset = 0

  const ACTIVITY_EVENTS = ['mousemove', 'keydown', 'click', 'scroll', 'touchstart']

  function clearTimers() {
    if (mainCountdownTimer) { clearTimeout(mainCountdownTimer); mainCountdownTimer = null }
    if (hiddenTimer) { clearTimeout(hiddenTimer); hiddenTimer = null }
  }

  function armCountdown() {
    if (mainCountdownTimer) { clearTimeout(mainCountdownTimer); mainCountdownTimer = null }
    const expire = vaultStore.keyExpireTime
    if (!vaultStore.isUnlocked || !expire) return
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
    // 本地延展 30 分钟（与后端默认 window 一致）。下次拿密钥时后端 TTL 会重新对齐。
    vaultStore.extendExpire(30 * 60)
    armCountdown()
  }

  function onVisibilityChange() {
    if (!vaultStore.isUnlocked) {
      if (hiddenTimer) { clearTimeout(hiddenTimer); hiddenTimer = null }
      return
    }
    if (document.hidden) {
      if (hiddenTimer) clearTimeout(hiddenTimer)
      hiddenTimer = setTimeout(() => {
        lock()
      }, HIDDEN_LOCK_DELAY_MS)
    } else if (hiddenTimer) {
      clearTimeout(hiddenTimer)
      hiddenTimer = null
    }
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
    document.addEventListener('visibilitychange', onVisibilityChange)
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
    document.removeEventListener('visibilitychange', onVisibilityChange)
    window.removeEventListener('beforeunload', onBeforeUnload)
    clearTimers()
    if (stopWatch) stopWatch()
  })

  return { lock }
}
