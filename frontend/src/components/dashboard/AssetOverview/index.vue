<template>
  <div class="db-card">
    <div class="db-card-title"><i class="fas fa-cubes"></i> 知识资产概览</div>
    <div class="asset-grid" v-if="store.assets">
      <StatCard :value="store.assets.total_notes" label="笔记总数" icon="fas fa-sticky-note" color="cyan" href="/admin/knowledge_project/note/" />
      <StatCard :value="store.assets.total_folders" label="文件夹" icon="fas fa-folder" color="yellow" href="/admin/knowledge_project/folder/" />
      <StatCard :value="store.assets.total_assets" label="附件资源" icon="fas fa-paperclip" color="green" href="/admin/knowledge_project/asset/" />
      <StatCard :value="store.assets.total_users" label="活跃用户" icon="fas fa-users" color="cyan" href="/admin/auth/user/" />
      <StatCard :value="store.assets.public_notes" label="公开笔记" icon="fas fa-globe" color="green" href="/admin/knowledge_project/note/?is_public__exact=1" />
      <StatCard :value="store.assets.secret_notes" label="保密笔记" icon="fas fa-lock" color="red" href="/admin/knowledge_project/note/?is_secret__exact=1" />
    </div>
    <div v-else class="alert-empty">
      <i class="fas fa-spinner fa-spin"></i>
      加载中...
    </div>
  </div>
</template>

<script setup>
import { useDashboardStore } from '@stores/dashboard.js'
import StatCard from '../StatCard/index.vue'

const store = useDashboardStore()
</script>
