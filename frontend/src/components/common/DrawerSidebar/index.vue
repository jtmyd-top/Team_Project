<template>
  <aside
    class="drawer-sidebar"
    :class="{ collapsed: isCollapsed }"
  >
    <!-- 头部 -->
    <div class="drawer-header">
      <div class="workspace-info">
        <div class="workspace-icon">
          <i class="fas fa-book"></i>
        </div>
        <span class="workspace-name">{{ workspaceName }}</span>
      </div>
      <button class="collapse-btn" @click="$emit('toggle-collapse')" :title="isCollapsed ? '展开' : '收起'">
        <i :class="isCollapsed ? 'fas fa-chevron-right' : 'fas fa-chevron-left'"></i>
      </button>
    </div>

    <!-- 搜索框 -->
    <div class="drawer-search">
      <div class="search-box">
        <i class="fas fa-search"></i>
        <input
          type="text"
          :value="searchQuery"
          @input="$emit('update:searchQuery', $event.target.value)"
          placeholder="搜索..."
        />
      </div>
    </div>

    <!-- 视图切换标签 -->
    <div class="view-tabs">
      <button
        class="view-tab"
        :class="{ active: currentView === 'notes' }"
        @click="switchView('notes')"
      >
        <i class="fas fa-file-alt"></i>
        <span>全部笔记</span>
      </button>
      <button
        class="view-tab"
        :class="{ active: currentView === 'folders' }"
        @click="switchView('folders')"
      >
        <i class="fas fa-folder"></i>
        <span>文件夹</span>
      </button>
    </div>

    <!-- 内容区域 -->
    <div class="drawer-content">
      <!-- 全部笔记视图 -->
      <template v-if="currentView === 'notes'">
        <!-- 未分类笔记区域 -->
        <div class="section">
          <div class="section-header" @click="toggleSection('inbox')">
            <i :class="expandedSections.inbox ? 'fas fa-chevron-down' : 'fas fa-chevron-right'"></i>
            <i class="fas fa-inbox section-icon"></i>
            <span>未分类笔记</span>
            <span v-if="inboxCount" class="section-badge">{{ inboxCount }}</span>
          </div>
          <div class="section-content" v-show="expandedSections.inbox">
            <slot name="inbox">
              <div
                v-for="item in inboxItems"
                :key="item.id"
                class="list-item"
                :class="{ active: selectedId === item.id }"
                @click="$emit('select', item)"
              >
                <i class="fas fa-file-alt"></i>
                <span class="item-title">{{ item.title }}</span>
                <span class="item-date">{{ formatDate(item.updated_at) }}</span>
              </div>
            </slot>
            <div v-if="!inboxItems || !inboxItems.length" class="empty-hint">
              <span>暂无未分类笔记</span>
            </div>
          </div>
        </div>

        <!-- 收藏夹区域 -->
        <div class="section" v-if="favorites && favorites.length">
          <div class="section-header" @click="toggleSection('favorites')">
            <i :class="expandedSections.favorites ? 'fas fa-chevron-down' : 'fas fa-chevron-right'"></i>
            <i class="fas fa-star section-icon favorite-icon"></i>
            <span>收藏夹</span>
          </div>
          <div class="section-content" v-show="expandedSections.favorites">
            <slot name="favorites">
              <div
                v-for="item in favorites"
                :key="item.id"
                class="list-item"
                :class="{ active: selectedId === item.id }"
                @click="$emit('select', item)"
              >
                <i class="fas fa-file-alt"></i>
                <span class="item-title">{{ item.title }}</span>
              </div>
            </slot>
          </div>
        </div>

        <!-- 最近编辑区域 -->
        <div class="section">
          <div class="section-header" @click="toggleSection('recent')">
            <i :class="expandedSections.recent ? 'fas fa-chevron-down' : 'fas fa-chevron-right'"></i>
            <i class="fas fa-clock section-icon"></i>
            <span>最近编辑</span>
          </div>
          <div class="section-content" v-show="expandedSections.recent">
            <slot name="recent">
              <div
                v-for="item in recentItems"
                :key="item.id"
                class="list-item"
                :class="{ active: selectedId === item.id }"
                @click="$emit('select', item)"
              >
                <i class="fas fa-file-alt"></i>
                <span class="item-title">{{ item.title }}</span>
                <span class="item-date">{{ formatDate(item.updated_at) }}</span>
              </div>
            </slot>
          </div>
        </div>

        <!-- 所有笔记区域 -->
        <div class="section">
          <div class="section-header" @click="toggleSection('allNotes')">
            <i :class="expandedSections.allNotes ? 'fas fa-chevron-down' : 'fas fa-chevron-right'"></i>
            <i class="fas fa-layer-group section-icon"></i>
            <span>所有笔记</span>
            <span v-if="allNotesCount" class="section-badge">{{ allNotesCount }}</span>
          </div>
          <div class="section-content" v-show="expandedSections.allNotes">
            <slot name="all-notes"></slot>
          </div>
        </div>
      </template>

      <!-- 文件夹视图 -->
      <template v-else>
        <!-- 私人空间区域 -->
        <div class="section">
          <div class="section-header" @click="toggleSection('private')">
            <i :class="expandedSections.private ? 'fas fa-chevron-down' : 'fas fa-chevron-right'"></i>
            <i class="fas fa-user-lock section-icon"></i>
            <span>私人空间</span>
          </div>
          <div class="section-content" v-show="expandedSections.private">
            <slot name="private">
              <!-- 文件夹树将通过 slot 插入 -->
            </slot>
          </div>
        </div>

        <!-- 共享空间区域 (预留) -->
        <div class="section" v-if="sharedFolders && sharedFolders.length">
          <div class="section-header" @click="toggleSection('shared')">
            <i :class="expandedSections.shared ? 'fas fa-chevron-down' : 'fas fa-chevron-right'"></i>
            <i class="fas fa-users section-icon"></i>
            <span>共享空间</span>
          </div>
          <div class="section-content" v-show="expandedSections.shared">
            <slot name="shared"></slot>
          </div>
        </div>
      </template>

      <!-- 默认内容插槽 -->
      <slot></slot>
    </div>

    <!-- 底部操作区 -->
    <div class="drawer-footer">
      <button class="new-page-btn" @click="$emit('create-new')">
        <i class="fas fa-plus"></i>
        <span>新建页面</span>
      </button>
      <span class="shortcut-hint">Ctrl+N</span>
    </div>
  </aside>
</template>

<script setup>
import { useDrawerSidebar } from '@/composables/useDrawerSidebar'
import '@/assets/styles/components/drawer-sidebar.css'

const props = defineProps({
  isCollapsed: {
    type: Boolean,
    default: false
  },
  workspaceName: {
    type: String,
    default: '我的空间'
  },
  searchQuery: {
    type: String,
    default: ''
  },
  favorites: {
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
  sharedFolders: {
    type: Array,
    default: () => []
  },
  allNotesCount: {
    type: Number,
    default: 0
  },
  selectedId: {
    type: [String, Number],
    default: null
  },
  defaultView: {
    type: String,
    default: 'notes'
  }
})

const emit = defineEmits([
  'toggle-collapse',
  'update:searchQuery',
  'select',
  'create-new',
  'view-change'
])

const {
  currentView,
  expandedSections,
  inboxCount,
  switchView,
  toggleSection,
  formatDate
} = useDrawerSidebar(props, emit)
</script>
