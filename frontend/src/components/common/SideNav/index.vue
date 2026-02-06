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
import { useSideNav } from '@/composables/useSideNav'
import '@/assets/styles/components/side-nav.css'

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

const { navItems, handleClick } = useSideNav(emit)
</script>
