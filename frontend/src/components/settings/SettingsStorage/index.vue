<template>
  <div class="storage-settings">
    <el-alert
      title="存储用量"
      type="info"
      :closable="false"
      class="storage-alert"
    >
      查看你的笔记图片、聊天附件和群组附件占用情况。上传新文件时会自动检查剩余配额。
    </el-alert>

    <section class="export-panel">
      <div>
        <h3>数据导出</h3>
        <p>下载自己的普通笔记、可见聊天记录与附件清单。保密笔记和附件文件本体不会包含在导出包内。</p>
      </div>
      <el-button type="primary" :loading="exporting" @click="exportData">
        <i class="fas fa-download"></i>
        导出我的数据
      </el-button>
    </section>

    <el-skeleton v-if="loading" :rows="6" animated />

    <el-alert
      v-else-if="error"
      type="error"
      :closable="false"
      class="storage-alert"
    >
      {{ error }}
      <el-button size="small" text type="primary" @click="fetchQuota">重试</el-button>
    </el-alert>

    <template v-else>
      <section class="storage-overview">
        <div>
          <p class="storage-kicker">当前总用量</p>
          <h3>{{ formatBytes(quota.used_bytes) }}</h3>
          <span>剩余 {{ formatBytes(quota.remaining_bytes) }} / 共 {{ formatBytes(quota.limit_bytes) }}</span>
        </div>
        <el-progress
          type="dashboard"
          :percentage="quota.percent || 0"
          :color="progressColor"
          :width="132"
        />
      </section>

      <section class="storage-grid">
        <article class="storage-card">
          <i class="fas fa-image"></i>
          <div>
            <strong>{{ formatBytes(quota.breakdown.note_assets_bytes) }}</strong>
            <span>笔记图片与正文资源</span>
          </div>
        </article>
        <article class="storage-card">
          <i class="fas fa-paperclip"></i>
          <div>
            <strong>{{ formatBytes(quota.breakdown.message_attachments_bytes) }}</strong>
            <span>聊天附件</span>
          </div>
        </article>
        <article class="storage-card">
          <i class="fas fa-users"></i>
          <div>
            <strong>{{ formatBytes(quota.breakdown.owned_group_attachments_bytes) }}</strong>
            <span>我创建的群组附件</span>
          </div>
        </article>
      </section>

      <section class="storage-details">
        <h3 class="section-title">
          <i class="fas fa-chart-pie"></i> 资产数量
        </h3>
        <div class="storage-list">
          <div class="storage-row">
            <span>普通笔记</span>
            <strong>{{ quota.counts.notes }}</strong>
          </div>
          <div class="storage-row">
            <span>保密笔记</span>
            <strong>{{ quota.counts.secret_notes }}</strong>
          </div>
          <div class="storage-row">
            <span>笔记图片资源</span>
            <strong>{{ quota.counts.note_assets }}</strong>
          </div>
          <div class="storage-row">
            <span>聊天附件</span>
            <strong>{{ quota.counts.message_attachments }}</strong>
          </div>
          <div class="storage-row">
            <span>我创建的群组</span>
            <strong>{{ quota.counts.owned_groups }}</strong>
          </div>
        </div>
      </section>

      <section class="storage-details">
        <h3 class="section-title">
          <i class="fas fa-layer-group"></i> 附件类型
        </h3>
        <div class="storage-list">
          <div
            v-for="item in attachmentTypeRows"
            :key="item.type"
            class="storage-row"
          >
            <span>{{ item.label }} · {{ item.count }} 个</span>
            <strong>{{ formatBytes(item.bytes) }}</strong>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const exporting = ref(false)
const error = ref('')
const quota = ref({
  limit_bytes: 0,
  used_bytes: 0,
  remaining_bytes: 0,
  percent: 0,
  breakdown: {
    note_assets_bytes: 0,
    message_attachments_bytes: 0,
    owned_group_attachments_bytes: 0,
  },
  counts: {
    notes: 0,
    secret_notes: 0,
    note_assets: 0,
    message_attachments: 0,
    owned_groups: 0,
  },
  attachment_types: {},
})

const typeLabels = {
  image: '图片',
  video: '视频',
  audio: '音频',
  file: '文件',
}

const progressColor = computed(() => {
  const percent = Number(quota.value.percent || 0)
  if (percent >= 90) return '#ef4444'
  if (percent >= 75) return '#f59e0b'
  return '#2563eb'
})

const attachmentTypeRows = computed(() => {
  const types = quota.value.attachment_types || {}
  return Object.keys(typeLabels).map(type => ({
    type,
    label: typeLabels[type],
    count: types[type]?.count || 0,
    bytes: types[type]?.bytes || 0,
  }))
})

async function fetchQuota() {
  loading.value = true
  error.value = ''
  try {
    const response = await fetch('/api/storage/quota/')
    const data = await response.json().catch(() => ({}))
    if (!response.ok || data.status === 'error') {
      throw new Error(data.error || '存储用量加载失败')
    }
    quota.value = {
      ...quota.value,
      ...(data.quota || {}),
      breakdown: {
        ...quota.value.breakdown,
        ...(data.quota?.breakdown || {}),
      },
      counts: {
        ...quota.value.counts,
        ...(data.quota?.counts || {}),
      },
      attachment_types: data.quota?.attachment_types || {},
    }
  } catch (err) {
    error.value = err?.message || '存储用量加载失败'
    ElMessage.error(error.value)
  } finally {
    loading.value = false
  }
}

async function exportData() {
  exporting.value = true
  try {
    const response = await fetch('/api/account/export/')
    if (!response.ok) {
      const data = await response.json().catch(() => ({}))
      throw new Error(data.message || data.error || '导出失败')
    }
    const blob = await response.blob()
    const disposition = response.headers.get('content-disposition') || ''
    const filename = disposition.match(/filename="([^"]+)"/)?.[1] || 'knowledge-export.json'
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    URL.revokeObjectURL(url)
    ElMessage.success('数据导出已开始下载')
  } catch (err) {
    ElMessage.error(err?.message || '导出失败')
  } finally {
    exporting.value = false
  }
}

function formatBytes(bytes) {
  const size = Number(bytes || 0)
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  if (size < 1024 * 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`
  return `${(size / 1024 / 1024 / 1024).toFixed(1)} GB`
}

onMounted(fetchQuota)
</script>

<style scoped>
.storage-settings {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.storage-alert {
  margin-bottom: 2px;
}

.export-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 18px 20px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #f8fbff;
}

.export-panel h3 {
  margin: 0 0 6px;
  color: #0f172a;
  font-size: 15px;
}

.export-panel p {
  margin: 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.55;
}

.export-panel .el-button i {
  margin-right: 7px;
}

.storage-overview {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 24px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
}

.storage-kicker {
  margin: 0 0 8px;
  color: #64748b;
  font-size: 13px;
}

.storage-overview h3 {
  margin: 0 0 8px;
  color: #0f172a;
  font-size: 30px;
  font-weight: 700;
}

.storage-overview span {
  color: #64748b;
  font-size: 14px;
}

.storage-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.storage-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
}

.storage-card i {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  color: #2563eb;
  background: #eff6ff;
}

.storage-card strong {
  display: block;
  color: #0f172a;
  font-size: 18px;
  margin-bottom: 4px;
}

.storage-card span,
.storage-row span {
  color: #64748b;
  font-size: 13px;
}

.storage-details {
  padding: 20px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
}

.section-title {
  margin: 0 0 16px;
  color: #0f172a;
  font-size: 15px;
  font-weight: 600;
}

.section-title i {
  margin-right: 8px;
  color: #2563eb;
}

.storage-list {
  display: flex;
  flex-direction: column;
}

.storage-row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 0;
  border-top: 1px solid #f1f5f9;
}

.storage-row:first-child {
  border-top: 0;
  padding-top: 0;
}

.storage-row:last-child {
  padding-bottom: 0;
}

.storage-row strong {
  color: #0f172a;
  font-size: 14px;
}

@media (max-width: 820px) {
  .storage-overview {
    align-items: flex-start;
    flex-direction: column;
  }

  .storage-grid {
    grid-template-columns: 1fr;
  }

  .export-panel {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
