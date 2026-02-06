<template>
  <div>
    <el-alert
      title="通知设置"
      type="info"
      :closable="false"
      style="margin-bottom: 24px;">
      管理您的通知偏好设置
    </el-alert>

    <!-- 功能可用性提示 -->
    <el-alert
      type="warning"
      :closable="false"
      style="margin-bottom: 24px;">
      <template #title>
        <i class="fas fa-info-circle"></i> 功能说明
      </template>
      <p>目前仅支持以下通知功能：</p>
      <ul style="margin: 8px 0 0 20px; padding: 0;">
        <li><strong>账户安全通知</strong>：登录、密码修改、密码重置等</li>
        <li><strong>笔记活动通知</strong>：笔记创建、修改、删除等</li>
        <li><strong>个人主页点赞通知</strong>：他人点赞您的个人主页</li>
      </ul>
      <p style="margin-top: 8px;">其他通知功能正在开发中，敬请期待...</p>
    </el-alert>

    <div class="notification-section">
      <h3 class="section-title">
        <i class="fas fa-envelope"></i> 邮件通知
      </h3>
      <el-form label-position="left" label-width="180px">
        <!-- 可用功能 -->
        <el-form-item label="登录通知">
          <el-switch v-model="notifications.notify_login" @change="saveNotifications" />
          <div class="form-hint">
            <i class="fas fa-check-circle" style="color: #67C23A;"></i>
            账户在新设备或位置登录时通知您
          </div>
        </el-form-item>

        <el-form-item label="密码修改通知">
          <el-switch v-model="notifications.notify_password_change" @change="saveNotifications" />
          <div class="form-hint">
            <i class="fas fa-check-circle" style="color: #67C23A;"></i>
            密码修改成功后发送确认邮件
          </div>
        </el-form-item>

        <el-form-item label="密码重置通知">
          <el-switch v-model="notifications.notify_password_reset" @change="saveNotifications" />
          <div class="form-hint">
            <i class="fas fa-check-circle" style="color: #67C23A;"></i>
            密码重置成功后发送确认邮件
          </div>
        </el-form-item>

        <el-form-item label="笔记活动通知">
          <el-switch v-model="notifications.notify_note_activities" @change="saveNotifications" />
          <div class="form-hint">
            <i class="fas fa-check-circle" style="color: #67C23A;"></i>
            笔记创建、修改、删除时发送通知
          </div>
        </el-form-item>

        <el-form-item label="主页点赞通知">
          <el-switch v-model="notifications.notify_profile_likes" @change="saveNotifications" />
          <div class="form-hint">
            <i class="fas fa-check-circle" style="color: #67C23A;"></i>
            有人点赞您的个人主页时通知您
          </div>
        </el-form-item>

        <el-divider style="margin: 24px 0;" />

        <!-- 未实现功能 - 禁用状态 -->
        <el-form-item label="系统通知">
          <el-switch v-model="notifications.email_system" disabled />
          <div class="form-hint" style="color: #909399;">
            <i class="fas fa-clock"></i> 开发中 - 接收系统重要通知和公告
          </div>
        </el-form-item>

        <el-form-item label="新消息提醒">
          <el-switch v-model="notifications.email_messages" disabled />
          <div class="form-hint" style="color: #909399;">
            <i class="fas fa-clock"></i> 开发中 - 有新消息时发送邮件提醒
          </div>
        </el-form-item>

        <el-form-item label="活动更新">
          <el-switch v-model="notifications.email_updates" disabled />
          <div class="form-hint" style="color: #909399;">
            <i class="fas fa-clock"></i> 开发中 - 接收平台活动和更新通知
          </div>
        </el-form-item>
      </el-form>
    </div>

    <el-divider />

    <div class="notification-section">
      <h3 class="section-title">
        <i class="fas fa-bell"></i> 浏览器通知
      </h3>
      <el-alert
        type="info"
        :closable="false"
        style="margin-bottom: 16px;">
        浏览器通知功能正在开发中
      </el-alert>
      <el-form label-position="left" label-width="180px">
        <el-form-item label="启用浏览器通知">
          <el-switch v-model="notifications.browser_enabled" disabled />
          <div class="form-hint" style="color: #909399;">
            <i class="fas fa-clock"></i> 开发中 - 允许浏览器显示桌面通知
          </div>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { useSettingsNotifications } from '@composables/useSettingsNotifications.js';
import '@/assets/styles/components/settings-notifications.css';

const {
  notifications,
  saveNotifications,
  handleBrowserNotificationToggle
} = useSettingsNotifications();
</script>
