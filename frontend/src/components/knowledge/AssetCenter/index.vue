<template>
  <section class="knowledge-center">
    <header class="center-header">
      <div>
        <p class="center-kicker">聊天资料</p>
        <h2>文件中心</h2>
        <span>{{ scopeDescription }}</span>
      </div>
      <div class="center-actions">
        <div class="scope-tabs" role="tablist" aria-label="文件范围">
          <button
            v-for="item in scopes"
            :key="item.value"
            class="scope-tab"
            :class="{ active: activeScope === item.value }"
            type="button"
            @click="setScope(item.value)"
          >
            {{ item.label }}
          </button>
        </div>
        <button
          v-for="item in filters"
          :key="item.value"
          class="segment-btn"
          :class="{ active: activeType === item.value }"
          @click="setType(item.value)"
        >
          {{ item.label }}
        </button>
        <button class="ghost-action" :disabled="loading" @click="fetchAttachments">
          <i class="fas fa-rotate-right"></i>
        </button>
        <button class="ghost-action" :disabled="loadingOrphans" @click="openOrphanCleanup">
          <i :class="loadingOrphans ? 'fas fa-spinner fa-spin' : 'fas fa-broom'"></i>
          清理未引用
        </button>
      </div>
    </header>

    <div v-if="loading && !attachments.length" class="center-state">
      <i class="fas fa-spinner fa-spin"></i>
      <span>加载中...</span>
    </div>

    <div v-else-if="error && !attachments.length" class="center-state error">
      <i class="fas fa-circle-exclamation"></i>
      <span>{{ error }}</span>
      <button @click="fetchAttachments">重试</button>
    </div>

    <div v-else-if="attachments.length === 0" class="center-state">
      <i class="fas fa-folder-open"></i>
      <span>暂无附件</span>
    </div>

    <div v-else class="asset-grid">
      <article v-for="item in attachments" :key="item.id" class="asset-card">
        <a class="asset-preview" :href="item.url" target="_blank" rel="noopener noreferrer">
          <img v-if="item.type === 'image'" :src="item.url" alt="" />
          <i v-else :class="typeIcon(item.type)"></i>
        </a>
        <div class="asset-body">
          <h3 :title="item.name">{{ item.name }}</h3>
          <p>{{ typeLabel(item.type) }} · {{ formatSize(item.size) }}</p>
          <p v-if="item.context">
            {{ item.context.type === 'group' ? item.context.group_name : item.context.peer_name }}
            · {{ formatMonthDayShortTime(item.context.sent_at || item.created_at) }}
          </p>
          <p v-else>未发送 · {{ formatMonthDayShortTime(item.created_at) }}</p>
        </div>
        <div class="asset-actions">
          <a class="ghost-action" :href="item.url" target="_blank" rel="noopener noreferrer">打开</a>
          <a class="ghost-action" :href="conversationUrl(item)">定位聊天</a>
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

    <el-dialog v-model="orphanDialogVisible" width="620px" title="待清理资源" append-to-body>
      <p class="orphan-summary">
        以下资源未被任何笔记引用。删除后无法恢复，共 {{ orphanAssets.length }} 个，{{ formatSize(orphanTotalBytes) }}。
      </p>
      <div v-if="!orphanAssets.length" class="orphan-empty">没有发现可清理的笔记资源</div>
      <div v-else class="orphan-list">
        <label v-for="item in orphanAssets" :key="item.id" class="orphan-row">
          <input v-model="selectedOrphanIds" type="checkbox" :value="item.id" />
          <i :class="typeIcon(item.type)"></i>
          <span :title="item.name">{{ item.name }}</span>
          <small>{{ formatSize(item.size) }}</small>
        </label>
      </div>
      <template #footer>
        <button class="ghost-action" @click="orphanDialogVisible = false">取消</button>
        <button class="danger-cleanup" :disabled="!selectedOrphanIds.length || deletingOrphans" @click="deleteSelectedOrphans">
          {{ deletingOrphans ? '删除中' : `删除 ${selectedOrphanIds.length} 个资源` }}
        </button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElDialog, ElMessage, ElMessageBox } from 'element-plus'
import 'element-plus/es/components/dialog/style/css'
import { formatMonthDayShortTime } from '@/utils/datetime'
import { extractApiErrorMessage } from '@/utils/apiError'

const filters = [
  { label: '全部', value: 'all' },
  { label: '图片', value: 'image' },
  { label: '视频', value: 'video' },
  { label: '音频', value: 'audio' },
  { label: '文件', value: 'file' },
]
const scopes = [
  { label: '我上传的', value: 'mine' },
  { label: '我可访问的', value: 'accessible' },
]

const attachments = ref([])
const activeType = ref('all')
const activeScope = ref('mine')
const loading = ref(false)
const loadingMore = ref(false)
const error = ref('')
const pagination = ref({
  page: 1,
  has_next: false,
})
const orphanDialogVisible = ref(false)
const orphanAssets = ref([])
const selectedOrphanIds = ref([])
const orphanTotalBytes = ref(0)
const loadingOrphans = ref(false)
const deletingOrphans = ref(false)
const scopeDescription = computed(() => (
  activeScope.value === 'mine'
    ? '集中查看你上传到私信和群聊的附件'
    : '只显示你当前有权限查看的私信和群聊附件'
))

async function fetchAttachments(options = {}) {
  const append = options?.append === true
  const targetPage = Number(options?.page || 1)
  if (append) {
    loadingMore.value = true
  } else {
    loading.value = true
    error.value = ''
  }
  try {
    const params = new URLSearchParams({
      page_size: '60',
      page: String(targetPage),
      scope: activeScope.value,
    })
    if (activeType.value !== 'all') params.set('type', activeType.value)
    const response = await fetch(`/api/messages/attachments/mine/?${params.toString()}`)
    const data = await response.json().catch(() => ({}))
    if (!response.ok || data.status === 'error') {
      throw new Error(extractApiErrorMessage(data, '附件加载失败'))
    }
    const nextItems = data.attachments || []
    attachments.value = append ? [...attachments.value, ...nextItems] : nextItems
    pagination.value = data.pagination || { page: targetPage, has_next: false }
  } catch (err) {
    error.value = err?.message || '附件加载失败'
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

function setType(value) {
  if (activeType.value === value) return
  activeType.value = value
  fetchAttachments({ page: 1 })
}

function setScope(value) {
  if (activeScope.value === value) return
  activeScope.value = value
  fetchAttachments({ page: 1 })
}

function loadMore() {
  if (loading.value || loadingMore.value || !pagination.value.has_next) return
  fetchAttachments({ page: pagination.value.page + 1, append: true })
}

function conversationUrl(item) {
  const context = item?.context
  if (!context) return '/messages/'
  if (context.type === 'group') {
    return `/messages/?group_id=${encodeURIComponent(context.group_id)}&message_id=${encodeURIComponent(context.message_id)}`
  }
  return `/messages/?user_id=${encodeURIComponent(context.peer_id)}&message_id=${encodeURIComponent(context.message_id)}`
}

function typeLabel(type) {
  return {
    image: '图片',
    video: '视频',
    audio: '音频',
    file: '文件',
  }[type] || '附件'
}

function typeIcon(type) {
  return {
    image: 'fas fa-image',
    video: 'fas fa-video',
    audio: 'fas fa-music',
    file: 'fas fa-file-lines',
  }[type] || 'fas fa-paperclip'
}

function formatSize(bytes) {
  const size = Number(bytes || 0)
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  if (size < 1024 * 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`
  return `${(size / 1024 / 1024 / 1024).toFixed(1)} GB`
}

function csrfToken() {
  return document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)?.[1] || ''
}

async function openOrphanCleanup() {
  loadingOrphans.value = true
  try {
    const response = await fetch('/api/note-assets/orphans/')
    const data = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(extractApiErrorMessage(data, '待清理资源加载失败'))
    orphanAssets.value = data.assets || []
    selectedOrphanIds.value = orphanAssets.value.map(item => item.id)
    orphanTotalBytes.value = Number(data.total_bytes || 0)
    orphanDialogVisible.value = true
  } catch (error) {
    ElMessage.error(error.message || '待清理资源加载失败')
  } finally {
    loadingOrphans.value = false
  }
}

async function deleteSelectedOrphans() {
  try {
    await ElMessageBox.confirm(
      `确认永久删除 ${selectedOrphanIds.value.length} 个未引用资源吗？此操作无法恢复。`,
      '删除待清理资源',
      { type: 'warning', confirmButtonText: '永久删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  deletingOrphans.value = true
  try {
    const response = await fetch('/api/note-assets/orphans/delete/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
      body: JSON.stringify({ asset_ids: selectedOrphanIds.value }),
    })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(extractApiErrorMessage(data, '资源删除失败'))
    const removed = new Set(data.deleted_ids || [])
    orphanAssets.value = orphanAssets.value.filter(item => !removed.has(item.id))
    selectedOrphanIds.value = selectedOrphanIds.value.filter(id => !removed.has(id))
    orphanTotalBytes.value = Math.max(0, orphanTotalBytes.value - Number(data.freed_bytes || 0))
    ElMessage.success(`已删除 ${removed.size} 个资源`)
  } catch (error) {
    ElMessage.error(error.message || '资源删除失败')
  } finally {
    deletingOrphans.value = false
  }
}

onMounted(fetchAttachments)
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

.center-header span {
  color: #64748b;
  font-size: 14px;
}

.center-actions,
.asset-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.scope-tabs {
  display: inline-flex;
  overflow: hidden;
  border: 1px solid #dbe3ef;
  border-radius: 8px;
  background: #fff;
}

.scope-tab {
  min-height: 34px;
  border: 0;
  border-right: 1px solid #dbe3ef;
  padding: 0 12px;
  color: #475569;
  background: transparent;
  cursor: pointer;
  font-size: 14px;
}

.scope-tab:last-child {
  border-right: 0;
}

.scope-tab.active {
  color: #fff;
  background: #2563eb;
}

.segment-btn,
.ghost-action,
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

.ghost-action:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.load-more {
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
  justify-content: center;
  gap: 8px;
  grid-column: 1 / -1;
  justify-self: center;
}

.load-more:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.asset-grid {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 18px 0 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
  gap: 14px;
}

.asset-card {
  min-width: 0;
  display: flex;
  flex-direction: column;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
}

.asset-preview {
  height: 150px;
  display: grid;
  place-items: center;
  color: #2563eb;
  background: #eef2ff;
  text-decoration: none;
}

.asset-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.asset-preview i {
  font-size: 34px;
}

.asset-body {
  padding: 14px;
  min-width: 0;
}

.asset-body h3 {
  margin: 0 0 8px;
  color: #0f172a;
  font-size: 15px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.asset-body p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 13px;
}

.asset-actions {
  padding: 0 14px 14px;
  justify-content: flex-start;
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

.orphan-summary { margin: 0 0 14px; color: #475569; font-size: 14px; line-height: 1.6; }
.orphan-list { max-height: 320px; overflow: auto; border-top: 1px solid #e2e8f0; }
.orphan-row { display: grid; grid-template-columns: 20px 24px minmax(0, 1fr) auto; align-items: center; gap: 9px; min-height: 44px; border-bottom: 1px solid #e2e8f0; color: #475569; cursor: pointer; }
.orphan-row span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.orphan-row small { color: #94a3b8; }
.orphan-empty { padding: 28px; color: #64748b; text-align: center; }
.danger-cleanup { min-height: 34px; border: 1px solid #dc2626; border-radius: 6px; padding: 0 12px; color: #fff; background: #dc2626; cursor: pointer; }
.danger-cleanup:disabled { opacity: .55; cursor: not-allowed; }

@media (max-width: 720px) {
  .knowledge-center {
    padding: 18px;
  }

  .center-header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
