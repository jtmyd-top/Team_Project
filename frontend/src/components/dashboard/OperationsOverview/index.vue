<template>
  <section class="db-card operations-overview">
    <div class="db-card__header">
      <div>
        <span class="db-card__eyebrow">COLLABORATION</span>
        <h3>运营概览</h3>
      </div>
      <a class="operations-overview__link" href="/admin/moderation/messagereport/" title="打开待处理举报">
        <i class="fas fa-arrow-up-right-from-square"></i>
      </a>
    </div>

    <div v-if="operations" class="operations-overview__metrics">
      <div class="operations-metric">
        <span>活跃群组</span>
        <strong>{{ operations.active_groups }}</strong>
      </div>
      <div class="operations-metric">
        <span>近 7 天消息</span>
        <strong>{{ operations.messages_7d }}</strong>
        <small>私信 {{ operations.direct_messages_7d }} / 群聊 {{ operations.group_messages_7d }}</small>
      </div>
      <div class="operations-metric">
        <span>新增用户</span>
        <strong>{{ operations.new_users_7d }}</strong>
      </div>
      <div class="operations-metric operations-metric--attention">
        <span>待处理事项</span>
        <strong>{{ pendingTotal }}</strong>
        <small>举报 {{ operations.pending_reports }} / 入群 {{ operations.pending_join_requests }}</small>
      </div>
    </div>
    <div v-else class="alert-empty">
      <i class="fas fa-spinner fa-spin"></i>
      加载中...
    </div>

    <div v-if="operations?.activity_trend?.length" class="operations-overview__trend" aria-label="近七日协作趋势">
      <div
        v-for="item in operations.activity_trend"
        :key="item.date"
        class="operations-trend__day"
        :title="`${item.date}: 私信 ${item.direct}，群聊 ${item.group}，新增用户 ${item.users}`"
      >
        <div class="operations-trend__bars">
          <span class="operations-trend__bar operations-trend__bar--direct" :style="{ height: `${barHeight(item.direct)}%` }"></span>
          <span class="operations-trend__bar operations-trend__bar--group" :style="{ height: `${barHeight(item.group)}%` }"></span>
        </div>
        <small>{{ item.date }}</small>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useDashboardStore } from '@stores/dashboard.js'

const store = useDashboardStore()
const operations = computed(() => store.operations)
const pendingTotal = computed(() => {
  const value = operations.value
  return (value?.pending_reports || 0) + (value?.pending_join_requests || 0)
})
const trendMaximum = computed(() => Math.max(
  1,
  ...(operations.value?.activity_trend || []).flatMap(item => [item.direct, item.group]),
))

function barHeight(value) {
  return Math.max(8, Math.round((Number(value || 0) / trendMaximum.value) * 100))
}
</script>

<style scoped>
.operations-overview__link {
  color: var(--db-text-muted, #8691a8);
  font-size: 13px;
}

.operations-overview__metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.operations-metric {
  min-width: 0;
  padding: 10px;
  border: 1px solid rgba(148, 163, 184, .18);
  background: rgba(15, 23, 42, .24);
}

.operations-metric span,
.operations-metric small {
  display: block;
  color: var(--db-text-muted, #8691a8);
  font-size: 11px;
}

.operations-metric strong {
  display: block;
  margin: 4px 0;
  color: #f8fafc;
  font-size: 20px;
  line-height: 1.1;
}

.operations-metric--attention strong {
  color: #fbbf24;
}

.operations-overview__trend {
  display: flex;
  align-items: end;
  gap: 7px;
  height: 86px;
  margin-top: 16px;
}

.operations-trend__day {
  display: grid;
  flex: 1;
  min-width: 0;
  grid-template-rows: 62px auto;
  gap: 4px;
  text-align: center;
}

.operations-trend__bars {
  display: flex;
  align-items: end;
  justify-content: center;
  gap: 3px;
  height: 62px;
}

.operations-trend__bar {
  width: min(9px, 30%);
  min-height: 5px;
}

.operations-trend__bar--direct {
  background: #38bdf8;
}

.operations-trend__bar--group {
  background: #a3e635;
}

.operations-trend__day small {
  overflow: hidden;
  color: var(--db-text-muted, #8691a8);
  font-size: 9px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
