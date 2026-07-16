// frontend/src/stores/dashboard.js
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getCsrfToken } from '@utils/csrf'

export const useDashboardStore = defineStore('dashboard', () => {
  // State
  const heartbeat = ref(null)
  const assets = ref(null)
  const operations = ref(null)
  const actionItems = ref([])
  const vaultAlerts = ref([])
  const trashBacklog = ref(null)
  const contentTrend = ref(null)
  const loginMonitor = ref(null)
  const auditLog = ref(null)
  const serviceHealth = ref(null)
  const emailDelivery = ref(null)
  const errorLogs = ref(null)
  const cpuHistory = ref([])
  const memHistory = ref([])
  const netSentHistory = ref([])
  const netRecvHistory = ref([])
  const loading = ref(false)
  const error = ref(null)
  const connected = ref(true)
  const lastUpdated = ref(null)
  const reconnectCountdown = ref(0)

  let heartbeatTimer = null
  let assetsTimer = null
  let reconnectTimer = null
  let consecutiveErrors = 0
  let prevNetSent = null
  let prevNetRecv = null

  const MAX_HISTORY = 60

  // Getters
  const alertCount = computed(() => vaultAlerts.value.length)
  const criticalCount = computed(() =>
    vaultAlerts.value.filter(a => a.severity === 'critical').length
  )
  const suspiciousCount = computed(() =>
    loginMonitor.value?.suspicious_count || 0
  )

  // Actions
  async function fetchSection(section) {
    try {
      const resp = await fetch(
        `/api/dashboard/stats/?section=${section}`,
        { headers: { 'X-CSRFToken': getCsrfToken() }, credentials: 'same-origin' }
      )
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const data = await resp.json()
      consecutiveErrors = 0
      connected.value = true
      error.value = null
      stopReconnectCountdown()
      return data
    } catch (e) {
      consecutiveErrors++
      if (consecutiveErrors >= 3) {
        connected.value = false
        startReconnectCountdown()
      }
      error.value = e.message
      return null
    }
  }

  function startReconnectCountdown() {
    if (reconnectTimer) return
    reconnectCountdown.value = 10
    reconnectTimer = setInterval(() => {
      reconnectCountdown.value--
      if (reconnectCountdown.value <= 0) {
        stopReconnectCountdown()
        manualRefresh()
      }
    }, 1000)
  }

  function stopReconnectCountdown() {
    if (reconnectTimer) {
      clearInterval(reconnectTimer)
      reconnectTimer = null
    }
    reconnectCountdown.value = 0
  }

  function pushHistory(hb) {
    const now = new Date().toLocaleTimeString('zh-CN', {
      hour: '2-digit', minute: '2-digit', second: '2-digit'
    })
    cpuHistory.value.push({ time: now, value: hb.cpu_percent })
    memHistory.value.push({ time: now, value: hb.memory_percent })
    if (cpuHistory.value.length > MAX_HISTORY) cpuHistory.value.shift()
    if (memHistory.value.length > MAX_HISTORY) memHistory.value.shift()

    // Network rate calculation (bytes/sec → KB/s)
    if (hb.net_bytes_sent !== undefined && hb.net_bytes_recv !== undefined) {
      if (prevNetSent !== null) {
        const sentRate = Math.max(0, (hb.net_bytes_sent - prevNetSent) / 5 / 1024)
        const recvRate = Math.max(0, (hb.net_bytes_recv - prevNetRecv) / 5 / 1024)
        netSentHistory.value.push({ time: now, value: Math.round(sentRate * 100) / 100 })
        netRecvHistory.value.push({ time: now, value: Math.round(recvRate * 100) / 100 })
        if (netSentHistory.value.length > MAX_HISTORY) netSentHistory.value.shift()
        if (netRecvHistory.value.length > MAX_HISTORY) netRecvHistory.value.shift()
      }
      prevNetSent = hb.net_bytes_sent
      prevNetRecv = hb.net_bytes_recv
    }
  }

  async function fetchHeartbeat() {
    const data = await fetchSection('heartbeat')
    if (data && data.heartbeat) {
      heartbeat.value = data.heartbeat
      pushHistory(data.heartbeat)
      lastUpdated.value = new Date()
    }
  }

  async function fetchAssets() {
    const data = await fetchSection('assets')
    if (data && data.assets) {
      assets.value = data.assets
      lastUpdated.value = new Date()
    }
  }

  async function fetchVaultAlerts() {
    const data = await fetchSection('vault_alerts')
    if (data && data.vault_alerts) {
      vaultAlerts.value = data.vault_alerts
      lastUpdated.value = new Date()
    }
  }

  async function fetchOperations() {
    const data = await fetchSection('operations')
    if (data && data.operations) {
      operations.value = data.operations
      lastUpdated.value = new Date()
    }
  }

  async function fetchSlowSections() {
    const data = await fetchSection('trash_backlog')
    if (data && data.trash_backlog) trashBacklog.value = data.trash_backlog

    const data2 = await fetchSection('content_trend')
    if (data2 && data2.content_trend) contentTrend.value = data2.content_trend

    const data3 = await fetchSection('login_monitor')
    if (data3 && data3.login_monitor) loginMonitor.value = data3.login_monitor

    const data4 = await fetchSection('audit_log')
    if (data4 && data4.audit_log) auditLog.value = data4.audit_log

    const data5 = await fetchSection('service_health')
    if (data5 && data5.service_health) serviceHealth.value = data5.service_health

    const data6 = await fetchSection('error_logs')
    if (data6 && data6.error_logs) errorLogs.value = data6.error_logs

    const data7 = await fetchSection('email_delivery')
    if (data7 && data7.email_delivery) emailDelivery.value = data7.email_delivery

    const data8 = await fetchSection('action_items')
    if (data8 && data8.action_items) actionItems.value = data8.action_items

    await fetchOperations()
    lastUpdated.value = new Date()
  }

  async function fetchAll() {
    loading.value = true
    const data = await fetchSection('all')
    if (data) {
      if (data.heartbeat) {
        heartbeat.value = data.heartbeat
        pushHistory(data.heartbeat)
      }
      if (data.assets) assets.value = data.assets
      if (data.operations) operations.value = data.operations
      if (data.action_items) actionItems.value = data.action_items
      if (data.vault_alerts) vaultAlerts.value = data.vault_alerts
      if (data.trash_backlog) trashBacklog.value = data.trash_backlog
      if (data.content_trend) contentTrend.value = data.content_trend
      if (data.login_monitor) loginMonitor.value = data.login_monitor
      if (data.audit_log) auditLog.value = data.audit_log
      if (data.service_health) serviceHealth.value = data.service_health
      if (data.email_delivery) emailDelivery.value = data.email_delivery
      if (data.error_logs) errorLogs.value = data.error_logs
      lastUpdated.value = new Date()
    }
    loading.value = false
  }

  function startPolling() {
    fetchAll()
    heartbeatTimer = setInterval(fetchHeartbeat, 5000)
    assetsTimer = setInterval(() => {
      fetchAssets()
      fetchVaultAlerts()
      fetchSlowSections()
    }, 30000)
  }

  function stopPolling() {
    if (heartbeatTimer) { clearInterval(heartbeatTimer); heartbeatTimer = null }
    if (assetsTimer) { clearInterval(assetsTimer); assetsTimer = null }
    stopReconnectCountdown()
  }

  async function manualRefresh() {
    await fetchAll()
  }

  async function banIp(ip) {
    try {
      const resp = await fetch('/api/ban_ip/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
        },
        credentials: 'same-origin',
        body: JSON.stringify({ ip }),
      })
      const data = await resp.json()
      return data
    } catch (e) {
      return { status: 'error', message: e.message }
    }
  }

  return {
    heartbeat, assets, operations, actionItems, vaultAlerts,
    trashBacklog, contentTrend, loginMonitor, auditLog,
    serviceHealth, emailDelivery, errorLogs,
    cpuHistory, memHistory, netSentHistory, netRecvHistory,
    loading, error, connected, lastUpdated, reconnectCountdown,
    alertCount, criticalCount, suspiciousCount,
    startPolling, stopPolling, manualRefresh, banIp,
    fetchAll, fetchHeartbeat, fetchAssets, fetchVaultAlerts, fetchOperations, fetchSlowSections,
  }
})
