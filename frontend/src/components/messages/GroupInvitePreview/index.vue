<template>
  <div class="gip-overlay">
    <div class="gip-card" :class="{ 'is-state': loading || error }">
      <!-- Loading State -->
      <div v-if="loading" class="gip-state">
        <el-icon class="gip-spinner is-loading"><Loading /></el-icon>
        <p class="gip-state-text">正在加载群组信息...</p>
      </div>

      <!-- Error State -->
      <div v-else-if="error" class="gip-state">
        <div class="gip-state-icon error">
          <el-icon><CircleClose /></el-icon>
        </div>
        <h3 class="gip-state-title">{{ errorTitle }}</h3>
        <p class="gip-state-text">{{ errorMessage }}</p>
        <button class="gip-btn gip-btn-ghost" @click="emit('close')">返回</button>
      </div>

      <!-- Preview Content -->
      <template v-else-if="groupInfo">
        <!-- Banner / Header -->
        <div class="gip-banner">
          <button class="gip-close" title="关闭" @click="emit('close')">
            <el-icon><Close /></el-icon>
          </button>
          <div class="gip-avatar-wrap">
            <el-avatar :src="groupInfo.avatar" :size="88" class="gip-avatar">
              {{ (groupInfo.name || '群')[0] }}
            </el-avatar>
          </div>
          <h2 class="gip-name">{{ groupInfo.name }}</h2>
          <div class="gip-meta">
            <span class="gip-chip">
              <el-icon><UserFilled /></el-icon>
              {{ groupInfo.member_count }} 名成员
            </span>
            <span v-if="linkInfo && linkInfo.remaining_uses !== null" class="gip-chip">
              <el-icon><Link /></el-icon>
              剩余 {{ linkInfo.remaining_uses }} 次
            </span>
          </div>
        </div>

        <!-- Body -->
        <div class="gip-body">
          <!-- Description -->
          <div v-if="groupInfo.description" class="gip-section">
            <div class="gip-section-label">群简介</div>
            <p class="gip-desc">{{ groupInfo.description }}</p>
          </div>

          <!-- Link meta -->
          <div v-if="linkExpiresText" class="gip-linkmeta">
            <el-icon><Clock /></el-icon>
            <span>{{ linkExpiresText }}</span>
          </div>

          <!-- Viewer status -->
          <div v-if="viewer && viewer.is_member" class="gip-status success">
            <el-icon><CircleCheck /></el-icon>
            <span>你已经是该群组的成员</span>
          </div>

          <div v-else-if="viewer && viewer.is_banned" class="gip-status danger">
            <el-icon><Warning /></el-icon>
            <div class="gip-status-detail">
              <strong>你已被该群组封禁，无法加入</strong>
              <span v-if="viewer.ban && viewer.ban.expires_at">
                封禁到期：{{ formatDate(viewer.ban.expires_at) }}
              </span>
              <span v-else>永久封禁</span>
              <span v-if="viewer.ban && viewer.ban.reason">原因：{{ viewer.ban.reason }}</span>
            </div>
          </div>

          <div v-else-if="!inviteValid" class="gip-status warning">
            <el-icon><Warning /></el-icon>
            <span>{{ getInvalidReason() }}</span>
          </div>

          <div v-else class="gip-hint">
            <el-icon><InfoFilled /></el-icon>
            <span>加入后即可查看群内消息并参与聊天</span>
          </div>
        </div>

        <!-- Footer actions -->
        <div class="gip-footer">
          <button
            v-if="viewer && viewer.is_member"
            class="gip-btn gip-btn-primary"
            @click="openGroupChat"
          >
            进入群聊
          </button>
          <button
            v-else-if="viewer && viewer.can_join"
            class="gip-btn gip-btn-primary"
            :disabled="joining"
            @click="joinGroup"
          >
            <el-icon v-if="joining" class="is-loading"><Loading /></el-icon>
            {{ joining ? '加入中...' : '加入群组' }}
          </button>
          <button v-else class="gip-btn gip-btn-disabled" disabled>
            无法加入
          </button>
          <button class="gip-btn gip-btn-ghost" @click="emit('close')">返回</button>
        </div>
      </template>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import {
  Loading,
  CircleClose,
  CircleCheck,
  Close,
  Clock,
  Link,
  Warning,
  InfoFilled,
  UserFilled,
} from '@element-plus/icons-vue';
import { getCsrfToken } from '../../../utils/csrf';

export default {
  name: 'GroupInvitePreview',
  components: {
    Loading,
    CircleClose,
    CircleCheck,
    Close,
    Clock,
    Link,
    Warning,
    InfoFilled,
    UserFilled,
  },
  props: {
    token: {
      type: String,
      required: true,
    },
  },
  emits: ['close', 'joined'],
  setup(props, { emit }) {
    const loading = ref(true);
    const error = ref(false);
    const errorTitle = ref('');
    const errorMessage = ref('');
    const joining = ref(false);

    const inviteValid = ref(false);
    const invalidReason = ref('');
    const groupInfo = ref(null);
    const linkInfo = ref(null);
    const viewer = ref(null);

    const linkExpiresText = computed(() => {
      if (!linkInfo.value || !linkInfo.value.expires_at) return '';
      return `链接将于 ${formatDate(linkInfo.value.expires_at)} 过期`;
    });

    const loadPreview = async () => {
      loading.value = true;
      error.value = false;

      try {
        const resp = await fetch(`/api/messages/groups/invites/${props.token}/preview/`);
        const data = await resp.json();

        if (resp.status === 404) {
          error.value = true;
          errorTitle.value = '邀请链接不存在';
          errorMessage.value = '该邀请链接可能已被删除或无效';
          return;
        }

        if (data.status === 'success') {
          inviteValid.value = data.valid;
          invalidReason.value = data.reason;
          groupInfo.value = data.group;
          linkInfo.value = data.link;
          viewer.value = data.viewer;
        } else {
          error.value = true;
          errorTitle.value = '加载失败';
          errorMessage.value = data.error || '无法加载群组信息';
        }
      } catch (err) {
        console.error('加载群组预览失败:', err);
        error.value = true;
        errorTitle.value = '加载失败';
        errorMessage.value = '网络错误，请稍后重试';
      } finally {
        loading.value = false;
      }
    };

    const joinGroup = async () => {
      joining.value = true;
      try {
        const resp = await fetch(`/api/messages/groups/invites/${props.token}/join/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
          },
        });

        const data = await resp.json();
        if (data.status === 'success') {
          ElMessage.success('成功加入群组');
          emit('joined', data.group.id);
        } else {
          ElMessage.error(data.error || '加入失败');
          await loadPreview();
        }
      } catch (err) {
        console.error('加入群组失败:', err);
        ElMessage.error('操作失败，请稍后重试');
      } finally {
        joining.value = false;
      }
    };

    const openGroupChat = () => {
      if (groupInfo.value) {
        emit('joined', groupInfo.value.id);
      }
    };

    const getInvalidReason = () => {
      const reasons = {
        revoked: '邀请链接已被撤销',
        expired: '邀请链接已过期',
        max_uses_reached: '邀请链接使用次数已达上限',
        group_inactive: '群组已被停用',
      };
      return reasons[invalidReason.value] || '邀请链接无效';
    };

    const formatDate = (dateStr) => {
      if (!dateStr) return '';
      const date = new Date(dateStr);
      return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      });
    };

    onMounted(() => {
      loadPreview();
    });

    return {
      loading,
      error,
      errorTitle,
      errorMessage,
      joining,
      inviteValid,
      groupInfo,
      linkInfo,
      viewer,
      linkExpiresText,
      loadPreview,
      joinGroup,
      openGroupChat,
      getInvalidReason,
      formatDate,
      emit,
    };
  },
};
</script>

<style scoped>
/* Full-screen overlay that breaks out of the grid layout */
.gip-overlay {
  position: fixed;
  inset: 0;
  z-index: 3000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(17, 24, 39, 0.55);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
}

.gip-card {
  width: 100%;
  max-width: 420px;
  background: #fff;
  border-radius: 20px;
  overflow: hidden;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.28);
  animation: gip-pop 0.24s cubic-bezier(0.16, 1, 0.3, 1);
}

.gip-card.is-state {
  max-width: 380px;
}

@keyframes gip-pop {
  from { opacity: 0; transform: translateY(12px) scale(0.97); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

/* ---- States ---- */
.gip-state {
  padding: 48px 32px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
}

.gip-spinner {
  font-size: 40px;
  color: #6366f1;
}

.gip-state-icon {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 36px;
}

.gip-state-icon.error {
  background: #fef2f2;
  color: #ef4444;
}

.gip-state-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
}

.gip-state-text {
  margin: 0;
  font-size: 14px;
  color: #6b7280;
}

/* ---- Banner ---- */
.gip-banner {
  position: relative;
  padding: 36px 24px 24px;
  text-align: center;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #a855f7 100%);
  color: #fff;
}

.gip-close {
  position: absolute;
  top: 14px;
  right: 14px;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.2);
  color: #fff;
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
}

.gip-close:hover {
  background: rgba(255, 255, 255, 0.35);
}

.gip-avatar-wrap {
  display: inline-flex;
  padding: 4px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.25);
  margin-bottom: 14px;
}

.gip-avatar {
  background: #fff;
  color: #6366f1;
  font-size: 34px;
  font-weight: 700;
  border: 3px solid #fff;
}

.gip-name {
  margin: 0 0 12px;
  font-size: 22px;
  font-weight: 700;
  word-break: break-word;
}

.gip-meta {
  display: flex;
  gap: 10px;
  justify-content: center;
  flex-wrap: wrap;
}

.gip-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.2);
  font-size: 13px;
  font-weight: 500;
}

/* ---- Body ---- */
.gip-body {
  padding: 22px 24px 6px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.gip-section-label {
  font-size: 13px;
  font-weight: 600;
  color: #9ca3af;
  margin-bottom: 6px;
}

.gip-desc {
  margin: 0;
  font-size: 14px;
  line-height: 1.6;
  color: #4b5563;
  white-space: pre-wrap;
  word-break: break-word;
}

.gip-linkmeta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #9ca3af;
}

.gip-status {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 14px;
  border-radius: 12px;
  font-size: 14px;
}

.gip-status .el-icon {
  font-size: 18px;
  flex-shrink: 0;
  margin-top: 1px;
}

.gip-status.success {
  background: #ecfdf5;
  color: #059669;
}

.gip-status.danger {
  background: #fef2f2;
  color: #dc2626;
}

.gip-status.warning {
  background: #fffbeb;
  color: #d97706;
}

.gip-status-detail {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.gip-status-detail strong {
  font-weight: 600;
}

.gip-status-detail span {
  font-size: 12px;
  opacity: 0.85;
}

.gip-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  border-radius: 12px;
  background: #eef2ff;
  color: #6366f1;
  font-size: 13px;
}

.gip-hint .el-icon {
  font-size: 16px;
}

/* ---- Footer ---- */
.gip-footer {
  padding: 18px 24px 24px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.gip-btn {
  width: 100%;
  height: 46px;
  border: none;
  border-radius: 12px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  transition: transform 0.1s, box-shadow 0.2s, background 0.2s;
}

.gip-btn:active {
  transform: scale(0.98);
}

.gip-btn-primary {
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
  box-shadow: 0 6px 16px rgba(99, 102, 241, 0.35);
}

.gip-btn-primary:hover {
  box-shadow: 0 8px 22px rgba(99, 102, 241, 0.45);
}

.gip-btn-primary:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.gip-btn-disabled {
  background: #f3f4f6;
  color: #9ca3af;
  cursor: not-allowed;
}

.gip-btn-ghost {
  background: transparent;
  color: #6b7280;
  height: 40px;
  font-weight: 500;
}

.gip-btn-ghost:hover {
  background: #f3f4f6;
}

@media (max-width: 480px) {
  .gip-overlay {
    padding: 0;
    align-items: flex-end;
  }
  .gip-card {
    max-width: 100%;
    border-radius: 20px 20px 0 0;
  }
}
</style>
