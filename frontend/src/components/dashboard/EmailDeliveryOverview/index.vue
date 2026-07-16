<template>
  <section id="email-delivery-overview" class="db-card email-delivery-overview">
    <div class="db-card__header">
      <div>
        <span class="db-card__eyebrow">EMAIL DELIVERY</span>
        <h3>邮件投递</h3>
      </div>
      <strong :class="rateClass">{{ rateText }}</strong>
    </div>

    <div v-if="metrics" class="email-delivery-overview__metrics">
      <div>
        <span>近 {{ metrics.window_days }} 天发送</span>
        <strong>{{ metrics.total }}</strong>
      </div>
      <div>
        <span>成功</span>
        <strong class="is-success">{{ metrics.succeeded }}</strong>
      </div>
      <div>
        <span>失败</span>
        <strong :class="{ 'is-failure': metrics.failed }">{{ metrics.failed }}</strong>
      </div>
    </div>

    <div v-if="metrics?.by_category?.length" class="email-delivery-overview__categories">
      <div v-for="item in metrics.by_category.slice(0, 5)" :key="item.category">
        <span>{{ categoryName(item.category) }}</span>
        <small>{{ item.succeeded }}/{{ item.total }}</small>
      </div>
    </div>
    <div v-if="metrics?.recent_failures?.length" class="email-delivery-overview__failure">
      <i class="fas fa-triangle-exclamation"></i>
      最近失败：{{ metrics.recent_failures[0].category }}
    </div>
    <div v-else-if="!metrics" class="alert-empty">
      <i class="fas fa-spinner fa-spin"></i>
      加载中...
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useDashboardStore } from '@stores/dashboard.js'

const store = useDashboardStore()
const metrics = computed(() => store.emailDelivery)
const rateText = computed(() => metrics.value?.success_rate == null ? '暂无数据' : `${metrics.value.success_rate}%`)
const rateClass = computed(() => {
  const rate = metrics.value?.success_rate
  if (rate == null) return {}
  return {
    'is-success': rate >= 98,
    'is-warning': rate < 98 && rate >= 90,
    'is-failure': rate < 90,
  }
})

const categories = {
  registration_code: '注册验证码',
  email_change_code: '邮箱修改验证码',
  password_change_code: '密码修改验证码',
  password_reset: '密码重置',
  login_2fa: '登录验证码',
  admin_login_2fa: '后台登录验证码',
  vault_code: '保密柜验证码',
  verification_code: '其他验证码',
  login_alert: '登录提醒',
  security_alert: '安全提醒',
  notification: '业务通知',
  other: '其他邮件',
}

function categoryName(category) {
  return categories[category] || category
}
</script>

<style scoped>
.email-delivery-overview > .db-card__header > strong {
  font-size: 18px;
}

.email-delivery-overview .is-success { color: #4ade80; }
.email-delivery-overview .is-warning { color: #fbbf24; }
.email-delivery-overview .is-failure { color: #fb7185; }

.email-delivery-overview__metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-top: 14px;
}

.email-delivery-overview__metrics > div {
  padding: 8px;
  border: 1px solid rgba(148, 163, 184, .18);
  background: rgba(15, 23, 42, .24);
}

.email-delivery-overview__metrics span,
.email-delivery-overview__categories span,
.email-delivery-overview__categories small {
  display: block;
  color: var(--db-text-muted, #8691a8);
  font-size: 10px;
}

.email-delivery-overview__metrics strong {
  display: block;
  margin-top: 4px;
  color: #f8fafc;
  font-size: 18px;
}

.email-delivery-overview__categories {
  display: grid;
  gap: 6px;
  margin-top: 12px;
}

.email-delivery-overview__categories > div {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.email-delivery-overview__categories small {
  color: #cbd5e1;
}

.email-delivery-overview__failure {
  margin-top: 12px;
  overflow: hidden;
  color: #fbbf24;
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
