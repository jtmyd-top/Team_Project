<template>
  <div class="db-card middleware-status">
    <div class="db-card-title"><i class="fas fa-server"></i> 中间件状态</div>
    <div class="middleware-grid">
      <div
        v-for="(info, name) in services"
        :key="name"
        class="middleware-item"
        :class="'middleware--' + info.status"
      >
        <span class="middleware-dot" :class="'dot--' + info.status"></span>
        <span class="middleware-name">{{ nameMap[name] || name }}</span>
        <span class="middleware-label">{{ info.status === 'ok' ? '正常' : '异常' }}</span>
        <span v-if="info.used_memory_human" class="middleware-detail">
          {{ info.used_memory_human }}
        </span>
      </div>
      <div v-if="!services || Object.keys(services).length === 0" class="middleware-empty">
        <i class="fas fa-spinner fa-spin"></i> 加载中...
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useDashboardStore } from '@stores/dashboard.js'

const store = useDashboardStore()

const nameMap = {
  redis: 'Redis',
  database: 'Database',
  celery: 'Celery',
  nginx: 'Nginx',
}

const services = computed(() => store.serviceHealth || {})
</script>
