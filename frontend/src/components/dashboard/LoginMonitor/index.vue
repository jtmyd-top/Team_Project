<template>
  <div class="db-card">
    <div class="db-card-title">
      <i class="fas fa-map-marker-alt"></i> 登录监控
      <span v-if="store.suspiciousCount > 0" class="login-warn-badge">
        {{ store.suspiciousCount }} 条可疑
      </span>
    </div>
    <template v-if="store.loginMonitor">
      <!-- IP 分布 -->
      <div class="login-section-title">IP 归属地分布</div>
      <div class="ip-dist-list">
        <div
          v-for="(item, idx) in store.loginMonitor.ip_distribution"
          :key="idx"
          class="ip-dist-item"
        >
          <span class="ip-dist-loc">{{ item.ip_location || '未知' }}</span>
          <div class="ip-dist-bar-wrap">
            <div
              class="ip-dist-bar"
              :style="{ width: barWidth(item.count) }"
            ></div>
          </div>
          <span class="ip-dist-count">{{ item.count }}</span>
        </div>
      </div>

      <!-- 可疑登录 -->
      <div class="login-section-title" style="margin-top: 16px;">
        <i class="fas fa-exclamation-triangle" style="color: var(--db-yellow);"></i>
        可疑登录记录
      </div>
      <div class="suspicious-list" v-if="store.loginMonitor.suspicious_logins.length > 0">
        <div
          v-for="(s, idx) in store.loginMonitor.suspicious_logins.slice(0, 10)"
          :key="idx"
          class="suspicious-item"
        >
          <span class="alert-dot" :class="dotClass(s.reason_code)"></span>
          <div style="flex: 1; min-width: 0;">
            <div class="alert-user">{{ s.user }}</div>
            <div class="alert-detail">
              {{ s.reason }} · {{ s.location }} · {{ formatTime(s.time) }}
            </div>
          </div>
          <span class="suspicious-ip">{{ s.ip }}</span>
          <button
            class="ban-btn"
            :class="{ 'ban-btn--done': bannedIps.has(s.ip) }"
            :disabled="banningIp === s.ip || bannedIps.has(s.ip)"
            @click.stop="handleBan(s.ip)"
            :title="bannedIps.has(s.ip) ? '已封禁' : '封禁此 IP'"
          >
            <i :class="banBtnIcon(s.ip)"></i>
            {{ bannedIps.has(s.ip) ? '已封禁' : '封禁' }}
          </button>
        </div>
      </div>
      <div v-else class="alert-empty" style="padding: 20px 0;">
        <i class="fas fa-check-circle"></i> 暂无可疑登录
      </div>
    </template>
    <div v-else class="alert-empty">
      <i class="fas fa-spinner fa-spin"></i> 加载中...
    </div>
  </div>
</template>

<script setup>
import { ref, computed, reactive, watch } from 'vue'
import { useDashboardStore } from '@stores/dashboard.js'

const store = useDashboardStore()
const banningIp = ref('')
const bannedIps = reactive(new Set())

// 从 API 数据初始化已封禁 IP 列表
watch(
  () => store.loginMonitor?.suspicious_logins,
  (logins) => {
    if (!logins) return
    logins.forEach(s => {
      if (s.is_banned) bannedIps.add(s.ip)
    })
  },
  { immediate: true }
)

const maxCount = computed(() => {
  if (!store.loginMonitor?.ip_distribution?.length) return 1
  return Math.max(...store.loginMonitor.ip_distribution.map(i => i.count), 1)
})

function barWidth(count) {
  return Math.round((count / maxCount.value) * 100) + '%'
}

function dotClass(reason) {
  if (reason === 'suspicious') return 'alert-dot--critical'
  if (reason === 'new_location') return 'alert-dot--warning'
  return 'alert-dot--info'
}

function formatTime(iso) {
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', {
    month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

function banBtnIcon(ip) {
  if (banningIp.value === ip) return 'fas fa-spinner fa-spin'
  if (bannedIps.has(ip)) return 'fas fa-check'
  return 'fas fa-ban'
}

async function handleBan(ip) {
  if (bannedIps.has(ip) || banningIp.value) return
  banningIp.value = ip
  const result = await store.banIp(ip)
  banningIp.value = ''
  if (result.status === 'success') {
    bannedIps.add(ip)
  } else {
    alert(result.message || '封禁失败')
  }
}
</script>
