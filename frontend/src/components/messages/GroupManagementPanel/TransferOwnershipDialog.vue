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
        :disabled="!form.newOwnerId || !form.password"
      >
        确认转让
      </el-button>
    </template>
  </el-dialog>
</template>

<script>
import { ref, computed, watch } from 'vue';
import { ElMessage } from 'element-plus';
import { getCsrfToken } from '../../../utils/csrf';

export default {
  name: 'TransferOwnershipDialog',
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
    const form = ref({
      newOwnerId: null,
      password: '',
    });

    const eligibleMembers = computed(() => {
      return props.members.filter(m => m.role !== 'owner');
    });

    const getRoleLabel = (role) => {
      const labels = {
        owner: '群主',
        admin: '管理员',
        member: '成员',
      };
      return labels[role] || role;
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
          ElMessage.error(data.error || '转让失败');
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
      form,
      eligibleMembers,
      getRoleLabel,
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
</style>
