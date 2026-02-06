<template>
  <div class="folder-tree-item" :class="{ 'is-expanded': isExpanded }">
    <div
      class="folder-row"
      :class="{ 'is-editing': isEditing, 'is-drop-target': isDragOver }"
      @click="handleClick"
      @contextmenu.prevent="showContextMenu"
      @dragover.prevent="handleDragOver"
      @dragleave="handleDragLeave"
      @drop="handleDrop"
    >
      <!-- 展开/收起图标（只有有子文件夹时显示） -->
      <button
        v-if="hasChildren"
        class="toggle-btn"
        @click.stop="toggleExpand"
      >
        <i class="fas" :class="isExpanded ? 'fa-chevron-down' : 'fa-chevron-right'"></i>
      </button>

      <!-- 文件夹图标 -->
      <i class="fas folder-icon" :class="isExpanded ? 'fa-folder-open' : 'fa-folder'"></i>

      <!-- 名称（编辑模式） -->
      <input
        v-if="isEditing"
        ref="nameInput"
        v-model="editName"
        class="name-input"
        @blur="finishEdit"
        @keyup.enter="finishEdit"
        @keyup.escape="cancelEdit"
        @click.stop
      />

      <!-- 名称（显示模式） -->
      <span v-else class="folder-name">{{ folder.name }}</span>

      <!-- 笔记数量 -->
      <span v-if="folder.notes_count > 0" class="notes-count">
        {{ folder.notes_count }}
      </span>

      <!-- 操作按钮 -->
      <div class="folder-actions" @click.stop>
        <button class="action-btn" @click="startEdit" title="重命名">
          <i class="fas fa-pen"></i>
        </button>
        <button class="action-btn" @click="handleCreateSubfolder" title="新建子文件夹">
          <i class="fas fa-folder-plus"></i>
        </button>
        <button class="action-btn delete-btn" @click="handleDelete" title="删除">
          <i class="fas fa-trash"></i>
        </button>
      </div>
    </div>

    <!-- 子文件夹 -->
    <div v-if="hasChildren && isExpanded" class="folder-children">
      <FolderTreeItem
        v-for="child in folder.children"
        :key="child.id"
        :folder="child"
        @click="$emit('click', $event)"
        @rename="$emit('rename', $event.folder, $event.newName)"
        @delete="$emit('delete', $event)"
        @create-subfolder="$emit('create-subfolder', $event)"
        @note-drop="$emit('note-drop', $event)"
      />
    </div>
  </div>
</template>

<script setup>
import { useFolderTreeItem } from '@/composables/useFolderTreeItem'
import '@/assets/styles/components/folder-tree-item.css'

const props = defineProps({
  folder: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['click', 'rename', 'delete', 'create-subfolder', 'note-drop'])

const {
  isExpanded,
  isEditing,
  editName,
  nameInput,
  isDragOver,
  hasChildren,
  handleDragOver,
  handleDragLeave,
  handleDrop,
  toggleExpand,
  handleClick,
  startEdit,
  finishEdit,
  cancelEdit,
  handleDelete,
  handleCreateSubfolder,
  showContextMenu
} = useFolderTreeItem(props, emit)
</script>

<script>
// 定义组件名称用于递归引用
export default {
  name: 'FolderTreeItem'
}
</script>
