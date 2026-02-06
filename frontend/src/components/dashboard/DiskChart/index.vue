<template>
  <div class="db-card">
    <div class="db-card-title"><i class="fas fa-hdd"></i> 磁盘占用</div>
    <div class="gauge-wrap" ref="chartRef"></div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts/core'
import { PieChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { useDashboardStore } from '@stores/dashboard.js'

echarts.use([PieChart, TooltipComponent, LegendComponent, CanvasRenderer])

const store = useDashboardStore()
const chartRef = ref(null)
let chart = null

function handleResize() { chart?.resize() }

function formatBytes(bytes) {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return (bytes / Math.pow(k, i)).toFixed(1) + ' ' + sizes[i]
}

function getOption(hb) {
  const used = hb.disk_used
  const free = hb.disk_total - hb.disk_used
  return {
    tooltip: {
      trigger: 'item',
      formatter: (p) => `${p.name}: ${formatBytes(p.value)}`,
      backgroundColor: 'rgba(10,14,39,0.9)',
      borderColor: 'rgba(0,240,255,0.2)',
      textStyle: { color: '#e0e6ff' },
    },
    series: [{
      type: 'pie',
      radius: ['50%', '75%'],
      center: ['50%', '50%'],
      avoidLabelOverlap: false,
      itemStyle: { borderRadius: 6, borderColor: '#0a0e27', borderWidth: 2 },
      label: {
        show: true, position: 'center',
        formatter: `${hb.disk_percent}%`,
        fontSize: 24, fontWeight: 700,
        color: hb.disk_percent > 85 ? '#ff4d4f' : '#00f0ff',
      },
      data: [
        { value: used, name: '已用', itemStyle: { color: '#00f0ff' } },
        { value: free, name: '可用', itemStyle: { color: 'rgba(0,240,255,0.12)' } },
      ],
    }],
  }
}

onMounted(() => {
  chart = echarts.init(chartRef.value)
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
})

watch(() => store.heartbeat, (hb) => {
  if (hb && chart) chart.setOption(getOption(hb))
}, { deep: true })
</script>
