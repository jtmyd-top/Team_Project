<template>
  <el-dialog
    v-model="visible"
    title="创建邀请链接"
    width="500px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <div class="invite-dialog">
      <el-form :model="form" label-width="100px">
        <el-form-item label="过期时间">
          <el-radio-group v-model="form.expireType">
            <el-radio label="never">永不过期</el-radio>
            <el-radio label="custom">自定义</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="过期日期" v-if="form.expireType === 'custom'">
          <el-date-picker
            v-model="form.expiresAt"
            type="datetime"
            placeholder="选择日期时间"
            style="width: 100%"
            :disabled-date="disabledDate"
            format="YYYY-MM-DD HH:mm"
          />
        </el-form-item>

        <el-form-item label="使用次数">
          <el-radio-group v-model="form.usesType">
            <el-radio label="unlimited">不限制</el-radio>
            <el-radio label="limited">限制次数</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="最大使用次数" v-if="form.usesType === 'limited'">
          <el-input-number
            v-model="form.maxUses"
            :min="1"
            :max="1000"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>

      <div class="preview-section" v-if="previewLink">
        <div class="preview-label">预览链接</div>
        <div class="preview-link">
          <span>{{ previewLink }}</span>
          <el-button type="text" @click="copyPreview">复制</el-button>
        </div>
      </div>
    </div>

    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button
        type="primary"
        @click="handleCreate"
        :loading="loading"
      >
        创建链接
      </el-button>
    </template>
  </el-dialog>
</template>

<script>
import { ref, computed, watch } from 'vue';
import { ElMessage } from 'element-plus';
import { getCsrfToken } from '../../../utils/csrf';

export default {
  name: 'InvitePreviewDialog',
  props: {
    modelValue: {
      type: Boolean,
      default: false,
    },
    groupId: {
      type: Number,
      required: true,
    },
  },
  emits: ['update:modelValue', 'success'],
  setup(props, { emit }) {
    const visible = computed({
      get: () => props.modelValue,
      set: (val) => emit('update:modelValue', val),
    });

    const loading = ref(false);
    const previewLink = ref('');

    const form = ref({
      expireType: 'never',
      expiresAt: null,
      usesType: 'unlimited',
      maxUses: 100,
    });

    const disabledDate = (date) => {
      return date < new Date();
    };

    const handleCreate = async () => {
      loading.value = true;
      try {
        const body = {};

        if (form.value.expireType === 'custom' && form.value.expiresAt) {
          body.expires_at = new Date(form.value.expiresAt).toISOString();
        }

        if (form.value.usesType === 'limited') {
          body.max_uses = form.value.maxUses;
        }

        const resp = await fetch(`/api/messages/groups/${props.groupId}/invites/create/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
          },
          body: JSON.stringify(body),
        });

        const data = await resp.json();
        if (data.status === 'success') {
          previewLink.value = `${window.location.origin}/messages/groups/join/${data.token}`;
          ElMessage.success('邀请链接已创建');
          emit('success');

          // Auto-copy the link
          try {
            await navigator.clipboard.writeText(previewLink.value);
            ElMessage.success('链接已自动复制到剪贴板');
          } catch (error) {
            console.error('Auto-copy failed:', error);
          }

          // Close after 2 seconds
          setTimeout(() => {
            handleClose();
          }, 2000);
        } else {
          ElMessage.error(data.error || '创建失败');
        }
      } catch (error) {
        console.error('创建邀请链接失败:', error);
        ElMessage.error('操作失败');
      } finally {
        loading.value = false;
      }
    };

    const copyPreview = async () => {
      try {
        await navigator.clipboard.writeText(previewLink.value);
        ElMessage.success('链接已复制');
      } catch (error) {
        console.error('复制失败:', error);
        ElMessage.error('复制失败');
      }
    };

    const handleClose = () => {
      form.value = {
        expireType: 'never',
        expiresAt: null,
        usesType: 'unlimited',
        maxUses: 100,
      };
      previewLink.value = '';
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
      previewLink,
      disabledDate,
      handleCreate,
      copyPreview,
      handleClose,
    };
  },
};
</script>

<style scoped>
.invite-dialog {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.preview-section {
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
  margin-top: 20px;
}

.preview-label {
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 8px;
  color: #606266;
}

.preview-link {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #fff;
  border-radius: 4px;
  font-family: monospace;
  font-size: 12px;
  color: #409eff;
  word-break: break-all;
}
</style>
