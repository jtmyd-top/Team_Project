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
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'

const props = defineProps({
  title: {
    type: String,
    default: '全部笔记'
  },
  isCollapsed: {
    type: Boolean,
    default: false
  },
  searchQuery: {
    type: String,
    default: ''
  },
  hasMore: {
    type: Boolean,
    default: false
  },
  isLoadingMore: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits([
  'toggle-collapse',
  'update:searchQuery',
  'create-note',
  'load-more'
])

// Infinite Scroll
const contentRef = ref(null)
const loadTrigger = ref(null)
let observer = null

const setupObserver = () => {
  if (observer) observer.disconnect()

  observer = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting && props.hasMore && !props.isLoadingMore) {
      emit('load-more')
    }
  }, {
    root: contentRef.value,
    threshold: 0.1
  })

  if (loadTrigger.value) {
    observer.observe(loadTrigger.value)
  }
}

watch(() => props.hasMore, (newVal) => {
  if (newVal) {
    nextTick(setupObserver)
  }
})

onMounted(() => {
  setupObserver()
})

onUnmounted(() => {
  if (observer) observer.disconnect()
})
</script>

<style scoped>
.secondary-sidebar {
  width: 260px;
  height: 100%;
  background: var(--bg-primary); /* Use a slightly lighter/different bg than primary sidebar */
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
  position: relative;
  flex-shrink: 0;
  z-index: 101;
}

.secondary-sidebar.collapsed {
  width: 0;
  border-right: none;
  opacity: 0;
}

.sidebar-header {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  flex-shrink: 0;
}

.sidebar-title {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
  white-space: nowrap;
}

.collapse-btn {
  padding: 8px;
  background: transparent;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  border-radius: 4px;
}

.collapse-btn:hover {
  background: var(--hover-bg);
  color: var(--text-primary);
}

.search-section {
  padding: 0 16px 12px;
  flex-shrink: 0;
}

.search-box {
  position: relative;
}

.search-box i {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-secondary);
  font-size: 14px;
}

.search-box input {
  width: 100%;
  padding: 8px 12px 8px 32px;
  border-radius: 6px;
  border: 1px solid var(--border-color);
  background: var(--input-bg, var(--bg-secondary));
  color: var(--text-primary);
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s;
}

.search-box input:focus {
  border-color: var(--primary-color);
}

.sidebar-actions {
  padding: 0 16px 16px;
  flex-shrink: 0;
}

.new-note-btn {
  width: 100%;
  padding: 8px;
  background: var(--primary-color);
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 500;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: opacity 0.2s;
}

.new-note-btn:hover {
  opacity: 0.9;
}

.sidebar-content {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 0 8px;
}

.load-trigger {
  height: 20px;
  margin-top: 10px;
}

.loading-more {
  text-align: center;
  padding: 10px;
  color: var(--text-secondary);
  font-size: 13px;
}

/* Scrollbar styling */
.sidebar-content::-webkit-scrollbar {
  width: 4px;
}

.sidebar-content::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 2px;
}

.sidebar-content::-webkit-scrollbar-track {
  background: transparent;
}
</style>
