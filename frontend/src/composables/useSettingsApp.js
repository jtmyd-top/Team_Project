import { ref, computed, shallowRef } from 'vue';
import { useUserStore } from '../stores/user.js';
import { ElMessage } from 'element-plus';
import SettingsProfile from '../components/settings/SettingsProfile/index.vue';
import SettingsSecurity from '../components/settings/SettingsSecurity/index.vue';
import SettingsNotifications from '../components/settings/SettingsNotifications/index.vue';
import SettingsPrivacy from '../components/settings/SettingsPrivacy/index.vue';
import SettingsTheme from '../components/settings/SettingsTheme/index.vue';

export function useSettingsApp() {
  const userStore = useUserStore();

  // API 端点和 CSRF 令牌
  const API_ENDPOINTS = window.API_ENDPOINTS || {};
  const csrfHeader = { "X-CSRFToken": window.SETTINGS_INITIAL?.csrfToken || "" };

  // 导航项配置
  const navItems = [
    { id: 'profile', label: '个人资料', icon: 'fas fa-user', component: SettingsProfile },
    { id: 'security', label: '安全设置', icon: 'fas fa-shield-alt', component: SettingsSecurity },
    { id: 'notifications', label: '通知设置', icon: 'fas fa-bell', component: SettingsNotifications },
    { id: 'privacy', label: '隐私与通信', icon: 'fas fa-user-shield', component: SettingsPrivacy },
    { id: 'theme', label: '主题设置', icon: 'fas fa-palette', component: SettingsTheme }
  ];

  const activeView = ref('profile');
  const activeComponent = shallowRef(SettingsProfile);

  const currentTitle = computed(() => {
    const item = navItems.find(item => item.id === activeView.value);
    return item ? item.label : '';
  });

  const switchView = (viewId) => {
    if (activeView.value === viewId) return;
    const item = navItems.find(item => item.id === viewId);
    if (item) {
      activeView.value = viewId;
      activeComponent.value = item.component;
      window.location.hash = viewId;
    }
  };

  const handleAvatarSuccess = (response) => {
    if (response.status === 'success') {
      userStore.updateAvatar(response.avatar_url);
      ElMessage.success('头像上传成功');
    } else {
      ElMessage.error(response.message || '头像上传失败');
    }
  };

  const initViewFromHash = () => {
    const hash = window.location.hash.slice(1);
    if (hash) {
      const validView = navItems.find(item => item.id === hash);
      if (validView) {
        activeView.value = hash;
        activeComponent.value = validView.component;
        return;
      }
    }
    activeView.value = 'profile';
    activeComponent.value = SettingsProfile;
  };

  const setupHashListener = () => {
    window.addEventListener('hashchange', initViewFromHash);
  };

  return {
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
  };
}
