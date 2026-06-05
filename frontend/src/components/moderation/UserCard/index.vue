<template>
  <div v-if="user" class="uc">
    <div class="uc-head">
      <img :src="user.avatar || '/static/img/default-avatar.png'" :alt="user.username" class="uc-avatar" />
      <div class="uc-info">
        <div class="uc-name">
          {{ user.username }}
          <el-tag v-if="!user.is_active" size="small" type="danger" effect="dark">已停用</el-tag>
        </div>
        <div class="uc-bio">{{ user.bio || '（无简介）' }}</div>
      </div>
    </div>

    <div class="uc-stats">
      <span title="公开笔记数"><i class="fas fa-file-alt"></i> {{ user.notes_count }}</span>
      <span title="发起的举报数"><i class="fas fa-flag"></i> 发起 {{ user.reports_filed }}</span>
      <span title="被举报次数"><i class="fas fa-exclamation-triangle"></i> 被举报 {{ user.reports_received }}</span>
    </div>
    <div class="uc-meta">
      <span v-if="user.email">{{ user.email }}</span>
      <span v-if="user.date_joined">注册于 {{ formatDate(user.date_joined) }}</span>
    </div>

    <div class="uc-sanctions">
      <div v-if="!user.active_sanctions || user.active_sanctions.length === 0" class="uc-clean">
        <i class="fas fa-check-circle"></i> 当前无生效制裁
      </div>
      <div v-else>
        <div v-for="s in user.active_sanctions" :key="s.id" class="uc-sanction">
          <el-tag size="small" :type="s.type === 'ban_login' ? 'danger' : 'warning'">
            {{ s.type_display }}
          </el-tag>
          <span class="uc-sanction-exp">
            {{ s.is_permanent ? '永久' : ('至 ' + formatTime(s.expires_at)) }}
          </span>
          <el-button size="small" text type="primary" @click="$emit('revoke', s.id)">解除</el-button>
        </div>
      </div>
    </div>

    <a :href="`/user/${user.id}/`" target="_blank" class="uc-profile-link">
      <i class="fas fa-external-link-alt"></i> 在新标签页打开主页
    </a>
  </div>
  <div v-else class="uc-empty">用户信息缺失</div>
</template>

<script setup>
defineProps({ user: { type: Object, default: null } })
defineEmits(['revoke'])

function formatTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('zh-CN', { hour12: false })
}
function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('zh-CN')
}
</script>

<style scoped>
.uc-head { display: flex; gap: 10px; align-items: center; }
.uc-avatar { width: 44px; height: 44px; border-radius: 50%; object-fit: cover; flex-shrink: 0; }
.uc-name { font-weight: 600; color: #303133; display: flex; align-items: center; gap: 6px; }
.uc-bio { font-size: 12px; color: #909399; overflow: hidden; text-overflow: ellipsis; }
.uc-stats { display: flex; gap: 14px; font-size: 12px; color: #606266; margin: 10px 0 6px; flex-wrap: wrap; }
.uc-meta { font-size: 12px; color: #c0c4cc; display: flex; flex-direction: column; gap: 2px; margin-bottom: 8px; }
.uc-sanctions { border-top: 1px dashed #ebeef5; padding-top: 8px; }
.uc-clean { font-size: 13px; color: #67c23a; }
.uc-sanction { display: flex; align-items: center; gap: 8px; margin: 4px 0; }
.uc-sanction-exp { font-size: 12px; color: #909399; margin-right: auto; }
.uc-profile-link { display: inline-block; margin-top: 8px; font-size: 12px; color: #409eff; text-decoration: none; }
.uc-empty { color: #909399; font-size: 13px; }
</style>
