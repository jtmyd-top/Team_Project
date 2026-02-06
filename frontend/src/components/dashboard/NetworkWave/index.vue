<template>
  <div class="db-card">
    <div class="db-card-title"><i class="fas fa-network-wired"></i> 网络流量</div>
    <div class="gauge-wrap" ref="chartRef" style="min-height: 200px;"></div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { useDashboardStore } from '@stores/dashboard.js'

echarts.use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const store = useDashboardStore()
const chartRef = ref(null)
let chart = null

function handleResize() { chart?.resize() }

function getOption(sent, recv) {
  return {
    animation: false,
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(10,14,39,0.9)',
      borderColor: 'rgba(0,240,255,0.2)',
      textStyle: { color: '#e0e6ff', fontSize: 12 },
      formatter(params) {
        let s = params[0]?.axisValue + '<br/>'
        params.forEach(p => {
          s += `${p.marker} ${p.seriesName}: ${p.value.toFixed(1)} KB/s<br/>`
        })
        return s
      },
    },
    legend: {
      data: ['上传', '下载'],
      textStyle: { color: '#7a82a6', fontSize: 11 },
      top: 0, right: 0,
    },
    grid: { top: 30, right: 16, bottom: 24, left: 50 },
    xAxis: {
      type: 'category',
      data: recv.map(h => h.time),
      axisLine: { lineStyle: { color: 'rgba(0,240,255,0.15)' } },
      axisLabel: { color: '#7a82a6', fontSize: 10 },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value', min: 0,
      axisLine: { show: false },
      splitLine: { lineStyle: { color: 'rgba(0,240,255,0.06)' } },
      axisLabel: { color: '#7a82a6', fontSize: 10, formatter: '{value} KB/s' },
    },
    series: [
      {
        name: '下载',
        type: 'line',
        data: recv.map(h => h.value),
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#00f0ff', width: 2 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(0,240,255,0.2)' },
            { offset: 1, color: 'rgba(0,240,255,0)' },
          ]),
        },
      },
      {
        name: '上传',
        type: 'line',
        data: sent.map(h => h.value),
        smooth: true,
        symbol: 'none',
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
  chart.setOption(getOption([], []))
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
})

watch(
  () => [store.netSentHistory, store.netRecvHistory],
  ([sent, recv]) => {
    if (chart) chart.setOption(getOption(sent, recv))
  },
  { deep: true }
)
</script>
