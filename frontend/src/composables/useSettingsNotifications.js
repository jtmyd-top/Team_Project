import { reactive, ref, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import { apiService } from '../services/apiService.js';

export function useSettingsNotifications() {
  const notifications = reactive({
    email_system: true,
    email_security: true,
    email_messages: true,
    notify_group_mentions_email: false,
    email_mention_group_ids: [],
    available_email_mention_groups: [],
    email_updates: false,
    browser_enabled: false,
    browser_messages: false,
    frequency: 'realtime'
  });

  const browserNotificationSupported =
    typeof window !== 'undefined' && 'Notification' in window;
  const notificationItems = ref([]);
  const unreadCount = ref(0);
  const notificationsLoading = ref(false);

  const loadNotifications = async () => {
    try {
      const data = await apiService.getNotificationPreferences();
      if (data.status === 'success' && data.preferences) {
        Object.assign(notifications, data.preferences);
        notifications.browser_messages = !!notifications.browser_enabled;
        notifications.email_mention_group_ids = Array.isArray(notifications.email_mention_group_ids)
          ? notifications.email_mention_group_ids
          : [];
        notifications.available_email_mention_groups = Array.isArray(notifications.available_email_mention_groups)
          ? notifications.available_email_mention_groups
          : [];
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
        ElMessage.error(data.message || data.error || '保存失败');
      }
    } catch (error) {
      ElMessage.error(error.message || '网络错误');
    }
  };

  const handleBrowserNotificationToggle = async () => {
    if (notifications.browser_enabled) {
      if (browserNotificationSupported) {
        const permission = await Notification.requestPermission();
        if (permission !== 'granted') {
          notifications.browser_enabled = false;
          notifications.browser_messages = false;
          ElMessage.warning('需要浏览器通知权限才能启用此功能');
          return;
        }
      } else {
        notifications.browser_enabled = false;
        notifications.browser_messages = false;
        ElMessage.error('您的浏览器不支持通知功能');
        return;
      }
    }
    notifications.browser_messages = !!notifications.browser_enabled;
    await saveNotifications();
  };

  const loadNotificationCenter = async () => {
    notificationsLoading.value = true;
    try {
      const data = await apiService.listNotifications({ page_size: 10 });
      notificationItems.value = data.notifications || [];
      unreadCount.value = data.unread_count || 0;
    } catch (error) {
      console.error('加载站内通知失败:', error);
      ElMessage.error('加载站内通知失败');
    } finally {
      notificationsLoading.value = false;
    }
  };

  const markNotificationRead = async (id) => {
    try {
      await apiService.markNotificationsRead({ notification_ids: [id] });
      await loadNotificationCenter();
    } catch (error) {
      ElMessage.error(error.message || '标记已读失败');
    }
  };

  const markAllNotificationsRead = async () => {
    try {
      await apiService.markNotificationsRead({ all: true });
      await loadNotificationCenter();
    } catch (error) {
      ElMessage.error(error.message || '标记已读失败');
    }
  };

  onMounted(() => {
    loadNotifications();
    loadNotificationCenter();
  });

  return {
    notifications,
    notificationItems,
    unreadCount,
    notificationsLoading,
    browserNotificationSupported,
    loadNotifications,
    loadNotificationCenter,
    markNotificationRead,
    markAllNotificationsRead,
    saveNotifications,
    handleBrowserNotificationToggle
  };
}
