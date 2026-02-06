<template>
  <div class="db-card">
    <div class="db-card-title">
      <i class="fas fa-chart-area"></i> 内容增长趋势
      <div class="trend-toggle">
        <button
          :class="{ active: range === 7 }"
          @click="range = 7"
        >7天</button>
        <button
          :class="{ active: range === 30 }"
          @click="range = 30"
        >30天</button>
      </div>
    </div>
    <div class="gauge-wrap" ref="chartRef" style="min-height: 240px;"></div>
  </div>
</template>

<script setup>
import { ref, watch, computed, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { useDashboardStore } from '@stores/dashboard.js'

echarts.use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const store = useDashboardStore()
const chartRef = ref(null)
const range = ref(7)
let chart = null

function handleResize() { chart?.resize() }

const chartData = computed(() => {
  if (!store.contentTrend) return null
  const created = store.contentTrend.created
  const modified = store.contentTrend.modified
  if (range.value === 7) {
    return { created: created.slice(-7), modified: modified.slice(-7) }
  }
  return { created, modified }
})

function getOption(data) {
  if (!data) return {}
  return {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(10,14,39,0.9)',
      borderColor: 'rgba(0,240,255,0.2)',
      textStyle: { color: '#e0e6ff', fontSize: 12 },
    },
    legend: {
      data: ['新增', '修改'],
      textStyle: { color: '#7a82a6', fontSize: 11 },
      top: 0, right: 0,
    },
    grid: { top: 30, right: 16, bottom: 24, left: 40 },
    xAxis: {
      type: 'category',
      data: data.created.map(d => d.date),
      axisLine: { lineStyle: { color: 'rgba(0,240,255,0.15)' } },
      axisLabel: { color: '#7a82a6', fontSize: 10, interval: range.value > 7 ? 3 : 0 },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value', minInterval: 1,
      axisLine: { show: false },
      splitLine: { lineStyle: { color: 'rgba(0,240,255,0.06)' } },
      axisLabel: { color: '#7a82a6', fontSize: 10 },
    },
    series: [
      {
        name: '新增', type: 'line',
        data: data.created.map(d => d.count),
        smooth: true, symbol: 'none',
        lineStyle: { color: '#00f0ff', width: 2 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(0,240,255,0.2)' },
            { offset: 1, color: 'rgba(0,240,255,0)' },
          ]),
        },
      },
      {
        name: '修改', type: 'line',
        data: data.modified.map(d => d.count),
        smooth: true, symbol: 'none',
        lineStyle: { color: '#a78bfa', width: 2 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(167,139,250,0.2)' },
            { offset: 1, color: 'rgba(167,139,250,0)' },
          ]),
        },
      },
    ],
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

watch(chartData, (data) => {
  if (data && chart) chart.setOption(getOption(data), true)
}, { deep: true })

watch(range, () => {
  if (chartData.value && chart) chart.setOption(getOption(chartData.value), true)
})
</script>
