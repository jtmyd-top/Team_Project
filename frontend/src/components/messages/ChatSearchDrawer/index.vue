<template>
  <div class="drawer-overlay" @click.self="$emit('close')">
    <aside class="drawer">
      <div class="drawer-header">
        <h3>
          <i class="fas fa-search"></i>
          在此对话中搜索
        </h3>
        <button class="close-btn" @click="$emit('close')">
          <i class="fas fa-times"></i>
        </button>
      </div>

      <div class="drawer-body">
        <div class="input-wrap">
          <input
            ref="inputRef"
            v-model="keyword"
            type="text"
            placeholder="输入关键字..."
            @input="debouncedSearch"
            @keyup.enter="search"
          />
          <button v-if="keyword" class="clear-btn" @click="clearKeyword">
            <i class="fas fa-times-circle"></i>
          </button>
        </div>

        <div v-if="loading" class="state">
          <i class="fas fa-spinner fa-spin"></i>
        </div>

        <div v-else-if="keyword && results.length === 0" class="state">
          <i class="fas fa-search-minus"></i>
          <p>未找到匹配的消息</p>
        </div>

        <div v-else-if="!keyword" class="state">
          <i class="fas fa-keyboard"></i>
          <p>输入关键字查找本对话内的历史消息</p>
        </div>

        <div v-else class="results">
          <p class="result-count">找到 {{ results.length }} 条匹配消息</p>
          <div
            v-for="m in results"
            :key="m.id"
            class="result-item"
            @click="$emit('jump', m)"
          >
            <div class="result-header">
              <span class="sender" :class="{ own: m.is_own }">{{ m.is_own ? '我' : m.sender }}</span>
              <span class="time">{{ formatTime(m.created_at) }}</span>
            </div>
            <p class="result-content" v-html="highlightText(m.content)"></p>
          </div>
        </div>
      </div>
    </aside>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { formatMonthDayHm } from '@utils/datetime'
import { escapeHtml, sanitizeHtml } from '@utils/sanitize'

const props = defineProps({
  peerId: { type: Number, required: true },
})

defineEmits(['close', 'jump'])

const inputRef = ref(null)
const keyword = ref('')
const results = ref([])
const loading = ref(false)
let debounceTimer = null

function debouncedSearch() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(search, 280)
}

async function search() {
  const q = keyword.value.trim()
  if (!q || q.length < 1) {
    results.value = []
    return
  }
  loading.value = true
  try {
    const r = await fetch(
      `/api/messages/get/?user_id=${props.peerId}&q=${encodeURIComponent(q)}`
    )
    if (r.ok) {
      const d = await r.json()
      results.value = d.messages || []
    }
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

function clearKeyword() {
  keyword.value = ''
  results.value = []
  inputRef.value?.focus()
}

function highlightText(text) {
  if (!text) return ''
  const safe = escapeHtml(text)
  const q = keyword.value.trim()
  if (!q) return safe
  const pattern = new RegExp(`(${q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi')
  return sanitizeHtml(safe.replace(pattern, '<mark>$1</mark>'))
}

function formatTime(iso) {
  return formatMonthDayHm(iso)
}

onMounted(async () => {
  await nextTick()
  inputRef.value?.focus()
})
</script>

<style scoped>
.drawer-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.28);
  z-index: 900;
  display: flex;
  justify-content: flex-end;
  animation: fade-in 0.2s;
}

@keyframes fade-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.drawer {
  width: 380px;
  max-width: 90vw;
  background: var(--bg-primary);
  border-left: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  animation: slide-in 0.25s ease;
}

@keyframes slide-in {
  from {
    transform: translateX(20px);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

.drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color);
}

.drawer-header h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 8px;
}

.close-btn {
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 16px;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.close-btn:hover {
  background: var(--bg-tertiary);
}

.drawer-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.input-wrap {
  position: relative;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color);
}

.input-wrap input {
  width: 100%;
  padding: 10px 34px 10px 12px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--bg-secondary);
  color: var(--text-primary);
  font-size: 14px;
  outline: none;
}

.input-wrap input:focus {
  border-color: var(--primary-color);
}

.clear-btn {
  position: absolute;
  right: 28px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  color: var(--text-tertiary);
  cursor: pointer;
  font-size: 16px;
}

.state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  color: var(--text-tertiary);
  gap: 10px;
}

.state i {
  font-size: 40px;
  opacity: 0.4;
}

.results {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.result-count {
  padding: 6px 10px;
  margin: 0 0 8px 0;
  color: var(--text-tertiary);
  font-size: 12px;
}

.result-item {
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
  border: 1px solid transparent;
}

.result-item:hover {
  background: var(--bg-secondary);
  border-color: var(--border-color);
}

.result-header {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--text-tertiary);
  margin-bottom: 4px;
}

.sender.own {
  color: var(--primary-color);
  font-weight: 500;
}

.result-content {
  margin: 0;
  font-size: 13.5px;
  color: var(--text-primary);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.result-content :deep(mark) {
  background: rgba(250, 204, 21, 0.6);
  color: var(--text-primary);
  padding: 0 2px;
  border-radius: 2px;
}
</style>
