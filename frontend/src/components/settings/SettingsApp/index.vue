<template>
  <div class="settings-container settings-app">
    <!-- 第一层：横幅 -->
    <section class="banner-section">
      <!-- 横幅图片 -->
      <img
        v-if="userStore.banner && !userStore.bannerIsVideo"
        :src="userStore.banner"
        alt="个人主页横幅"
        class="banner-image">

      <!-- 横幅视频 -->
      <video
        v-if="userStore.banner && userStore.bannerIsVideo"
        ref="bannerVideoRef"
        :src="userStore.banner"
        class="banner-image"
        autoplay
        loop
        playsinline
        :muted="videoMuted"
        @loadedmetadata="checkVideoAudio">
      </video>

      <!-- 音量控制容器 -->
      <div v-if="userStore.bannerIsVideo && videoHasAudio"
           class="volume-control-container"
           @mouseenter.stop="volumeSliderVisible = true"
           @mouseleave.stop="volumeSliderVisible = false">

        <!-- 音量图标按钮 -->
        <button class="volume-icon-btn"
                @click.stop="toggleVideoMute"
                :title="videoMuted ? '开启声音' : '静音'">
          <i :class="volumeIconClass" :key="volumeIconClass"></i>
        </button>

        <!-- 音量调节滑块 -->
        <div class="volume-slider-wrapper" :class="{ visible: volumeSliderVisible }">
          <input type="range"
                 min="0"
                 max="1"
                 step="0.01"
                 v-model.number="videoVolume"
                 @input="updateVideoVolume"
                 class="volume-slider">
        </div>
      </div>

      <!-- 默认横幅（如果没有上传） -->
      <div v-if="!userStore.banner" class="banner-placeholder">
        <i class="fas fa-image"></i>
        <p>点击下方头像区域上传横幅</p>
      </div>

      <!-- 横幅上传按钮 -->
      <div class="banner-overlay">
        <el-upload
          :action="API_ENDPOINTS.uploadAvatar"
          name="banner"
          :headers="csrfHeader"
          :show-file-list="false"
          :on-success="handleBannerSuccess"
          :on-error="() => ElMessage.error('横幅上传失败')"
          accept="image/jpeg,image/png,image/webp,image/gif,video/mp4,video/webm">
          <button class="banner-upload-btn">
            <i class="fas fa-camera"></i>
            {{ userStore.banner ? '更换横幅' : '上传横幅' }}
          </button>
        </el-upload>
      </div>
    </section>

    <!-- 第二层：用户信息卡片（头像 + 个性签名） -->
    <section class="user-info-section">
      <div class="user-info-card">
        <!-- 头像 -->
        <div class="avatar-container">
          <el-avatar :size="120" :src="userStore.avatar"></el-avatar>
          <!-- 头像编辑遮罩 -->
          <el-upload
            :action="API_ENDPOINTS.uploadAvatar"
            name="avatar"
            :headers="csrfHeader"
            :show-file-list="false"
            :on-success="handleAvatarSuccess"
            :on-error="() => ElMessage.error('头像上传失败')"
            accept="image/*">
            <div class="avatar-edit-overlay">
              <i class="fas fa-camera"></i>
            </div>
          </el-upload>
        </div>

        <!-- 用户信息 -->
        <div class="user-details">
          <h2 class="user-nickname">{{ userStore.nickname }}</h2>
          <p class="user-email">{{ userStore.email }}</p>
          <p v-if="userStore.bio" class="user-bio">{{ userStore.bio }}</p>
          <p v-else class="user-bio-placeholder">这个人很懒，什么都没写...</p>

          <!-- 统计信息 -->
          <div class="user-stats">
            <div class="stat-item">
              <i class="fas fa-sticky-note"></i>
              <span>笔记 <strong>{{ userStore.notes_count }}</strong></span>
            </div>
            <div class="stat-item">
              <i class="fas fa-eye"></i>
              <span>访问 <strong>{{ userStore.views_count }}</strong></span>
            </div>
            <div class="stat-item">
              <i class="fas fa-heart"></i>
              <span>点赞 <strong>{{ userStore.likes_count }}</strong></span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 第三层：设置导航和内容 -->
    <section class="settings-content-section">
      <!-- 横向导航标签 -->
      <nav class="settings-tabs">
        <button
          v-for="item in navItems"
          :key="item.id"
          :class="['tab-item', { active: activeView === item.id }]"
          @click="switchView(item.id)">
          <i :class="item.icon"></i>
          <span>{{ item.label }}</span>
        </button>
      </nav>

      <!-- 主内容区域 -->
      <main class="settings-main">
        <!-- 动态组件切换 -->
        <component
          :is="activeComponent"
          v-if="activeComponent"
          class="settings-view" />
      </main>
    </section>
  </div>
</template>

<script setup>
import { ElMessage, ElUpload } from 'element-plus';
import { useSettingsApp } from '@composables/useSettingsApp.js';
import '@/assets/styles/components/settings-app.css';

const {
  // Store
  userStore,

  // API
  API_ENDPOINTS,
  csrfHeader,

  // Navigation
  navItems,
  activeView,
  activeComponent,
  switchView,
  initViewFromHash,
  setupHashListener,

  // Upload handlers
  handleAvatarSuccess,
  handleBannerSuccess,

  // Video controls
  bannerVideoRef,
  videoHasAudio,
  videoMuted,
  videoVolume,
  volumeSliderVisible,
  volumeIconClass,
  checkVideoAudio,
  toggleVideoMute,
  updateVideoVolume,
} = useSettingsApp();

// 初始化
setupHashListener();
initViewFromHash();
</script>
