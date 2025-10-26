<template>
  <div class="settings-container">
    <!-- 顶部横幅区域 - 保留原有HTML结构 -->
    <section class="profile-banner-section">
      <img v-if="userStore.banner && !isBannerVideo" 
           :src="userStore.banner" 
           alt="个人主页横幅" 
           class="banner-image">

      <video v-if="userStore.banner && isBannerVideo"
             ref="bannerVideo"
             :src="userStore.banner"
             class="banner-image"
             autoplay loop playsinline muted
             @loadedmetadata="checkVideoAudio">
      </video>

      <!-- 音量控制 - 如果是视频 -->
      <div v-if="isBannerVideo && videoHasAudio"
           class="volume-control-container"
           @mouseenter="volumeSliderVisible = true"
           @mouseleave="volumeSliderVisible = false">
        
        <button class="volume-icon-btn" @click="toggleVideoMute">
          <i v-if="videoVolume === 0" class="fas fa-volume-mute"></i>
          <i v-else-if="videoVolume > 0 && videoVolume <= 0.5" class="fas fa-volume-down"></i>
          <i v-else class="fas fa-volume-up"></i>
        </button>

        <div class="volume-slider-wrapper" :class="{ visible: volumeSliderVisible }">
          <input type="range" min="0" max="1" step="0.01"
                 v-model.number="videoVolume"
                 @input="updateVideoVolume"
                 class="volume-slider">
        </div>
      </div>

      <!-- 横幅上传按钮 -->
      <div class="banner-overlay">
        <el-upload
          :action="uploadBannerUrl"
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

    <!-- 用户信息卡片 -->
    <div class="settings-content-wrapper">
      <div class="user-info-card">
        <div class="user-info-left">
          <div class="avatar-wrapper">
            <el-avatar :size="120" :src="userStore.avatar"></el-avatar>
            <el-upload
              :action="uploadAvatarUrl"
              name="avatar"
              :headers="csrfHeader"
              :show-file-list="false"
              :on-success="handleAvatarSuccess"
              :on-error="() => ElMessage.error('头像上传失败')"
              accept="image/*">
              <div class="avatar-edit-overlay">
                <i class="fas fa-camera avatar-edit-icon"></i>
              </div>
            </el-upload>
          </div>
        </div>

        <div class="user-info-right">
          <div class="user-basic-info">
            <h2 class="user-nickname">{{ userStore.nickname }}</h2>
            <button class="like-button" :class="{ liked: isLiked }" @click="toggleLike">
              <span class="heart-icon">{{ isLiked ? '❤️' : '🤍' }}</span>
              <span>{{ userStore.likes_count || 0 }}</span>
            </button>
          </div>
          <div class="user-stats">
            <div class="stat-item">
              <i class="fas fa-sticky-note"></i>
              <span>笔记：<span class="stat-number">{{ notesCount }}</span> 篇</span>
            </div>
            <div class="stat-item">
              <i class="fas fa-eye"></i>
              <span>访问：<span class="stat-number">{{ viewsCount }}</span> 次</span>
            </div>
          </div>
          <div v-if="userStore.bio" style="word-break: break-word; color: #606266; margin-top: 8px;">
            {{ userStore.bio }}
          </div>
        </div>
      </div>
    </div>

    <!-- 主内容区域 -->
    <div class="settings-content-wrapper">
      <!-- 选项卡导航 -->
      <nav class="settings-tabs">
        <el-menu :default-active="active" @select="active = $event" mode="horizontal">
          <el-menu-item index="profile">
            <i class="fas fa-user"></i> 个人资料
          </el-menu-item>
          <el-menu-item index="security">
            <i class="fas fa-shield-alt"></i> 账户安全
          </el-menu-item>
          <el-menu-item index="notifications">
            <i class="fas fa-bell"></i> 通知偏好
          </el-menu-item>
          <el-menu-item index="theme">
            <i class="fas fa-palette"></i> 外观主题
          </el-menu-item>
        </el-menu>
      </nav>

      <!-- 动态组件 - 根据当前标签页显示对应组件 -->
      <component :is="activeComponent"></component>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@stores/user.js'
import { apiService } from '@services/apiService.js'

// 导入子组件
import SettingsProfile from './SettingsProfile.vue'
import SettingsSecurity from './SettingsSecurity.vue'
import SettingsNotifications from './SettingsNotifications.vue'
import SettingsTheme from './SettingsTheme.vue'

// 使用user store
const userStore = useUserStore()

// 当前激活的标签页
const active = ref(localStorage.getItem('settings_active_tab') || 'profile')

// 组件映射
const componentMap = {
  profile: SettingsProfile,
  security: SettingsSecurity,
  notifications: SettingsNotifications,
  theme: SettingsTheme,
}

// 当前激活的组件
const activeComponent = computed(() => componentMap[active.value] || SettingsProfile)

// 监听标签页变化，保存到localStorage
watch(active, (newValue) => {
  localStorage.setItem('settings_active_tab', newValue)
})

// 统计数据
const notesCount = ref(window.SETTINGS_INITIAL?.notes_count || 0)
const viewsCount = ref(window.SETTINGS_INITIAL?.views_count || 0)
const isLiked = ref(window.SETTINGS_INITIAL?.is_liked || false)

// CSRF Token
const csrfHeader = { "X-CSRFToken": window.SETTINGS_INITIAL?.csrfToken || "" }

// 上传接口
const uploadAvatarUrl = window.API_ENDPOINTS?.uploadAvatar || '/api/upload-avatar/'
const uploadBannerUrl = window.API_ENDPOINTS?.uploadBanner || '/api/upload-avatar/'

// 视频相关状态
const bannerVideo = ref(null)
const videoHasAudio = ref(false)
const videoVolume = ref(0)
const volumeSliderVisible = ref(false)
const previousVolume = ref(0.5)

// 判断横幅是否为视频
const isBannerVideo = computed(() => {
  if (!userStore.banner) return false
  const videoExtensions = ['.mp4', '.webm', '.ogg']
  return videoExtensions.some(ext => userStore.banner.toLowerCase().includes(ext))
})

// 检测视频音频
const checkVideoAudio = async () => {
  await nextTick()
  const video = bannerVideo.value
  if (!video) {
    videoHasAudio.value = false
    return
  }

  try {
    if (video.audioTracks && video.audioTracks.length !== undefined) {
      videoHasAudio.value = video.audioTracks.length > 0
      return
    }
    videoHasAudio.value = true
  } catch (error) {
    console.error('检测视频音频失败:', error)
    videoHasAudio.value = true
  }
}

// 切换静音
const toggleVideoMute = () => {
  const video = bannerVideo.value
  if (!video) return

  if (videoVolume.value === 0) {
    const targetVolume = previousVolume.value > 0 ? previousVolume.value : 0.5
    video.muted = false
    video.volume = targetVolume
    videoVolume.value = targetVolume
  } else {
    if (videoVolume.value > 0) {
      previousVolume.value = videoVolume.value
    }
    video.muted = true
    video.volume = 0
    videoVolume.value = 0
  }
}

// 更新音量
const updateVideoVolume = () => {
  const video = bannerVideo.value
  if (!video) return

  video.volume = videoVolume.value
  video.muted = videoVolume.value === 0
  
  if (videoVolume.value > 0) {
    previousVolume.value = videoVolume.value
  }
}

// 处理头像上传成功
const handleAvatarSuccess = (res) => {
  if (res && res.status === "success" && res.avatar_url) {
    userStore.updateAvatar(res.avatar_url)
    ElMessage.success("头像更新成功")
  } else {
    ElMessage.error(res?.message || "头像上传失败")
  }
}

// 处理横幅上传成功
const handleBannerSuccess = (res) => {
  if (res && res.status === "success" && res.banner_url) {
    userStore.updateBanner(res.banner_url, res.is_video || false)
    ElMessage.success(res.is_video ? "横幅视频更新成功" : "横幅图片更新成功")
  } else {
    ElMessage.error(res?.message || "横幅上传失败")
  }
}

// 切换点赞
const toggleLike = async () => {
  const previousState = isLiked.value
  const previousCount = userStore.likes_count

  // 乐观更新
  isLiked.value = !isLiked.value
  userStore.updateLikesCount(isLiked.value ? previousCount + 1 : previousCount - 1)

  try {
    const data = await apiService.toggleLike()
    if (data.status === "success") {
      isLiked.value = data.is_liked
      userStore.updateLikesCount(data.likes_count)
      ElMessage.success(data.is_liked ? "已点赞 ❤️" : "已取消点赞")
    } else {
      // 回滚
      isLiked.value = previousState
      userStore.updateLikesCount(previousCount)
      ElMessage.error(data.message || "操作失败")
    }
  } catch (error) {
    // 回滚
    isLiked.value = previousState
    userStore.updateLikesCount(previousCount)
    ElMessage.error("网络错误")
  }
}

onMounted(() => {
  console.log('Settings app mounted')
})
</script>

<style scoped>
/* 样式保持与原始setting.html一致 */
.settings-container {
  max-width: 1200px;
  margin: 0 auto;
}

.profile-banner-section {
  position: relative;
  width: 100%;
  height: 300px;
  background: #f5f7fa;
  overflow: hidden;
}

.banner-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
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

.profile-banner-section:hover .banner-overlay {
  opacity: 1;
}

.banner-upload-btn {
  background: white;
  border: none;
  padding: 12px 24px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.3s;
}

.banner-upload-btn:hover {
  transform: scale(1.05);
}

.volume-control-container {
  position: absolute;
  bottom: 20px;
  right: 20px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.volume-icon-btn {
  background: rgba(0, 0, 0, 0.6);
  border: none;
  color: white;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  cursor: pointer;
  font-size: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.volume-slider-wrapper {
  opacity: 0;
  transition: opacity 0.3s;
}

.volume-slider-wrapper.visible {
  opacity: 1;
}

.volume-slider {
  width: 100px;
}

.settings-content-wrapper {
  margin-top: 20px;
}

.user-info-card {
  background: white;
  border-radius: 8px;
  padding: 24px;
  display: flex;
  gap: 24px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.avatar-wrapper {
  position: relative;
}

.avatar-edit-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.3s;
  cursor: pointer;
}

.avatar-wrapper:hover .avatar-edit-overlay {
  opacity: 1;
}

.avatar-edit-icon {
  color: white;
  font-size: 24px;
}

.user-info-right {
  flex: 1;
}

.user-basic-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.user-nickname {
  font-size: 24px;
  font-weight: 600;
  margin: 0;
}

.like-button {
  background: none;
  border: 1px solid #dcdfe6;
  padding: 8px 16px;
  border-radius: 20px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.3s;
}

.like-button.liked {
  background: #ffebee;
  border-color: #f56c6c;
}

.user-stats {
  display: flex;
  gap: 24px;
  margin-bottom: 12px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #606266;
}

.stat-number {
  font-weight: 600;
  color: #303133;
}

.settings-tabs {
  margin-bottom: 20px;
}
</style>
