<template>
  <div class="folder-tree">
    <div
      v-for="item in items"
      :key="item.id"
      class="tree-node"
    >
      <!-- 节点内容 -->
      <div
        class="node-content"
        :class="{
          active: selectedId === item.id,
          'is-folder': item.type === 'folder',
          'drag-over': dragOverId === item.id,
          'dragging': draggingId === item.id
        }"
        :style="{ paddingLeft: `${depth * 16 + 8}px` }"
        :draggable="draggable && item.type !== 'folder'"
        @click="handleClick(item)"
        @dragstart="handleDragStart($event, item)"
        @dragend="handleDragEnd"
        @dragover="handleDragOver($event, item)"
        @dragleave="handleDragLeave"
        @drop="handleDrop($event, item)"
      >
        <!-- 展开/收起图标 (仅文件夹显示) -->
        <span
          v-if="item.type === 'folder'"
          class="expand-icon"
          @click.stop="toggleExpand(item.id)"
        >
          <i :class="isExpanded(item.id) ? 'fas fa-chevron-down' : 'fas fa-chevron-right'"></i>
        </span>
        <span v-else class="expand-icon placeholder"></span>

        <!-- 图标 -->
        <span class="node-icon">
          <i :class="getIcon(item)"></i>
        </span>

        <!-- 标题 -->
        <span class="node-title">{{ item.title || item.name }}</span>

        <!-- 操作按钮 (hover 显示) -->
        <div class="node-actions" @click.stop>
          <button
            v-if="item.type === 'folder'"
            class="action-btn"
            @click="$emit('add-child', item)"
            title="添加子页面"
          >
            <i class="fas fa-plus"></i>
          </button>
          <button
            class="action-btn"
            @click="$emit('more', item)"
            title="更多"
          >
            <i class="fas fa-ellipsis-h"></i>
          </button>
        </div>
      </div>

      <!-- 子节点递归 -->
      <div
        v-if="item.type === 'folder' && item.children && item.children.length && isExpanded(item.id)"
        class="node-children"
      >
        <FolderTree
          :items="item.children"
          :depth="depth + 1"
          :selected-id="selectedId"
          :expanded-ids="expandedIds"
          :draggable="draggable"
          :dragging-id="draggingId"
          @select="$emit('select', $event)"
          @toggle-expand="$emit('toggle-expand', $event)"
          @add-child="$emit('add-child', $event)"
          @more="$emit('more', $event)"
          @move-item="$emit('move-item', $event)"
          @update:dragging-id="$emit('update:dragging-id', $event)"
        />
      </div>
    </div>

    <!-- 空状态 -->
    <div v-if="!items || !items.length" class="empty-state" :style="{ paddingLeft: `${depth * 16 + 8}px` }">
      <span class="empty-text">暂无内容</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  items: {
    type: Array,
    default: () => []
  },
  depth: {
    type: Number,
    default: 0
  },
  selectedId: {
    type: [String, Number],
    default: null
  },
  expandedIds: {
    type: Array,
    default: () => []
  },
  draggable: {
    type: Boolean,
    default: true
  },
  draggingId: {
    type: [String, Number],
    default: null
  }
})

const emit = defineEmits([
  'select',
  'toggle-expand',
  'add-child',
  'more',
  'move-item',
  'update:dragging-id'
])

// 本地拖拽状态
const dragOverId = ref(null)

// 检查节点是否展开
const isExpanded = (id) => {
  return props.expandedIds.includes(id)
}

// 切换展开状态
const toggleExpand = (id) => {
  emit('toggle-expand', id)
}

// 点击节点
const handleClick = (item) => {
  if (item.type === 'folder') {
    toggleExpand(item.id)
  }
  emit('select', item)
}

// 获取图标
const getIcon = (item) => {
  if (item.icon) return item.icon

  if (item.type === 'folder') {
    return isExpanded(item.id) ? 'fas fa-folder-open' : 'fas fa-folder'
  }

  // 根据类型返回不同图标
  const iconMap = {
    note: 'fas fa-file-alt',
    document: 'fas fa-file-word',
    image: 'fas fa-file-image',
    code: 'fas fa-file-code',
    default: 'fas fa-file'
  }

  return iconMap[item.type] || iconMap.default
}

// 拖拽开始
const handleDragStart = (event, item) => {
  if (!props.draggable || item.type === 'folder') {
    event.preventDefault()
    return
  }

  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('application/json', JSON.stringify({
    id: item.id,
    type: item.type,
    title: item.title || item.name
  }))

  emit('update:dragging-id', item.id)
}

// 拖拽结束
const handleDragEnd = () => {
  emit('update:dragging-id', null)
  dragOverId.value = null
}

// 拖拽经过
const handleDragOver = (event, item) => {
  // 只有文件夹可以作为放置目标
  if (item.type !== 'folder') return
  // 不能拖到正在拖拽的元素本身
  if (item.id === props.draggingId) return

  event.preventDefault()
  event.dataTransfer.dropEffect = 'move'
  dragOverId.value = item.id
}

// 拖拽离开
const handleDragLeave = () => {
  dragOverId.value = null
}

// 放置
const handleDrop = (event, targetFolder) => {
  event.preventDefault()
  dragOverId.value = null

  // 只有文件夹可以作为放置目标
  if (targetFolder.type !== 'folder') return

  try {
    const data = JSON.parse(event.dataTransfer.getData('application/json'))

    // 不能移动到自己
    if (data.id === targetFolder.id) return

    emit('move-item', {
      itemId: data.id,
      itemType: data.type,
      itemTitle: data.title,
      targetFolderId: targetFolder.id,
      targetFolderTitle: targetFolder.title || targetFolder.name
    })
  } catch (e) {
    console.error('Drop failed:', e)
  }
}
</script>

<script>
// 定义组件名称用于递归
export default {
  name: 'FolderTree'
}
</script>

<style scoped>
.folder-tree {
  width: 100%;
}

.tree-node {
  width: 100%;
}

.node-content {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 8px;
  margin: 1px 0;
  border-radius: 6px;
  cursor: pointer;
  color: var(--text-secondary, rgba(255, 255, 255, 0.7));
  font-size: 13px;
  transition: all 0.15s ease;
  position: relative;
}

.node-content:hover {
  background: var(--hover-bg, rgba(255, 255, 255, 0.08));
  color: var(--text-primary, #fff);
}

.node-content.active {
  background: var(--active-bg, rgba(64, 158, 255, 0.15));
  color: var(--primary-color, #409eff);
}

.expand-icon {
  width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 10px;
  color: var(--text-secondary, rgba(255, 255, 255, 0.4));
  transition: color 0.2s ease;
}

.expand-icon.placeholder {
  visibility: hidden;
}

.node-content:hover .expand-icon {
  color: var(--text-primary, #fff);
}

.node-icon {
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 14px;
}

.node-icon .fa-folder,
.node-icon .fa-folder-open {
  color: var(--folder-color, #f0c674);
}

.node-title {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

.node-actions {
  display: none;
  align-items: center;
  gap: 2px;
  margin-left: auto;
  flex-shrink: 0;
}

.node-content:hover .node-actions {
  display: flex;
}

.action-btn {
  width: 22px;
  height: 22px;
  border: none;
  background: transparent;
  color: var(--text-secondary, rgba(255, 255, 255, 0.5));
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  transition: all 0.15s ease;
}

.action-btn:hover {
  background: var(--hover-bg, rgba(255, 255, 255, 0.1));
  color: var(--text-primary, #fff);
}

.node-children {
  width: 100%;
}

.empty-state {
  padding: 12px 8px;
}

.empty-text {
  font-size: 12px;
  color: var(--text-secondary, rgba(255, 255, 255, 0.4));
  font-style: italic;
}

/* 拖拽指示器样式 */
.node-content.drag-over {
  border: 1px dashed var(--primary-color, #409eff);
  background: var(--primary-color-light, rgba(64, 158, 255, 0.1));
}

.node-content.dragging {
  opacity: 0.5;
  background: var(--hover-bg, rgba(255, 255, 255, 0.08));
}

.node-content[draggable="true"] {
  cursor: grab;
}

.node-content[draggable="true"]:active {
  cursor: grabbing;
}
</style>
