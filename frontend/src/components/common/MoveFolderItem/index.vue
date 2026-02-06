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
import { useMoveFolderItem } from '@/composables/useMoveFolderItem'
import '@/assets/styles/components/move-folder-item.css'

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

const {
  hasChildren,
  isExpanded,
  handleClick
} = useMoveFolderItem(props, emit)
</script>
