<template>
  <Teleport to="body">
    <Transition name="slide-fade">
      <div v-if="isVisible" class="drag-drop-overlay">
        <div class="overlay-panel">
          <div class="panel-header">
            <i class="fas fa-folder-tree"></i>
            <span>移动到...</span>
          </div>

          <div class="panel-content">
            <!-- 未分类笔记 -->
            <div
              class="drop-item inbox-item"
              :class="{ 'is-drop-target': dropTargetId === 'inbox' }"
              @dragover.prevent="handleDragOver('inbox', $event)"
              @dragleave="handleDragLeave"
              @drop="handleDrop(null, '未分类笔记', $event)"
            >
              <i class="fas fa-inbox"></i>
              <span>未分类笔记</span>
              <span v-if="inboxCount > 0" class="item-count">{{ inboxCount }}</span>
            </div>

            <div class="divider"></div>

            <!-- 文件夹树 -->
            <div v-if="folders.length > 0" class="folder-list">
              <DropFolderItem
                v-for="folder in folders"
                :key="folder.id"
                :folder="folder"
                :drop-target-id="dropTargetId"
                :current-folder-id="currentFolderId"
                @dragover="handleDragOver"
                @dragleave="handleDragLeave"
                @drop="handleDrop"
              />
            </div>

            <!-- 空状态 -->
            <div v-else class="empty-state">
              <p>暂无文件夹</p>
            </div>
          </div>

          <div class="panel-footer">
            <i class="fas fa-info-circle"></i>
            <span>拖动笔记到文件夹上松开即可移动</span>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import DropFolderItem from '@components/common/DropFolderItem/index.vue'
import { useDragDropOverlay } from '@composables/useDragDropOverlay'
import '@/assets/styles/components/drag-drop-overlay.css'

const {
  isVisible,
  dropTargetId,
  currentFolderId,
  folders,
  inboxCount,
  handleDragOver,
  handleDragLeave,
  handleDrop
} = useDragDropOverlay()
</script>
