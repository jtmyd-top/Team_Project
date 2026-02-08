<template>
  <div class="db-card">
    <div class="db-card-title" style="justify-content: space-between;">
      <div style="display: flex; align-items: center; gap: 8px;">
        <i class="fas fa-shield-alt"></i> 保密柜安全告警
        <span v-if="store.alertCount > 0" style="color: var(--db-red); font-size: 12px;">
          {{ store.alertCount }} 条告警
        </span>
      </div>
      <a href="/admin/knowledge_project/accesslog/?action__exact=vault_fail" target="_blank" style="font-size: 12px; color: var(--db-cyan); text-decoration: none; white-space: nowrap;">
        <i class="fas fa-external-link-alt"></i> 查看全部
      </a>
    </div>
    <div class="vault-alert-panel" v-if="store.vaultAlerts.length > 0">
      <div
        v-for="(alert, idx) in store.vaultAlerts"
        :key="idx"
        class="alert-item"
        :class="`alert-item--${alert.severity}`"
        @click="handleAlertClick(alert)"
        style="cursor: pointer;"
      >
        <span class="alert-dot" :class="`alert-dot--${alert.severity}`"></span>
        <div style="flex:1;">
          <div class="alert-user">{{ alert.user }}</div>
          <div class="alert-detail">
            <span class="alert-time" v-if="alert.time">{{ alert.time }}</span>
            <span class="alert-ip">{{ alert.ip }}</span>
            <span>{{ alert.fail_count }}次失败</span>
            <span v-if="alert.user_locked" class="locked-tag">账户冻结</span>
            <span v-if="alert.is_banned" class="banned-tag">IP封禁</span>
          </div>
        </div>
        <div class="alert-actions">
          <button
            v-if="!alert.is_banned"
            class="ban-btn"
            @click.stop="handleBanIp(alert.ip)"
            :disabled="banning"
          >
            BAN
          </button>
          <span
            style="font-size: 11px; padding: 2px 8px; border-radius: 4px;"
            :style="severityStyle(alert.severity)"
          >
            {{ severityLabel(alert.severity) }}
          </span>
        </div>
      </div>
    </div>
    <div v-else class="alert-empty">
      <i class="fas fa-check-circle"></i>
      暂无安全告警
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useDashboardStore } from '@stores/dashboard.js'
import { ElMessage } from 'element-plus'

const store = useDashboardStore()
const banning = ref(false)

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

function handleAlertClick(alert) {
  // 跳转到Admin审计日志，自动过滤IP
  const url = `/admin/knowledge_project/accesslog/?ip_address__exact=${encodeURIComponent(alert.ip)}`
  window.open(url, '_blank')
}

async function handleBanIp(ip) {
  if (banning.value) return

  if (!confirm(`确定要封禁 IP: ${ip} 吗？`)) return

  banning.value = true
  try {
    const result = await store.banIp(ip)
    if (result.status === 'success') {
      ElMessage.success(`IP ${ip} 已被封禁`)
      // 刷新告警数据
      store.fetchVaultAlerts()
    } else {
      ElMessage.error(result.message || '封禁失败')
    }
  } catch (error) {
    ElMessage.error(error.message || '封禁失败')
  } finally {
    banning.value = false
  }
}
</script>

<style scoped>
.alert-detail {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--db-text-muted);
  flex-wrap: wrap;
}

.alert-time {
  color: var(--db-text-muted);
}

.alert-ip {
  font-family: 'Consolas', 'Monaco', monospace;
  color: var(--db-cyan);
}

.banned-tag {
  background: rgba(255, 77, 79, 0.2);
  color: #ff4d4f;
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 10px;
}

.locked-tag {
  background: rgba(250, 173, 20, 0.2);
  color: #faad14;
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 10px;
}

.alert-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ban-btn {
  background: transparent;
  border: 1px solid var(--db-red);
  color: var(--db-red);
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 10px;
  cursor: pointer;
  transition: all 0.2s;
}

.ban-btn:hover:not(:disabled) {
  background: var(--db-red);
  color: #fff;
}

.ban-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
