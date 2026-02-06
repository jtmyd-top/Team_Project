<template>
  <Teleport to="body">
    <Transition name="modal-fade">
      <div
        v-if="visible"
        class="move-dialog-overlay"
        @click.self="handleClose"
        @keydown.esc="handleClose"
      >
        <div class="move-dialog" ref="dialogRef">
          <!-- 头部 -->
          <div class="dialog-header">
            <i class="fas fa-folder-open"></i>
            <span>{{ mode === 'copy' ? '复制到' : '移动到' }}</span>
            <button class="close-btn" @click="handleClose">
              <i class="fas fa-times"></i>
            </button>
          </div>

          <!-- 当前笔记信息 -->
          <div class="note-info">
            <i class="fas fa-file-alt"></i>
            <span class="note-title">{{ note?.title || '无标题' }}</span>
          </div>

          <!-- 搜索框 -->
          <div class="search-box">
            <i class="fas fa-search"></i>
            <input
              v-model="searchQuery"
              type="text"
              placeholder="搜索文件夹..."
              ref="searchInput"
            />
            <button v-if="searchQuery" class="clear-btn" @click="searchQuery = ''">
              <i class="fas fa-times"></i>
            </button>
          </div>

          <!-- 文件夹列表 -->
          <div class="folder-list">
            <!-- 未分类笔记 -->
            <div
              class="folder-item inbox-item"
              :class="{
                'is-selected': selectedFolderId === null,
                'is-current': note?.folder?.id === null || !note?.folder
              }"
              @click="selectFolder(null, '未分类笔记')"
            >
              <span class="folder-indent"></span>
              <i class="fas fa-inbox folder-icon inbox-icon"></i>
              <span class="folder-name">未分类笔记</span>
              <span v-if="inboxCount > 0" class="folder-count">{{ inboxCount }}</span>
              <span v-if="!note?.folder" class="current-badge">当前</span>
            </div>

            <div class="list-divider"></div>

            <!-- 文件夹树 -->
            <template v-if="filteredFolders.length > 0">
              <MoveFolderItem
                v-for="folder in filteredFolders"
                :key="folder.id"
                :folder="folder"
                :selected-id="selectedFolderId"
                :current-folder-id="note?.folder?.id"
                :depth="0"
                :expanded-ids="expandedIds"
                @select="selectFolder"
                @toggle="toggleExpand"
              />
            </template>

            <!-- 空状态 -->
            <div v-else-if="!isLoading" class="empty-state">
              <p v-if="searchQuery">未找到匹配的文件夹</p>
              <p v-else>暂无文件夹</p>
            </div>

            <!-- 加载状态 -->
            <div v-if="isLoading" class="loading-state">
              <i class="fas fa-spinner fa-spin"></i>
              <span>加载中...</span>
            </div>
          </div>

          <!-- 底部操作 -->
          <div class="dialog-footer">
            <button class="btn-cancel" @click="handleClose">取消</button>
            <button
              class="btn-confirm"
              :disabled="!canConfirm"
              @click="handleConfirm"
            >
              {{ mode === 'copy' ? '复制' : '移动' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import MoveFolderItem from '@components/common/MoveFolderItem/index.vue'
import { useMoveToDialog } from '@composables/useMoveToDialog'
import '@/assets/styles/components/move-to-dialog.css'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  note: {
    type: Object,
    default: null
  },
  mode: {
    type: String,
    default: 'move', // 'move' or 'copy'
    validator: (v) => ['move', 'copy'].includes(v)
  }
})

const emit = defineEmits(['close', 'confirm'])

const {
  searchQuery,
  selectedFolderId,
  inboxCount,
  isLoading,
  expandedIds,
  searchInput,
  dialogRef,
  filteredFolders,
  canConfirm,
  selectFolder,
  toggleExpand,
  handleClose,
  handleConfirm
} = useMoveToDialog(props, emit)
</script>
