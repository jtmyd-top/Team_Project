<template>
  <div class="db-card">
    <div class="db-card-title"><i class="fas fa-chart-bar"></i> 7天笔记趋势</div>
    <div class="gauge-wrap" ref="chartRef" style="min-height: 220px;"></div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { useDashboardStore } from '@stores/dashboard.js'

echarts.use([BarChart, GridComponent, TooltipComponent, CanvasRenderer])

const store = useDashboardStore()
const chartRef = ref(null)
let chart = null

function handleResize() { chart?.resize() }

function getOption(trend) {
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
      data: trend.map(t => t.date),
      axisLine: { lineStyle: { color: 'rgba(0,240,255,0.15)' } },
      axisLabel: { color: '#7a82a6', fontSize: 11 },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLine: { show: false },
      splitLine: { lineStyle: { color: 'rgba(0,240,255,0.06)' } },
      axisLabel: { color: '#7a82a6', fontSize: 10 },
    },
    series: [{
      type: 'bar',
      data: trend.map(t => t.count),
      barWidth: '50%',
      itemStyle: {
        borderRadius: [4, 4, 0, 0],
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#00f0ff' },
          { offset: 1, color: 'rgba(0,240,255,0.2)' },
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

watch(() => store.assets?.notes_trend, (trend) => {
  if (trend && chart) chart.setOption(getOption(trend))
}, { deep: true })
</script>
