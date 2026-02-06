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
import { useDropFolderItem } from '@/composables/useDropFolderItem'
import '@/assets/styles/components/drop-folder-item.css'

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

const {
  isExpanded,
  hasChildren,
  toggleExpand,
  handleDragOver,
  handleDragLeave,
  handleDrop
} = useDropFolderItem(props, emit)
</script>
