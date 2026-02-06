<template>
  <aside
    class="secondary-sidebar"
    :class="{ 'collapsed': isCollapsed }"
  >
    <div class="sidebar-header">
      <h2 class="sidebar-title">{{ title }}</h2>
      <button class="icon-btn collapse-btn" @click="$emit('toggle-collapse')">
        <i class="fas fa-chevron-left"></i>
      </button>
    </div>

    <!-- Search Box -->
    <div class="search-section">
      <div class="search-box">
        <i class="fas fa-search"></i>
        <input
          :value="searchQuery"
          @input="$emit('update:searchQuery', $event.target.value)"
          placeholder="搜索笔记..."
        />
      </div>
    </div>

    <!-- Actions -->
    <div class="sidebar-actions">
      <button class="new-note-btn" @click="$emit('create-note')">
        <i class="fas fa-plus"></i> 新建笔记
      </button>
    </div>

    <!-- Content Area (Folder Tree or List) -->
    <div class="sidebar-content" ref="contentRef">
      <slot></slot>

      <!-- Infinite Scroll Trigger -->
      <div v-if="hasMore" ref="loadTrigger" class="load-trigger"></div>

      <div v-if="isLoadingMore" class="loading-more">
        <i class="fas fa-spinner fa-spin"></i> 加载中...
      </div>
    </div>
  </aside>
</template>

<script setup>
import { useSecondarySidebar } from '@/composables/useSecondarySidebar'
import '@/assets/styles/components/secondary-sidebar.css'

const props = defineProps({
  title: { type: String, default: '全部笔记' },
  isCollapsed: { type: Boolean, default: false },
  searchQuery: { type: String, default: '' },
  hasMore: { type: Boolean, default: false },
  isLoadingMore: { type: Boolean, default: false }
})

const emit = defineEmits([
  'toggle-collapse',
  'update:searchQuery',
  'create-note',
  'load-more'
])

const { contentRef, loadTrigger } = useSecondarySidebar(props, emit)
</script>
