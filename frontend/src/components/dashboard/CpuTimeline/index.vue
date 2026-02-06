<template>
  <div class="db-card">
    <div class="db-card-title"><i class="fas fa-chart-line"></i> CPU 趋势</div>
    <div class="gauge-wrap" ref="chartRef" style="min-height: 180px;"></div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { useDashboardStore } from '@stores/dashboard.js'

echarts.use([LineChart, GridComponent, TooltipComponent, CanvasRenderer])

const store = useDashboardStore()
const chartRef = ref(null)
let chart = null

function handleResize() { chart?.resize() }

function getOption(history) {
  return {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(10,14,39,0.9)',
      borderColor: 'rgba(0,240,255,0.2)',
      textStyle: { color: '#e0e6ff', fontSize: 12 },
    },
    grid: { top: 10, right: 16, bottom: 24, left: 40 },
    xAxis: {
      type: 'category',
      data: history.map(h => h.time),
      axisLine: { lineStyle: { color: 'rgba(0,240,255,0.15)' } },
      axisLabel: { color: '#7a82a6', fontSize: 10 },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value', min: 0, max: 100,
      axisLine: { show: false },
      splitLine: { lineStyle: { color: 'rgba(0,240,255,0.06)' } },
      axisLabel: { color: '#7a82a6', fontSize: 10, formatter: '{value}%' },
    },
    series: [{
      type: 'line',
      data: history.map(h => h.value),
      smooth: true,
      symbol: 'none',
      lineStyle: { color: '#00f0ff', width: 2 },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(0,240,255,0.25)' },
          { offset: 1, color: 'rgba(0,240,255,0)' },
        ]),
      },
    }],
  }
}

onMounted(() => {
  chart = echarts.init(chartRef.value)
  chart.setOption(getOption([]))
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
})

watch(() => store.cpuHistory, (history) => {
  if (chart) chart.setOption(getOption(history))
}, { deep: true })
</script>
