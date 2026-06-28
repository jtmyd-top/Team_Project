<template>
  <div class="gip-overlay">
    <div class="gip-card" :class="{ 'is-state': loading || error }" :style="cardStyle">
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
        <div class="gip-banner" :style="bannerStyle">
          <button class="gip-close" title="关闭" @click="emit('close')">
            <el-icon><Close /></el-icon>
          </button>
          <div class="gip-avatar-wrap">
            <el-avatar :src="groupInfo.avatar" :size="96" class="gip-avatar">
              {{ (groupInfo.name || '群')[0] }}
            </el-avatar>
          </div>
          <h2 class="gip-name">{{ groupInfo.name }}</h2>
          <div class="gip-meta">
            <span class="gip-chip">
              <el-icon><UserFilled /></el-icon>
              {{ formatMemberCount }}
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
            <div class="gip-section-label">
              <el-icon><Document /></el-icon>
              <span>群简介</span>
            </div>
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

          <div v-else-if="!inviteValid" class="gip-status" :class="linkStatusClass">
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
            :style="primaryButtonStyle"
            @click="openGroupChat"
          >
            <el-icon><ChatDotRound /></el-icon>
            <span>进入群聊</span>
          </button>
          <button
            v-else-if="viewer && viewer.can_join"
            class="gip-btn"
            :class="joinButtonClass"
            :style="joinButtonStyle"
            :disabled="joining"
            @click="joinGroup"
          >
            <el-icon v-if="joining" class="is-loading"><Loading /></el-icon>
            <el-icon v-else-if="joinSuccess"><CircleCheck /></el-icon>
            <el-icon v-else><Plus /></el-icon>
            <span>{{ joinButtonText }}</span>
          </button>
          <button v-else class="gip-btn gip-btn-disabled" disabled>
            <span>无法加入</span>
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
  Document,
  ChatDotRound,
  Plus,
} from '@element-plus/icons-vue';
import { getCsrfToken } from '../../../utils/csrf';

// 颜色工具函数
function hexToRgb(hex) {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result ? {
    r: parseInt(result[1], 16),
    g: parseInt(result[2], 16),
    b: parseInt(result[3], 16)
  } : null;
}

function rgbToHsl(r, g, b) {
  r /= 255;
  g /= 255;
  b /= 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  let h, s, l = (max + min) / 2;

  if (max === min) {
    h = s = 0;
  } else {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case r: h = ((g - b) / d + (g < b ? 6 : 0)) / 6; break;
      case g: h = ((b - r) / d + 2) / 6; break;
      case b: h = ((r - g) / d + 4) / 6; break;
    }
  }
  return { h: h * 360, s: s * 100, l: l * 100 };
}

function hslToHex(h, s, l) {
  s /= 100;
  l /= 100;
  const c = (1 - Math.abs(2 * l - 1)) * s;
  const x = c * (1 - Math.abs((h / 60) % 2 - 1));
  const m = l - c / 2;
  let r = 0, g = 0, b = 0;

  if (0 <= h && h < 60) { r = c; g = x; b = 0; }
  else if (60 <= h && h < 120) { r = x; g = c; b = 0; }
  else if (120 <= h && h < 180) { r = 0; g = c; b = x; }
  else if (180 <= h && h < 240) { r = 0; g = x; b = c; }
  else if (240 <= h && h < 300) { r = x; g = 0; b = c; }
  else if (300 <= h && h < 360) { r = c; g = 0; b = x; }

  const toHex = (val) => {
    const hex = Math.round((val + m) * 255).toString(16);
    return hex.length === 1 ? '0' + hex : hex;
  };
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}

function lightenColor(hex, percent) {
  const rgb = hexToRgb(hex);
  if (!rgb) return hex;
  const hsl = rgbToHsl(rgb.r, rgb.g, rgb.b);
  hsl.l = Math.min(100, hsl.l + percent);
  return hslToHex(hsl.h, hsl.s, hsl.l);
}

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
    Document,
    ChatDotRound,
    Plus,
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
    const joinSuccess = ref(false);

    const inviteValid = ref(false);
    const invalidReason = ref('');
    const groupInfo = ref(null);
    const linkInfo = ref(null);
    const viewer = ref(null);

    // 读取用户主题色
    const userTheme = window.userTheme || { primary_color: '#409EFF' };
    const primaryColor = userTheme.primary_color || '#409EFF';

    // 动态生成渐变背景
    const bannerStyle = computed(() => {
      const color1 = primaryColor;
      const color2 = lightenColor(primaryColor, 8);
      const color3 = lightenColor(primaryColor, 15);
      return {
        background: `linear-gradient(135deg, ${color1} 0%, ${color2} 50%, ${color3} 100%)`
      };
    });

    // 卡片样式（CSS变量）
    const cardStyle = computed(() => ({
      '--user-primary': primaryColor,
      '--user-primary-light': lightenColor(primaryColor, 10),
    }));

    // 主要按钮样式
    const primaryButtonStyle = computed(() => ({
      background: `linear-gradient(135deg, ${primaryColor}, ${lightenColor(primaryColor, 10)})`,
      boxShadow: `0 6px 16px ${primaryColor}40`,
    }));

    // 加入按钮样式
    const joinButtonClass = computed(() => ({
      'gip-btn-primary': !joinSuccess.value,
      'gip-btn-success': joinSuccess.value,
    }));

    const joinButtonStyle = computed(() => {
      if (joinSuccess.value) {
        return {
          background: 'linear-gradient(135deg, #10b981, #059669)',
          boxShadow: '0 6px 16px rgba(16, 185, 129, 0.35)',
        };
      }
      return primaryButtonStyle.value;
    });

    const joinButtonText = computed(() => {
      if (joinSuccess.value) return '加入成功';
      if (joining.value) return '加入中...';
      return '加入群组';
    });

    // 成员数格式化
    const formatMemberCount = computed(() => {
      if (!groupInfo.value) return '0 名成员';
      const count = groupInfo.value.member_count || 0;
      const onlineCount = groupInfo.value.online_count;
      if (onlineCount !== undefined && onlineCount !== null) {
        return `${count} 名成员 · ${onlineCount} 人在线`;
      }
      return `${count} 名成员`;
    });

    // 链接过期文本
    const linkExpiresText = computed(() => {
      if (!linkInfo.value || !linkInfo.value.expires_at) return '';
      return `链接将于 ${formatDate(linkInfo.value.expires_at)} 过期`;
    });

    // 链接状态样式类
    const linkStatusClass = computed(() => {
      if (!linkInfo.value) return 'warning';
      const expiresAt = new Date(linkInfo.value.expires_at);
      const now = new Date();
      const hoursUntilExpiry = (expiresAt - now) / (1000 * 60 * 60);
      if (hoursUntilExpiry < 24) return 'warning';
      return 'danger';
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

        // 处理等待审批状态
        if (data.status === 'pending' || data.pending_approval === true) {
          ElMessage.success(data.message || '入群申请已提交，请等待管理员审批');
          await loadPreview();
          setTimeout(() => {
            emit('close');
          }, 1500);
          return;
        }

        if (data.status === 'success') {
          joinSuccess.value = true;
          ElMessage.success('成功加入群组');
          // 延迟1秒后触发joined事件并关闭弹窗
          setTimeout(() => {
            emit('joined', data.group.id);
            emit('close');
          }, 1000);
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
        emit('close');
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
      joinSuccess,
      inviteValid,
      groupInfo,
      linkInfo,
      viewer,
      bannerStyle,
      cardStyle,
      primaryButtonStyle,
      joinButtonClass,
      joinButtonStyle,
      joinButtonText,
      formatMemberCount,
      linkExpiresText,
      linkStatusClass,
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
/* Full-screen overlay with enhanced backdrop */
.gip-overlay {
  position: fixed;
  inset: 0;
  z-index: 3000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(17, 24, 39, 0.65);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  animation: gip-overlay-in 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes gip-overlay-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

/* Enhanced card with multi-layer shadows */
.gip-card {
  width: 100%;
  max-width: 440px;
  background: #fff;
  border-radius: 24px;
  overflow: hidden;
  box-shadow:
    0 4px 6px rgba(0, 0, 0, 0.07),
    0 10px 20px rgba(0, 0, 0, 0.10),
    0 20px 40px rgba(0, 0, 0, 0.15);
  animation: gip-card-in 0.35s cubic-bezier(0.16, 1, 0.3, 1);
  transform-origin: center;
}

.gip-card.is-state {
  max-width: 400px;
}

@keyframes gip-card-in {
  from {
    opacity: 0;
    transform: scale(0.92) translateY(20px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

/* Reduced motion support */
@media (prefers-reduced-motion: reduce) {
  .gip-overlay,
  .gip-card {
    animation-duration: 0.01ms !important;
  }
}

/* ---- States ---- */
.gip-state {
  padding: 56px 36px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.gip-spinner {
  font-size: 44px;
  color: var(--user-primary, #6366f1);
}

.gip-state-icon {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 40px;
}

.gip-state-icon.error {
  background: #fef2f2;
  color: #ef4444;
}

.gip-state-title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: #1f2937;
  letter-spacing: -0.01em;
}

.gip-state-text {
  margin: 0;
  font-size: 15px;
  color: #6b7280;
  line-height: 1.6;
}

/* ---- Banner ---- */
.gip-banner {
  position: relative;
  padding: 44px 28px 28px;
  text-align: center;
  color: #fff;
  overflow: hidden;
}

.gip-close {
  position: absolute;
  top: 16px;
  right: 16px;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.18);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  color: #fff;
  font-size: 18px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 10;
}

.gip-close:hover {
  background: rgba(255, 255, 255, 0.32);
  transform: scale(1.08);
}

.gip-close:active {
  transform: scale(0.96);
}

.gip-avatar-wrap {
  display: inline-flex;
  padding: 5px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.22);
  margin-bottom: 16px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
}

.gip-avatar {
  background: #fff;
  color: var(--user-primary, #6366f1);
  font-size: 38px;
  font-weight: 800;
  border: 4px solid #fff;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.gip-name {
  margin: 0 0 14px;
  font-size: 26px;
  font-weight: 800;
  word-break: break-word;
  letter-spacing: -0.02em;
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
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
  gap: 6px;
  padding: 6px 14px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.22);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  font-size: 14px;
  font-weight: 600;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

/* ---- Body ---- */
.gip-body {
  padding: 26px 28px 8px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.gip-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.gip-section-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 700;
  color: #9ca3af;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.gip-desc {
  margin: 0;
  font-size: 15px;
  line-height: 1.7;
  color: #4b5563;
  white-space: pre-wrap;
  word-break: break-word;
}

.gip-linkmeta {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 13px;
  color: #9ca3af;
}

.gip-status {
  display: flex;
  align-items: flex-start;
  gap: 11px;
  padding: 14px 16px;
  border-radius: 14px;
  font-size: 14px;
  line-height: 1.6;
}

.gip-status .el-icon {
  font-size: 20px;
  flex-shrink: 0;
  margin-top: 2px;
}

.gip-status.success {
  background: #ecfdf5;
  color: #059669;
  border: 1px solid #a7f3d0;
}

.gip-status.danger {
  background: #fef2f2;
  color: #dc2626;
  border: 1px solid #fecaca;
}

.gip-status.warning {
  background: #fffbeb;
  color: #d97706;
  border: 1px solid #fde68a;
}

.gip-status-detail {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.gip-status-detail strong {
  font-weight: 700;
}

.gip-status-detail span {
  font-size: 13px;
  opacity: 0.9;
}

.gip-hint {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  border-radius: 14px;
  background: #eef2ff;
  color: var(--user-primary, #6366f1);
  font-size: 14px;
  line-height: 1.6;
  border: 1px solid #c7d2fe;
}

.gip-hint .el-icon {
  font-size: 18px;
  flex-shrink: 0;
}

/* ---- Footer ---- */
.gip-footer {
  padding: 20px 28px 28px;
  display: flex;
  flex-direction: column;
  gap: 11px;
}

.gip-btn {
  width: 100%;
  height: 50px;
  border: none;
  border-radius: 14px;
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  letter-spacing: -0.01em;
}

.gip-btn:active:not(:disabled) {
  transform: scale(0.97);
}

.gip-btn-primary {
  color: #fff;
}

.gip-btn-primary:hover:not(:disabled) {
  transform: translateY(-1px);
  filter: brightness(1.08);
}

.gip-btn-success {
  color: #fff;
}

.gip-btn-disabled {
  background: #f3f4f6;
  color: #9ca3af;
  cursor: not-allowed;
}

.gip-btn-ghost {
  background: transparent;
  color: #6b7280;
  height: 44px;
  font-weight: 600;
}

.gip-btn-ghost:hover {
  background: #f3f4f6;
}

@media (max-width: 520px) {
  .gip-overlay {
    padding: 0;
    align-items: flex-end;
  }
  .gip-card {
    max-width: 100%;
    border-radius: 24px 24px 0 0;
    animation: gip-card-in-mobile 0.35s cubic-bezier(0.16, 1, 0.3, 1);
  }
  @keyframes gip-card-in-mobile {
    from {
      opacity: 0;
      transform: translateY(100%);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
}
</style>
