<template>
  <div class="drop-folder-item">
    <div
      class="folder-row"
      :class="{
        'is-drop-target': dropTargetId === folder.id,
        'is-current': currentFolderId === folder.id
      }"
      @dragover.prevent="handleDragOver"
      @dragleave="handleDragLeave"
      @drop="handleDrop"
    >
      <!-- 展开/收起图标 -->
      <button
        v-if="hasChildren"
        class="toggle-btn"
        @click.stop="toggleExpand"
      >
        <i class="fas" :class="isExpanded ? 'fa-chevron-down' : 'fa-chevron-right'"></i>
      </button>
      <span v-else class="toggle-placeholder"></span>

      <!-- 文件夹图标 -->
      <i class="fas folder-icon" :class="isExpanded ? 'fa-folder-open' : 'fa-folder'"></i>

      <!-- 名称 -->
      <span class="folder-name">{{ folder.name }}</span>

      <!-- 笔记数量 -->
      <span v-if="folder.notes_count > 0" class="notes-count">
        {{ folder.notes_count }}
      </span>

      <!-- 当前位置标记 -->
      <span v-if="currentFolderId === folder.id" class="current-badge">
        当前
      </span>
    </div>

    <!-- 子文件夹 -->
    <div v-if="hasChildren && isExpanded" class="folder-children">
      <DropFolderItem
        v-for="child in folder.children"
        :key="child.id"
        :folder="child"
        :drop-target-id="dropTargetId"
        :current-folder-id="currentFolderId"
        @dragover="(id, e) => $emit('dragover', id, e)"
        @dragleave="$emit('dragleave')"
        @drop="(id, name, e) => $emit('drop', id, name, e)"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onUnmounted } from 'vue'

const props = defineProps({
  folder: {
    type: Object,
    required: true
  },
  dropTargetId: {
    type: [Number, String],
    default: null
  },
  currentFolderId: {
    type: [Number, String],
    default: null
  }
})

const emit = defineEmits(['dragover', 'dragleave', 'drop'])

// 状态
const isExpanded = ref(true) // 默认展开
let springLoadTimer = null // Spring-loading 定时器

// 计算属性
const hasChildren = computed(() => {
  return props.folder.children && props.folder.children.length > 0
})

// 方法
function toggleExpand() {
  isExpanded.value = !isExpanded.value
}

function handleDragOver(event) {
  emit('dragover', props.folder.id, event)

  // Spring-loading: 悬停 500ms 后自动展开
  if (hasChildren.value && !isExpanded.value && !springLoadTimer) {
    springLoadTimer = setTimeout(() => {
      isExpanded.value = true
      springLoadTimer = null
    }, 500)
  }
}

function handleDragLeave() {
  // 清除 spring-loading 定时器
  if (springLoadTimer) {
    clearTimeout(springLoadTimer)
    springLoadTimer = null
  }
  emit('dragleave')
}

function handleDrop(event) {
  // 清除 spring-loading 定时器
  if (springLoadTimer) {
    clearTimeout(springLoadTimer)
    springLoadTimer = null
  }
  emit('drop', props.folder.id, props.folder.name, event)
}

// 清理定时器
onUnmounted(() => {
  if (springLoadTimer) {
    clearTimeout(springLoadTimer)
  }
})
</script>

<style scoped>
.drop-folder-item {
  user-select: none;
}

.folder-row {
  display: flex;
  align-items: center;
  padding: 8px 10px;
  border-radius: 6px;
  cursor: copy;
  transition: all 0.2s;
  gap: 6px;
  border: 2px solid transparent;
}

.folder-row:hover {
  background: var(--hover-bg, rgba(0,0,0,0.05));
}

/* 拖拽放置目标高亮 */
.folder-row.is-drop-target {
  background: var(--primary-bg, rgba(64, 158, 255, 0.15));
  border-color: var(--primary-color, #409eff);
  cursor: move;
  transform: scale(1.02);
}

.folder-row.is-drop-target .folder-icon,
.folder-row.is-drop-target .folder-name {
  color: var(--primary-color, #409eff);
}

.folder-row.is-drop-target .folder-name {
  font-weight: 600;
}

/* 当前文件夹（不可放置） */
.folder-row.is-current {
  opacity: 0.6;
  cursor: not-allowed;
}

.toggle-btn {
  width: 18px;
  height: 18px;
  border: none;
  background: transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary, #999);
  font-size: 10px;
  border-radius: 4px;
  flex-shrink: 0;
}

.toggle-btn:hover {
  background: var(--hover-bg, rgba(0,0,0,0.1));
}

.toggle-placeholder {
  width: 18px;
  flex-shrink: 0;
}

.folder-icon {
  color: var(--warning-color, #e6a23c);
  font-size: 13px;
  flex-shrink: 0;
}

.folder-name {
  flex: 1;
  font-size: 13px;
  color: var(--text-primary, #333);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.notes-count {
  font-size: 11px;
  color: var(--text-secondary, #999);
  background: var(--bg-tertiary, #e0e0e0);
  padding: 1px 6px;
  border-radius: 8px;
  flex-shrink: 0;
}

.current-badge {
  font-size: 10px;
  color: var(--text-tertiary, #bbb);
  background: var(--bg-tertiary, #f0f0f0);
  padding: 2px 6px;
  border-radius: 4px;
  flex-shrink: 0;
}

.folder-children {
  padding-left: 18px;
}
</style>
