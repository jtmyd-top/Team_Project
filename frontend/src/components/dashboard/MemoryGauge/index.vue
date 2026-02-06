<template>
  <div class="db-card">
    <div class="db-card-title"><i class="fas fa-memory"></i> 内存使用率</div>
    <div class="gauge-wrap" ref="chartRef"></div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts/core'
import { GaugeChart } from 'echarts/charts'
import { CanvasRenderer } from 'echarts/renderers'
import { useDashboardStore } from '@stores/dashboard.js'

echarts.use([GaugeChart, CanvasRenderer])

const store = useDashboardStore()
const chartRef = ref(null)
let chart = null

function handleResize() { chart?.resize() }

function getOption(value) {
  const color = value > 85 ? '#ff4d4f' : value > 70 ? '#faad14' : '#a78bfa'
  return {
    series: [{
      type: 'gauge',
      startAngle: 220,
      endAngle: -40,
      radius: '90%',
      progress: { show: true, width: 14, itemStyle: { color } },
      axisLine: { lineStyle: { width: 14, color: [[1, 'rgba(167,139,250,0.1)']] } },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: { show: false },
      pointer: { show: false },
      title: { show: false },
      detail: {
        fontSize: 28, fontWeight: 700, color,
        offsetCenter: [0, '10%'],
        formatter: '{value}%',
      },
      data: [{ value }],
    }],
  }
}

onMounted(() => {
  chart = echarts.init(chartRef.value)
  chart.setOption(getOption(0))
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
})

watch(() => store.heartbeat?.memory_percent, (val) => {
  if (val !== undefined && chart) chart.setOption(getOption(val))
})
</script>
