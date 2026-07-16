<template>
  <div v-if="visible" class="global-search-overlay" @click.self="close">
    <section class="global-search-dialog" role="dialog" aria-modal="true" aria-label="全局搜索">
      <header class="global-search-header">
        <i class="fas fa-magnifying-glass"></i>
        <input
          ref="inputRef"
          v-model="query"
          type="search"
          placeholder="搜索笔记、消息、群组、用户或文件"
          @input="scheduleSearch"
          @keydown.esc.prevent="close"
        >
        <button type="button" class="icon-button" title="关闭搜索" @click="close">
          <i class="fas fa-xmark"></i>
        </button>
      </header>

      <div v-if="loading" class="search-state"><i class="fas fa-spinner fa-spin"></i> 正在搜索</div>
      <div v-else-if="error" class="search-state error">{{ error }}</div>
      <div v-else-if="query && !hasResults" class="search-state">未找到可访问的内容</div>
      <div v-else-if="hasResults" class="search-results">
        <section v-for="section in sections" :key="section.key" v-show="section.items.length" class="result-section">
          <h3>{{ section.label }}</h3>
          <button
            v-for="item in section.items"
            :key="`${item.type}-${item.id}`"
            type="button"
            class="result-item"
            @click="openResult(item)"
          >
            <i :class="resultIcon(item.type)"></i>
            <span class="result-copy">
              <strong>{{ item.title }}</strong>
              <small>{{ item.summary }}</small>
            </span>
          </button>
        </section>
      </div>
      <footer v-else class="search-hint">输入至少一个关键词开始搜索</footer>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

const visible = ref(false)
const query = ref('')
const loading = ref(false)
const error = ref('')
const results = ref({})
const inputRef = ref(null)
let timer = null

const sections = computed(() => [
  { key: 'notes', label: '笔记', items: results.value.notes || [] },
  { key: 'messages', label: '消息', items: results.value.messages || [] },
  { key: 'groups', label: '群组', items: results.value.groups || [] },
  { key: 'users', label: '用户', items: results.value.users || [] },
  { key: 'files', label: '文件', items: results.value.files || [] },
])

const hasResults = computed(() => sections.value.some(section => section.items.length))

function getCSRFToken() {
  const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : ''
}

async function search() {
  const term = query.value.trim()
  if (!term) {
    results.value = {}
    return
  }
  loading.value = true
  error.value = ''
  try {
    const response = await fetch(`/api/search/?q=${encodeURIComponent(term)}`, {
      headers: { 'X-CSRFToken': getCSRFToken() },
    })
    const data = await response.json().catch(() => ({}))
    if (!response.ok || data.status === 'error') throw new Error(data.message || data.error || '搜索失败')
    results.value = data.results || {}
  } catch (err) {
    error.value = err?.message || '搜索失败'
  } finally {
    loading.value = false
  }
}

function scheduleSearch() {
  clearTimeout(timer)
  timer = setTimeout(search, 220)
}

function open() {
  visible.value = true
  nextTick(() => inputRef.value?.focus())
}

function close() {
  visible.value = false
  query.value = ''
  results.value = {}
  error.value = ''
  clearTimeout(timer)
}

function openResult(item) {
  // 笔记结果在知识库页内直接切换并高亮关键词，避免整页刷新
  if (item.type === 'note' && item.id && window.location.pathname.startsWith('/knowledge')) {
    const keyword = query.value.trim()
    close()
    window.dispatchEvent(new CustomEvent('search-result-clicked', {
      detail: { noteId: item.id, highlightKeyword: keyword }
    }))
    return
  }
  if (!item.url) return
  window.location.href = item.url
}

function resultIcon(type) {
  return {
    note: 'fas fa-note-sticky',
    direct_message: 'fas fa-message',
    group_message: 'fas fa-comments',
    group: 'fas fa-users',
    user: 'fas fa-user',
    file: 'fas fa-file',
  }[type] || 'fas fa-magnifying-glass'
}

function handleShortcut(event) {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault()
    open()
  }
}

function handleOpenEvent() {
  open()
}

onMounted(() => {
  // 告知全局命令面板（base.html 注入）本页已有更全面的 Ctrl+K 搜索，让其退让
  window.__globalSearchDialogActive = true
  window.addEventListener('keydown', handleShortcut)
  window.addEventListener('open-global-search', handleOpenEvent)
})

onBeforeUnmount(() => {
  window.__globalSearchDialogActive = false
  clearTimeout(timer)
  window.removeEventListener('keydown', handleShortcut)
  window.removeEventListener('open-global-search', handleOpenEvent)
})
</script>

<style scoped>
.global-search-overlay {
  position: fixed;
  inset: 0;
  z-index: 3000;
  display: grid;
  place-items: start center;
  padding: min(13vh, 120px) 18px 18px;
  background: rgba(15, 23, 42, 0.32);
}

.global-search-dialog {
  width: min(680px, 100%);
  max-height: min(72vh, 720px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid rgba(148, 163, 184, 0.45);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.97);
  box-shadow: 0 24px 60px rgba(15, 23, 42, 0.25);
}

.global-search-header {
  min-height: 56px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 14px;
  border-bottom: 1px solid #e2e8f0;
  color: #64748b;
}

.global-search-header input {
  flex: 1;
  min-width: 0;
  border: 0;
  outline: 0;
  color: #0f172a;
  background: transparent;
  font-size: 15px;
}

.icon-button {
  width: 32px;
  height: 32px;
  border: 0;
  border-radius: 6px;
  color: #64748b;
  background: transparent;
  cursor: pointer;
}

.icon-button:hover {
  color: #0f172a;
  background: #f1f5f9;
}

.search-results {
  overflow: auto;
  padding: 10px;
}

.result-section + .result-section {
  margin-top: 12px;
}

.result-section h3 {
  margin: 8px 8px 6px;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
}

.result-item {
  width: 100%;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 10px;
  border: 0;
  border-radius: 6px;
  color: #334155;
  background: transparent;
  text-align: left;
  cursor: pointer;
}

.result-item:hover {
  background: #eff6ff;
}

.result-item > i {
  width: 18px;
  margin-top: 2px;
  color: #2563eb;
  text-align: center;
}

.result-copy {
  min-width: 0;
  display: grid;
  gap: 3px;
}

.result-copy strong,
.result-copy small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.result-copy strong {
  color: #0f172a;
  font-size: 14px;
}

.result-copy small,
.search-hint,
.search-state {
  color: #64748b;
  font-size: 13px;
}

.search-hint,
.search-state {
  padding: 28px;
  text-align: center;
}

.search-state.error {
  color: #dc2626;
}
</style>
