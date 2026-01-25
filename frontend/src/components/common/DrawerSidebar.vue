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
import { ref, reactive, computed, watch } from 'vue'

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
    default: 'notes' // 'notes' | 'folders'
  }
})

const emit = defineEmits([
  'toggle-collapse',
  'update:searchQuery',
  'select',
  'create-new',
  'view-change'
])

// 当前视图 (全部笔记 / 文件夹)
const currentView = ref(props.defaultView)

// 收件箱数量
const inboxCount = computed(() => props.inboxItems?.length || 0)

// 展开/收起的区域状态
const expandedSections = reactive({
  inbox: true,
  favorites: true,
  recent: true,
  allNotes: false,
  private: true,
  shared: true
})

// 切换视图
const switchView = (view) => {
  currentView.value = view
  emit('view-change', view)
  // 持久化到 localStorage
  localStorage.setItem('sidebarView', view)
}

// 初始化从 localStorage 读取视图设置
const savedView = localStorage.getItem('sidebarView')
if (savedView && ['notes', 'folders'].includes(savedView)) {
  currentView.value = savedView
}

const toggleSection = (section) => {
  expandedSections[section] = !expandedSections[section]
}

// 格式化日期
const formatDate = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now - date

  // 今天内
  if (diff < 24 * 60 * 60 * 1000 && date.getDate() === now.getDate()) {
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  // 昨天
  const yesterday = new Date(now)
  yesterday.setDate(yesterday.getDate() - 1)
  if (date.getDate() === yesterday.getDate() && date.getMonth() === yesterday.getMonth()) {
    return '昨天'
  }
  // 一周内
  if (diff < 7 * 24 * 60 * 60 * 1000) {
    const days = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
    return days[date.getDay()]
  }
  // 更久
  return `${date.getMonth() + 1}/${date.getDate()}`
}
</script>

<style scoped>
.drawer-sidebar {
  width: 260px;
  height: 100%;
  background: var(--bg-secondary, #16213e);
  border-right: 1px solid var(--border-color, rgba(255, 255, 255, 0.08));
  display: flex;
  flex-direction: column;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
  flex-shrink: 0;
  z-index: 105;
}

.drawer-sidebar.collapsed {
  width: 0;
  border-right: none;
  opacity: 0;
  pointer-events: none;
}

/* 头部 */
.drawer-header {
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  flex-shrink: 0;
  border-bottom: 1px solid var(--border-color, rgba(255, 255, 255, 0.05));
}

.workspace-info {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
}

.workspace-icon {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  background: var(--primary-color, #409eff);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 12px;
  flex-shrink: 0;
}

.workspace-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #fff);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.collapse-btn {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: var(--text-secondary, rgba(255, 255, 255, 0.6));
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.collapse-btn:hover {
  background: var(--hover-bg, rgba(255, 255, 255, 0.08));
  color: var(--text-primary, #fff);
}

/* 搜索框 */
.drawer-search {
  padding: 12px;
  flex-shrink: 0;
}

/* 视图切换标签 */
.view-tabs {
  display: flex;
  padding: 0 12px 12px;
  gap: 4px;
  flex-shrink: 0;
}

.view-tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 12px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--text-secondary, rgba(255, 255, 255, 0.5));
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.view-tab:hover {
  background: var(--hover-bg, rgba(255, 255, 255, 0.08));
  color: var(--text-primary, #fff);
}

.view-tab.active {
  background: var(--active-bg, rgba(64, 158, 255, 0.15));
  color: var(--primary-color, #409eff);
}

.view-tab i {
  font-size: 12px;
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

/* 内容区域 */
.drawer-content {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 0 8px;
}

/* 滚动条样式 */
.drawer-content::-webkit-scrollbar {
  width: 4px;
}

.drawer-content::-webkit-scrollbar-track {
  background: transparent;
}

.drawer-content::-webkit-scrollbar-thumb {
  background: var(--border-color, rgba(255, 255, 255, 0.1));
  border-radius: 2px;
}

.drawer-content::-webkit-scrollbar-thumb:hover {
  background: var(--text-secondary, rgba(255, 255, 255, 0.2));
}

/* 区域样式 */
.section {
  margin-bottom: 8px;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary, rgba(255, 255, 255, 0.5));
  text-transform: uppercase;
  letter-spacing: 0.5px;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.2s ease;
}

.section-header:hover {
  background: var(--hover-bg, rgba(255, 255, 255, 0.05));
  color: var(--text-primary, #fff);
}

.section-header i {
  font-size: 10px;
  width: 12px;
  text-align: center;
}

.section-header .section-icon {
  font-size: 12px;
  width: 14px;
  margin-left: 2px;
}

.section-header .favorite-icon {
  color: var(--warning-color, #f0c674);
}

.section-badge {
  margin-left: auto;
  background: var(--primary-color, #409eff);
  color: white;
  font-size: 10px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 10px;
  min-width: 18px;
  text-align: center;
}

.section-content {
  padding-left: 4px;
}

.empty-hint {
  padding: 12px 16px;
  font-size: 12px;
  color: var(--text-secondary, rgba(255, 255, 255, 0.4));
  font-style: italic;
}

/* 列表项 */
.list-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  margin: 2px 0;
  border-radius: 6px;
  cursor: pointer;
  color: var(--text-secondary, rgba(255, 255, 255, 0.7));
  font-size: 13px;
  transition: all 0.15s ease;
}

.list-item:hover {
  background: var(--hover-bg, rgba(255, 255, 255, 0.08));
  color: var(--text-primary, #fff);
}

.list-item.active {
  background: var(--active-bg, rgba(64, 158, 255, 0.15));
  color: var(--primary-color, #409eff);
}

.list-item i {
  font-size: 14px;
  flex-shrink: 0;
}

.item-title {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-date {
  font-size: 11px;
  color: var(--text-secondary, rgba(255, 255, 255, 0.4));
  flex-shrink: 0;
}

/* 底部 */
.drawer-footer {
  padding: 12px;
  border-top: 1px solid var(--border-color, rgba(255, 255, 255, 0.05));
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.new-page-btn {
  flex: 1;
  padding: 10px 16px;
  background: transparent;
  border: 1px dashed var(--border-color, rgba(255, 255, 255, 0.2));
  border-radius: 6px;
  color: var(--text-secondary, rgba(255, 255, 255, 0.6));
  font-size: 13px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: all 0.2s ease;
}

.new-page-btn:hover {
  border-color: var(--primary-color, #409eff);
  color: var(--primary-color, #409eff);
  background: var(--primary-color-light, rgba(64, 158, 255, 0.1));
}

.shortcut-hint {
  font-size: 11px;
  color: var(--text-secondary, rgba(255, 255, 255, 0.3));
  background: var(--hover-bg, rgba(255, 255, 255, 0.05));
  padding: 4px 8px;
  border-radius: 4px;
  flex-shrink: 0;
}

/* 响应式 */
@media (max-width: 1024px) {
  .drawer-sidebar {
    position: fixed;
    top: 0;
    left: 56px;
    height: 100vh;
    z-index: 200;
    box-shadow: 4px 0 20px rgba(0, 0, 0, 0.3);
  }

  .drawer-sidebar.collapsed {
    left: 0;
  }
}

@media (max-width: 768px) {
  .drawer-sidebar {
    left: 0;
    width: 280px;
  }
}
</style>
