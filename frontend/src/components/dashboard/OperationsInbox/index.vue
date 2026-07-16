<template>
  <section class="db-card operations-inbox">
    <div class="db-card__header">
      <div>
        <span class="db-card__eyebrow">ACTION QUEUE</span>
        <h3>运营待办</h3>
      </div>
      <strong>{{ items.length }}</strong>
    </div>
    <div v-if="items.length" class="operations-inbox__list">
      <a
        v-for="item in items"
        :key="`${item.title}-${item.detail}`"
        :href="item.href || '#'"
        class="operations-inbox__item"
        :class="`is-${item.level}`"
      >
        <i :class="iconFor(item.level)"></i>
        <span>
          <strong>{{ item.title }}</strong>
          <small>{{ item.detail }}</small>
        </span>
        <i v-if="item.href" class="fas fa-chevron-right"></i>
      </a>
    </div>
    <div v-else class="operations-inbox__empty">
      <i class="fas fa-circle-check"></i>
      暂无需要管理员处理的事项
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useDashboardStore } from '@stores/dashboard.js'

const store = useDashboardStore()
const items = computed(() => store.actionItems || [])

function iconFor(level) {
  if (level === 'critical') return 'fas fa-circle-exclamation'
  if (level === 'warning') return 'fas fa-triangle-exclamation'
  return 'fas fa-circle-info'
}
</script>

<style scoped>
.operations-inbox > .db-card__header > strong {
  color: #f8fafc;
  font-size: 18px;
}

.operations-inbox__list {
  display: grid;
  gap: 8px;
  margin-top: 14px;
}

.operations-inbox__item {
  display: grid;
  grid-template-columns: 16px minmax(0, 1fr) 10px;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid rgba(148, 163, 184, .14);
  color: #cbd5e1;
  text-decoration: none;
}

.operations-inbox__item:last-child {
  border-bottom: 0;
}

.operations-inbox__item span {
  min-width: 0;
}

.operations-inbox__item strong,
.operations-inbox__item small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.operations-inbox__item strong {
  color: #f8fafc;
  font-size: 12px;
}

.operations-inbox__item small {
  margin-top: 2px;
  color: var(--db-text-muted, #8691a8);
  font-size: 10px;
}

.operations-inbox__item.is-critical > i:first-child { color: #fb7185; }
.operations-inbox__item.is-warning > i:first-child { color: #fbbf24; }
.operations-inbox__item.is-info > i:first-child { color: #38bdf8; }
.operations-inbox__item > i:last-child { color: #64748b; font-size: 9px; }

.operations-inbox__empty {
  margin-top: 16px;
  color: var(--db-text-muted, #8691a8);
  font-size: 12px;
}

.operations-inbox__empty i {
  margin-right: 6px;
  color: #4ade80;
}
</style>
