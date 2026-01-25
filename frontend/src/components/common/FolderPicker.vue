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
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'

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

const searchQuery = ref('')
const searchInput = ref(null)

// 计算弹窗位置
const popupStyle = computed(() => {
  return {
    left: `${props.anchorPosition.x}px`,
    top: `${props.anchorPosition.y}px`
  }
})

// 扁平化文件夹树
const flattenFolders = (items, result = [], depth = 0) => {
  for (const item of items) {
    if (item.type === 'folder') {
      result.push({
        ...item,
        depth,
        displayTitle: '  '.repeat(depth) + (item.title || item.name)
      })
      if (item.children && item.children.length) {
        flattenFolders(item.children, result, depth + 1)
      }
    }
  }
  return result
}

const allFolders = computed(() => flattenFolders(props.folders))

// 过滤文件夹
const filteredFolders = computed(() => {
  if (!searchQuery.value) return allFolders.value

  const query = searchQuery.value.toLowerCase()
  return allFolders.value.filter(folder =>
    (folder.title || folder.name || '').toLowerCase().includes(query)
  )
})

// 选择文件夹
const selectFolder = (folder) => {
  if (folder.id === props.currentFolderId) return
  emit('select', folder)
  handleClose()
}

// 关闭弹窗
const handleClose = () => {
  searchQuery.value = ''
  emit('close')
}

// 创建文件夹
const handleCreateFolder = () => {
  emit('create-folder')
}

// 监听 visible 变化，自动聚焦搜索框
watch(() => props.visible, (newVal) => {
  if (newVal) {
    nextTick(() => {
      searchInput.value?.focus()
    })
  }
})

// 键盘事件处理
const handleKeydown = (event) => {
  if (!props.visible) return

  if (event.key === 'Escape') {
    handleClose()
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<style scoped>
.folder-picker-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.3);
  z-index: 1000;
}

.folder-picker-popup {
  position: absolute;
  width: 280px;
  max-height: 400px;
  background: var(--bg-secondary, #16213e);
  border: 1px solid var(--border-color, rgba(255, 255, 255, 0.1));
  border-radius: 8px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 头部 */
.picker-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color, rgba(255, 255, 255, 0.08));
}

.picker-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #fff);
}

.close-btn {
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: var(--text-secondary, rgba(255, 255, 255, 0.6));
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.close-btn:hover {
  background: var(--hover-bg, rgba(255, 255, 255, 0.08));
  color: var(--text-primary, #fff);
}

/* 搜索框 */
.picker-search {
  padding: 12px;
}

.search-box {
  position: relative;
}

.search-box i {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-secondary, rgba(255, 255, 255, 0.4));
  font-size: 12px;
}

.search-box input {
  width: 100%;
  padding: 8px 12px 8px 32px;
  border-radius: 6px;
  border: 1px solid var(--border-color, rgba(255, 255, 255, 0.1));
  background: var(--input-bg, rgba(255, 255, 255, 0.05));
  color: var(--text-primary, #fff);
  font-size: 13px;
  outline: none;
  transition: all 0.2s ease;
}

.search-box input::placeholder {
  color: var(--text-secondary, rgba(255, 255, 255, 0.4));
}

.search-box input:focus {
  border-color: var(--primary-color, #409eff);
  background: var(--input-bg-focus, rgba(255, 255, 255, 0.08));
}

/* 快捷选项 */
.quick-options {
  display: flex;
  gap: 8px;
  padding: 0 12px 12px;
}

.quick-option {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 12px;
  background: var(--hover-bg, rgba(255, 255, 255, 0.05));
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  color: var(--text-secondary, rgba(255, 255, 255, 0.7));
  transition: all 0.2s ease;
}

.quick-option:hover {
  background: var(--active-bg, rgba(64, 158, 255, 0.15));
  color: var(--primary-color, #409eff);
}

.quick-option i {
  font-size: 12px;
}

/* 分隔线 */
.picker-divider {
  height: 1px;
  background: var(--border-color, rgba(255, 255, 255, 0.08));
  margin: 0 12px;
}

/* 文件夹列表 */
.folder-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  max-height: 200px;
}

.folder-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  color: var(--text-secondary, rgba(255, 255, 255, 0.7));
  transition: all 0.15s ease;
}

.folder-item:hover:not(.disabled) {
  background: var(--hover-bg, rgba(255, 255, 255, 0.08));
  color: var(--text-primary, #fff);
}

.folder-item.disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.folder-item i {
  color: var(--folder-color, #f0c674);
  font-size: 14px;
}

.folder-name {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.current-badge {
  font-size: 10px;
  padding: 2px 6px;
  background: var(--primary-color, #409eff);
  color: white;
  border-radius: 4px;
}

/* 空状态 */
.empty-state {
  padding: 24px;
  text-align: center;
  color: var(--text-secondary, rgba(255, 255, 255, 0.4));
  font-size: 12px;
}

/* 底部 */
.picker-footer {
  padding: 12px;
  border-top: 1px solid var(--border-color, rgba(255, 255, 255, 0.08));
}

.create-folder-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 16px;
  border: 1px dashed var(--border-color, rgba(255, 255, 255, 0.2));
  border-radius: 6px;
  background: transparent;
  color: var(--text-secondary, rgba(255, 255, 255, 0.6));
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.create-folder-btn:hover {
  border-color: var(--primary-color, #409eff);
  color: var(--primary-color, #409eff);
}

/* 滚动条 */
.folder-list::-webkit-scrollbar {
  width: 4px;
}

.folder-list::-webkit-scrollbar-track {
  background: transparent;
}

.folder-list::-webkit-scrollbar-thumb {
  background: var(--border-color, rgba(255, 255, 255, 0.1));
  border-radius: 2px;
}
</style>
