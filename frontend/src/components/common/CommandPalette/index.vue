<template>
  <transition name="cmdk-fade">
    <div v-if="visible" class="cmdk-overlay" @click.self="close">
      <div class="cmdk-panel" role="dialog" aria-modal="true" aria-label="快速搜索">
        <div class="cmdk-input-row">
          <i class="fas fa-search cmdk-input-icon"></i>
          <input
            ref="inputRef"
            v-model="query"
            class="cmdk-input"
            type="text"
            placeholder="搜索笔记、群聊，或执行操作…"
            autocomplete="off"
            spellcheck="false"
            @keydown.down.prevent="move(1)"
            @keydown.up.prevent="move(-1)"
            @keydown.enter.prevent="activate"
            @keydown.esc.prevent="close"
          />
          <span class="cmdk-hint-esc">ESC</span>
        </div>

        <div class="cmdk-results" ref="resultsRef">
          <div v-if="loading" class="cmdk-status">
            <i class="fas fa-spinner fa-spin"></i> 搜索中…
          </div>

          <template v-else>
            <div
              v-for="section in sections"
              :key="section.key"
              class="cmdk-section"
            >
              <div class="cmdk-section-title">{{ section.title }}</div>
              <button
                v-for="item in section.items"
                :key="item.uid"
                type="button"
                class="cmdk-item"
                :class="{ 'is-active': item.index === activeIndex }"
                @click="run(item)"
                @mousemove="activeIndex = item.index"
              >
                <span class="cmdk-item-icon"><i :class="item.icon"></i></span>
                <span class="cmdk-item-body">
                  <span class="cmdk-item-label">{{ item.label }}</span>
                  <span v-if="item.meta" class="cmdk-item-meta">{{ item.meta }}</span>
                </span>
                <span v-if="item.badge" class="cmdk-item-badge">{{ item.badge }}</span>
              </button>
            </div>

            <div v-if="!hasAnyItem" class="cmdk-status cmdk-empty">
              <i class="far fa-folder-open"></i>
              {{ query ? '没有找到匹配结果' : '输入关键词开始搜索' }}
            </div>
          </template>
        </div>

        <div class="cmdk-footer">
          <span><kbd>↑</kbd><kbd>↓</kbd> 选择</span>
          <span><kbd>↵</kbd> 打开</span>
          <span><kbd>Ctrl</kbd><kbd>K</kbd> 唤起</span>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import '@/assets/styles/components/command-palette.css'

const visible = ref(false)
const query = ref('')
const loading = ref(false)
const notes = ref([])
const groups = ref([])
const activeIndex = ref(0)
const inputRef = ref(null)
const resultsRef = ref(null)

let debounceTimer = null
let abortController = null

const isAuthenticated = computed(() => {
  return document.body?.dataset?.authenticated === 'true' ||
    !!document.querySelector('[name=csrfmiddlewaretoken]')
})

// Static quick actions, filtered by the current query text.
const ALL_ACTIONS = [
  { key: 'new-note', label: '新建笔记', icon: 'fas fa-file-circle-plus', keywords: '新建 笔记 note new create', href: '/knowledge/?create=1' },
  { key: 'notes', label: '打开知识笔记', icon: 'fas fa-book', keywords: '笔记 知识 notes knowledge', href: '/knowledge/' },
  { key: 'messages', label: '打开私信', icon: 'fas fa-comments', keywords: '私信 消息 messages chat', href: '/messages/' },
  { key: 'dashboard', label: '打开仪表盘', icon: 'fas fa-gauge-high', keywords: '仪表盘 dashboard 数据', href: '/dashboard/' },
  { key: 'settings', label: '打开设置', icon: 'fas fa-gear', keywords: '设置 settings 偏好', href: '/settings/' },
  { key: 'home', label: '返回首页', icon: 'fas fa-house', keywords: '首页 home', href: '/' },
]

const matchedActions = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return ALL_ACTIONS
  return ALL_ACTIONS.filter(
    (a) => a.label.toLowerCase().includes(q) || a.keywords.toLowerCase().includes(q),
  )
})

const ROLE_LABELS = { owner: '群主', admin: '管理员', member: '成员' }

// Flatten all sections into an indexed list for keyboard navigation.
const sections = computed(() => {
  let index = 0
  const out = []

  if (notes.value.length) {
    out.push({
      key: 'notes',
      title: '笔记',
      items: notes.value.map((n) => ({
        uid: `note-${n.id}`,
        index: index++,
        icon: n.is_public ? 'fas fa-globe' : 'fas fa-file-lines',
        label: n.title || '(无标题)',
        meta: n.updated_at,
        badge: n.is_public ? '公开' : '',
        type: 'note',
        payload: n,
      })),
    })
  }

  if (groups.value.length) {
    out.push({
      key: 'groups',
      title: '群聊',
      items: groups.value.map((g) => ({
        uid: `group-${g.id}`,
        index: index++,
        icon: 'fas fa-user-group',
        label: g.name,
        meta: ROLE_LABELS[g.role] || '',
        type: 'group',
        payload: g,
      })),
    })
  }

  if (matchedActions.value.length) {
    out.push({
      key: 'actions',
      title: '快捷操作',
      items: matchedActions.value.map((a) => ({
        uid: `action-${a.key}`,
        index: index++,
        icon: a.icon,
        label: a.label,
        type: 'action',
        payload: a,
      })),
    })
  }

  return out
})

const flatItems = computed(() => sections.value.flatMap((s) => s.items))
const hasAnyItem = computed(() => flatItems.value.length > 0)

watch(query, () => {
  activeIndex.value = 0
  scheduleSearch()
})

watch(sections, () => {
  if (activeIndex.value >= flatItems.value.length) {
    activeIndex.value = Math.max(0, flatItems.value.length - 1)
  }
})

function scheduleSearch() {
  clearTimeout(debounceTimer)
  const q = query.value.trim()
  if (!q) {
    notes.value = []
    groups.value = []
    loading.value = false
    return
  }
  debounceTimer = setTimeout(runSearch, 220)
}

async function runSearch() {
  const q = query.value.trim()
  if (!q) return
  if (abortController) abortController.abort()
  abortController = new AbortController()
  loading.value = true
  try {
    const res = await fetch(`/api/quick-search/?q=${encodeURIComponent(q)}`, {
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      signal: abortController.signal,
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    notes.value = Array.isArray(data.notes) ? data.notes : []
    groups.value = Array.isArray(data.groups) ? data.groups : []
  } catch (err) {
    if (err.name !== 'AbortError') {
      notes.value = []
      groups.value = []
    }
  } finally {
    if (!abortController.signal.aborted) loading.value = false
  }
}

function move(delta) {
  const total = flatItems.value.length
  if (!total) return
  activeIndex.value = (activeIndex.value + delta + total) % total
  nextTick(scrollActiveIntoView)
}

function scrollActiveIntoView() {
  const el = resultsRef.value?.querySelector('.cmdk-item.is-active')
  el?.scrollIntoView({ block: 'nearest' })
}

function activate() {
  const item = flatItems.value[activeIndex.value]
  if (item) run(item)
}

function run(item) {
  if (item.type === 'note') {
    go(`/knowledge/?note=${item.payload.id}`)
  } else if (item.type === 'group') {
    go(`/messages/?open_group=${item.payload.id}`)
  } else if (item.type === 'action') {
    go(item.payload.href)
  }
}

function go(href) {
  close()
  window.location.href = href
}

function open() {
  if (!isAuthenticated.value) return
  visible.value = true
  nextTick(() => inputRef.value?.focus())
}

function close() {
  visible.value = false
  query.value = ''
  notes.value = []
  groups.value = []
  activeIndex.value = 0
  loading.value = false
  clearTimeout(debounceTimer)
  if (abortController) abortController.abort()
}

function onKeydown(e) {
  const key = e.key?.toLowerCase()
  if ((e.metaKey || e.ctrlKey) && key === 'k') {
    // 知识库页有覆盖更全面的 GlobalSearchDialog（笔记/消息/用户/文件），把 Ctrl+K 让给它
    if (window.__globalSearchDialogActive) return
    e.preventDefault()
    visible.value ? close() : open()
  }
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
  window.addEventListener('open-command-palette', open)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  window.removeEventListener('open-command-palette', open)
})
</script>
