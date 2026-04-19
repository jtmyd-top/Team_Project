import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

export function useSettingsPrivacy() {
  const csrfToken = window.SETTINGS_INITIAL?.csrfToken || ''

  const loading = ref(false)
  const saving = ref(false)

  // 私信偏好
  const privacy = ref({
    allow_messages: false,
    message_mode: 'all',
    show_read_status: true,
    auto_reply_enabled: false,
    auto_reply_text: '',
    notify_new_message: true
  })

  // 屏蔽列表
  const blockedUsers = ref([])
  const loadingBlocked = ref(false)

  /**
   * 加载私信偏好设置
   */
  const loadPreference = async () => {
    loading.value = true
    try {
      const res = await fetch('/api/messages/preference/', {
        headers: { 'X-CSRFToken': csrfToken }
      })
      if (res.ok) {
        const data = await res.json()
        if (data.status === 'success' && data.preference) {
          Object.assign(privacy.value, data.preference)
        }
      }
    } catch (e) {
      console.error('加载私信设置失败:', e)
    } finally {
      loading.value = false
    }
  }

  /**
   * 保存私信偏好设置
   */
  const savePreference = async () => {
    saving.value = true
    try {
      const res = await fetch('/api/messages/preference/update/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
        body: JSON.stringify(privacy.value)
      })
      const data = await res.json()
      if (res.ok && data.status === 'success') {
        ElMessage.success('私信设置已保存')
      } else {
        ElMessage.error(data.error || '保存失败')
      }
    } catch (e) {
      ElMessage.error('保存失败，请重试')
    } finally {
      saving.value = false
    }
  }

  /**
   * 加载屏蔽用户列表
   */
  const loadBlockedUsers = async () => {
    loadingBlocked.value = true
    try {
      const res = await fetch('/api/users/blocked/', {
        headers: { 'X-CSRFToken': csrfToken }
      })
      if (res.ok) {
        const data = await res.json()
        if (data.status === 'success') {
          blockedUsers.value = data.blocked_users || []
        }
      }
    } catch (e) {
      console.error('加载屏蔽列表失败:', e)
    } finally {
      loadingBlocked.value = false
    }
  }

  /**
   * 取消屏蔽用户
   */
  const unblockUser = async (userId) => {
    try {
      const res = await fetch('/api/users/unblock/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({ user_id: userId })
      })
      const data = await res.json()
      if (res.ok && data.status === 'success') {
        blockedUsers.value = blockedUsers.value.filter(u => u.id !== userId)
        ElMessage.success('已取消屏蔽')
      } else {
        ElMessage.error(data.error || '操作失败')
      }
    } catch (e) {
      ElMessage.error('操作失败，请重试')
    }
  }

  onMounted(() => {
    loadPreference()
    loadBlockedUsers()
  })

  return {
    loading,
    saving,
    privacy,
    blockedUsers,
    loadingBlocked,
    savePreference,
    unblockUser
  }
}
