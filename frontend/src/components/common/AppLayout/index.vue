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
import SideNav from '@components/common/SideNav/index.vue'
import DrawerSidebar from '@components/common/DrawerSidebar/index.vue'
import FolderTree from '@components/common/FolderTree/index.vue'
import FolderPicker from '@components/common/FolderPicker/index.vue'
import { useAppLayout } from '@composables/useAppLayout'
import '@/assets/styles/components/app-layout.css'

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

const {
  userStore,
  searchQuery,
  activeNav,
  draggingItemId,
  folderPickerVisible,
  folderPickerPosition,
  isSidebarCollapsed,
  expandedFolderIds,
  themeClass,
  toggleSidebar,
  handleNavChange,
  handleSelect,
  handleCreateNew,
  handleToggleExpand,
  handleAddChild,
  handleMoreAction,
  handleBreadcrumbClick,
  handleUserClick,
  handleViewChange,
  handleMoveItem,
  handleFolderSelect,
  handleCreateFolder
} = useAppLayout(props, emit)
</script>
