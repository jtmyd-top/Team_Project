<template>
  <section class="db-card backup-status-card">
    <div class="db-card__header">
      <div>
        <span class="db-card__eyebrow">DATA PROTECTION</span>
        <h3>备份与恢复演练</h3>
      </div>
      <button class="dashboard-header__btn" :disabled="loading" title="刷新备份状态" @click="load">
        <i :class="loading ? 'fas fa-spinner fa-spin' : 'fas fa-rotate'"></i>
      </button>
    </div>

    <div v-if="error" class="backup-status-card__error">{{ error }}</div>
    <template v-else>
      <div class="backup-status-card__row">
        <span>最近快照</span>
        <strong :class="snapshotClass">{{ snapshotText }}</strong>
      </div>
      <div class="backup-status-card__meta">{{ snapshotMeta }}</div>
      <div class="backup-status-card__row">
        <span>最近恢复演练</span>
        <strong :class="drillClass">{{ drillText }}</strong>
      </div>
      <div class="backup-status-card__meta">{{ drillMeta }}</div>
      <div class="backup-status-card__actions">
        <el-button size="small" @click="showCommand = !showCommand">备份命令</el-button>
        <el-button size="small" type="primary" @click="recordDrill">记录演练</el-button>
      </div>
      <code v-if="showCommand" class="backup-status-card__command">{{ runCommand }}</code>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getCsrfToken } from '@/utils/csrf'

const loading = ref(false)
const error = ref('')
const snapshot = ref(null)
const drill = ref(null)
const runCommand = ref('python manage.py run_backup --include-media')
const showCommand = ref(false)

const formatDate = value => value ? new Date(value).toLocaleString() : '尚无记录'
const formatBytes = value => {
  const bytes = Number(value || 0)
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  return `${(bytes / (1024 ** index)).toFixed(index ? 1 : 0)} ${units[index]}`
}

const snapshotText = computed(() => snapshot.value?.status === 'succeeded' ? '已完成' : '尚未备份')
const snapshotClass = computed(() => snapshot.value?.status === 'succeeded' ? 'is-ok' : 'is-warn')
const snapshotMeta = computed(() => snapshot.value
  ? `${formatDate(snapshot.value.completed_at || snapshot.value.started_at)} · ${formatBytes(snapshot.value.size_bytes)}`
  : '使用定时任务运行快照命令')
const drillText = computed(() => drill.value ? '已记录' : '尚未演练')
const drillClass = computed(() => drill.value ? 'is-ok' : 'is-warn')
const drillMeta = computed(() => drill.value ? formatDate(drill.value.completed_at || drill.value.started_at) : '完成恢复演练后在此记录')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const response = await fetch('/api/ops/backups/')
    const data = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(data.message || data.error || '加载备份状态失败')
    snapshot.value = data.latest_snapshot
    drill.value = data.latest_recovery_drill
    runCommand.value = data.run_command || runCommand.value
  } catch (err) {
    error.value = err.message || '加载备份状态失败'
  } finally {
    loading.value = false
  }
}

async function recordDrill() {
  try {
    const { value } = await ElMessageBox.prompt('填写本次恢复演练的范围或结果', '记录恢复演练', {
      inputPlaceholder: '例如：在隔离数据库成功校验笔记与附件',
      confirmButtonText: '记录',
      cancelButtonText: '取消',
    })
    const response = await fetch('/api/ops/backups/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify({ notes: value || '' }),
    })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(data.message || data.error || '记录失败')
    drill.value = data.record
    ElMessage.success('恢复演练已记录')
  } catch (err) {
    if (err !== 'cancel' && err !== 'close') ElMessage.error(err.message || '记录失败')
  }
}

onMounted(load)
</script>

<style scoped>
.backup-status-card__error {
  color: var(--el-color-danger);
  font-size: 12px;
}

.backup-status-card__row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-top: 14px;
  font-size: 13px;
}

.backup-status-card__row span,
.backup-status-card__meta {
  color: var(--db-text-muted, #8691a8);
}

.backup-status-card__row strong.is-ok {
  color: #22c55e;
}

.backup-status-card__row strong.is-warn {
  color: #f59e0b;
}

.backup-status-card__meta {
  margin-top: 4px;
  font-size: 11px;
}

.backup-status-card__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
}

.backup-status-card__command {
  display: block;
  margin-top: 12px;
  padding: 8px;
  overflow: auto;
  border: 1px solid rgba(148, 163, 184, .24);
  background: rgba(15, 23, 42, .55);
  color: #cbd5e1;
  font-size: 11px;
}
</style>
