<template>
  <div class="app-layout" :class="themeClass">
    <!-- 一级极窄功能条 -->
    <SideNav
      :active-item="activeNav"
      :user-avatar="userStore.avatar"
      @nav-change="handleNavChange"
      @user-click="handleUserClick"
    />

    <!-- 二级抽屉式侧边栏 -->
    <DrawerSidebar
      :is-collapsed="isSidebarCollapsed"
      :workspace-name="workspaceName"
      v-model:search-query="searchQuery"
      :favorites="favoriteItems"
      :inbox-items="inboxItems"
      :recent-items="recentItems"
      :all-notes-count="allNotesCount"
      :selected-id="selectedItemId"
      @toggle-collapse="toggleSidebar"
      @select="handleSelect"
      @create-new="handleCreateNew"
      @view-change="handleViewChange"
    >
      <!-- 私人空间插槽 - 文件夹树 -->
      <template #private>
        <FolderTree
          :items="folderTree"
          :selected-id="selectedItemId"
          :expanded-ids="expandedFolderIds"
          :draggable="true"
          v-model:dragging-id="draggingItemId"
          @select="handleSelect"
          @toggle-expand="handleToggleExpand"
          @add-child="handleAddChild"
          @more="handleMoreAction"
          @move-item="handleMoveItem"
        />
      </template>
    </DrawerSidebar>

    <!-- 主内容区域 -->
    <main class="app-main">
      <!-- 面包屑导航 -->
      <div v-if="breadcrumbs.length" class="breadcrumb-bar">
        <div class="breadcrumb-list">
          <template v-for="(crumb, index) in breadcrumbs" :key="crumb.id || index">
            <span
              class="breadcrumb-item"
              :class="{ active: index === breadcrumbs.length - 1 }"
              @click="handleBreadcrumbClick(crumb, index, $event)"
            >
              {{ crumb.title }}
            </span>
            <i v-if="index < breadcrumbs.length - 1" class="fas fa-chevron-right breadcrumb-separator"></i>
          </template>
        </div>

        <!-- 侧边栏展开按钮 (收起时显示) -->
        <button
          v-if="isSidebarCollapsed"
          class="expand-sidebar-btn"
          @click="toggleSidebar"
          title="展开侧边栏"
        >
          <i class="fas fa-bars"></i>
        </button>
      </div>

      <!-- 内容插槽 -->
      <div class="app-content" :class="{ 'immersive-mode': isSidebarCollapsed }">
        <div class="content-wrapper">
          <slot></slot>
        </div>
      </div>
    </main>

    <!-- 文件夹选择器弹窗 -->
    <FolderPicker
      :visible="folderPickerVisible"
      :folders="folderTree"
      :current-folder-id="currentFolderId"
      :anchor-position="folderPickerPosition"
      @close="folderPickerVisible = false"
      @select="handleFolderSelect"
      @create-folder="handleCreateFolder"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useUserStore } from '@stores/user.js'
import SideNav from './SideNav.vue'
import DrawerSidebar from './DrawerSidebar.vue'
import FolderTree from './FolderTree.vue'
import FolderPicker from './FolderPicker.vue'

const props = defineProps({
  workspaceName: {
    type: String,
    default: '我的空间'
  },
  folderTree: {
    type: Array,
    default: () => []
  },
  favoriteItems: {
    type: Array,
    default: () => []
  },
  inboxItems: {
    type: Array,
    default: () => []
  },
  recentItems: {
    type: Array,
    default: () => []
  },
  allNotesCount: {
    type: Number,
    default: 0
  },
  breadcrumbs: {
    type: Array,
    default: () => []
  },
  selectedItemId: {
    type: [String, Number],
    default: null
  },
  currentFolderId: {
    type: [String, Number],
    default: null
  }
})

const emit = defineEmits([
  'nav-change',
  'select',
  'create-new',
  'add-child',
  'more-action',
  'breadcrumb-click',
  'user-click',
  'view-change',
  'search',
  'move-item',
  'folder-select',
  'create-folder'
])

// 使用 Pinia store
const userStore = useUserStore()

// 本地状态
const searchQuery = ref('')
const activeNav = ref(userStore.activeTab || 'all')
const draggingItemId = ref(null)
const folderPickerVisible = ref(false)
const folderPickerPosition = ref({ x: 0, y: 0 })

// 计算属性
const isSidebarCollapsed = computed(() => userStore.isSidebarCollapsed)
const expandedFolderIds = computed(() => userStore.expandedFolderIds)

// 主题类
const themeClass = computed(() => {
  const mode = userStore.theme?.mode || 'system'
  if (mode === 'system') {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark-theme' : 'light-theme'
  }
  return mode === 'dark' ? 'dark-theme' : 'light-theme'
})

// 方法
const toggleSidebar = () => {
  userStore.toggleSidebar()
}

const handleNavChange = (navId) => {
  activeNav.value = navId
  userStore.setActiveTab(navId)
  emit('nav-change', navId)

  // 自动展开侧边栏
  if (userStore.isSidebarCollapsed && navId !== 'settings') {
    userStore.setSidebarCollapsed(false)
  }
}

const handleSelect = (item) => {
  emit('select', item)
}

const handleCreateNew = () => {
  emit('create-new')
}

const handleToggleExpand = (folderId) => {
  userStore.toggleFolderExpanded(folderId)
}

const handleAddChild = (folder) => {
  emit('add-child', folder)
}

const handleMoreAction = (item) => {
  emit('more-action', item)
}

const handleBreadcrumbClick = (crumb, index, event) => {
  // 如果是最后一个面包屑(当前位置)，显示文件夹选择器
  if (index === props.breadcrumbs.length - 1 && event) {
    const rect = event.target.getBoundingClientRect()
    folderPickerPosition.value = {
      x: rect.left,
      y: rect.bottom + 8
    }
    folderPickerVisible.value = true
  } else {
    emit('breadcrumb-click', { crumb, index })
  }
}

const handleUserClick = () => {
  emit('user-click')
}

const handleViewChange = (view) => {
  emit('view-change', view)
}

const handleMoveItem = (moveData) => {
  emit('move-item', moveData)
}

const handleFolderSelect = (folder) => {
  emit('folder-select', folder)
}

const handleCreateFolder = () => {
  emit('create-folder')
}

// 键盘快捷键处理
const handleKeydown = (event) => {
  // Ctrl+N: 新建笔记
  if ((event.ctrlKey || event.metaKey) && event.key === 'n') {
    event.preventDefault()
    handleCreateNew()
  }
  // Ctrl+B: 切换侧边栏
  if ((event.ctrlKey || event.metaKey) && event.key === 'b') {
    event.preventDefault()
    toggleSidebar()
  }
  // Ctrl+K: 聚焦搜索
  if ((event.ctrlKey || event.metaKey) && event.key === 'k') {
    event.preventDefault()
    emit('search')
  }
}

// 监听系统主题变化和键盘事件
onMounted(() => {
  const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
  mediaQuery.addEventListener('change', () => {
    // 触发重新计算主题类
  })

  // 添加键盘事件监听
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<style scoped>
.app-layout {
  display: flex;
  width: 100%;
  height: 100vh;
  overflow: hidden;
  background: var(--bg-primary, #0f0f23);
  color: var(--text-primary, #fff);
}

/* 主内容区 */
.app-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  height: 100%;
  overflow: hidden;
}

/* 面包屑导航栏 */
.breadcrumb-bar {
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  background: var(--bg-secondary, #16213e);
  border-bottom: 1px solid var(--border-color, rgba(255, 255, 255, 0.08));
  flex-shrink: 0;
}

.breadcrumb-list {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
  overflow: hidden;
}

.breadcrumb-item {
  font-size: 13px;
  color: var(--text-secondary, rgba(255, 255, 255, 0.6));
  cursor: pointer;
  white-space: nowrap;
  transition: color 0.2s ease;
}

.breadcrumb-item:hover {
  color: var(--text-primary, #fff);
}

.breadcrumb-item.active {
  color: var(--text-primary, #fff);
  font-weight: 500;
  cursor: default;
}

.breadcrumb-separator {
  font-size: 10px;
  color: var(--text-secondary, rgba(255, 255, 255, 0.3));
}

.expand-sidebar-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  color: var(--text-secondary, rgba(255, 255, 255, 0.6));
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  margin-left: 12px;
}

.expand-sidebar-btn:hover {
  background: var(--hover-bg, rgba(255, 255, 255, 0.08));
  color: var(--text-primary, #fff);
}

/* 内容区域 */
.app-content {
  flex: 1;
  overflow: auto;
  padding: 0;
}

.content-wrapper {
  width: 100%;
  height: 100%;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

/* 沉浸模式 - 侧边栏收起时内容居中 */
.app-content.immersive-mode .content-wrapper {
  max-width: 800px;
  margin: 0 auto;
  padding: 0 24px;
}

/* 沉浸模式过渡动画 */
.app-content.immersive-mode {
  background: var(--bg-primary, #0f0f23);
}

/* 亮色主题变量 */
.light-theme {
  --bg-primary: #ffffff;
  --bg-secondary: #f7f7f8;
  --bg-tertiary: #ebebef;
  --text-primary: #1a1a2e;
  --text-secondary: rgba(26, 26, 46, 0.6);
  --border-color: rgba(0, 0, 0, 0.1);
  --hover-bg: rgba(0, 0, 0, 0.05);
  --active-bg: rgba(64, 158, 255, 0.1);
  --input-bg: rgba(0, 0, 0, 0.03);
  --input-bg-focus: rgba(0, 0, 0, 0.05);
}

/* 暗色主题变量 */
.dark-theme {
  --bg-primary: #0f0f23;
  --bg-secondary: #16213e;
  --bg-tertiary: #1a1a2e;
  --text-primary: #ffffff;
  --text-secondary: rgba(255, 255, 255, 0.6);
  --border-color: rgba(255, 255, 255, 0.08);
  --hover-bg: rgba(255, 255, 255, 0.08);
  --active-bg: rgba(64, 158, 255, 0.15);
  --input-bg: rgba(255, 255, 255, 0.05);
  --input-bg-focus: rgba(255, 255, 255, 0.08);
}

/* 响应式布局 */
@media (max-width: 1024px) {
  .breadcrumb-bar {
    padding: 0 12px;
  }
}

@media (max-width: 768px) {
  .app-layout {
    flex-direction: column;
  }

  .breadcrumb-bar {
    height: 40px;
  }

  .breadcrumb-item {
    font-size: 12px;
  }
}
</style>
