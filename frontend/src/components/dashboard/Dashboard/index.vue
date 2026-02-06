<template>
  <div class="dashboard-root">
    <div class="dashboard-grid">
      <DashboardHeader />

      <!-- 连接断开提示 -->
      <div class="db-error-banner" v-if="!store.connected">
        <i class="fas fa-exclamation-triangle"></i>
        服务器连接已断开，数据可能已过期。
        <span v-if="store.reconnectCountdown > 0">
          {{ store.reconnectCountdown }}s 后自动重连...
        </span>
        <span v-else>正在尝试重连...</span>
      </div>

      <!-- 初始加载骨架屏 -->
      <template v-if="store.loading && !store.heartbeat">
        <div class="dashboard-col-left">
          <div class="db-card db-skeleton"><div class="db-skeleton-pulse" style="height: 200px;"></div></div>
          <div class="db-card db-skeleton"><div class="db-skeleton-pulse" style="height: 200px;"></div></div>
        </div>
        <div class="dashboard-col-center">
          <div class="db-card db-skeleton"><div class="db-skeleton-pulse" style="height: 300px;"></div></div>
        </div>
        <div class="dashboard-col-right">
          <div class="db-card db-skeleton"><div class="db-skeleton-pulse" style="height: 300px;"></div></div>
        </div>
      </template>

      <!-- 正常内容 -->
      <template v-else>
        <!-- 左栏: 服务器状态 + 网络流量 -->
        <div class="dashboard-col-left">
          <div class="gauge-row">
            <CpuGauge />
            <MemoryGauge />
          </div>
          <DiskChart />
          <CpuTimeline />
          <NetworkWave />
        </div>

        <!-- 中栏: 业务数据 + 中间件状态 -->
        <div class="dashboard-col-center">
          <AssetOverview />
          <MiddlewareStatus />
          <ContentTrend />
          <TrashBacklog />
        </div>

        <!-- 右栏: 安全态势 + 日志流 -->
        <div class="dashboard-col-right">
          <VaultAlertPanel />
          <LoginMonitor />
          <AuditLog />
          <LogTerminal />
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted } from 'vue'
import { useDashboardStore } from '@stores/dashboard.js'
import '@/assets/styles/components/dashboard.css'

import DashboardHeader from '../DashboardHeader/index.vue'
import CpuGauge from '../CpuGauge/index.vue'
import MemoryGauge from '../MemoryGauge/index.vue'
import DiskChart from '../DiskChart/index.vue'
import CpuTimeline from '../CpuTimeline/index.vue'
import NetworkWave from '../NetworkWave/index.vue'
import AssetOverview from '../AssetOverview/index.vue'
import MiddlewareStatus from '../MiddlewareStatus/index.vue'
import ContentTrend from '../ContentTrend/index.vue'
import TrashBacklog from '../TrashBacklog/index.vue'
import VaultAlertPanel from '../VaultAlertPanel/index.vue'
import LoginMonitor from '../LoginMonitor/index.vue'
import AuditLog from '../AuditLog/index.vue'
import LogTerminal from '../LogTerminal/index.vue'

const store = useDashboardStore()

onMounted(() => { store.startPolling() })
onUnmounted(() => { store.stopPolling() })
</script>
