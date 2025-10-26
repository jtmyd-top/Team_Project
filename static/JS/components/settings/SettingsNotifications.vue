<template>
  <div class="settings-content-card">
    <div class="form-section">
      <h3 class="form-section-title">邮件通知偏好</h3>
      <p style="color: #606266; margin-bottom: 24px;">
        选择您希望接收邮件通知的场景。虽然部分功能尚未完善，但您可以提前配置您的偏好设置。
      </p>

      <div style="max-width: 600px;">
        <!-- 账户安全类通知 -->
        <div style="margin-bottom: 32px;">
          <h4 style="font-size: 16px; margin-bottom: 16px; color: #303133;">
            <i class="fas fa-shield-alt" style="color: #409EFF;"></i> 账户安全
          </h4>

          <el-form label-position="left" label-width="280px">
            <el-form-item label="账户登录通知" style="margin-bottom: 20px;">
              <el-switch
                v-model="userStore.notifications.notify_login"
                @change="savePreference('notify_login')"
                active-text="开启"
                inactive-text="关闭"
                :loading="savingStates.notify_login">
              </el-switch>
              <div style="color: #909399; font-size: 12px; margin-top: 4px;">
                当有新设备或异常登录时，发送邮件提醒
              </div>
            </el-form-item>

            <el-form-item label="密码修改通知" style="margin-bottom: 20px;">
              <el-switch
                v-model="userStore.notifications.notify_password_change"
                @change="savePreference('notify_password_change')"
                active-text="开启"
                inactive-text="关闭"
                :loading="savingStates.notify_password_change">
              </el-switch>
              <div style="color: #909399; font-size: 12px; margin-top: 4px;">
                密码修改成功后，发送邮件确认
              </div>
            </el-form-item>

            <el-form-item label="密码重置通知" style="margin-bottom: 20px;">
              <el-switch
                v-model="userStore.notifications.notify_password_reset"
                @change="savePreference('notify_password_reset')"
                active-text="开启"
                inactive-text="关闭"
                :loading="savingStates.notify_password_reset">
              </el-switch>
              <div style="color: #909399; font-size: 12px; margin-top: 4px;">
                当请求密码重置时，发送邮件通知
              </div>
            </el-form-item>
          </el-form>
        </div>

        <!-- 内容互动类通知 -->
        <div style="margin-bottom: 32px;">
          <h4 style="font-size: 16px; margin-bottom: 16px; color: #303133;">
            <i class="fas fa-bell" style="color: #67C23A;"></i> 内容与互动
          </h4>

          <el-form label-position="left" label-width="280px">
            <el-form-item label="笔记活动通知" style="margin-bottom: 20px;">
              <el-switch
                v-model="userStore.notifications.notify_note_activities"
                @change="savePreference('notify_note_activities')"
                active-text="开启"
                inactive-text="关闭"
                :loading="savingStates.notify_note_activities">
              </el-switch>
              <div style="color: #909399; font-size: 12px; margin-top: 4px;">
                笔记创建、修改或删除时发送通知
              </div>
            </el-form-item>

            <el-form-item label="获得点赞通知" style="margin-bottom: 20px;">
              <el-switch
                v-model="userStore.notifications.notify_profile_likes"
                @change="savePreference('notify_profile_likes')"
                active-text="开启"
                inactive-text="关闭"
                :loading="savingStates.notify_profile_likes">
              </el-switch>
              <div style="color: #909399; font-size: 12px; margin-top: 4px;">
                当您的个人空间或作品被点赞时接收通知
              </div>
            </el-form-item>
          </el-form>
        </div>

        <!-- 提示信息 -->
        <el-alert
          type="info"
          :closable="false"
          style="margin-top: 24px;">
          <template #title>
            <i class="fas fa-info-circle"></i> 提示
          </template>
          <div style="font-size: 13px;">
            • 所有邮件通知都会发送到您的注册邮箱：<strong>{{ userStore.email }}</strong><br>
            • 部分功能正在开发中，开关设置会在功能上线后生效<br>
            • 您可以随时回到这里调整您的通知偏好
          </div>
        </el-alert>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive } from 'vue';
import { useUserStore } from '../../stores/user.js';
import { apiService } from '../../services/apiService.js';
import { ElMessage } from 'element-plus';

const userStore = useUserStore();

// 每个开关的保存状态
const savingStates = reactive({
  notify_login: false,
  notify_password_change: false,
  notify_password_reset: false,
  notify_note_activities: false,
  notify_profile_likes: false,
});

// 字段名称映射
const fieldNameMap = {
  'notify_login': '登录通知',
  'notify_password_change': '密码修改通知',
  'notify_password_reset': '密码重置通知',
  'notify_note_activities': '笔记活动通知',
  'notify_profile_likes': '点赞通知'
};

// 防抖计时器
let saveTimer = null;

/**
 * 保存单个通知偏好
 */
const savePreference = (fieldName) => {
  // 清除之前的计时器
  if (saveTimer) {
    clearTimeout(saveTimer);
  }

  // 设置防抖延迟
  saveTimer = setTimeout(async () => {
    // 如果正在保存，跳过
    if (savingStates[fieldName]) return;

    savingStates[fieldName] = true;

    try {
      const data = await apiService.updateNotificationPreferences(
        userStore.notifications
      );

      if (data.status === "success") {
        const fieldLabel = fieldNameMap[fieldName] || fieldName;
        const status = userStore.notifications[fieldName] ? '已开启' : '已关闭';
        ElMessage.success(`${fieldLabel}${status}`);
      } else {
        ElMessage.warning(data.message || "保存失败");
      }
    } catch (error) {
      ElMessage.error(error.message || "网络错误");
      console.error("保存通知偏好失败:", error);
    } finally {
      savingStates[fieldName] = false;
    }
  }, 500);
};
</script>

<style scoped>
.settings-content-card {
  background: white;
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.form-section {
  margin-bottom: 32px;
}

.form-section-title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 16px;
}
</style>
