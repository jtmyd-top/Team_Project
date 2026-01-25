<template>
  <div class="primary-sidebar">
    <div class="primary-top">
      <!-- 品牌/Logo区域 (可选) -->
      <!-- <div class="brand-icon">
        <i class="fas fa-book-reader"></i>
      </div> -->

      <!-- 核心导航 -->
      <nav class="primary-nav">
        <button
          v-for="item in navItems"
          :key="item.id"
          class="nav-item"
          :class="{ active: sidebarStore.activeModule === item.id }"
          @click="handleNavClick(item)"
          :title="item.label"
        >
          <i :class="item.icon"></i>
          <!-- <span class="nav-label">{{ item.label }}</span> -->
        </button>
      </nav>
    </div>

    <div class="primary-bottom">
      <button
        class="nav-item"
        :class="{ active: sidebarStore.activeModule === 'settings' }"
        @click="handleNavClick({ id: 'settings', label: '设置' })"
        title="设置"
      >
        <i class="fas fa-cog"></i>
      </button>

      <div class="user-avatar" @click="$emit('user-profile')">
        <!-- 这里可以放用户头像 -->
        <div class="avatar-placeholder">
          <i class="fas fa-user"></i>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useSidebarStore } from '@/stores/sidebar'

const emit = defineEmits(['user-profile'])

const sidebarStore = useSidebarStore()

const navItems = [
  { id: 'all-notes', label: '全部笔记', icon: 'fas fa-house' },
  { id: 'my-space', label: '我的空间', icon: 'fas fa-folder' },
  { id: 'favorites', label: '收藏夹', icon: 'fas fa-star' },
  { id: 'vault', label: '保密柜', icon: 'fas fa-lock' },
  { id: 'trash', label: '回收站', icon: 'fas fa-trash' },
]

function handleNavClick(item) {
  sidebarStore.setActiveModule(item.id)
  
  // 如果侧边栏是收起的，则展开
  if (sidebarStore.isCollapsed) {
    sidebarStore.setCollapsed(false)
  }
}
</script>

<style scoped>
.primary-sidebar {
  width: 64px;
  height: 100%;
  background: var(--bg-secondary, #f5f5f5); /* 使用稍深的背景色 */
  border-right: 1px solid var(--border-color, #e0e0e0);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: center;
  padding: 16px 0;
  z-index: 102; /* 高于二级侧边栏 */
  flex-shrink: 0;
}

.primary-nav, .primary-bottom {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  width: 100%;
}

.nav-item {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  border: none;
  background: transparent;
  color: var(--text-secondary, #999);
  font-size: 18px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.nav-item:hover {
  background: var(--hover-bg, rgba(0,0,0,0.05));
  color: var(--text-primary, #333);
}

.nav-item.active {
  background: var(--primary-color-light, rgba(64, 158, 255, 0.1));
  color: var(--primary-color, #409eff);
}

.user-avatar {
  margin-top: 16px;
  cursor: pointer;
}

.avatar-placeholder {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--hover-bg, rgba(0,0,0,0.05));
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary, #999);
  border: 1px solid var(--border-color, #e0e0e0);
}
</style>
