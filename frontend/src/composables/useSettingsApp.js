import { ref, computed, shallowRef } from 'vue';
import { useUserStore } from '../stores/user.js';
import { ElMessage } from 'element-plus';
import SettingsProfile from '../components/settings/SettingsProfile/index.vue';
import SettingsSecurity from '../components/settings/SettingsSecurity/index.vue';
import SettingsNotifications from '../components/settings/SettingsNotifications/index.vue';
import SettingsTheme from '../components/settings/SettingsTheme/index.vue';

export function useSettingsApp() {
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
  const setupHashListener = () => {
    window.addEventListener('hashchange', initViewFromHash);
  };

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

  return {
    // Store
    userStore,

    // API
    API_ENDPOINTS,
    csrfHeader,

    // Navigation
    navItems,
    activeView,
    activeComponent,
    currentTitle,
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
  };
}
