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
      <span title="公开笔记数"><i class="fas fa-file-alt"></i><b>{{ user.notes_count }}</b><em>笔记</em></span>
      <span title="发起的举报数"><i class="fas fa-flag"></i><b>{{ user.reports_filed }}</b><em>发起</em></span>
      <span title="被举报次数"><i class="fas fa-exclamation-triangle"></i><b>{{ user.reports_received }}</b><em>被举报</em></span>
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
          <span v-if="s.pending_appeal" class="uc-appeal">有待处理申诉</span>
          <el-button size="small" text type="primary" @click="$emit('revoke', s.id)">解除</el-button>
        </div>
      </div>
    </div>

    <div class="uc-actions">
      <el-button
        v-if="!user.active_sanctions || user.active_sanctions.length === 0"
        size="small"
        type="warning"
        plain
        @click="$emit('sanction', user)"
      >
        <i class="fas fa-gavel"></i> 重新处置
      </el-button>
      <a :href="`/user/${user.id}/`" target="_blank" class="uc-profile-link">
        <i class="fas fa-external-link-alt"></i> 在新标签页打开主页
      </a>
    </div>
  </div>
  <div v-else class="uc-empty">用户信息缺失</div>
</template>

<script setup>
defineProps({ user: { type: Object, default: null } })
defineEmits(['revoke', 'sanction'])

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
.uc {
  color: #1e293b;
}

.uc-head {
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr);
  gap: 10px;
  align-items: center;
}

.uc-avatar {
  width: 44px;
  height: 44px;
  border-radius: 8px;
  object-fit: cover;
  background: #eff6ff;
  border: 1px solid #dbeafe;
}

.uc-info {
  min-width: 0;
}

.uc-name {
  display: flex;
  align-items: center;
  gap: 7px;
  color: #111827;
  font-size: 14px;
  font-weight: 800;
}

.uc-bio {
  margin-top: 3px;
  color: #64748b;
  font-size: 12px;
  line-height: 1.45;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.uc-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1px;
  margin: 14px 0 10px;
  overflow: hidden;
  border: 1px solid #e5ebf3;
  border-radius: 8px;
  background: #e5ebf3;
}

.uc-stats span {
  min-width: 0;
  padding: 9px 6px;
  background: #f8fafc;
  color: #64748b;
  font-size: 12px;
  display: grid;
  grid-template-columns: auto auto minmax(0, auto);
  align-items: center;
  justify-content: center;
  gap: 5px;
}

.uc-stats i {
  color: #2563eb;
}

.uc-stats b {
  color: #111827;
  font-size: 13px;
}

.uc-stats em {
  min-width: 0;
  font-style: normal;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.uc-meta {
  display: flex;
  flex-direction: column;
  gap: 3px;
  margin-bottom: 10px;
  color: #64748b;
  font-size: 12px;
}

.uc-sanctions {
  padding-top: 10px;
  border-top: 1px solid #eef2f7;
}

.uc-clean {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 9px;
  border-radius: 8px;
  color: #047857;
  background: #ecfdf5;
  border: 1px solid #bbf7d0;
  font-size: 12px;
}

.uc-sanction {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 6px 0;
  padding: 8px;
  border-radius: 8px;
  background: #fff7ed;
  border: 1px solid #fed7aa;
}

.uc-sanction-exp {
  margin-right: auto;
  color: #64748b;
  font-size: 12px;
}

.uc-appeal {
  color: #b45309;
  background: #fef3c7;
  border: 1px solid #fde68a;
  border-radius: 999px;
  padding: 2px 7px;
  font-size: 12px;
  white-space: nowrap;
}

.uc-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.uc-profile-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 9px;
  border-radius: 8px;
  color: #2563eb;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  font-size: 12px;
  font-weight: 700;
  text-decoration: none;
  transition: background 0.18s ease, border-color 0.18s ease;
}

.uc-profile-link:hover {
  background: #dbeafe;
  border-color: #93c5fd;
}

.uc-empty {
  color: #94a3b8;
  font-size: 13px;
}

@media (max-width: 520px) {
  .uc-stats {
    grid-template-columns: 1fr;
  }
}
</style>
