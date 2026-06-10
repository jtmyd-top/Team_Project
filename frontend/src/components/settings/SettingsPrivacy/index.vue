<template>
  <div v-loading="loading">
    <el-alert
      title="隐私与通信"
      type="info"
      :closable="false"
      style="margin-bottom: 24px;"
    >
      管理你的私信接收策略与隐私设置。
    </el-alert>

    <div class="privacy-section">
      <h3 class="section-title">
        <i class="fas fa-users"></i> 群组创建资格
      </h3>
      <div v-loading="loadingGroupPolicy" class="group-policy-card">
        <template v-if="groupPolicy">
          <div class="group-policy-head">
            <div>
              <strong>{{ groupPolicy.eligible ? '已满足创建群组条件' : '暂未满足创建群组条件' }}</strong>
              <p v-if="groupPolicy.enabled">满足下列任一条件即可创建私信群组。</p>
              <p v-else>管理员已暂时关闭用户创建群组。</p>
            </div>
            <el-tag :type="groupPolicy.eligible ? 'success' : 'warning'" effect="plain">
              {{ groupPolicy.eligible ? '可创建' : '不可创建' }}
            </el-tag>
          </div>

          <div class="group-policy-grid">
            <div
              class="group-policy-item"
              :class="{ ok: groupPolicy.reasons?.public_notes }"
            >
              <i :class="groupPolicy.reasons?.public_notes ? 'fas fa-circle-check' : 'fas fa-file-lines'"></i>
              <span>公开文章</span>
              <strong>{{ groupPolicy.stats?.public_notes || 0 }}/{{ groupPolicy.min_public_notes }}</strong>
            </div>
            <div
              class="group-policy-item"
              :class="{ ok: groupPolicy.reasons?.followers }"
            >
              <i :class="groupPolicy.reasons?.followers ? 'fas fa-circle-check' : 'fas fa-user-plus'"></i>
              <span>关注者</span>
              <strong>{{ groupPolicy.stats?.followers || 0 }}/{{ groupPolicy.min_followers }}</strong>
            </div>
          </div>

          <el-form
            v-if="groupPolicy.can_manage"
            class="group-policy-admin-form"
            label-position="top"
          >
            <el-form-item label="允许用户创建群组">
              <el-switch v-model="groupPolicyForm.enabled" />
            </el-form-item>
            <div class="group-policy-admin-grid">
              <el-form-item label="公开文章门槛">
                <el-input-number
                  v-model="groupPolicyForm.min_public_notes"
                  :min="0"
                  :max="9999"
                  controls-position="right"
                />
              </el-form-item>
              <el-form-item label="关注者门槛">
                <el-input-number
                  v-model="groupPolicyForm.min_followers"
                  :min="0"
                  :max="999999"
                  controls-position="right"
                />
              </el-form-item>
            </div>
            <div class="group-policy-admin-actions">
              <el-button
                type="primary"
                :loading="groupPolicySaving"
                @click="saveGroupPolicy"
              >
                保存群组创建条件
              </el-button>
            </div>
          </el-form>
        </template>
        <div v-else class="form-hint">群组创建条件加载失败，请稍后刷新设置页。</div>
      </div>
    </div>

    <el-divider />

    <div class="privacy-section">
      <h3 class="section-title">
        <i class="fas fa-envelope"></i> 私信设置
      </h3>
      <el-form label-position="left" label-width="180px">
        <el-form-item label="开启私信功能">
          <el-switch v-model="privacy.allow_messages" @change="savePreference" />
          <div class="form-hint">
            <i class="fas fa-info-circle" style="color: #409EFF;"></i>
            关闭后，任何用户都无法向你发送私信。
          </div>
        </el-form-item>

        <el-form-item label="私信权限范围">
          <el-radio-group
            v-model="privacy.message_mode"
            :disabled="!privacy.allow_messages"
            @change="savePreference"
          >
            <el-radio value="all">全域用户都可私信</el-radio>
            <el-radio value="followers_only">仅限关注我的人</el-radio>
            <el-radio value="following_only">仅限我关注的人</el-radio>
          </el-radio-group>
          <div class="form-hint">
            <i class="fas fa-info-circle" style="color: #409EFF;"></i>
            当前策略由后端发送接口强校验，前端无法绕过。
          </div>
        </el-form-item>

        <el-form-item label="显示已读状态">
          <el-switch
            v-model="privacy.show_read_status"
            :disabled="!privacy.allow_messages"
            @change="savePreference"
          />
          <div class="form-hint">关闭后，对方无法看到你是否已读。</div>
        </el-form-item>

      </el-form>
    </div>

    <el-divider />

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
          <div class="form-hint">开启后，收到私信时会自动发送预设回复。</div>
        </el-form-item>

        <el-form-item v-if="privacy.auto_reply_enabled" label="自动回复内容">
          <el-input
            v-model="privacy.auto_reply_text"
            type="textarea"
            :rows="3"
            maxlength="500"
            show-word-limit
            placeholder="例如：你好，我暂时不在线，稍后回复你。"
            :disabled="!privacy.allow_messages"
            @blur="savePreference"
          />
        </el-form-item>
      </el-form>
    </div>

    <el-divider />

    <div class="privacy-section">
      <h3 class="section-title">
        <i class="fas fa-user-shield"></i> 账户可发现性
      </h3>
      <el-alert type="warning" :closable="false" style="margin-bottom: 16px;">
        关闭后，即使别人输入完整用户名或邮箱，也无法通过搜索找到你。
      </el-alert>
      <el-form label-position="left" label-width="220px">
        <el-form-item label="允许通过用户名搜索到我">
          <el-switch
            v-model="discoverability.discoverable_by_username"
            @change="saveDiscoverability"
          />
          <div class="form-hint">
            <i class="fas fa-info-circle" style="color: #409EFF;"></i>
            默认关闭。开启后，别人输入你的完整用户名可找到你。
          </div>
        </el-form-item>

        <el-form-item label="允许通过邮箱搜索到我">
          <el-switch
            v-model="discoverability.discoverable_by_email"
            @change="saveDiscoverability"
          />
          <div class="form-hint">
            <i class="fas fa-info-circle" style="color: #409EFF;"></i>
            默认关闭。开启后，别人输入你的完整邮箱可找到你。
          </div>
        </el-form-item>

        <el-form-item label="我的搜索码">
          <div class="search-code-row">
            <el-input
              :model-value="discoverability.search_code"
              readonly
              class="search-code-input"
              placeholder="未生成"
            />
            <el-button :disabled="!discoverability.search_code" @click="copySearchCode">
              <i class="fas fa-copy"></i>
              复制
            </el-button>
            <el-button type="warning" plain :loading="regeneratingCode" @click="onRegenerateCode">
              <i class="fas fa-sync-alt"></i>
              重新生成
            </el-button>
          </div>
          <div class="form-hint">
            <i class="fas fa-shield-alt" style="color: #67C23A;"></i>
            8 位随机码，可主动分享给朋友进行精准搜索。重置后旧码立即失效。
          </div>
        </el-form-item>
      </el-form>
    </div>

    <el-divider />

    <div class="privacy-section">
      <h3 class="section-title">
        <i class="fas fa-ban"></i> 屏蔽管理
      </h3>
      <el-alert type="info" :closable="false" style="margin-bottom: 16px;">
        被屏蔽用户无法向你发送私信。
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
import { ElMessageBox } from 'element-plus'
import '@/assets/styles/components/settings-privacy.css'

const {
  loading,
  groupPolicy,
  groupPolicyForm,
  groupPolicySaving,
  loadingGroupPolicy,
  privacy,
  discoverability,
  regeneratingCode,
  blockedUsers,
  loadingBlocked,
  savePreference,
  saveGroupPolicy,
  saveDiscoverability,
  regenerateSearchCode,
  copySearchCode,
  unblockUser
} = useSettingsPrivacy()

async function onRegenerateCode() {
  try {
    await ElMessageBox.confirm(
      '重新生成后，当前搜索码会立即失效。确认继续？',
      '重新生成搜索码',
      { confirmButtonText: '继续', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  await regenerateSearchCode()
}
</script>

<style scoped>
.search-code-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.search-code-input {
  max-width: 200px;
  font-family: 'Courier New', monospace;
  letter-spacing: 2px;
  font-weight: 600;
}
</style>
