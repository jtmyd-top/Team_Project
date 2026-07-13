<template>
  <section class="security-devices">
    <div class="security-devices-heading">
      <div>
        <h3><i class="fas fa-laptop-shield"></i> 登录设备</h3>
        <p>查看当前登录会话，并移除不再使用或无法确认的设备。</p>
      </div>
      <button class="device-refresh" type="button" :disabled="loading" title="刷新设备列表" @click="loadDevices">
        <i :class="loading ? 'fas fa-spinner fa-spin' : 'fas fa-rotate'"></i>
      </button>
    </div>

    <div v-if="loading && !devices.length" class="device-state">正在加载设备…</div>
    <div v-else-if="error" class="device-state device-error">{{ error }}</div>
    <div v-else-if="!devices.length" class="device-state">暂无登录设备记录。</div>

    <div v-else class="device-list">
      <article v-for="device in devices" :key="device.id" class="device-row" :class="{ inactive: !device.is_active }">
        <i class="fas fa-desktop device-icon"></i>
        <div class="device-copy">
          <div class="device-title">
            <strong>{{ device.device_info || 'Unknown device' }}</strong>
            <span v-if="device.is_current" class="current-device">当前设备</span>
            <span v-else-if="!device.is_active" class="inactive-device">已移除</span>
          </div>
          <small>{{ device.ip_address || 'IP unavailable' }} · 最近活跃 {{ formatTime(device.last_login_at) }}</small>
        </div>
        <button
          v-if="device.is_active && !device.is_current"
          type="button"
          class="revoke-device"
          :disabled="revokingId === device.id"
          @click="revokeDevice(device)"
        >
          {{ revokingId === device.id ? '移除中…' : '移除' }}
        </button>
      </article>
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const devices = ref([])
const loading = ref(false)
const error = ref('')
const revokingId = ref(null)

function csrfToken() {
  const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : ''
}

function formatTime(value) {
  if (!value) return '未知'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '未知' : date.toLocaleString()
}

async function loadDevices() {
  loading.value = true
  error.value = ''
  try {
    const response = await fetch('/api/security/devices/')
    const data = await response.json().catch(() => ({}))
    if (!response.ok || data.status !== 'success') {
      throw new Error(data.message || '无法加载设备列表')
    }
    devices.value = data.devices || []
  } catch (err) {
    error.value = err?.message || '无法加载设备列表'
  } finally {
    loading.value = false
  }
}

async function revokeDevice(device) {
  try {
    await ElMessageBox.confirm(
      `移除“${device.device_info || '该设备'}”后，该设备需要重新登录。`,
      '移除登录设备',
      { type: 'warning', confirmButtonText: '移除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }

  revokingId.value = device.id
  try {
    const response = await fetch(`/api/security/devices/${device.id}/revoke/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': csrfToken() },
    })
    const data = await response.json().catch(() => ({}))
    if (!response.ok || data.status !== 'success') {
      throw new Error(data.message || '移除设备失败')
    }
    devices.value = devices.value.map(item => item.id === device.id ? data.device : item)
    ElMessage.success('设备已移除')
  } catch (err) {
    ElMessage.error(err?.message || '移除设备失败')
  } finally {
    revokingId.value = null
  }
}

onMounted(loadDevices)
</script>

<style scoped>
.security-devices {
  margin-top: 22px;
  padding-top: 22px;
  border-top: 1px solid #e5e7eb;
}

.security-devices-heading {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: flex-start;
  margin-bottom: 14px;
}

.security-devices h3 {
  margin: 0 0 5px;
  color: #1f2937;
  font-size: 16px;
}

.security-devices h3 i {
  margin-right: 7px;
  color: #2563eb;
}

.security-devices p,
.device-copy small,
.device-state {
  margin: 0;
  color: #6b7280;
  font-size: 13px;
  line-height: 1.55;
}

.device-refresh {
  width: 34px;
  height: 34px;
  border: 1px solid #dbe3ee;
  border-radius: 6px;
  color: #475569;
  background: #fff;
  cursor: pointer;
}

.device-refresh:hover:not(:disabled) {
  color: #1d4ed8;
  border-color: #93c5fd;
  background: #eff6ff;
}

.device-list {
  display: grid;
  gap: 9px;
}

.device-row {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 66px;
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
}

.device-row.inactive {
  opacity: 0.62;
}

.device-icon {
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  border-radius: 6px;
  color: #2563eb;
  background: #eff6ff;
}

.device-copy {
  min-width: 0;
  flex: 1;
}

.device-title {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 7px;
  margin-bottom: 3px;
}

.device-title strong {
  overflow: hidden;
  color: #1f2937;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.current-device,
.inactive-device {
  padding: 2px 7px;
  border-radius: 999px;
  font-size: 11px;
  line-height: 1.35;
}

.current-device {
  color: #166534;
  background: #dcfce7;
}

.inactive-device {
  color: #64748b;
  background: #f1f5f9;
}

.revoke-device {
  flex: 0 0 auto;
  padding: 7px 10px;
  border: 1px solid #fecaca;
  border-radius: 6px;
  color: #b91c1c;
  background: #fff;
  cursor: pointer;
}

.revoke-device:hover:not(:disabled) {
  color: #fff;
  background: #dc2626;
}

.device-error {
  color: #b91c1c;
}

@media (max-width: 560px) {
  .device-row {
    align-items: flex-start;
  }
}
</style>
