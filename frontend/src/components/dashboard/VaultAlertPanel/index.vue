<template>
  <div class="db-card">
    <div class="db-card-title">
      <i class="fas fa-shield-alt"></i> 保密柜安全告警
      <span v-if="store.alertCount > 0" style="margin-left: auto; color: var(--db-red); font-size: 12px;">
        {{ store.alertCount }} 条告警
      </span>
    </div>
    <div class="vault-alert-panel" v-if="store.vaultAlerts.length > 0">
      <div
        v-for="(alert, idx) in store.vaultAlerts"
        :key="idx"
        class="alert-item"
        :class="`alert-item--${alert.severity}`"
      >
        <span class="alert-dot" :class="`alert-dot--${alert.severity}`"></span>
        <div style="flex:1;">
          <div class="alert-user">{{ alert.user }}</div>
          <div class="alert-detail">
            <template v-if="alert.is_locked">
              <i class="fas fa-lock"></i>
              已锁定，剩余 {{ Math.ceil(alert.remaining_seconds / 60) }} 分钟
            </template>
            <template v-else>
              验证失败 {{ alert.fail_count }} 次
            </template>
          </div>
        </div>
        <span
          style="font-size: 11px; padding: 2px 8px; border-radius: 4px;"
          :style="severityStyle(alert.severity)"
        >
          {{ severityLabel(alert.severity) }}
        </span>
      </div>
    </div>
    <div v-else class="alert-empty">
      <i class="fas fa-check-circle"></i>
      暂无安全告警
    </div>
  </div>
</template>

<script setup>
import { useDashboardStore } from '@stores/dashboard.js'

const store = useDashboardStore()

function severityLabel(s) {
  return { critical: '严重', warning: '警告', info: '提示' }[s] || s
}

function severityStyle(s) {
  const map = {
    critical: { background: 'rgba(255,77,79,0.15)', color: '#ff4d4f' },
    warning: { background: 'rgba(250,173,20,0.15)', color: '#faad14' },
    info: { background: 'rgba(0,240,255,0.1)', color: '#00f0ff' },
  }
  return map[s] || map.info
}
</script>
