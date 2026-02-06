<template>
  <div class="dashboard-header">
    <div class="dashboard-header__left">
      <a href="/" class="dashboard-header__back">
        <i class="fas fa-arrow-left"></i> 返回
      </a>
      <span class="dashboard-header__title">WARROOM</span>
      <span class="dashboard-header__uptime" v-if="store.heartbeat">
        <i class="fas fa-server"></i>
        运行 {{ uptimeText }}
      </span>
      <span class="dashboard-header__status" :class="statusClass">
        <i :class="statusIcon"></i> {{ statusText }}
      </span>
    </div>
    <div class="dashboard-header__right">
      <div class="dashboard-header__alert-badge" v-if="store.criticalCount > 0">
        <i class="fas fa-bell" style="color: var(--db-red);"></i>
        <span class="badge-dot"></span>
      </div>
      <span class="dashboard-header__clock">{{ clock }}</span>
      <button
        class="dashboard-header__btn"
        @click="handleRefresh"
        :disabled="store.loading"
        title="手动刷新"
      >
        <i class="fas fa-sync-alt" :class="{ 'fa-spin': store.loading }"></i>
      </button>
      <button
        class="dashboard-header__btn"
        @click="toggleFullscreen"
        :title="isFullscreen ? '退出全屏' : '全屏'"
      >
        <i :class="isFullscreen ? 'fas fa-compress' : 'fas fa-expand'"></i>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useDashboardStore } from '@stores/dashboard.js'
import { useDashboard } from '@composables/useDashboard.js'

const store = useDashboardStore()
const { isFullscreen, toggleFullscreen, setupFullscreenListener, removeFullscreenListener } = useDashboard()

const clock = ref('')
let clockTimer = null

function updateClock() {
  const now = new Date()
  clock.value = now.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

const uptimeText = computed(() => {
  if (!store.heartbeat) return ''
  const s = store.heartbeat.uptime_seconds
  const d = Math.floor(s / 86400)
  const h = Math.floor((s % 86400) / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (d > 0) return `${d}天${h}时${m}分`
  if (h > 0) return `${h}时${m}分`
  return `${m}分`
})

const statusClass = computed(() => {
  if (store.loading && !store.heartbeat) return 'status--loading'
  if (!store.connected) return 'status--disconnected'
  return 'status--connected'
})

const statusIcon = computed(() => {
  if (store.loading && !store.heartbeat) return 'fas fa-spinner fa-spin'
  if (!store.connected) return 'fas fa-unlink'
  return 'fas fa-link'
})

const statusText = computed(() => {
  if (store.loading && !store.heartbeat) return '连接中...'
  if (!store.connected) {
    return store.reconnectCountdown > 0
      ? `连接断开 (${store.reconnectCountdown}s 后重连)`
      : '连接断开'
  }
  return '已连接'
})

function handleRefresh() {
  store.manualRefresh()
}

onMounted(() => {
  updateClock()
  clockTimer = setInterval(updateClock, 1000)
  setupFullscreenListener()
})
onUnmounted(() => {
  clearInterval(clockTimer)
  removeFullscreenListener()
})
</script>
