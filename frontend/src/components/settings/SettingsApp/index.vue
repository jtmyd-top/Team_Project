<template>
  <div class="st-page">
    <div class="st-layout">

      <!-- 左侧边栏 -->
      <aside class="st-sidebar">
        <div class="st-sidebar-header">
          <!-- 头像 -->
          <div class="st-avatar-wrap">
            <el-avatar :size="72" :src="userStore.avatar"></el-avatar>
            <el-upload
              :action="API_ENDPOINTS.uploadAvatar"
              name="avatar"
              :headers="csrfHeader"
              :show-file-list="false"
              :on-success="handleAvatarSuccess"
              :on-error="() => ElMessage.error('头像上传失败')"
              accept="image/*">
              <div class="st-avatar-overlay">
                <i class="fas fa-camera"></i>
              </div>
            </el-upload>
          </div>

          <!-- 用户名 + 邮箱 -->
          <div class="st-user-brief">
            <h3 class="st-user-name">{{ userStore.nickname }}</h3>
            <span class="st-user-email">{{ userStore.email }}</span>
          </div>

          <!-- 统计 -->
          <div class="st-user-stats">
            <div class="st-stat">
              <strong>{{ userStore.notes_count }}</strong>
              <span>笔记</span>
            </div>
            <div class="st-stat">
              <strong>{{ userStore.views_count }}</strong>
              <span>访问</span>
            </div>
            <div class="st-stat">
              <strong>{{ userStore.likes_count }}</strong>
              <span>点赞</span>
            </div>
          </div>
        </div>

        <!-- 导航菜单 -->
        <nav class="st-nav">
          <button
            v-for="item in navItems"
            :key="item.id"
            :class="['st-nav-item', { active: activeView === item.id }]"
            @click="switchView(item.id)">
            <i :class="item.icon"></i>
            <span>{{ item.label }}</span>
          </button>
        </nav>
      </aside>

      <!-- 右侧内容区 -->
      <main class="st-content">
        <div class="st-content-header">
          <h2 class="st-content-title">{{ currentTitle }}</h2>
        </div>
        <div class="st-content-body">
          <component
            :is="activeComponent"
            v-if="activeComponent"
            class="st-view" />
        </div>
      </main>

    </div>
  </div>
</template>

<script setup>
import { ElMessage, ElUpload } from 'element-plus';
import { useSettingsApp } from '@composables/useSettingsApp.js';
import '@/assets/styles/components/settings-app.css';

const {
  userStore,
  API_ENDPOINTS,
  csrfHeader,
  navItems,
  activeView,
  activeComponent,
  currentTitle,
  switchView,
  initViewFromHash,
  setupHashListener,
  handleAvatarSuccess,
} = useSettingsApp();

// 初始化
setupHashListener();
initViewFromHash();
</script>
