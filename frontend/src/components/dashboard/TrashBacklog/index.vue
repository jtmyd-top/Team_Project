<template>
  <div class="db-card">
    <div class="db-card-title"><i class="fas fa-trash-alt"></i> 回收站积压</div>
    <template v-if="store.trashBacklog">
      <div class="trash-stats">
        <div class="trash-stat-item">
          <span class="trash-stat-num" :class="{ 'text-warn': store.trashBacklog.total_trashed > 20 }">
            {{ store.trashBacklog.total_trashed }}
          </span>
          <span class="trash-stat-label">待清理项</span>
        </div>
        <div class="trash-stat-item">
          <span class="trash-stat-num text-danger" v-if="store.trashBacklog.total_stale > 0">
            {{ store.trashBacklog.total_stale }}
          </span>
          <span class="trash-stat-num" v-else>0</span>
          <span class="trash-stat-label">超30天未清理</span>
        </div>
      </div>
      <div class="trash-detail">
        <span><i class="fas fa-sticky-note"></i> 笔记 {{ store.trashBacklog.trashed_notes }}</span>
        <span><i class="fas fa-folder"></i> 文件夹 {{ store.trashBacklog.trashed_folders }}</span>
      </div>
      <div v-if="store.trashBacklog.total_stale > 0" class="trash-warning">
        <i class="fas fa-exclamation-circle"></i>
        {{ store.trashBacklog.total_stale }} 项已超过 30 天，建议尽快清理
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
</script>
