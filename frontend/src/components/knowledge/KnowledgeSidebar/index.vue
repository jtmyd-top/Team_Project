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
import { useKnowledgeSidebar } from '@/composables/useKnowledgeSidebar'
import '@/assets/styles/components/knowledge-sidebar.css'

const props = defineProps({
  notes: { type: Array, default: () => [] },
  selectedNoteId: { type: [String, Number], default: null },
  readingNoteId: { type: [String, Number], default: null },
  searchQuery: { type: String, default: '' },
  isLoading: { type: Boolean, default: false },
  isLoadingMore: { type: Boolean, default: false },
  hasMore: { type: Boolean, default: true },
  isCollapsed: { type: Boolean, default: false },
  isMobileOpen: { type: Boolean, default: false },
  isMobile: { type: Boolean, default: false },
  pageSize: { type: Number, default: 30 }
})

const emit = defineEmits([
  'toggle-collapse',
  'close-mobile',
  'create-note',
  'search',
  'select-note',
  'load-more'
])

const {
  listRef,
  loadTrigger,
  displayNotes,
  setNoteRef,
  formatDate,
  loadMore,
  getNoteElement
} = useKnowledgeSidebar(props, emit)

defineExpose({
  loadMore,
  getNoteElement,
  listRef
})
</script>
