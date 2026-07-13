import { reactive, ref, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import { apiService } from '../../services/apiService.js';

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

  const browserPushSupported =
    typeof window !== 'undefined' &&
    'Notification' in window &&
    'PushManager' in window &&
    'serviceWorker' in navigator;
  const browserPushConfigured = ref(false);
  const browserPushSubscribed = ref(false);
  const browserPushSubscriptionCount = ref(0);
  const browserPushLoading = ref(false);
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

  const saveNotifications = async ({ showSuccess = true } = {}) => {
    try {
      const data = await apiService.updateNotificationPreferences(notifications);
      if (data.status === 'success') {
        if (showSuccess) {
          ElMessage.success('通知设置已保存');
        }
      } else {
        ElMessage.error(data.message || data.error || '保存失败');
      }
    } catch (error) {
      ElMessage.error(error.message || '网络错误');
      throw error;
    }
  };

  const urlBase64ToUint8Array = (value) => {
    const normalized = String(value || '')
      .replace(/-/g, '+')
      .replace(/_/g, '/');
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=');
    const raw = window.atob(padded);
    return Uint8Array.from(raw, (character) => character.charCodeAt(0));
  };

  const subscriptionPayload = (subscription) => {
    const payload = subscription.toJSON();
    return {
      endpoint: payload.endpoint,
      keys: payload.keys,
      expiration_time: payload.expirationTime,
    };
  };

  const loadBrowserPushConfiguration = async () => {
    try {
      const data = await apiService.getPushSubscriptionConfiguration();
      browserPushConfigured.value = !!data.configured;
      browserPushSubscribed.value = !!data.enabled;
      browserPushSubscriptionCount.value = Number(data.subscription_count || 0);
      return data;
    } catch (error) {
      browserPushConfigured.value = false;
      browserPushSubscribed.value = false;
      browserPushSubscriptionCount.value = 0;
      throw error;
    }
  };

  const disableBrowserPush = async () => {
    if (browserPushSupported) {
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.getSubscription();
      if (subscription) {
        try {
          await apiService.removePushSubscription(subscriptionPayload(subscription));
        } finally {
          await subscription.unsubscribe();
        }
      }
    }

    notifications.browser_enabled = false;
    notifications.browser_messages = false;
    await saveNotifications({ showSuccess: false });
    browserPushSubscribed.value = false;
    await loadBrowserPushConfiguration();
  };

  const enableBrowserPush = async () => {
    if (!browserPushSupported) {
      throw new Error('当前浏览器不支持后台推送通知');
    }

    const configuration = await loadBrowserPushConfiguration();
    if (!configuration.configured || !configuration.public_key) {
      throw new Error('服务器尚未配置 Web Push 密钥，暂时无法开启后台通知');
    }

    const permission = await Notification.requestPermission();
    if (permission !== 'granted') {
      throw new Error('需要授予浏览器通知权限才能开启后台通知');
    }

    const registration = await navigator.serviceWorker.ready;
    let subscription = await registration.pushManager.getSubscription();
    if (!subscription) {
      subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(configuration.public_key),
      });
    }

    const result = await apiService.registerPushSubscription(subscriptionPayload(subscription));
    browserPushConfigured.value = !!result.configured;
    browserPushSubscribed.value = !!result.enabled;
    browserPushSubscriptionCount.value = Number(result.subscription_count || 0);
    notifications.browser_enabled = true;
    notifications.browser_messages = true;
    await saveNotifications({ showSuccess: false });
  };

  const handleBrowserNotificationToggle = async () => {
    const requestedEnabled = !!notifications.browser_enabled;
    browserPushLoading.value = true;
    try {
      if (requestedEnabled) {
        await enableBrowserPush();
        ElMessage.success('后台浏览器通知已开启');
      } else {
        await disableBrowserPush();
        ElMessage.success('后台浏览器通知已关闭');
      }
    } catch (error) {
      notifications.browser_enabled = false;
      notifications.browser_messages = false;
      browserPushSubscribed.value = false;
      ElMessage.error(error.message || '浏览器通知设置失败');
    } finally {
      browserPushLoading.value = false;
    }
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

  onMounted(async () => {
    await Promise.all([
      loadNotifications(),
      loadNotificationCenter(),
      loadBrowserPushConfiguration().catch(() => {}),
    ]);
  });

  return {
    notifications,
    notificationItems,
    unreadCount,
    notificationsLoading,
    browserPushSupported,
    browserPushConfigured,
    browserPushSubscribed,
    browserPushSubscriptionCount,
    browserPushLoading,
    loadNotifications,
    loadNotificationCenter,
    loadBrowserPushConfiguration,
    markNotificationRead,
    markAllNotificationsRead,
    saveNotifications,
    handleBrowserNotificationToggle
  };
}
