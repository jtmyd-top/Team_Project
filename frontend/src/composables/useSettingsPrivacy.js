import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

export function useSettingsPrivacy() {
  const csrfToken = window.SETTINGS_INITIAL?.csrfToken || ''

  const loading = ref(false)
  const saving = ref(false)
  const groupPolicy = ref(null)
  const loadingGroupPolicy = ref(false)

  // 私信偏好
  const privacy = ref({
    allow_messages: false,
    message_mode: 'all',
    show_read_status: true,
    auto_reply_enabled: false,
    auto_reply_text: ''
  })

  // 可发现性设置（防用户枚举）
  const discoverability = ref({
    discoverable_by_username: false,
    discoverable_by_email: false,
    search_code: ''
  })
  const regeneratingCode = ref(false)

  // 屏蔽列表
  const blockedUsers = ref([])
  const loadingBlocked = ref(false)

  const loadGroupPolicy = async () => {
    loadingGroupPolicy.value = true
    try {
      const res = await fetch('/api/messages/groups/policy/', {
        headers: { 'X-CSRFToken': csrfToken },
        cache: 'no-store'
      })
      if (res.ok) {
        const data = await res.json()
        if (data.status === 'success') {
          groupPolicy.value = data.policy || null
        }
      }
    } catch (e) {
      console.error('加载群组创建策略失败:', e)
    } finally {
      loadingGroupPolicy.value = false
    }
  }

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
        body: JSON.stringify({
          allow_messages: privacy.value.allow_messages,
          message_mode: privacy.value.message_mode,
          show_read_status: privacy.value.show_read_status,
          auto_reply_enabled: privacy.value.auto_reply_enabled,
          auto_reply_text: privacy.value.auto_reply_text
        })
      })
      const data = await res.json()
      if (res.ok && data.status === 'success') {
        ElMessage.success('私信设置已保存')
      } else {
        ElMessage.error(data.message || data.error || '保存失败')
      }
    } catch (e) {
      ElMessage.error('保存失败，请重试')
    } finally {
      saving.value = false
    }
  }

  /**
   * 加载账户可发现性设置
   */
  const loadDiscoverability = async () => {
    try {
      const res = await fetch('/api/users/discoverability/', {
        headers: { 'X-CSRFToken': csrfToken }
      })
      if (res.ok) {
        const data = await res.json()
        if (data.status === 'success') {
          discoverability.value = {
            discoverable_by_username: !!data.discoverable_by_username,
            discoverable_by_email: !!data.discoverable_by_email,
            search_code: data.search_code || ''
          }
        }
      }
    } catch (e) {
      console.error('加载可发现性设置失败:', e)
    }
  }

  /**
   * 保存账户可发现性开关
   */
  const saveDiscoverability = async () => {
    try {
      const res = await fetch('/api/users/discoverability/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
          discoverable_by_username: discoverability.value.discoverable_by_username,
          discoverable_by_email: discoverability.value.discoverable_by_email
        })
      })
      const data = await res.json()
      if (res.ok && data.status === 'success') {
        ElMessage.success('可发现性已更新')
      } else {
        ElMessage.error(data.message || data.error || '保存失败')
      }
    } catch (e) {
      ElMessage.error('保存失败，请重试')
    }
  }

  /**
   * 生成新的搜索码
   */
  const regenerateSearchCode = async () => {
    regeneratingCode.value = true
    try {
      const res = await fetch('/api/users/discoverability/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({ regenerate_code: true })
      })
      const data = await res.json()
      if (res.ok && data.status === 'success') {
        discoverability.value.search_code = data.search_code || ''
        ElMessage.success('已生成新的搜索码')
      } else {
        ElMessage.error(data.message || data.error || '生成失败')
      }
    } catch (e) {
      ElMessage.error('生成失败，请重试')
    } finally {
      regeneratingCode.value = false
    }
  }

  /**
   * 复制搜索码到剪贴板
   */
  const copySearchCode = async () => {
    const code = discoverability.value.search_code
    if (!code) return
    try {
      await navigator.clipboard.writeText(code)
      ElMessage.success('搜索码已复制到剪贴板')
    } catch (e) {
      // 回退方案
      const ta = document.createElement('textarea')
      ta.value = code
      document.body.appendChild(ta)
      ta.select()
      try {
        document.execCommand('copy')
        ElMessage.success('搜索码已复制')
      } catch {
        ElMessage.error('复制失败，请手动选择并复制')
      }
      document.body.removeChild(ta)
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
        ElMessage.error(data.message || data.error || '操作失败')
      }
    } catch (e) {
      ElMessage.error('操作失败，请重试')
    }
  }

  onMounted(() => {
    loadPreference()
    loadBlockedUsers()
    loadDiscoverability()
    loadGroupPolicy()
  })

  return {
    loading,
    saving,
    groupPolicy,
    loadingGroupPolicy,
    privacy,
    discoverability,
    regeneratingCode,
    blockedUsers,
    loadingBlocked,
    savePreference,
    saveDiscoverability,
    regenerateSearchCode,
    copySearchCode,
    unblockUser
  }
}
