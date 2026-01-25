<template>
  <aside
    class="sidebar"
    :class="{
      'collapsed': isCollapsed,
      'mobile-open': isMobileOpen
    }"
  >
    <div class="sidebar-header">
      <h2 v-show="!isCollapsed">知识库</h2>
      <!-- 移动端：关闭按钮 -->
      <button
        v-if="isMobile"
        class="icon-btn"
        @click="$emit('close-mobile')"
      >
        <i class="fas fa-times"></i>
      </button>
      <!-- 桌面端：折叠按钮 -->
      <button
        v-else
        class="icon-btn toggle-btn"
        @click="$emit('toggle-collapse')"
      >
        <i :class="isCollapsed ? 'fas fa-chevron-right' : 'fas fa-chevron-left'"></i>
      </button>
    </div>

    <div class="sidebar-content" v-show="!isCollapsed || isMobileOpen">
      <div class="sidebar-actions">
        <button class="new-note-btn" @click="$emit('create-note')">
          <i class="fas fa-plus"></i> 新建笔记
        </button>
      </div>

      <div class="search-box">
        <i class="fas fa-search"></i>
        <input
          :value="searchQuery"
          placeholder="搜索..."
          @input="$emit('search', $event.target.value)"
        />
      </div>

      <div class="note-list" ref="listRef">
        <!-- 骨架屏加载状态 -->
        <template v-if="isLoading && !notes.length">
          <div v-for="i in 5" :key="'skeleton-' + i" class="skeleton-note-item">
            <div class="skeleton" style="height: 16px; width: 70%;"></div>
            <div class="skeleton" style="height: 12px; width: 40%;"></div>
          </div>
        </template>

        <div v-else-if="displayNotes.length === 0" class="empty-text">无笔记</div>

        <div
          v-for="note in displayNotes"
          :key="note.id"
          :ref="el => setNoteRef(el, note.id)"
          class="note-item"
          :class="{
            'active': selectedNoteId === note.id,
            'reading': readingNoteId === note.id
          }"
          @click="$emit('select-note', note.id)"
        >
          <div class="note-title-row">
            <span class="note-item-title">{{ note.title || '无标题' }}</span>
            <i v-if="note.is_public" class="fas fa-globe public-icon" title="公开"></i>
          </div>
          <div class="note-item-meta">
            {{ formatDate(note.updated_at) }}
          </div>
        </div>

        <!-- 无限滚动触发器 -->
        <div
          v-if="hasMore && !isLoadingMore"
          ref="loadTrigger"
          style="height: 1px; margin: 0;"
        ></div>

        <!-- 加载更多 -->
        <div v-if="isLoadingMore" class="loading-more">
          <div class="skeleton-note-item">
            <div class="skeleton" style="height: 16px; width: 70%;"></div>
            <div class="skeleton" style="height: 12px; width: 40%;"></div>
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'

// Props
const props = defineProps({
  // 笔记列表
  notes: {
    type: Array,
    default: () => []
  },
  // 当前选中的笔记 ID
  selectedNoteId: {
    type: [String, Number],
    default: null
  },
  // 当前正在阅读的笔记 ID (Scroll Spy)
  readingNoteId: {
    type: [String, Number],
    default: null
  },
  // 搜索关键词
  searchQuery: {
    type: String,
    default: ''
  },
  // 是否正在加载
  isLoading: {
    type: Boolean,
    default: false
  },
  // 是否正在加载更多
  isLoadingMore: {
    type: Boolean,
    default: false
  },
  // 是否还有更多
  hasMore: {
    type: Boolean,
    default: true
  },
  // 侧边栏是否折叠
  isCollapsed: {
    type: Boolean,
    default: false
  },
  // 移动端是否打开
  isMobileOpen: {
    type: Boolean,
    default: false
  },
  // 是否是移动端
  isMobile: {
    type: Boolean,
    default: false
  },
  // 每页显示数量
  pageSize: {
    type: Number,
    default: 30
  }
})

// Emits
const emit = defineEmits([
  'toggle-collapse',
  'close-mobile',
  'create-note',
  'search',
  'select-note',
  'load-more'
])

// Refs
const listRef = ref(null)
const loadTrigger = ref(null)
const noteItemRefs = ref(new Map())

// 显示的笔记数量（用于无限滚动）
const displayedCount = ref(props.pageSize)

// Computed - 显示的笔记
const displayNotes = computed(() => {
  return props.notes.slice(0, displayedCount.value)
})

// 设置笔记元素引用
const setNoteRef = (el, noteId) => {
  if (el) {
    noteItemRefs.value.set(noteId, el)
  }
}

// 格式化日期
const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString()
}

// 设置 Intersection Observer 用于无限滚动
let intersectionObserver = null

const setupIntersectionObserver = () => {
  if (typeof IntersectionObserver === 'undefined') return

  intersectionObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting && props.hasMore && !props.isLoadingMore) {
        emit('load-more')
      }
    })
  }, {
    root: listRef.value,
    rootMargin: '200px',
    threshold: 0.1
  })

  nextTick(() => {
    if (loadTrigger.value) {
      intersectionObserver.observe(loadTrigger.value)
    }
  })
}

// 监听显示数量变化，触发加载更多
watch(displayedCount, (newVal) => {
  if (newVal < props.notes.length) {
    nextTick(() => {
      if (loadTrigger.value && intersectionObserver) {
        intersectionObserver.observe(loadTrigger.value)
      }
    })
  }
})

// 监听笔记列表变化，重置显示数量
watch(() => props.notes, () => {
  displayedCount.value = props.pageSize
})

// 监听搜索关键词变化，重置显示数量
watch(() => props.searchQuery, () => {
  displayedCount.value = props.pageSize
})

// 暴露方法给父组件
const loadMore = () => {
  displayedCount.value += props.pageSize
}

const getNoteElement = (noteId) => {
  return noteItemRefs.value.get(noteId)
}

defineExpose({
  loadMore,
  getNoteElement,
  listRef
})

onMounted(() => {
  setupIntersectionObserver()
})

onUnmounted(() => {
  if (intersectionObserver) {
    intersectionObserver.disconnect()
  }
})
</script>

<style scoped>
/* Sidebar - 固定宽度，独立滚动 */
.sidebar {
  width: 260px !important;
  background: var(--k-sidebar-bg) !important;
  border-right: 1px solid var(--k-border);
  display: flex !important;
  flex-direction: column !important;
  transition: width 0.3s ease, transform 0.3s ease;
  flex-shrink: 0 !important;
  height: 100% !important;
  max-width: 260px !important;
  padding: 0 !important;
  position: relative !important;
  z-index: 100;
}

.sidebar.collapsed {
  width: 50px !important;
  max-width: 50px !important;
}

.sidebar-header {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  border-bottom: 1px solid var(--k-border);
  flex-shrink: 0;
}

.sidebar-header h2 {
  font-size: 18px;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
}

.toggle-btn {
  margin-left: auto;
}

.sidebar-content {
  flex: 1 !important;
  display: flex !important;
  flex-direction: column !important;
  overflow-y: auto !important;
  overflow-x: hidden !important;
  scroll-behavior: smooth;
  scrollbar-width: thin;
  scrollbar-color: var(--k-border) transparent;
}

.sidebar-content::-webkit-scrollbar {
  width: 6px;
}

.sidebar-content::-webkit-scrollbar-track {
  background: transparent;
}

.sidebar-content::-webkit-scrollbar-thumb {
  background: var(--k-border);
  border-radius: 3px;
}

.sidebar-content::-webkit-scrollbar-thumb:hover {
  background: var(--k-text-sec);
}

.sidebar-actions {
  padding: 16px;
  flex-shrink: 0;
}

.new-note-btn {
  width: 100%;
  padding: 8px;
  background: var(--k-primary);
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

.search-box {
  padding: 0 16px 12px;
  position: relative;
  flex-shrink: 0;
}

.search-box i {
  position: absolute;
  left: 26px;
  top: 8px;
  color: var(--k-text-sec);
  font-size: 12px;
}

.search-box input {
  width: 100%;
  padding: 6px 6px 6px 30px;
  border: 1px solid var(--k-border);
  background: var(--k-bg);
  color: var(--k-text);
  border-radius: 4px;
}

.note-list {
  flex: 1;
  padding: 0 8px;
}

.note-item {
  padding: 10px 12px;
  margin-bottom: 4px;
  border-radius: 6px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.2s ease;
}

.note-item:hover {
  background: var(--k-hover);
}

.note-item.active {
  background: var(--k-active);
  border-color: var(--k-border);
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.note-item.reading {
  border-left: 3px solid var(--k-primary);
}

.note-title-row {
  display: flex;
  justify-content: space-between;
  font-weight: 500;
  margin-bottom: 4px;
}

.note-item-meta {
  font-size: 12px;
  color: var(--k-text-sec);
}

.public-icon {
  font-size: 10px;
  color: var(--k-text-sec);
}

.empty-text {
  text-align: center;
  color: var(--k-text-sec);
  padding: 20px;
}

.loading-more {
  padding: 12px;
}

.icon-btn {
  background: transparent;
  border: none;
  color: var(--k-text-sec);
  cursor: pointer;
  padding: 6px;
  border-radius: 4px;
}

.icon-btn:hover {
  background: var(--k-hover);
  color: var(--k-text);
}

/* 骨架屏 */
.skeleton {
  background: linear-gradient(90deg, var(--k-bg) 25%, var(--k-hover) 50%, var(--k-bg) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 4px;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.skeleton-note-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  margin-bottom: 4px;
  border-radius: 6px;
}

/* 移动端响应式 */
@media (max-width: 1024px) {
  .sidebar {
    position: fixed !important;
    top: 64px;
    left: 0;
    bottom: 0;
    width: 280px !important;
    transform: translateX(-100%) !important;
    background: var(--k-sidebar-bg);
    box-shadow: 2px 0 10px rgba(0,0,0,0.2);
    z-index: 100;
  }

  .sidebar.mobile-open {
    transform: translateX(0) !important;
  }

  .sidebar.collapsed {
    width: 280px !important;
    transform: translateX(-100%) !important;
  }
}

@media (max-width: 768px) {
  .sidebar {
    top: 56px;
  }
}
</style>
