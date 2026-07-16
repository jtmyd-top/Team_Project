<template>
  <div class="insights-page">
    <header class="insights-header">
      <div>
        <h1><i class="fas fa-chart-line"></i> 数据洞察</h1>
        <p class="subtitle">你的知识创作与协作全景</p>
      </div>
      <div v-if="!loading && !error" class="streak-badges">
        <div class="streak-badge">
          <span class="streak-num">{{ streak.current }}</span>
          <span class="streak-label">当前连续活跃（天）</span>
        </div>
        <div class="streak-badge">
          <span class="streak-num">{{ streak.longest }}</span>
          <span class="streak-label">最长连续（近半年）</span>
        </div>
      </div>
    </header>

    <div v-if="loading" class="insights-state">
      <i class="fas fa-spinner fa-spin"></i> 正在统计数据…
    </div>
    <div v-else-if="error" class="insights-state error">
      <i class="fas fa-triangle-exclamation"></i> {{ error }}
      <button type="button" class="retry-btn" @click="load">重试</button>
    </div>

    <template v-else>
      <!-- 概览卡片 -->
      <section class="stat-grid">
        <div v-for="card in statCards" :key="card.label" class="stat-card">
          <span class="stat-icon" :style="{ background: card.bg, color: card.color }">
            <i :class="card.icon"></i>
          </span>
          <div class="stat-copy">
            <strong>{{ card.value }}</strong>
            <small>{{ card.label }}</small>
          </div>
        </div>
      </section>

      <!-- 活动热力图 -->
      <section class="panel">
        <h2><i class="fas fa-fire"></i> 创作活动热力图 <small>近 26 周 · 按笔记保存次数</small></h2>
        <div class="heatmap-scroll">
          <div class="heatmap-grid">
            <span
              v-for="(cell, i) in heatmapCells"
              :key="i"
              class="heat-cell"
              :class="`level-${cell.level}`"
              :title="cell.title"
            ></span>
          </div>
        </div>
        <div class="heatmap-legend">
          <span>少</span>
          <span v-for="l in 5" :key="l" class="heat-cell" :class="`level-${l - 1}`"></span>
          <span>多</span>
        </div>
      </section>

      <div class="two-col">
        <!-- 文件夹分布 -->
        <section class="panel">
          <h2><i class="fas fa-folder-tree"></i> 笔记文件夹分布</h2>
          <div v-if="!data.folder_distribution.length" class="panel-empty">还没有可统计的笔记</div>
          <div v-else ref="pieRef" class="chart-box"></div>
        </section>

        <!-- 消息趋势 -->
        <section class="panel">
          <h2><i class="fas fa-paper-plane"></i> 私信往来（近 14 天）</h2>
          <div ref="lineRef" class="chart-box"></div>
        </section>
      </div>

      <div class="two-col">
        <!-- 热门笔记 -->
        <section class="panel">
          <h2><i class="fas fa-ranking-star"></i> 热门笔记 Top {{ data.top_notes.length || 5 }}</h2>
          <div v-if="!data.top_notes.length" class="panel-empty">还没有被浏览过的笔记</div>
          <ol v-else class="top-notes">
            <li v-for="(note, i) in data.top_notes" :key="note.id">
              <span class="rank" :class="{ podium: i < 3 }">{{ i + 1 }}</span>
              <a :href="`/knowledge/?note=${note.id}`" class="note-link">{{ note.title }}</a>
              <span v-if="note.is_public" class="public-tag"><i class="fas fa-globe"></i></span>
              <span class="views"><i class="far fa-eye"></i> {{ note.views }}</span>
            </li>
          </ol>
        </section>

        <!-- 常用标签 -->
        <section class="panel">
          <h2><i class="fas fa-tags"></i> 常用标签</h2>
          <div v-if="!data.top_tags.length" class="panel-empty">还没有标签</div>
          <div v-else class="tag-cloud">
            <span
              v-for="tag in data.top_tags"
              :key="tag.name"
              class="tag-chip"
              :style="{ fontSize: tagFontSize(tag.count) }"
            >{{ tag.name }} <em>{{ tag.count }}</em></span>
          </div>
        </section>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as echarts from 'echarts/core'
import { PieChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([PieChart, LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const loading = ref(true)
const error = ref('')
const data = ref({
  summary: {},
  heatmap: [],
  streak: { current: 0, longest: 0 },
  folder_distribution: [],
  top_tags: [],
  top_notes: [],
  message_trend: [],
})

const pieRef = ref(null)
const lineRef = ref(null)
let pieChart = null
let lineChart = null

const isDark = document.documentElement.getAttribute('data-theme') === 'dark'
const textColor = isDark ? '#cbd5e1' : '#475569'

const streak = computed(() => data.value.streak || { current: 0, longest: 0 })

function formatNumber(n) {
  const num = Number(n) || 0
  if (num >= 10000) return (num / 10000).toFixed(1) + ' 万'
  return String(num)
}

const statCards = computed(() => {
  const s = data.value.summary || {}
  return [
    { label: '笔记总数', value: formatNumber(s.note_count), icon: 'fas fa-file-lines', color: '#2563eb', bg: 'rgba(37,99,235,.12)' },
    { label: '公开笔记', value: formatNumber(s.public_count), icon: 'fas fa-globe', color: '#059669', bg: 'rgba(5,150,105,.12)' },
    { label: '收藏笔记', value: formatNumber(s.favorited_count), icon: 'fas fa-star', color: '#d97706', bg: 'rgba(217,119,6,.12)' },
    { label: '保密笔记', value: formatNumber(s.vault_count), icon: 'fas fa-lock', color: '#7c3aed', bg: 'rgba(124,58,237,.12)' },
    { label: '累计浏览', value: formatNumber(s.total_views), icon: 'fas fa-eye', color: '#0891b2', bg: 'rgba(8,145,178,.12)' },
    { label: '内容字符数', value: formatNumber(s.content_chars), icon: 'fas fa-keyboard', color: '#db2777', bg: 'rgba(219,39,119,.12)' },
    { label: '使用标签', value: formatNumber(s.tag_count), icon: 'fas fa-tags', color: '#65a30d', bg: 'rgba(101,163,13,.12)' },
    { label: '30 天消息', value: `${formatNumber(s.messages_sent_30d)} 发 / ${formatNumber(s.messages_received_30d)} 收`, icon: 'fas fa-comments', color: '#dc2626', bg: 'rgba(220,38,38,.12)' },
  ]
})

// ==================== 热力图 ====================
function heatLevel(count) {
  if (!count) return 0
  if (count <= 2) return 1
  if (count <= 5) return 2
  if (count <= 9) return 3
  return 4
}

const heatmapCells = computed(() => {
  const days = data.value.heatmap || []
  if (!days.length) return []
  const cells = []
  // 周一置顶对齐：第一天之前补空位
  const first = new Date(days[0].date + 'T00:00:00')
  const offset = (first.getDay() + 6) % 7
  for (let i = 0; i < offset; i++) {
    cells.push({ level: 'empty', title: '' })
  }
  for (const day of days) {
    cells.push({
      level: heatLevel(day.count),
      title: `${day.date} · ${day.count} 次保存`,
    })
  }
  return cells
})

// ==================== 标签字号 ====================
function tagFontSize(count) {
  const counts = (data.value.top_tags || []).map((t) => t.count)
  const max = Math.max(...counts, 1)
  const ratio = count / max
  return `${(12 + ratio * 8).toFixed(1)}px`
}

// ==================== 图表 ====================
function renderPie() {
  if (!pieRef.value || !data.value.folder_distribution.length) return
  pieChart = echarts.init(pieRef.value)
  pieChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} 篇 ({d}%)' },
    legend: { bottom: 0, type: 'scroll', textStyle: { color: textColor, fontSize: 12 } },
    series: [{
      type: 'pie',
      radius: ['42%', '68%'],
      center: ['50%', '44%'],
      itemStyle: { borderRadius: 6, borderWidth: 2, borderColor: isDark ? '#1e293b' : '#fff' },
      label: { color: textColor, formatter: '{b}' },
      data: data.value.folder_distribution.map((f) => ({ name: f.name, value: f.count })),
    }],
  })
}

function renderLine() {
  if (!lineRef.value) return
  const trend = data.value.message_trend || []
  lineChart = echarts.init(lineRef.value)
  lineChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0, textStyle: { color: textColor, fontSize: 12 } },
    grid: { left: 40, right: 16, top: 20, bottom: 44 },
    xAxis: {
      type: 'category',
      data: trend.map((d) => d.date.slice(5)),
      axisLabel: { color: textColor, fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLabel: { color: textColor, fontSize: 11 },
      splitLine: { lineStyle: { color: isDark ? 'rgba(148,163,184,.15)' : 'rgba(148,163,184,.25)' } },
    },
    series: [
      {
        name: '发出', type: 'line', smooth: true, data: trend.map((d) => d.sent),
        itemStyle: { color: '#409eff' }, areaStyle: { opacity: 0.08 },
      },
      {
        name: '收到', type: 'line', smooth: true, data: trend.map((d) => d.received),
        itemStyle: { color: '#67c23a' }, areaStyle: { opacity: 0.08 },
      },
    ],
  })
}

function handleResize() {
  pieChart?.resize()
  lineChart?.resize()
}

// ==================== 加载 ====================
async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await fetch('/api/insights/', {
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const payload = await res.json()
    data.value = { ...data.value, ...payload }
    await nextTick()
    renderPie()
    renderLine()
  } catch (err) {
    error.value = err?.message || '统计数据加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  load()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  pieChart?.dispose()
  lineChart?.dispose()
})
</script>

<style scoped>
.insights-page {
  max-width: 1080px;
  margin: 0 auto;
  padding: 24px 20px 48px;
  color: var(--k-text, #1e293b);
}

.insights-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 20px;
}

.insights-header h1 {
  margin: 0;
  font-size: 26px;
}

.insights-header h1 i {
  color: #409eff;
  margin-right: 8px;
}

.subtitle {
  margin: 6px 0 0;
  color: #94a3b8;
  font-size: 14px;
}

.streak-badges {
  display: flex;
  gap: 12px;
}

.streak-badge {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 10px 18px;
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(64, 158, 255, 0.12), rgba(103, 194, 58, 0.12));
  border: 1px solid rgba(64, 158, 255, 0.25);
}

.streak-num {
  font-size: 22px;
  font-weight: 700;
  color: #409eff;
}

.streak-label {
  font-size: 12px;
  color: #94a3b8;
}

.insights-state {
  padding: 60px 0;
  text-align: center;
  color: #94a3b8;
}

.insights-state.error {
  color: #dc2626;
}

.retry-btn {
  margin-left: 10px;
  padding: 4px 14px;
  border: 1px solid #dc2626;
  border-radius: 6px;
  background: transparent;
  color: #dc2626;
  cursor: pointer;
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 14px;
  margin-bottom: 20px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 12px;
  background: var(--k-bg, rgba(255, 255, 255, 0.75));
}

.stat-icon {
  width: 42px;
  height: 42px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  font-size: 17px;
  flex-shrink: 0;
}

.stat-copy {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.stat-copy strong {
  font-size: 17px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.stat-copy small {
  color: #94a3b8;
  font-size: 12px;
}

.panel {
  padding: 18px 20px;
  margin-bottom: 20px;
  border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 12px;
  background: var(--k-bg, rgba(255, 255, 255, 0.75));
}

.panel h2 {
  margin: 0 0 14px;
  font-size: 16px;
}

.panel h2 i {
  color: #409eff;
  margin-right: 6px;
}

.panel h2 small {
  margin-left: 8px;
  font-weight: 400;
  font-size: 12px;
  color: #94a3b8;
}

.panel-empty {
  padding: 36px 0;
  text-align: center;
  color: #94a3b8;
  font-size: 13px;
}

.heatmap-scroll {
  overflow-x: auto;
  padding-bottom: 6px;
}

.heatmap-grid {
  display: grid;
  grid-template-rows: repeat(7, 12px);
  grid-auto-flow: column;
  grid-auto-columns: 12px;
  gap: 3px;
  width: max-content;
}

.heat-cell {
  width: 12px;
  height: 12px;
  border-radius: 3px;
  background: rgba(148, 163, 184, 0.18);
}

.heat-cell.level-empty { background: transparent; }
.heat-cell.level-0 { background: rgba(148, 163, 184, 0.18); }
.heat-cell.level-1 { background: #bfe3ff; }
.heat-cell.level-2 { background: #74c0fc; }
.heat-cell.level-3 { background: #339af0; }
.heat-cell.level-4 { background: #1864ab; }

[data-theme="dark"] .heat-cell.level-0 { background: rgba(148, 163, 184, 0.12); }

.heatmap-legend {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 8px;
  justify-content: flex-end;
  color: #94a3b8;
  font-size: 12px;
}

.two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

@media (max-width: 820px) {
  .two-col {
    grid-template-columns: 1fr;
  }
}

.two-col .panel {
  min-width: 0;
}

.chart-box {
  height: 280px;
}

.top-notes {
  margin: 0;
  padding: 0;
  list-style: none;
}

.top-notes li {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 4px;
  border-bottom: 1px dashed rgba(148, 163, 184, 0.25);
}

.top-notes li:last-child {
  border-bottom: none;
}

.rank {
  width: 22px;
  height: 22px;
  display: grid;
  place-items: center;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
  background: rgba(148, 163, 184, 0.15);
  flex-shrink: 0;
}

.rank.podium {
  color: #fff;
  background: linear-gradient(135deg, #f59e0b, #f97316);
}

.note-link {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: inherit;
  text-decoration: none;
}

.note-link:hover {
  color: #409eff;
}

.public-tag {
  color: #059669;
  font-size: 12px;
}

.views {
  color: #94a3b8;
  font-size: 12px;
  white-space: nowrap;
}

.tag-cloud {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  padding: 6px 0;
}

.tag-chip {
  padding: 4px 12px;
  border-radius: 999px;
  background: rgba(64, 158, 255, 0.1);
  color: #409eff;
  line-height: 1.4;
}

.tag-chip em {
  font-style: normal;
  font-size: 11px;
  opacity: 0.7;
}
</style>
