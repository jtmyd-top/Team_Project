<template>
  <div class="move-folder-item">
    <div
      class="folder-row"
      :class="{
        'is-selected': selectedId === folder.id,
        'is-current': currentFolderId === folder.id
      }"
      :style="{ paddingLeft: `${16 + depth * 20}px` }"
      @click="handleClick"
    >
      <!-- 展开/收起按钮 -->
      <button
        v-if="hasChildren"
        class="toggle-btn"
        @click.stop="$emit('toggle', folder.id)"
      >
        <i class="fas" :class="isExpanded ? 'fa-chevron-down' : 'fa-chevron-right'"></i>
      </button>
      <span v-else class="toggle-placeholder"></span>

      <!-- 文件夹图标 -->
      <i class="fas folder-icon" :class="isExpanded ? 'fa-folder-open' : 'fa-folder'"></i>

      <!-- 名称 -->
      <span class="folder-name">{{ folder.name }}</span>

      <!-- 笔记数量 -->
      <span v-if="folder.notes_count > 0" class="folder-count">
        {{ folder.notes_count }}
      </span>

      <!-- 当前位置标记 -->
      <span v-if="currentFolderId === folder.id" class="current-badge">
        当前
      </span>
    </div>

    <!-- 子文件夹 -->
    <Transition name="expand">
      <div v-if="hasChildren && isExpanded" class="folder-children">
        <MoveFolderItem
          v-for="child in folder.children"
          :key="child.id"
          :folder="child"
          :selected-id="selectedId"
          :current-folder-id="currentFolderId"
          :depth="depth + 1"
          :expanded-ids="expandedIds"
          @select="(id, name) => $emit('select', id, name)"
          @toggle="(id) => $emit('toggle', id)"
        />
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  folder: {
    type: Object,
    required: true
  },
  selectedId: {
    type: [Number, String],
    default: undefined
  },
  currentFolderId: {
    type: [Number, String],
    default: null
  },
  depth: {
    type: Number,
    default: 0
  },
  expandedIds: {
    type: Set,
    default: () => new Set()
  }
})

const emit = defineEmits(['select', 'toggle'])

const hasChildren = computed(() => {
  return props.folder.children && props.folder.children.length > 0
})

const isExpanded = computed(() => {
  return props.expandedIds.has(props.folder.id)
})

function handleClick() {
  // 如果是当前文件夹，不允许选择
  if (props.currentFolderId === props.folder.id) return

  emit('select', props.folder.id, props.folder.name)
}
</script>

<style scoped>
.move-folder-item {
  user-select: none;
}

.folder-row {
  display: flex;
  align-items: center;
  padding: 10px 16px;
  cursor: pointer;
  transition: all 0.15s;
  gap: 8px;
  border-radius: 6px;
  margin: 2px 8px;
}

.folder-row:hover {
  background: var(--hover-bg, rgba(0, 0, 0, 0.03));
}

.folder-row.is-selected {
  background: var(--primary-bg, rgba(64, 158, 255, 0.1));
}

.folder-row.is-selected .folder-name {
  color: var(--primary-color, #409eff);
  font-weight: 600;
}

.folder-row.is-selected .folder-icon {
  color: var(--primary-color, #409eff);
}

.folder-row.is-current {
  opacity: 0.5;
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
  transition: all 0.15s;
}

.toggle-btn:hover {
  background: var(--hover-bg, rgba(0, 0, 0, 0.1));
  color: var(--text-primary, #333);
}

.toggle-placeholder {
  width: 18px;
  flex-shrink: 0;
}

.folder-icon {
  color: var(--warning-color, #e6a23c);
  font-size: 14px;
  flex-shrink: 0;
  transition: color 0.15s;
}

.folder-name {
  flex: 1;
  font-size: 13px;
  color: var(--text-primary, #333);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: color 0.15s;
}

.folder-count {
  font-size: 11px;
  color: var(--text-secondary, #999);
  background: var(--bg-tertiary, #eee);
  padding: 2px 6px;
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
  overflow: hidden;
}

/* 展开动画 */
.expand-enter-active,
.expand-leave-active {
  transition: all 0.2s ease;
}

.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  transform: translateY(-5px);
}
</style>
