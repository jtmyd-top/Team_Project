<template>
  <div class="gjr-container">
    <div class="gjr-header">
      <h3 class="gjr-title">入群申请</h3>
      <div class="gjr-tabs">
        <button
          :class="['gjr-tab', { active: activeTab === 'pending' }]"
          @click="activeTab = 'pending'; loadRequests()"
        >
          待审核 <span v-if="pendingCount > 0" class="gjr-badge">{{ pendingCount }}</span>
        </button>
        <button
          :class="['gjr-tab', { active: activeTab === 'approved' }]"
          @click="activeTab = 'approved'; loadRequests()"
        >
          已通过
        </button>
        <button
          :class="['gjr-tab', { active: activeTab === 'rejected' }]"
          @click="activeTab = 'rejected'; loadRequests()"
        >
          已拒绝
        </button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="gjr-loading">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>加载中...</span>
    </div>

    <!-- Empty State -->
    <div v-else-if="requests.length === 0" class="gjr-empty">
      <el-icon><Document /></el-icon>
      <p>{{ emptyText }}</p>
    </div>

    <!-- Request List -->
    <div v-else class="gjr-list">
      <div
        v-for="req in requests"
        :key="req.id"
        class="gjr-item"
      >
        <el-avatar :src="req.user.avatar" :size="48" class="gjr-avatar">
          {{ req.user.username[0] }}
        </el-avatar>

        <div class="gjr-content">
          <div class="gjr-user">
            <span class="gjr-username">{{ req.user.username }}</span>
            <span class="gjr-time">{{ formatTime(req.created_at) }}</span>
          </div>

          <div v-if="req.request_message" class="gjr-message">
            {{ req.request_message }}
          </div>

          <div v-if="req.status !== 'pending'" class="gjr-review-info">
            <span v-if="req.status === 'approved'" class="gjr-status success">
              <el-icon><CircleCheck /></el-icon>
              已通过
            </span>
            <span v-else-if="req.status === 'rejected'" class="gjr-status rejected">
              <el-icon><CircleClose /></el-icon>
              已拒绝
            </span>
            <span v-if="req.reviewed_by" class="gjr-reviewer">
              by {{ req.reviewed_by.username }}
            </span>
            <span v-if="req.reviewed_at" class="gjr-review-time">
              {{ formatTime(req.reviewed_at) }}
            </span>
          </div>

          <div v-if="req.status === 'rejected' && req.rejection_reason" class="gjr-rejection-reason">
            拒绝原因：{{ req.rejection_reason }}
          </div>
        </div>

        <div v-if="req.status === 'pending'" class="gjr-actions">
          <el-button
            type="success"
            size="small"
            :loading="processingId === req.id"
            @click="approveRequest(req)"
          >
            <el-icon><CircleCheck /></el-icon>
            通过
          </el-button>
          <el-button
            type="danger"
            size="small"
            :loading="processingId === req.id"
            @click="showRejectDialog(req)"
          >
            <el-icon><CircleClose /></el-icon>
            拒绝
          </el-button>
        </div>
      </div>
    </div>

    <!-- Reject Dialog -->
    <el-dialog
      v-model="rejectDialogVisible"
      title="拒绝入群申请"
      width="400px"
    >
      <div class="gjr-reject-form">
        <p class="gjr-reject-hint">
          拒绝 <strong>{{ currentRequest?.user?.username }}</strong> 的入群申请
        </p>
        <el-input
          v-model="rejectionReason"
          type="textarea"
          :rows="3"
          placeholder="请输入拒绝原因（必填）"
          maxlength="200"
          show-word-limit
        />
      </div>
      <template #footer>
        <el-button @click="rejectDialogVisible = false">取消</el-button>
        <el-button
          type="danger"
          :loading="processingId === currentRequest?.id"
          :disabled="!rejectionReason.trim()"
          @click="rejectRequest"
        >
          确认拒绝
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import { Loading, Document, CircleCheck, CircleClose } from '@element-plus/icons-vue';
import { getCsrfToken } from '../../../utils/csrf';

export default {
  name: 'GroupJoinRequests',
  components: {
    Loading,
    Document,
    CircleCheck,
    CircleClose,
  },
  props: {
    groupId: {
      type: Number,
      required: true,
    },
  },
  emits: ['update'],
  setup(props, { emit }) {
    const activeTab = ref('pending');
    const loading = ref(false);
    const requests = ref([]);
    const pendingCount = ref(0);
    const processingId = ref(null);

    const rejectDialogVisible = ref(false);
    const currentRequest = ref(null);
    const rejectionReason = ref('');

    const emptyText = computed(() => {
      const texts = {
        pending: '暂无待审核的入群申请',
        approved: '暂无已通过的记录',
        rejected: '暂无已拒绝的记录',
      };
      return texts[activeTab.value] || '暂无数据';
    });

    const loadRequests = async () => {
      loading.value = true;
      try {
        const resp = await fetch(`/api/messages/groups/${props.groupId}/join-requests/?status=${activeTab.value}`);
        const data = await resp.json();

        if (data.status === 'success') {
          requests.value = data.requests || [];
          if (activeTab.value === 'pending') {
            pendingCount.value = requests.value.length;
          }
        } else {
          ElMessage.error(data.error || '加载失败');
        }
      } catch (err) {
        console.error('加载入群申请失败:', err);
        ElMessage.error('加载失败，请稍后重试');
      } finally {
        loading.value = false;
      }
    };

    const approveRequest = async (req) => {
      processingId.value = req.id;
      try {
        const resp = await fetch(`/api/messages/groups/${props.groupId}/join-requests/${req.id}/review/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
          },
          body: JSON.stringify({
            action: 'approve',
          }),
        });

        const data = await resp.json();
        if (data.status === 'success') {
          ElMessage.success('已通过申请');
          await loadRequests();
          emit('update');
        } else {
          ElMessage.error(data.error || '操作失败');
        }
      } catch (err) {
        console.error('通过申请失败:', err);
        ElMessage.error('操作失败，请稍后重试');
      } finally {
        processingId.value = null;
      }
    };

    const showRejectDialog = (req) => {
      currentRequest.value = req;
      rejectionReason.value = '';
      rejectDialogVisible.value = true;
    };

    const rejectRequest = async () => {
      if (!rejectionReason.value.trim()) {
        ElMessage.warning('请输入拒绝原因');
        return;
      }

      processingId.value = currentRequest.value.id;
      try {
        const resp = await fetch(`/api/messages/groups/${props.groupId}/join-requests/${currentRequest.value.id}/review/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
          },
          body: JSON.stringify({
            action: 'reject',
            rejection_reason: rejectionReason.value.trim(),
          }),
        });

        const data = await resp.json();
        if (data.status === 'success') {
          ElMessage.success('已拒绝申请');
          rejectDialogVisible.value = false;
          await loadRequests();
          emit('update');
        } else {
          ElMessage.error(data.error || '操作失败');
        }
      } catch (err) {
        console.error('拒绝申请失败:', err);
        ElMessage.error('操作失败，请稍后重试');
      } finally {
        processingId.value = null;
      }
    };

    const formatTime = (dateStr) => {
      if (!dateStr) return '';
      const date = new Date(dateStr);
      const now = new Date();
      const diff = now - date;
      const minutes = Math.floor(diff / 60000);
      const hours = Math.floor(diff / 3600000);
      const days = Math.floor(diff / 86400000);

      if (minutes < 1) return '刚刚';
      if (minutes < 60) return `${minutes}分钟前`;
      if (hours < 24) return `${hours}小时前`;
      if (days < 7) return `${days}天前`;

      return date.toLocaleDateString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
      });
    };

    onMounted(() => {
      loadRequests();
    });

    return {
      activeTab,
      loading,
      requests,
      pendingCount,
      processingId,
      rejectDialogVisible,
      currentRequest,
      rejectionReason,
      emptyText,
      loadRequests,
      approveRequest,
      showRejectDialog,
      rejectRequest,
      formatTime,
    };
  },
};
</script>

<style scoped>
.gjr-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fff;
}

.gjr-header {
  padding: 20px 24px;
  border-bottom: 1px solid #e5e7eb;
}

.gjr-title {
  margin: 0 0 16px;
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
}

.gjr-tabs {
  display: flex;
  gap: 8px;
}

.gjr-tab {
  padding: 8px 16px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #6b7280;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
}

.gjr-tab:hover {
  background: #f3f4f6;
}

.gjr-tab.active {
  background: #eff6ff;
  color: #2563eb;
}

.gjr-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  margin-left: 6px;
  border-radius: 10px;
  background: #ef4444;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
}

.gjr-loading,
.gjr-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #9ca3af;
}

.gjr-loading .el-icon {
  font-size: 32px;
}

.gjr-empty .el-icon {
  font-size: 48px;
  color: #d1d5db;
}

.gjr-empty p {
  margin: 0;
  font-size: 14px;
}

.gjr-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.gjr-item {
  display: flex;
  gap: 12px;
  padding: 16px;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  margin-bottom: 12px;
  transition: all 0.2s;
}

.gjr-item:hover {
  border-color: #d1d5db;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.gjr-avatar {
  flex-shrink: 0;
}

.gjr-content {
  flex: 1;
  min-width: 0;
}

.gjr-user {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.gjr-username {
  font-size: 15px;
  font-weight: 600;
  color: #1f2937;
}

.gjr-time {
  font-size: 13px;
  color: #9ca3af;
}

.gjr-message {
  padding: 10px 12px;
  border-radius: 8px;
  background: #f9fafb;
  color: #4b5563;
  font-size: 14px;
  line-height: 1.6;
  margin-bottom: 8px;
  word-break: break-word;
}

.gjr-review-info {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #6b7280;
  margin-top: 8px;
}

.gjr-status {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 6px;
  font-weight: 500;
}

.gjr-status.success {
  background: #d1fae5;
  color: #065f46;
}

.gjr-status.rejected {
  background: #fee2e2;
  color: #991b1b;
}

.gjr-reviewer,
.gjr-review-time {
  font-size: 12px;
  color: #9ca3af;
}

.gjr-rejection-reason {
  margin-top: 8px;
  padding: 10px 12px;
  border-left: 3px solid #ef4444;
  background: #fef2f2;
  color: #991b1b;
  font-size: 13px;
  line-height: 1.5;
}

.gjr-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex-shrink: 0;
}

.gjr-reject-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.gjr-reject-hint {
  margin: 0;
  font-size: 14px;
  color: #4b5563;
}

.gjr-reject-hint strong {
  color: #1f2937;
  font-weight: 600;
}
</style>
