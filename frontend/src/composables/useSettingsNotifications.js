import { reactive, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import { apiService } from '../services/apiService.js';

export function useSettingsNotifications() {
  const notifications = reactive({
    email_system: true,
    email_security: true,
    email_messages: false,
    email_updates: false,
    browser_enabled: false,
    browser_messages: false,
    frequency: 'realtime'
  });

  const loadNotifications = async () => {
    try {
      const data = await apiService.getNotificationPreferences();
      if (data.status === 'success' && data.preferences) {
        Object.assign(notifications, data.preferences);
      }
    } catch (error) {
      console.error('加载通知设置失败:', error);
      ElMessage.error('加载通知设置失败');
    }
  };

  const saveNotifications = async () => {
    try {
      const data = await apiService.updateNotificationPreferences(notifications);
      if (data.status === 'success') {
        ElMessage.success('通知设置已保存');
      } else {
        ElMessage.error(data.message || '保存失败');
      }
    } catch (error) {
      ElMessage.error(error.message || '网络错误');
    }
  };

  const handleBrowserNotificationToggle = async () => {
    if (notifications.browser_enabled) {
      if ('Notification' in window) {
        const permission = await Notification.requestPermission();
        if (permission !== 'granted') {
          notifications.browser_enabled = false;
          ElMessage.warning('需要浏览器通知权限才能启用此功能');
          return;
        }
      } else {
        notifications.browser_enabled = false;
        ElMessage.error('您的浏览器不支持通知功能');
        return;
      }
    }
    await saveNotifications();
  };

  onMounted(() => {
    loadNotifications();
  });

  return {
    notifications,
    loadNotifications,
    saveNotifications,
    handleBrowserNotificationToggle
  };
}
