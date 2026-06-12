<template>
  <el-dialog
    v-model="visible"
    title="转让群主"
    width="500px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <div class="transfer-dialog">
      <el-alert
        title="警告"
        type="warning"
        description="转让群主后，您将成为普通管理员，新群主将拥有全部管理权限。此操作不可撤销。"
        :closable="false"
        show-icon
      />

      <el-form :model="form" label-width="100px" class="transfer-form">
        <el-form-item label="选择新群主">
          <el-select
            v-model="form.newOwnerId"
            placeholder="请选择成员"
            filterable
            style="width: 100%"
            @change="handleMemberChange"
          >
            <el-option
              v-for="member in eligibleMembers"
              :key="member.user_id"
              :label="`${member.username} (${getRoleLabel(member.role)})`"
              :value="member.user_id"
            >
              <div class="member-option">
                <el-avatar :src="member.avatar" :size="32">
                  {{ member.username[0] }}
                </el-avatar>
                <span class="member-name">{{ member.username }}</span>
                <el-tag :type="member.role === 'admin' ? 'warning' : ''" size="small">
                  {{ getRoleLabel(member.role) }}
                </el-tag>
              </div>
            </el-option>
          </el-select>
        </el-form-item>

        <!-- 资格检查状态显示 -->
        <el-alert
          v-if="eligibilityLoading"
          type="info"
          :closable="false"
        >
          正在检查成员资格...
        </el-alert>

        <el-alert
          v-else-if="eligibilityData && !eligibilityData.eligible"
          type="error"
          :closable="false"
          show-icon
        >
          <template #title>该成员不满足创建群组条件</template>
          <div class="eligibility-details">
            <div class="stat-item">
              <span class="label">公开文章数：</span>
              <span :class="eligibilityData.reasons.public_notes ? 'success' : 'error'">
                {{ eligibilityData.stats.public_notes }} / {{ eligibilityData.policy.min_public_notes }}
                <el-icon v-if="eligibilityData.reasons.public_notes"><CircleCheck /></el-icon>
                <el-icon v-else><CircleClose /></el-icon>
              </span>
            </div>
            <div class="stat-item">
              <span class="label">关注者数：</span>
              <span :class="eligibilityData.reasons.followers ? 'success' : 'error'">
                {{ eligibilityData.stats.followers }} / {{ eligibilityData.policy.min_followers }}
                <el-icon v-if="eligibilityData.reasons.followers"><CircleCheck /></el-icon>
                <el-icon v-else><CircleClose /></el-icon>
              </span>
            </div>
            <div class="requirement-note">
              需满足其中一项条件。
            </div>
          </div>
        </el-alert>

        <el-alert
          v-else-if="eligibilityData && eligibilityData.eligible"
          type="success"
          :closable="false"
          show-icon
        >
          <template #title>该成员满足创建群组条件</template>
          <div class="eligibility-details">
            <div class="stat-item">
              <span class="label">公开文章数：</span>
              <span class="success">{{ eligibilityData.stats.public_notes }}</span>
            </div>
            <div class="stat-item">
              <span class="label">关注者数：</span>
              <span class="success">{{ eligibilityData.stats.followers }}</span>
            </div>
          </div>
        </el-alert>

        <el-form-item label="确认密码">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入您的账户密码以确认"
            show-password
            autocomplete="current-password"
          />
          <div class="form-tip">为了安全，请输入您的账户密码确认此操作</div>
        </el-form-item>
      </el-form>
    </div>

    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button
        type="danger"
        @click="handleTransfer"
        :loading="loading"
        :disabled="!canTransfer"
      >
        确认转让
      </el-button>
    </template>
  </el-dialog>
</template>

<script>
import { ref, computed, watch } from 'vue';
import { ElMessage } from 'element-plus';
import { CircleCheck, CircleClose } from '@element-plus/icons-vue';
import { getCsrfToken } from '../../../utils/csrf';

export default {
  name: 'TransferOwnershipDialog',
  components: {
    CircleCheck,
    CircleClose,
  },
  props: {
    modelValue: {
      type: Boolean,
      default: false,
    },
    groupId: {
      type: Number,
      required: true,
    },
    members: {
      type: Array,
      default: () => [],
    },
  },
  emits: ['update:modelValue', 'success'],
  setup(props, { emit }) {
    const visible = computed({
      get: () => props.modelValue,
      set: (val) => emit('update:modelValue', val),
    });

    const loading = ref(false);
    const eligibilityLoading = ref(false);
    const eligibilityData = ref(null);

    const form = ref({
      newOwnerId: null,
      password: '',
    });

    const eligibleMembers = computed(() => {
      return props.members.filter(m => m.role !== 'owner');
    });

    const canTransfer = computed(() => {
      return form.value.newOwnerId && form.value.password && !eligibilityLoading.value;
    });

    const getRoleLabel = (role) => {
      const labels = {
        owner: '群主',
        admin: '管理员',
        member: '成员',
      };
      return labels[role] || role;
    };

    const checkEligibility = async (userId) => {
      if (!userId) {
        eligibilityData.value = null;
        return;
      }

      eligibilityLoading.value = true;
      try {
        const resp = await fetch(`/api/messages/groups/${props.groupId}/check-transfer-eligibility/${userId}/`);
        const data = await resp.json();

        if (data.status === 'success') {
          eligibilityData.value = data;
        } else {
          ElMessage.error(data.error || '检查资格失败');
          eligibilityData.value = null;
        }
      } catch (error) {
        console.error('检查资格失败:', error);
        ElMessage.error('检查资格失败');
        eligibilityData.value = null;
      } finally {
        eligibilityLoading.value = false;
      }
    };

    const handleMemberChange = (userId) => {
      checkEligibility(userId);
    };

    const handleTransfer = async () => {
      if (!form.value.newOwnerId) {
        ElMessage.warning('请选择新群主');
        return;
      }
      if (!form.value.password) {
        ElMessage.warning('请输入密码');
        return;
      }

      loading.value = true;
      try {
        const resp = await fetch(`/api/messages/groups/${props.groupId}/transfer-ownership/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
          },
          body: JSON.stringify({
            new_owner_id: form.value.newOwnerId,
            password: form.value.password,
          }),
        });

        const data = await resp.json();
        if (data.status === 'success') {
          ElMessage.success('群主转让成功');
          emit('success');
          handleClose();
        } else {
          ElMessage.error(data.message || data.error || '转让失败');
        }
      } catch (error) {
        console.error('转让群主失败:', error);
        ElMessage.error('操作失败');
      } finally {
        loading.value = false;
      }
    };

    const handleClose = () => {
      form.value = {
        newOwnerId: null,
        password: '',
      };
      eligibilityData.value = null;
      visible.value = false;
    };

    watch(visible, (val) => {
      if (!val) {
        handleClose();
      }
    });

    return {
      visible,
      loading,
      eligibilityLoading,
      eligibilityData,
      form,
      eligibleMembers,
      canTransfer,
      getRoleLabel,
      handleMemberChange,
      handleTransfer,
      handleClose,
    };
  },
};
</script>

<style scoped>
.transfer-dialog {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.transfer-form {
  margin-top: 20px;
}

.member-option {
  display: flex;
  align-items: center;
  gap: 12px;
}

.member-name {
  flex: 1;
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 8px;
}

.eligibility-details {
  margin-top: 8px;
  font-size: 14px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.stat-item .label {
  font-weight: 500;
  color: #606266;
}

.stat-item .success {
  color: #67c23a;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 4px;
}

.stat-item .error {
  color: #f56c6c;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 4px;
}

.requirement-note {
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
  font-style: italic;
}
</style>
