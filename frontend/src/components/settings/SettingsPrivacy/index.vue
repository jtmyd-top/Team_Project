<template>
  <div v-loading="loading">
    <el-alert
      title="隐私与通信"
      type="info"
      :closable="false"
      style="margin-bottom: 24px;">
      管理您的私信接收和隐私设置
    </el-alert>

    <!-- 私信设置 -->
    <div class="privacy-section">
      <h3 class="section-title">
        <i class="fas fa-envelope"></i> 私信设置
      </h3>
      <el-form label-position="left" label-width="180px">
        <el-form-item label="开启私信功能">
          <el-switch v-model="privacy.allow_messages" @change="savePreference" />
          <div class="form-hint">
            <i class="fas fa-info-circle" style="color: #409EFF;"></i>
            开启后，其他用户可以向您发送私信
          </div>
        </el-form-item>

        <el-form-item label="接收范围">
          <el-radio-group
            v-model="privacy.message_mode"
            :disabled="!privacy.allow_messages"
            @change="savePreference"
          >
            <el-radio value="all">所有已登录用户</el-radio>
            <el-radio value="followers_only">仅关注者</el-radio>
          </el-radio-group>
          <div class="form-hint">
            <i class="fas fa-info-circle" style="color: #409EFF;"></i>
            选择哪些用户可以向您发送私信
          </div>
        </el-form-item>

        <el-form-item label="显示已读状态">
          <el-switch
            v-model="privacy.show_read_status"
            :disabled="!privacy.allow_messages"
            @change="savePreference"
          />
          <div class="form-hint">
            关闭后，对方无法看到您是否已读消息
          </div>
        </el-form-item>

        <el-form-item label="新消息通知">
          <el-switch
            v-model="privacy.notify_new_message"
            :disabled="!privacy.allow_messages"
            @change="savePreference"
          />
          <div class="form-hint">
            收到新私信时发送邮件通知
          </div>
        </el-form-item>
      </el-form>
    </div>

    <el-divider />

    <!-- 自动回复 -->
    <div class="privacy-section">
      <h3 class="section-title">
        <i class="fas fa-robot"></i> 自动回复
      </h3>
      <el-form label-position="left" label-width="180px">
        <el-form-item label="启用自动回复">
          <el-switch
            v-model="privacy.auto_reply_enabled"
            :disabled="!privacy.allow_messages"
            @change="savePreference"
          />
          <div class="form-hint">
            开启后，收到私信时自动发送预设回复
          </div>
        </el-form-item>

        <el-form-item v-if="privacy.auto_reply_enabled" label="自动回复内容">
          <el-input
            v-model="privacy.auto_reply_text"
            type="textarea"
            :rows="3"
            maxlength="500"
            show-word-limit
            placeholder="请输入自动回复内容，例如：您好，我暂时无法回复，稍后会联系您。"
            :disabled="!privacy.allow_messages"
            @blur="savePreference"
          />
        </el-form-item>
      </el-form>
    </div>

    <el-divider />

    <!-- 屏蔽列表 -->
    <div class="privacy-section">
      <h3 class="section-title">
        <i class="fas fa-ban"></i> 屏蔽管理
      </h3>
      <el-alert
        type="info"
        :closable="false"
        style="margin-bottom: 16px;">
        被屏蔽的用户无法向您发送私信
      </el-alert>

      <div v-loading="loadingBlocked">
        <div v-if="blockedUsers.length === 0" class="empty-blocked">
          <i class="fas fa-check-circle"></i>
          <span>暂无屏蔽用户</span>
        </div>

        <div v-else class="blocked-list">
          <div v-for="user in blockedUsers" :key="user.id" class="blocked-item">
            <div class="blocked-user-info">
              <img
                :src="user.avatar_url || '/static/img/default-avatar.png'"
                :alt="user.username"
                class="blocked-avatar"
              />
              <div class="blocked-details">
                <span class="blocked-username">{{ user.username }}</span>
                <span v-if="user.blocked_at" class="blocked-date">
                  屏蔽于 {{ user.blocked_at }}
                </span>
              </div>
            </div>
            <el-button
              type="danger"
              size="small"
              plain
              @click="unblockUser(user.id)"
            >
              取消屏蔽
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useSettingsPrivacy } from '@composables/useSettingsPrivacy.js'
import '@/assets/styles/components/settings-privacy.css'

const {
  loading,
  saving,
  privacy,
  blockedUsers,
  loadingBlocked,
  savePreference,
  unblockUser
} = useSettingsPrivacy()
</script>
