<template>
  <aside class="side-nav">
    <!-- 顶部区域 -->
    <div class="nav-top">
      <!-- 搜索按钮 -->
      <button
        class="nav-btn"
        :class="{ active: activeItem === 'search' }"
        @click="handleClick('search')"
        title="搜索"
      >
        <i class="fas fa-search"></i>
      </button>
    </div>

    <!-- 中间导航区域 -->
    <nav class="nav-main">
      <button
        v-for="item in navItems"
        :key="item.id"
        class="nav-btn"
        :class="{ active: activeItem === item.id }"
        @click="handleClick(item.id)"
        :title="item.label"
      >
        <i :class="item.icon"></i>
      </button>
    </nav>

    <!-- 底部区域 -->
    <div class="nav-bottom">
      <!-- 设置按钮 -->
      <button
        class="nav-btn"
        :class="{ active: activeItem === 'settings' }"
        @click="handleClick('settings')"
        title="设置"
      >
        <i class="fas fa-cog"></i>
      </button>

      <!-- 用户头像 -->
      <div class="user-avatar" @click="$emit('user-click')">
        <img
          v-if="userAvatar"
          :src="userAvatar"
          alt="用户头像"
          class="avatar-img"
        />
        <div v-else class="avatar-placeholder">
          <i class="fas fa-user"></i>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  activeItem: {
    type: String,
    default: 'all'
  },
  userAvatar: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['nav-change', 'user-click'])

// 导航项配置
const navItems = [
  { id: 'all', label: '全部笔记', icon: 'fas fa-home' },
  { id: 'spaces', label: '我的空间', icon: 'fas fa-folder' },
  { id: 'favorites', label: '收藏夹', icon: 'fas fa-star' },
  { id: 'private', label: '保密柜', icon: 'fas fa-lock' },
  { id: 'trash', label: '回收站', icon: 'fas fa-trash-alt' }
]

const handleClick = (itemId) => {
  emit('nav-change', itemId)
}
</script>

<style scoped>
.side-nav {
  width: 56px;
  height: 100%;
  background: var(--bg-tertiary, #1a1a2e);
  border-right: 1px solid var(--border-color, rgba(255, 255, 255, 0.1));
  display: flex;
  flex-direction: column;
  padding: 12px 0;
  flex-shrink: 0;
  z-index: 110;
}

.nav-top,
.nav-main,
.nav-bottom {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.nav-main {
  flex: 1;
  margin-top: 16px;
}

.nav-bottom {
  margin-top: auto;
}

.nav-btn {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  border: none;
  background: transparent;
  color: var(--text-secondary, rgba(255, 255, 255, 0.6));
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  position: relative;
}

.nav-btn:hover {
  background: var(--hover-bg, rgba(255, 255, 255, 0.08));
  color: var(--text-primary, #fff);
}

.nav-btn.active {
  background: var(--primary-color-light, rgba(64, 158, 255, 0.15));
  color: var(--primary-color, #409eff);
}

.nav-btn.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 20px;
  background: var(--primary-color, #409eff);
  border-radius: 0 2px 2px 0;
}

.user-avatar {
  margin-top: 12px;
  cursor: pointer;
  transition: transform 0.2s ease;
}

.user-avatar:hover {
  transform: scale(1.05);
}

.avatar-img {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  object-fit: cover;
  border: 2px solid var(--border-color, rgba(255, 255, 255, 0.1));
}

.avatar-placeholder {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--hover-bg, rgba(255, 255, 255, 0.08));
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary, rgba(255, 255, 255, 0.6));
  font-size: 14px;
  border: 2px solid var(--border-color, rgba(255, 255, 255, 0.1));
}

/* 响应式 - 移动端隐藏 */
@media (max-width: 768px) {
  .side-nav {
    display: none;
  }
}
</style>
