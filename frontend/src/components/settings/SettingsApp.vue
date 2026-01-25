<template>
  <div class="settings-container">
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
import { ref, computed, shallowRef } from 'vue';
import { useUserStore } from '@stores/user.js';
import { ElMessage, ElUpload } from 'element-plus';
import SettingsProfile from './SettingsProfile.vue';
import SettingsSecurity from './SettingsSecurity.vue';
import SettingsNotifications from './SettingsNotifications.vue';
import SettingsTheme from './SettingsTheme.vue';

const userStore = useUserStore();

// API 端点和 CSRF 令牌
const API_ENDPOINTS = window.API_ENDPOINTS || {};
const csrfHeader = { "X-CSRFToken": window.SETTINGS_INITIAL?.csrfToken || "" };

// 导航项配置
const navItems = [
  {
    id: 'profile',
    label: '个人资料',
    icon: 'fas fa-user',
    component: SettingsProfile
  },
  {
    id: 'security',
    label: '安全设置',
    icon: 'fas fa-shield-alt',
    component: SettingsSecurity
  },
  {
    id: 'notifications',
    label: '通知设置',
    icon: 'fas fa-bell',
    component: SettingsNotifications
  },
  {
    id: 'theme',
    label: '主题设置',
    icon: 'fas fa-palette',
    component: SettingsTheme
  }
];

// 当前激活的视图
const activeView = ref('profile');

// 当前激活的组件（使用 shallowRef 优化性能）
const activeComponent = shallowRef(SettingsProfile);

// 当前标题
const currentTitle = computed(() => {
  const item = navItems.find(item => item.id === activeView.value);
  return item ? item.label : '';
});

/**
 * 切换视图（带URL更新）
 */
const switchView = (viewId) => {
  if (activeView.value === viewId) return;
  
  const item = navItems.find(item => item.id === viewId);
  if (item) {
    activeView.value = viewId;
    activeComponent.value = item.component;
    window.location.hash = viewId; // 更新URL hash
  }
};

/**
 * 处理头像上传成功
 */
const handleAvatarSuccess = (response) => {
  if (response.status === 'success') {
    userStore.updateAvatar(response.avatar_url);
    ElMessage.success('头像上传成功');
  } else {
    ElMessage.error(response.message || '头像上传失败');
  }
};

/**
 * 处理横幅上传成功
 */
const handleBannerSuccess = (response) => {
  if (response.status === 'success') {
    const isVideo = /\.(mp4|webm|ogg)$/i.test(response.banner_url);
    userStore.updateBanner(response.banner_url, isVideo);
    ElMessage.success('横幅上传成功');
  } else {
    ElMessage.error(response.message || '横幅上传失败');
  }
};

/**
 * 从 URL hash 初始化视图
 */
const initViewFromHash = () => {
  const hash = window.location.hash.slice(1); // 移除 #
  if (hash) {
    const validView = navItems.find(item => item.id === hash);
    if (validView) {
      activeView.value = hash;
      activeComponent.value = validView.component;
      return;
    }
  }
  // 默认显示第一个视图
  activeView.value = 'profile';
  activeComponent.value = SettingsProfile;
};

// 监听 hash 变化（浏览器前进/后退按钮）
window.addEventListener('hashchange', initViewFromHash);

// 初始化视图
initViewFromHash();

// ==================== 视频音频控制 ====================
const bannerVideoRef = ref(null);
const videoHasAudio = ref(false);
const videoMuted = ref(true);
const videoVolume = ref(0.5);
const previousVolume = ref(0.5);
const volumeSliderVisible = ref(false);

// 音量图标类（根据静音状态和音量大小）
const volumeIconClass = computed(() => {
  if (videoMuted.value || videoVolume.value === 0) {
    return 'fas fa-volume-mute';
  } else if (videoVolume.value < 0.5) {
    return 'fas fa-volume-down';
  } else {
    return 'fas fa-volume-up';
  }
});

/**
 * 检测视频是否有音频
 */
const checkVideoAudio = async () => {
  console.log('开始检测视频音频...');
  const video = bannerVideoRef.value;
  if (!video) {
    videoHasAudio.value = false;
    console.log('视频元素未找到');
    return;
  }

  videoHasAudio.value = false;

  try {
    // 等待视频元数据加载完成
    if (video.readyState < 1) {
      console.log('等待视频元数据加载...');
      await new Promise(resolve => {
        video.addEventListener('loadedmetadata', resolve, { once: true });
      });
    }

    console.log('视频元数据已加载，readyState:', video.readyState);

    // 方法1: 检查是否有音频轨道（最可靠）
    if (video.audioTracks && video.audioTracks.length !== undefined) {
      console.log('audioTracks数量:', video.audioTracks.length);
      videoHasAudio.value = video.audioTracks.length > 0;
      console.log('使用audioTracks API检测，有音频:', videoHasAudio.value);
      return;
    }

    // 方法2: Firefox特有API
    if (video.mozHasAudio !== undefined) {
      videoHasAudio.value = video.mozHasAudio;
      console.log('使用Firefox API检测，有音频:', videoHasAudio.value);
      return;
    }

    // 方法3: Chrome/Safari特有API
    if (video.webkitAudioDecodedByteCount !== undefined) {
      await new Promise(resolve => setTimeout(resolve, 500));
      videoHasAudio.value = video.webkitAudioDecodedByteCount > 0;
      console.log('使用Chrome/Safari API检测，有音频:', videoHasAudio.value);
      return;
    }

    // 默认显示按钮
    console.log('无可用的音频检测API，默认显示音量按钮');
    videoHasAudio.value = true;
  } catch (error) {
    console.error('检测视频音频失败:', error);
    videoHasAudio.value = true;
  }

  // 设置初始状态（保持静音）
  if (videoHasAudio.value && video) {
    video.muted = true;
    videoMuted.value = true;
    video.volume = Number(videoVolume.value);
  }

  console.log('最终检测结果 - videoHasAudio:', videoHasAudio.value);
};

/**
 * 切换视频静音状态
 */
const toggleVideoMute = async () => {
  const video = bannerVideoRef.value;
  if (!video) return;

  if (videoMuted.value) {
    // 取消静音
    const targetVolume = previousVolume.value > 0 ? previousVolume.value : 0.5;
    video.muted = false;
    video.volume = targetVolume;
    videoMuted.value = false;
    videoVolume.value = targetVolume;

    if (video.paused) {
      try {
        await video.play();
      } catch (error) {
        console.log('视频自动播放:', error);
      }
    }
    console.log('取消静音 - 音量:', targetVolume);
  } else {
    // 静音
    if (videoVolume.value > 0) {
      previousVolume.value = Number(videoVolume.value);
    }
    video.muted = true;
    video.volume = 0;
    videoMuted.value = true;
    videoVolume.value = 0;
    console.log('静音 - 保存音量:', previousVolume.value);
  }
};

/**
 * 更新视频音量
 */
const updateVideoVolume = () => {
  const video = bannerVideoRef.value;
  if (!video) return;

  const volume = Number(videoVolume.value);
  video.volume = volume;
  
  const newMutedState = volume === 0;
  videoMuted.value = newMutedState;
  video.muted = newMutedState;
  
  if (!newMutedState) {
    previousVolume.value = volume;
  }
  
  console.log('音量更新 - 音量:', volume, '静音:', newMutedState);
};
</script>

<style scoped>
.settings-container {
  width: 1200px; /* 限制最大宽度 */
  margin: var(--spacing-lg, 24px) auto; /* 居中并添加上下边距 */
  background: var(--bg-primary, white); /* 使用主题变量 */
  border-radius: var(--border-radius-base, 12px); /* 圆角 */
  box-shadow: var(--shadow-base, 0 4px 12px rgba(0,0,0,0.1)); /* 阴影 */
  overflow: hidden; /* 确保圆角生效 */
  max-width:80%;
  transition: var(--transition-base, all 0.3s ease);
}

/* ==================== 第一层：横幅 ==================== */
.banner-section {
  position: relative;
  width: 100%;
  height: 60vh; /* 增加高度 */
  background: linear-gradient(135deg, var(--primary-color, #667eea) 0%, #764ba2 100%);
  overflow: hidden;
  border-radius: var(--border-radius-base, 12px) var(--border-radius-base, 12px) 0 0; /* 顶部圆角 */
  transition: var(--transition-base, all 0.3s ease);
}

.banner-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.banner-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: rgba(255, 255, 255, 0.8);
}

.banner-placeholder i {
  font-size: 48px;
  margin-bottom: 12px;
}

.banner-placeholder p {
  font-size: 14px;
  margin: 0;
}

.banner-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.3s;
}

.banner-section:hover .banner-overlay {
  opacity: 1;
}

.banner-upload-btn {
  padding: 12px 24px;
  background: rgba(255, 255, 255, 0.9);
  border: none;
  border-radius: 6px;
  color: #333;
  font-size: 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.3s;
}

.banner-upload-btn:hover {
  background: white;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}

/* 上传按钮组 */
.banner-upload-group {
  display: flex;
  gap: 16px;
  align-items: center;
}

/* 音频控制按钮 */
.audio-control {
  position: absolute;
  bottom: 20px;
  right: 20px;
  z-index: 100;
}

.audio-btn {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  border: none;
  background: rgba(0, 0, 0, 0.6);
  color: white;
  font-size: 20px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s ease;
  backdrop-filter: blur(10px);
}

.audio-btn:hover {
  background: rgba(0, 0, 0, 0.8);
  transform: scale(1.1);
}

.audio-btn i {
  transition: transform 0.3s ease;
}

.audio-btn:active i {
  transform: scale(0.9);
}

/* 音量控制容器 */
.volume-control-container {
  position: absolute;
  bottom: 20px;
  right: 20px;
  z-index: 100;
  display: flex;
  align-items: center;
  gap: 12px;
}

/* 音量图标按钮 */
.volume-icon-btn {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  border: none;
  background: rgba(0, 0, 0, 0.6);
  color: white;
  font-size: 20px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s ease;
  backdrop-filter: blur(10px);
  flex-shrink: 0;
}

.volume-icon-btn:hover {
  background: rgba(0, 0, 0, 0.8);
  transform: scale(1.1);
}

.volume-icon-btn i {
  transition: transform 0.3s ease;
}

.volume-icon-btn:active i {
  transform: scale(0.9);
}

/* 音量滑块包装器 */
.volume-slider-wrapper {
  width: 0;
  height: 48px;
  overflow: hidden;
  display: flex;
  align-items: center;
  transition: width 0.3s ease;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(10px);
  border-radius: 24px;
  padding: 0;
}

.volume-slider-wrapper.visible {
  width: 120px;
  padding: 0 16px;
}

/* 音量滑块 */
.volume-slider {
  width: 100%;
  height: 4px;
  -webkit-appearance: none;
  appearance: none;
  background: rgba(255, 255, 255, 0.3);
  border-radius: 2px;
  outline: none;
  cursor: pointer;
}

/* 滑块轨道 - Webkit/Blink */
.volume-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: white;
  cursor: pointer;
  transition: all 0.2s ease;
}

.volume-slider::-webkit-slider-thumb:hover {
  transform: scale(1.2);
  box-shadow: 0 0 8px rgba(255, 255, 255, 0.6);
}

/* 滑块轨道 - Firefox */
.volume-slider::-moz-range-thumb {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: white;
  cursor: pointer;
  border: none;
  transition: all 0.2s ease;
}

.volume-slider::-moz-range-thumb:hover {
  transform: scale(1.2);
  box-shadow: 0 0 8px rgba(255, 255, 255, 0.6);
}

/* ==================== 第二层：用户信息卡片 ==================== */
.user-info-section {
  /* 移除 max-width 和 margin auto */
  margin: 24px 0 0 0; /* 保持在正下方，并移除 auto */
  padding: 0 24px;
  position: relative;
  /* 移除 z-index，避免在对话框遮罩层之上显示 */
}

.user-info-card {
  /* 移除背景和阴影，因为父容器已经有了 */
  border-radius: 12px;
  padding: 24px;
  display: flex;
  align-items: flex-start;
  gap: 24px;
}

@media (max-width: 768px) {
  .user-info-card {
    flex-direction: column;
    align-items: center;
    text-align: center;
  }
}

/* 头像容器 */
.avatar-container {
  position: relative;
  flex-shrink: 0;
  width: 120px;
  height: 120px;
}

/* 确保 el-upload 完全覆盖头像 */
.avatar-container :deep(.el-upload) {
  position: absolute;
  top: 0;
  left: 0;
  width: 120px !important;
  height: 120px !important;
  border-radius: 50%;
  display: block;
}

.avatar-edit-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 120px;
  height: 120px;
  background: rgba(0, 0, 0, 0.5);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.3s;
  cursor: pointer;
}

.avatar-container:hover .avatar-edit-overlay {
  opacity: 1;
}

.avatar-edit-overlay i {
  color: white;
  font-size: 24px;
}

/* 用户详情 */
.user-details {
  flex: 1;
}

.user-nickname {
  font-size: calc(var(--font-size-base, 14px) * 1.7);
  font-weight: 600;
  color: var(--text-primary, #303133);
  margin: 0 0 var(--spacing-sm, 8px) 0;
}

.user-email {
  font-size: var(--font-size-base, 14px);
  color: var(--text-tertiary, #909399);
  margin: 0 0 calc(var(--spacing-md, 12px) * 1) 0;
}

.user-bio {
  font-size: var(--font-size-base, 14px);
  color: var(--text-secondary, #606266);
  line-height: 1.6;
  margin: 0 0 var(--spacing-md, 16px) 0;
  word-wrap: break-word;
  word-break: break-all;
  overflow-wrap: break-word;
}

.user-bio-placeholder {
  font-size: 14px;
  color: #c0c4cc;
  font-style: italic;
  margin: 0 0 16px 0;
}

.user-stats {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #606266;
}

.stat-item i {
  color: #409EFF;
  font-size: 16px;
}

.stat-item strong {
  color: #303133;
  font-weight: 600;
}

/* ==================== 第三层：设置内容 ==================== */


/* 导航栏容器 */
.settings-tabs {
    display: flex;
    align-items: center;
    gap: 16px;
    border-bottom: 1px solid var(--el-border-color-light);
    overflow-x: auto;
    flex-wrap: nowrap;
}

/* 标签页按钮 */
.tab-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 16px;
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: 1rem;
    font-weight: 500;
    color: var(--el-text-color-secondary);
    cursor: pointer;
    transition: all 0.2s ease-in-out;
    margin-bottom: -1px;
}

/* 标签页图标 */
.tab-item i {
    font-size: 1rem;
}

/* 鼠标悬停状态 */
.tab-item:hover {
    color: var(--el-text-color-primary);
}

/* 激活状态 */
.tab-item.active {
    color: var(--el-color-primary);
    border-bottom-color: var(--el-color-primary);
    font-weight: 600;
}

/* 移除按钮的默认聚焦轮廓 */
.tab-item:focus,
.tab-item:focus-visible {
    outline: none;
    background-color: var(--el-fill-color-light);
    border-radius: 4px 4px 0 0;
}

/* 主内容区 */
.settings-main {
  background: transparent;
  border-radius: 0 0 12px 12px;
  box-shadow: none;
  min-height: 500px;
  padding: 0; /* 移除内边距以适应分层卡片设计 */
}

.settings-view {
  width: 100%;
  max-width: 1000px; /* 统一最大宽度 */
  margin: 0 auto; /* 居中显示 */
  padding: 24px; /* 统一内边距 */
  height: 100%;
  background-color: var(--el-bg-color-page, #f5f7fa);
  box-sizing: border-box; /* 确保padding不会增加总宽度 */
}
.setting-group-card {
  /* 关键：增加卡片间距，将它们分开 */
  margin-bottom: 24px; 
  
  /* 使用更柔和的边框和阴影 */
  border: 1px solid var(--el-border-color-lighter);
  box-shadow: var(--el-box-shadow-light); /* 更柔和的阴影 */
  border-radius: 12px; /* 圆角可以稍大一点 */
}

/* 移除最后一个卡片的外边距 */
.setting-group-card:last-of-type {
  margin-bottom: 0;
}

/* --- 3. 美化卡片头部 --- */
.setting-group-card .el-card__header {
  padding: 20px 24px;
  font-size: 1.15rem; /* 约 18px */
  font-weight: 600;
  color: var(--el-text-color-primary);
  border-bottom: 1px solid var(--el-border-color-lighter);
}

/* --- 4. 确保卡片内容有内边距 --- */
/* Element 默认有 padding，但你的 style="" 覆盖了它。我们强制它回来 */
.setting-group-card .el-card__body {
  padding: 24px !important;
}

/* --- 5. 修复内容溢出问题 --- */
.bio-display p {
  word-break: break-word; /* 允许长单词或字符串换行 */
  line-height: 1.6;
  color: var(--el-text-color-regular);
  overflow-wrap: break-word;
  word-break: break-all;
  
}
@media (max-width: 768px) {
  .settings-tabs {
    overflow-x: auto;
    flex-wrap: nowrap;
  }
  
  .tab-item {
    flex-shrink: 0;
  }
}
</style>
