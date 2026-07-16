<template>
  <el-dialog
    v-model="visible"
    title="协作成员"
    width="520px"
    class="note-collaborators-dialog"
    @open="loadCollaborators"
  >
    <template v-if="canManage">
      <el-form class="collaborator-invite" @submit.prevent="saveCollaborator">
        <el-input v-model.trim="username" placeholder="输入用户名" :disabled="loading || saving" />
        <el-select v-model="role" :disabled="loading || saving">
          <el-option label="可阅读" value="reader" />
          <el-option label="可评论" value="commenter" />
          <el-option label="可编辑" value="editor" />
          <el-option label="可管理成员" value="manager" />
        </el-select>
        <el-button type="primary" native-type="submit" :loading="saving">添加</el-button>
      </el-form>
    </template>

    <div v-loading="loading" class="collaborator-list">
      <div class="collaborator-owner">
        <i class="fas fa-crown"></i>
        <span>{{ owner?.username || '笔记所有者' }}</span>
        <el-tag size="small" type="warning">所有者</el-tag>
      </div>
      <div v-if="!loading && collaborators.length === 0" class="collaborator-empty">
        尚未添加协作成员
      </div>
      <div v-for="item in collaborators" :key="item.id" class="collaborator-row">
        <div class="collaborator-user">
          <i class="fas fa-user"></i>
          <span>{{ item.user.username }}</span>
        </div>
        <div class="collaborator-actions">
          <el-tag size="small">{{ roleLabel(item.role) }}</el-tag>
          <el-button
            v-if="canManage"
            text
            type="danger"
            :disabled="saving"
            title="移除协作者"
            @click="removeCollaborator(item)"
          >
            <i class="fas fa-xmark"></i>
          </el-button>
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { computed, ref } from 'vue'
import {
  ElButton,
  ElDialog,
  ElForm,
  ElInput,
  ElMessage,
  ElMessageBox,
  ElOption,
  ElSelect,
  ElTag,
} from 'element-plus'
import 'element-plus/es/components/button/style/css'
import 'element-plus/es/components/dialog/style/css'
import 'element-plus/es/components/form/style/css'
import 'element-plus/es/components/input/style/css'
import 'element-plus/es/components/option/style/css'
import 'element-plus/es/components/select/style/css'
import 'element-plus/es/components/tag/style/css'
import { getCsrfToken } from '@/utils/csrf'

const props = defineProps({
  modelValue: Boolean,
  noteId: Number,
})

const emit = defineEmits(['update:modelValue'])
const loading = ref(false)
const saving = ref(false)
const canManage = ref(false)
const owner = ref(null)
const collaborators = ref([])
const username = ref('')
const role = ref('reader')

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

function roleLabel(value) {
  return {
    reader: '可阅读',
    commenter: '可评论',
    editor: '可编辑',
    manager: '可管理成员',
  }[value] || value
}

async function request(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrfToken(),
      ...(options.headers || {}),
    },
    ...options,
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.error || data.message || '请求失败')
  return data
}

async function loadCollaborators() {
  if (!props.noteId) return
  loading.value = true
  try {
    const data = await request(`/api/notes/${props.noteId}/collaborators/`)
    canManage.value = Boolean(data.can_manage)
    owner.value = data.owner || null
    collaborators.value = data.collaborators || []
  } catch (error) {
    ElMessage.error(error.message || '加载协作者失败')
  } finally {
    loading.value = false
  }
}

async function saveCollaborator() {
  if (!username.value) {
    ElMessage.warning('请输入用户名')
    return
  }
  saving.value = true
  try {
    await request(`/api/notes/${props.noteId}/collaborators/`, {
      method: 'POST',
      body: JSON.stringify({ username: username.value, role: role.value }),
    })
    username.value = ''
    await loadCollaborators()
    ElMessage.success('协作者已更新')
  } catch (error) {
    ElMessage.error(error.message || '保存协作者失败')
  } finally {
    saving.value = false
  }
}

async function removeCollaborator(item) {
  try {
    await ElMessageBox.confirm(`移除 ${item.user.username} 的访问权限？`, '移除协作者', {
      type: 'warning',
      confirmButtonText: '移除',
      cancelButtonText: '取消',
    })
    saving.value = true
    await request(`/api/notes/${props.noteId}/collaborators/${item.id}/`, { method: 'DELETE' })
    await loadCollaborators()
    ElMessage.success('已移除协作者')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error.message || '移除协作者失败')
    }
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.collaborator-invite {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 126px auto;
  gap: 8px;
  margin-bottom: 18px;
}

.collaborator-list {
  min-height: 108px;
}

.collaborator-owner,
.collaborator-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.collaborator-owner {
  color: var(--el-text-color-regular);
}

.collaborator-owner .fa-crown {
  color: var(--el-color-warning);
}

.collaborator-user,
.collaborator-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.collaborator-user span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.collaborator-empty {
  padding: 24px 0;
  text-align: center;
  color: var(--el-text-color-secondary);
}

@media (max-width: 560px) {
  .collaborator-invite {
    grid-template-columns: 1fr 1fr;
  }

  .collaborator-invite .el-button {
    grid-column: 1 / -1;
  }
}
</style>
