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
import { useFolderTree } from '@composables/useFolderTree'
import '@/assets/styles/components/folder-tree.css'

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

const {
  dragOverId,
  isExpanded,
  toggleExpand,
  handleClick,
  getIcon,
  handleDragStart,
  handleDragEnd,
  handleDragOver,
  handleDragLeave,
  handleDrop
} = useFolderTree(props, emit)
</script>

<script>
// 定义组件名称用于递归
export default {
  name: 'FolderTree'
}
</script>
