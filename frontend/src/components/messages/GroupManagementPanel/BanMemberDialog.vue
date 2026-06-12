<template>
  <el-dialog
    v-model="visible"
    title="封禁成员"
    width="500px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <div class="ban-dialog">
      <el-alert
        title="封禁说明"
        type="info"
        description="封禁后，该成员将被立即移出群组，并在封禁期间无法通过邀请链接重新加入。"
        :closable="false"
        show-icon
      />

      <div class="member-info" v-if="member">
        <el-avatar :src="member.avatar" :size="48">
          {{ member.username[0] }}
        </el-avatar>
        <div class="member-details">
          <div class="member-name">{{ member.username }}</div>
          <div class="member-meta">{{ member.user_id }}</div>
        </div>
      </div>

      <el-form :model="form" label-width="100px" class="ban-form">
        <el-form-item label="封禁时长">
          <el-radio-group v-model="form.durationType">
            <el-radio label="temporary">临时封禁</el-radio>
            <el-radio label="permanent">永久封禁</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="封禁时间" v-if="form.durationType === 'temporary'">
          <el-select v-model="form.duration" style="width: 100%">
            <el-option label="1 小时" :value="1" />
            <el-option label="6 小时" :value="6" />
            <el-option label="24 小时" :value="24" />
            <el-option label="3 天" :value="72" />
            <el-option label="7 天" :value="168" />
            <el-option label="30 天" :value="720" />
          </el-select>
        </el-form-item>

        <el-form-item label="封禁原因">
          <el-input
            v-model="form.reason"
            type="textarea"
            :rows="3"
            placeholder="请输入封禁原因（选填）"
            maxlength="200"
            show-word-limit
          />
        </el-form-item>
      </el-form>
    </div>

    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button
        type="danger"
        @click="handleBan"
        :loading="loading"
      >
        确认封禁
      </el-button>
    </template>
  </el-dialog>
</template>

<script>
import { ref, computed, watch } from 'vue';
import { ElMessage } from 'element-plus';
import { getCsrfToken } from '../../../utils/csrf';

export default {
  name: 'BanMemberDialog',
  props: {
    modelValue: {
      type: Boolean,
      default: false,
    },
    groupId: {
      type: Number,
      required: true,
    },
    member: {
      type: Object,
      default: null,
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
      durationType: 'temporary',
      duration: 24, // hours
      reason: '',
    });

    const handleBan = async () => {
      if (!props.member) {
        ElMessage.warning('未选择成员');
        return;
      }

      loading.value = true;
      try {
        const body = {
          reason: form.value.reason,
        };

        if (form.value.durationType === 'temporary') {
          body.duration_hours = form.value.duration;
        } else {
          body.permanent = true;
        }

        const resp = await fetch(
          `/api/messages/groups/${props.groupId}/members/${props.member.user_id}/ban/`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': getCsrfToken(),
            },
            body: JSON.stringify(body),
          }
        );

        const data = await resp.json();
        if (data.status === 'success') {
          ElMessage.success('成员已封禁');
          emit('success');
          handleClose();
        } else {
          ElMessage.error(data.error || '封禁失败');
        }
      } catch (error) {
        console.error('封禁成员失败:', error);
        ElMessage.error('操作失败');
      } finally {
        loading.value = false;
      }
    };

    const handleClose = () => {
      form.value = {
        durationType: 'temporary',
        duration: 24,
        reason: '',
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
      handleBan,
      handleClose,
    };
  },
};
</script>

<style scoped>
.ban-dialog {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.member-info {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
}

.member-details {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.member-name {
  font-weight: 500;
  font-size: 16px;
}

.member-meta {
  font-size: 12px;
  color: #909399;
}

.ban-form {
  margin-top: 20px;
}
</style>
