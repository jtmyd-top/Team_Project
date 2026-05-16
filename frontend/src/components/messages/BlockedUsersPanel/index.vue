<template>
  <div class="blocked-panel">
    <div v-if="loading" class="state">
      <i class="fas fa-spinner fa-spin"></i>
      <p>加载中...</p>
    </div>
    <div v-else-if="blockedUsers.length === 0" class="state">
      <i class="fas fa-user-shield"></i>
      <p>你还没有屏蔽任何人</p>
    </div>
    <div v-else class="list">
      <div class="panel-tip">
        <i class="fas fa-info-circle"></i>
        被屏蔽的用户无法向你发送私信，也不会出现在对话列表里。
      </div>
      <div
        v-for="u in blockedUsers"
        :key="u.id"
        class="blocked-row"
      >
        <img :src="u.avatar || u.avatar_url" :alt="u.username" class="blocked-avatar" />
        <div class="blocked-info">
          <h4>{{ u.username }}</h4>
          <p v-if="u.blocked_at">屏蔽于 {{ formatDate(u.blocked_at) }}</p>
          <p v-if="u.reason" class="reason">原因：{{ u.reason }}</p>
        </div>
        <button class="unblock-btn" @click="unblock(u)">
          <i class="fas fa-unlock"></i>
          解除屏蔽
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { formatDateOnly } from '@utils/datetime'

const props = defineProps({
  csrfToken: { type: String, default: '' },
})

const emit = defineEmits(['updated'])

const loading = ref(false)
const blockedUsers = ref([])

async function load() {
  loading.value = true
  try {
    const r = await fetch('/api/users/blocked/')
    if (r.ok) {
      const d = await r.json()
      blockedUsers.value = d.blocked_users || []
    }
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function unblock(u) {
  try {
    await ElMessageBox.confirm(`确定要解除对 ${u.username} 的屏蔽吗？`, '解除屏蔽', {
      confirmButtonText: '解除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    const r = await fetch('/api/users/unblock/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': props.csrfToken,
      },
      body: JSON.stringify({ user_id: u.id }),
    })
    if (r.ok) {
      ElMessage.success('已解除屏蔽')
      blockedUsers.value = blockedUsers.value.filter((x) => x.id !== u.id)
      emit('updated')
    } else {
      const d = await r.json().catch(() => ({}))
      ElMessage.error(d.error || '解除失败')
    }
  } catch (e) {
    ElMessage.error('网络错误')
  }
}

function formatDate(iso) {
  return typeof iso === 'string' && iso.length <= 10 ? iso : formatDateOnly(iso, 'zh-CN')
}

defineExpose({ reload: load })

onMounted(load)
</script>

<style scoped>
.blocked-panel {
  height: 100%;
  overflow-y: auto;
  padding: 12px;
}

.state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 60%;
  color: var(--text-tertiary);
  gap: 12px;
}

.state i {
  font-size: 44px;
  opacity: 0.4;
}

.panel-tip {
  padding: 10px 12px;
  background: color-mix(in srgb, var(--primary-color, #2563eb) 8%, transparent);
  color: var(--text-secondary);
  border-radius: 8px;
  font-size: 12.5px;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.blocked-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px;
  border-radius: 10px;
  transition: background 0.15s;
}

.blocked-row:hover {
  background: var(--bg-tertiary, rgba(0, 0, 0, 0.04));
}

.blocked-avatar {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
}

.blocked-info {
  flex: 1;
  min-width: 0;
}

.blocked-info h4 {
  margin: 0 0 2px 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.blocked-info p {
  font-size: 12px;
  color: var(--text-tertiary);
  margin: 0;
}

.blocked-info .reason {
  color: var(--text-secondary);
}

.unblock-btn {
  padding: 6px 12px;
  border: 1px solid var(--border-color);
  background: var(--bg-primary);
  color: var(--text-primary);
  border-radius: 6px;
  cursor: pointer;
  font-size: 12.5px;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all 0.15s;
}

.unblock-btn:hover {
  border-color: var(--primary-color);
  color: var(--primary-color);
}
</style>
