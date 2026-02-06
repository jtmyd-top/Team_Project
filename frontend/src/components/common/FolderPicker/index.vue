<template>
  <Teleport to="body">
    <div v-if="visible" class="folder-picker-overlay" @click="handleClose">
      <div
        class="folder-picker-popup"
        :style="popupStyle"
        @click.stop
      >
        <!-- 头部 -->
        <div class="picker-header">
          <span class="picker-title">移动到</span>
          <button class="close-btn" @click="handleClose">
            <i class="fas fa-times"></i>
          </button>
        </div>

        <!-- 搜索框 -->
        <div class="picker-search">
          <div class="search-box">
            <i class="fas fa-search"></i>
            <input
              type="text"
              v-model="searchQuery"
              placeholder="搜索文件夹..."
              ref="searchInput"
            />
          </div>
        </div>

        <!-- 快捷选项 -->
        <div class="quick-options">
          <div
            class="quick-option"
            @click="selectFolder({ id: 'inbox', title: '未分类笔记', type: 'inbox' })"
          >
            <i class="fas fa-inbox"></i>
            <span>未分类笔记</span>
          </div>
          <div
            class="quick-option"
            @click="selectFolder({ id: 'root', title: '根目录', type: 'root' })"
          >
            <i class="fas fa-home"></i>
            <span>根目录</span>
          </div>
        </div>

        <!-- 分隔线 -->
        <div class="picker-divider"></div>

        <!-- 文件夹列表 -->
        <div class="folder-list">
          <template v-if="filteredFolders.length">
            <div
              v-for="folder in filteredFolders"
              :key="folder.id"
              class="folder-item"
              :class="{ disabled: folder.id === currentFolderId }"
              @click="selectFolder(folder)"
            >
              <i class="fas fa-folder"></i>
              <span class="folder-name">{{ folder.title || folder.name }}</span>
              <span v-if="folder.id === currentFolderId" class="current-badge">当前</span>
            </div>
          </template>
          <div v-else class="empty-state">
            <span>{{ searchQuery ? '未找到匹配的文件夹' : '暂无文件夹' }}</span>
          </div>
        </div>

        <!-- 底部操作 -->
        <div class="picker-footer">
          <button class="create-folder-btn" @click="handleCreateFolder">
            <i class="fas fa-folder-plus"></i>
            <span>新建文件夹</span>
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { useFolderPicker } from '@/composables/useFolderPicker'
import '@/assets/styles/components/folder-picker.css'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  folders: {
    type: Array,
    default: () => []
  },
  currentFolderId: {
    type: [String, Number],
    default: null
  },
  anchorPosition: {
    type: Object,
    default: () => ({ x: 0, y: 0 })
  }
})

const emit = defineEmits(['close', 'select', 'create-folder'])

const {
  searchQuery,
  searchInput,
  popupStyle,
  filteredFolders,
  selectFolder,
  handleClose,
  handleCreateFolder
} = useFolderPicker(props, emit)
</script>
