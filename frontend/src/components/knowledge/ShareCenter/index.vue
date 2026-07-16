<template>
  <section class="knowledge-center">
    <header class="center-header">
      <div>
        <p class="center-kicker">笔记流转</p>
        <h2>分享管理</h2>
        <span>查看并撤销你发送到私信或群聊的笔记分享</span>
      </div>
      <div class="center-actions">
        <button
          v-for="item in filters"
          :key="item.value"
          class="segment-btn"
          :class="{ active: activeFilter === item.value }"
          @click="setFilter(item.value)"
        >
          {{ item.label }}
        </button>
        <button class="ghost-action" :disabled="loading" @click="fetchShares">
          <i class="fas fa-rotate-right"></i>
        </button>
      </div>
    </header>

    <div v-if="loading && !shares.length" class="center-state">
      <i class="fas fa-spinner fa-spin"></i>
      <span>加载中...</span>
    </div>

    <div v-else-if="error && !shares.length" class="center-state error">
      <i class="fas fa-circle-exclamation"></i>
      <span>{{ error }}</span>
      <button @click="fetchShares">重试</button>
    </div>

    <div v-else-if="shares.length === 0" class="center-state">
      <i class="fas fa-share-nodes"></i>
      <span>{{ activeFilter === 'active' ? '暂无有效分享' : '暂无分享记录' }}</span>
    </div>

    <div v-else class="center-list">
      <article v-for="share in shares" :key="`${share.scope}-${share.id}`" class="share-row">
        <div class="target-avatar">
          <img :src="share.target.avatar" alt="" />
        </div>
        <div class="share-body">
          <div class="share-title-line">
            <h3>{{ share.note.title }}</h3>
            <span class="share-status" :class="{ revoked: share.is_revoked }">
              {{ share.is_revoked ? '已撤销' : '有效' }}
            </span>
          </div>
          <p>
            分享至{{ share.target.type === 'group' ? '群聊' : '私信' }}：
            <strong>{{ share.target.name }}</strong>
            <span> · {{ formatMonthDayShortTime(share.created_at) }}</span>
          </p>
        </div>
        <div class="share-actions">
          <button class="ghost-action read-action" @click="openReaderDialog(share)">
            <i class="fas fa-eye"></i>
            查看 {{ share.view_count || 0 }} 次 · 已读 {{ share.read_count || 0 }} 人
          </button>
          <div class="forward-control">
            <span>允许转发</span>
            <el-switch
              :model-value="share.allow_forwarding !== false"
              :disabled="share.is_revoked || updatingForwardKey === `${share.scope}-${share.id}`"
              @change="updateForwarding(share, $event)"
            />
          </div>
          <a class="ghost-action" href="/messages/">去聊天</a>
          <button
            class="danger-action"
            :disabled="share.is_revoked || revokingKey === `${share.scope}-${share.id}`"
            @click="revokeShare(share)"
          >
            {{ revokingKey === `${share.scope}-${share.id}` ? '处理中' : '撤销' }}
          </button>
        </div>
      </article>
      <button
        v-if="pagination.has_next"
        class="load-more"
        :disabled="loadingMore"
        @click="loadMore"
      >
        <i v-if="loadingMore" class="fas fa-spinner fa-spin"></i>
        <span>{{ loadingMore ? '加载中...' : '加载更多' }}</span>
      </button>
    </div>

    <el-dialog
      v-model="readerDialogVisible"
      class="share-readers-dialog"
      width="460px"
      :title="readerDialogShare ? `${readerDialogShare.note.title} · 阅读记录` : '阅读记录'"
      append-to-body
    >
      <div v-if="loadingReaders" class="readers-state">
        <i class="fas fa-spinner fa-spin"></i>
        <span>正在加载阅读记录...</span>
      </div>
      <div v-else-if="!readerRecords.length" class="readers-state">
        <i class="fas fa-eye-slash"></i>
        <span>暂时还没有其他人阅读这篇笔记</span>
      </div>
      <div v-else class="reader-list">
        <div v-for="record in readerRecords" :key="record.user.id" class="reader-row">
          <img :src="record.user.avatar" alt="" class="reader-avatar" />
          <div class="reader-body">
            <strong>{{ record.user.username }}</strong>
            <span>首次阅读：{{ formatMonthDayShortTime(record.first_read_at) }}</span>
          </div>
          <time>{{ formatMonthDayShortTime(record.last_read_at) }}</time>
          <span class="reader-view-count">查看 {{ record.view_count || 0 }} 次</span>
        </div>
      </div>
    </el-dialog>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElDialog, ElMessage, ElSwitch } from 'element-plus'
import 'element-plus/es/components/dialog/style/css'
import 'element-plus/es/components/switch/style/css'
import { formatMonthDayShortTime } from '@/utils/datetime'
import { extractApiErrorMessage } from '@/utils/apiError'

const filters = [
  { label: '全部', value: 'all' },
  { label: '有效', value: 'active' },
  { label: '已撤销', value: 'revoked' },
]

const shares = ref([])
const loading = ref(false)
const loadingMore = ref(false)
const error = ref('')
const activeFilter = ref('all')
const revokingKey = ref('')
const updatingForwardKey = ref('')
const readerDialogVisible = ref(false)
const readerDialogShare = ref(null)
const readerRecords = ref([])
const loadingReaders = ref(false)
const pagination = ref({
  page: 1,
  has_next: false,
})

function getCSRFToken() {
  const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : ''
}

async function fetchShares(options = {}) {
  const append = options?.append === true
  const targetPage = Number(options?.page || 1)
  if (append) {
    loadingMore.value = true
  } else {
    loading.value = true
    error.value = ''
  }
  try {
    const params = new URLSearchParams({ page_size: '50', page: String(targetPage) })
    if (activeFilter.value !== 'all') params.set('status', activeFilter.value)
    const response = await fetch(`/api/messages/notes/shares/?${params.toString()}`)
    const data = await response.json().catch(() => ({}))
    if (!response.ok || data.status === 'error') {
      throw new Error(extractApiErrorMessage(data, '分享记录加载失败'))
    }
    const nextItems = data.shares || []
    shares.value = append ? [...shares.value, ...nextItems] : nextItems
    pagination.value = data.pagination || { page: targetPage, has_next: false }
  } catch (err) {
    error.value = err?.message || '分享记录加载失败'
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

function setFilter(value) {
  if (activeFilter.value === value) return
  activeFilter.value = value
  fetchShares({ page: 1 })
}

function loadMore() {
  if (loading.value || loadingMore.value || !pagination.value.has_next) return
  fetchShares({ page: pagination.value.page + 1, append: true })
}

function replaceShare(updatedShare) {
  shares.value = shares.value.map(item => (
    item.scope === updatedShare.scope && item.id === updatedShare.id ? updatedShare : item
  ))
}

async function updateForwarding(share, allowForwarding) {
  const key = `${share.scope}-${share.id}`
  updatingForwardKey.value = key
  try {
    const response = await fetch(`/api/messages/notes/shares/${share.scope}/${share.id}/forwarding/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCSRFToken(),
      },
      body: JSON.stringify({ allow_forwarding: Boolean(allowForwarding) }),
    })
    const data = await response.json().catch(() => ({}))
    if (!response.ok || data.status === 'error') {
      throw new Error(extractApiErrorMessage(data, '转发权限更新失败'))
    }
    replaceShare(data.share)
    ElMessage.success(allowForwarding ? '已允许转发该笔记' : '已禁止转发该笔记')
  } catch (err) {
    ElMessage.error(err?.message || '转发权限更新失败')
  } finally {
    updatingForwardKey.value = ''
  }
}

async function openReaderDialog(share) {
  readerDialogShare.value = share
  readerRecords.value = []
  readerDialogVisible.value = true
  loadingReaders.value = true
  try {
    const response = await fetch(`/api/messages/notes/shares/${share.scope}/${share.id}/reads/`)
    const data = await response.json().catch(() => ({}))
    if (!response.ok || data.status === 'error') {
      throw new Error(extractApiErrorMessage(data, '阅读记录加载失败'))
    }
    readerRecords.value = data.reads || []
  } catch (err) {
    readerDialogVisible.value = false
    ElMessage.error(err?.message || '阅读记录加载失败')
  } finally {
    loadingReaders.value = false
  }
}

async function revokeShare(share) {
  const key = `${share.scope}-${share.id}`
  revokingKey.value = key
  try {
    const response = await fetch(`/api/messages/notes/shares/${share.scope}/${share.id}/revoke/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCSRFToken(),
      },
      body: JSON.stringify({}),
    })
    const data = await response.json().catch(() => ({}))
    if (!response.ok || data.status === 'error') {
      throw new Error(extractApiErrorMessage(data, '撤销失败'))
    }
    const updated = data.share
    replaceShare(updated)
    shares.value = shares.value.filter(item => activeFilter.value !== 'active' || !item.is_revoked)
    ElMessage.success('分享已撤销')
  } catch (err) {
    ElMessage.error(err?.message || '撤销失败')
  } finally {
    revokingKey.value = ''
  }
}

onMounted(fetchShares)
</script>

<style scoped>
.knowledge-center {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 28px;
  background: #f8fafc;
  overflow: hidden;
}

.center-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 24px;
  padding-bottom: 20px;
  border-bottom: 1px solid #e5e7eb;
}

.center-kicker {
  margin: 0 0 6px;
  color: #64748b;
  font-size: 13px;
}

.center-header h2 {
  margin: 0 0 8px;
  color: #0f172a;
  font-size: 26px;
  font-weight: 700;
  letter-spacing: 0;
}

.center-header span,
.share-body p {
  color: #64748b;
  font-size: 14px;
}

.center-actions,
.share-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.forward-control {
  min-height: 34px;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 0 9px;
  border: 1px solid #dbe3ef;
  border-radius: 8px;
  background: #fff;
  color: #475569;
  font-size: 13px;
  white-space: nowrap;
}

.segment-btn,
.ghost-action,
.danger-action,
.center-state button {
  min-height: 34px;
  border: 1px solid #dbe3ef;
  border-radius: 8px;
  background: #fff;
  color: #334155;
  cursor: pointer;
  font-size: 14px;
  padding: 0 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  text-decoration: none;
}

.segment-btn.active {
  background: #2563eb;
  border-color: #2563eb;
  color: #fff;
}

.danger-action {
  border-color: #fecaca;
  color: #dc2626;
}

.danger-action:disabled,
.ghost-action:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.share-actions {
  max-width: 390px;
}

.read-action {
  gap: 6px;
}

.share-actions .el-switch {
  --el-switch-on-color: #2563eb;
}

.load-more {
  align-self: center;
  min-height: 36px;
  border: 1px solid #dbe3ef;
  border-radius: 8px;
  background: #fff;
  color: #2563eb;
  cursor: pointer;
  font-size: 14px;
  padding: 0 18px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.load-more:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.center-list {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 18px 0 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.share-row {
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr) auto;
  gap: 14px;
  align-items: center;
  padding: 14px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
}

.target-avatar {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  overflow: hidden;
  background: #e2e8f0;
}

.target-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.share-body {
  min-width: 0;
}

.share-title-line {
  display: flex;
  gap: 10px;
  align-items: center;
}

.share-title-line h3 {
  margin: 0;
  min-width: 0;
  color: #0f172a;
  font-size: 15px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.share-status {
  flex: 0 0 auto;
  border-radius: 999px;
  background: #dcfce7;
  color: #15803d;
  font-size: 12px;
  padding: 3px 8px;
}

.share-status.revoked {
  background: #f1f5f9;
  color: #64748b;
}

.share-body p {
  margin: 6px 0 0;
}

.center-state {
  flex: 1;
  display: grid;
  place-content: center;
  gap: 12px;
  color: #64748b;
  text-align: center;
}

.center-state i {
  font-size: 28px;
}

.center-state.error {
  color: #dc2626;
}

.readers-state {
  min-height: 160px;
  display: grid;
  place-content: center;
  gap: 10px;
  color: #64748b;
  text-align: center;
}

.readers-state i {
  font-size: 24px;
}

.reader-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 360px;
  overflow: auto;
}

.reader-row {
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 10px;
  padding: 10px 4px;
  border-bottom: 1px solid #eef2f7;
}

.reader-row:last-child {
  border-bottom: 0;
}

.reader-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  object-fit: cover;
  background: #e2e8f0;
}

.reader-body {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.reader-body strong {
  color: #1e293b;
  font-size: 14px;
}

.reader-body span,
.reader-row time {
  color: #64748b;
  font-size: 12px;
}

.reader-view-count {
  color: #64748b;
  font-size: 12px;
  white-space: nowrap;
}

.reader-row time {
  white-space: nowrap;
}

@media (max-width: 720px) {
  .knowledge-center {
    padding: 18px;
  }

  .center-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .share-row {
    grid-template-columns: 40px minmax(0, 1fr);
  }

  .share-actions {
    grid-column: 2;
    justify-content: flex-start;
    max-width: none;
  }

  .reader-row {
    grid-template-columns: 36px minmax(0, 1fr);
  }

  .reader-row time {
    grid-column: 2;
  }

  .reader-view-count {
    grid-column: 2;
  }
}
</style>
