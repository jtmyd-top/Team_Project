<template>
  <div class="db-card">
    <div class="db-card-title"><i class="fas fa-clipboard-list"></i> 敏感操作审计</div>
    <template v-if="store.auditLog">
      <!-- 操作统计 -->
      <div class="audit-summary">
        <div class="audit-summary-item">
          <span class="audit-num" style="color: var(--db-green);">{{ store.auditLog.summary.add }}</span>
          <span class="audit-label">新增</span>
        </div>
        <div class="audit-summary-item">
          <span class="audit-num" style="color: var(--db-yellow);">{{ store.auditLog.summary.change }}</span>
          <span class="audit-label">修改</span>
        </div>
        <div class="audit-summary-item">
          <span class="audit-num" style="color: var(--db-red);">{{ store.auditLog.summary.delete }}</span>
          <span class="audit-label">删除</span>
        </div>
      </div>

      <!-- 操作流 -->
      <div class="audit-stream" v-if="store.auditLog.logs.length > 0">
        <div
          v-for="(log, idx) in store.auditLog.logs.slice(0, 15)"
          :key="idx"
          class="audit-item"
        >
          <span class="audit-action-icon" :class="actionClass(log.action_flag)">
            <i :class="actionIcon(log.action_flag)"></i>
          </span>
          <div style="flex: 1; min-width: 0;">
            <div class="audit-item-title">
              <strong>{{ log.user }}</strong>
              <span class="audit-action-tag" :class="actionClass(log.action_flag)">
                {{ log.action }}
              </span>
              <span class="audit-target">{{ log.target }}</span>
            </div>
            <div class="audit-item-meta">
              {{ log.model }} · {{ formatTime(log.time) }}
            </div>
          </div>
        </div>
      </div>
      <div v-else class="alert-empty" style="padding: 20px 0;">
        <i class="fas fa-check-circle"></i> 近 7 天无敏感操作
      </div>
    </template>
    <div v-else class="alert-empty">
      <i class="fas fa-spinner fa-spin"></i> 加载中...
    </div>
  </div>
</template>

<script setup>
import { useDashboardStore } from '@stores/dashboard.js'

const store = useDashboardStore()

function actionClass(flag) {
  if (flag === 1) return 'action--add'
  if (flag === 2) return 'action--change'
  if (flag === 3) return 'action--delete'
  return ''
}

function actionIcon(flag) {
  if (flag === 1) return 'fas fa-plus'
  if (flag === 2) return 'fas fa-pen'
  if (flag === 3) return 'fas fa-trash'
  return 'fas fa-question'
}

function formatTime(iso) {
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', {
    month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}
</script>
