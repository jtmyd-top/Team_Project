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

      <div class="user-avatar" @click="handleUserProfile">
        <!-- 这里可以放用户头像 -->
        <div class="avatar-placeholder">
          <i class="fas fa-user"></i>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { usePrimarySidebar } from '@composables/usePrimarySidebar'
import '@/assets/styles/components/primary-sidebar.css'

const emit = defineEmits(['user-profile'])

const {
  sidebarStore,
  navItems,
  handleNavClick,
  handleUserProfile
} = usePrimarySidebar(emit)
</script>
