<template>
  <div>
    <el-alert
      title="通知设置"
      type="info"
      :closable="false"
      style="margin-bottom: 24px;"
    >
      管理你的通知偏好设置。
    </el-alert>

    <div class="notification-section">
      <h3 class="section-title">
        <i class="fas fa-envelope"></i> 邮件通知
      </h3>
      <el-form label-position="left" label-width="180px">
        <el-form-item label="登录通知">
          <el-switch v-model="notifications.notify_login" @change="saveNotifications" />
          <div class="form-hint">账户在新设备或位置登录时发送邮件。</div>
        </el-form-item>

        <el-form-item label="密码修改通知">
          <el-switch v-model="notifications.notify_password_change" @change="saveNotifications" />
          <div class="form-hint">密码修改成功后发送确认邮件。</div>
        </el-form-item>

        <el-form-item label="密码重置通知">
          <el-switch v-model="notifications.notify_password_reset" @change="saveNotifications" />
          <div class="form-hint">密码重置成功后发送确认邮件。</div>
        </el-form-item>

        <el-form-item label="笔记活动通知">
          <el-switch v-model="notifications.notify_note_activities" @change="saveNotifications" />
          <div class="form-hint">笔记创建、修改、删除时发送通知。</div>
        </el-form-item>

        <el-form-item label="主页点赞通知">
          <el-switch v-model="notifications.notify_profile_likes" @change="saveNotifications" />
          <div class="form-hint">有人点赞你的个人主页时发送通知。</div>
        </el-form-item>

        <el-form-item label="新消息邮件提醒">
          <el-switch v-model="notifications.email_messages" @change="saveNotifications" />
          <div class="form-hint">收到新私信时发送邮件提醒，同一用户短时间内会自动合并。</div>
          <div class="message-email-suboptions">
            <div class="suboption-row">
              <span>群组聊天被 @ 时发送邮件通知</span>
              <el-switch
                v-model="notifications.notify_group_mentions_email"
                :disabled="!notifications.email_messages"
                @change="saveNotifications"
              />
            </div>
            <el-select
              v-model="notifications.email_mention_group_ids"
              multiple
              collapse-tags
              collapse-tags-tooltip
              filterable
              placeholder="选择需要提醒的群组"
              :disabled="!notifications.email_messages || !notifications.notify_group_mentions_email"
              class="group-mention-select"
              @change="saveNotifications"
            >
              <el-option
                v-for="group in notifications.available_email_mention_groups"
                :key="group.id"
                :label="group.name"
                :value="group.id"
              />
            </el-select>
            <div class="form-hint">下拉框仅显示你已加入或创建的群组，可多选。</div>
          </div>
        </el-form-item>

        <el-divider style="margin: 24px 0;" />

        <el-form-item label="系统通知">
          <el-switch v-model="notifications.email_system" disabled />
          <div class="form-hint" style="color: #909399;">接收系统重要通知和公告。</div>
        </el-form-item>

        <el-form-item label="活动更新">
          <el-switch v-model="notifications.email_updates" disabled />
          <div class="form-hint" style="color: #909399;">接收平台活动和更新通知。</div>
        </el-form-item>
      </el-form>
    </div>

    <el-divider />

    <div class="notification-section">
      <div class="notification-center-header">
        <h3 class="section-title">
          <i class="fas fa-inbox"></i> 站内通知
          <el-badge v-if="unreadCount" :value="unreadCount" class="notification-badge" />
        </h3>
        <el-button
          size="small"
          :disabled="!unreadCount"
          @click="markAllNotificationsRead"
        >
          全部标记已读
        </el-button>
      </div>

      <el-skeleton v-if="notificationsLoading" :rows="3" animated />
      <el-empty v-else-if="!notificationItems.length" description="暂无站内通知" />
      <div v-else class="notification-center-list">
        <div
          v-for="item in notificationItems"
          :key="item.id"
          class="notification-center-item"
          :class="{ unread: !item.is_read }"
        >
          <div class="notification-center-main">
            <div class="notification-center-title">
              <span>{{ item.title }}</span>
              <el-tag v-if="!item.is_read" size="small" type="danger">未读</el-tag>
            </div>
            <div v-if="item.body" class="notification-center-body">{{ item.body }}</div>
            <div class="notification-center-time">
              {{ new Date(item.created_at).toLocaleString() }}
            </div>
          </div>
          <el-button
            v-if="!item.is_read"
            text
            type="primary"
            @click="markNotificationRead(item.id)"
          >
            标记已读
          </el-button>
        </div>
      </div>
    </div>

    <el-divider />

    <div class="notification-section">
      <h3 class="section-title">
        <i class="fas fa-bell"></i> 浏览器通知
      </h3>
      <el-alert
        type="info"
        :closable="false"
        style="margin-bottom: 16px;"
      >
        开启后，私信页面在后台或你正在查看其他会话时，收到新私信会显示浏览器桌面通知。
      </el-alert>
      <el-form label-position="left" label-width="180px">
        <el-form-item label="新消息浏览器通知">
          <el-switch
            v-model="notifications.browser_enabled"
            :disabled="!browserNotificationSupported"
            @change="handleBrowserNotificationToggle"
          />
          <div class="form-hint">
            {{ browserNotificationSupported ? '首次开启时浏览器会请求通知权限。' : '当前浏览器不支持桌面通知。' }}
          </div>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { useSettingsNotifications } from '@/features/notifications/useSettingsNotifications.js';
import '@/assets/styles/components/settings-notifications.css';

const {
  notifications,
  notificationItems,
  unreadCount,
  notificationsLoading,
  browserNotificationSupported,
  markNotificationRead,
  markAllNotificationsRead,
  saveNotifications,
  handleBrowserNotificationToggle
} = useSettingsNotifications();
</script>
