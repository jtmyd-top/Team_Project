<template>
  <div class="db-card log-terminal">
    <div class="db-card-title">
      <i class="fas fa-terminal"></i> 系统日志流
      <span class="log-source-tag" v-if="logData">{{ logData.source === 'file' ? 'FILE' : 'DB' }}</span>
    </div>
    <div class="log-terminal-body" ref="terminalRef">
      <div
        v-for="(line, idx) in logs"
        :key="idx"
        class="log-line"
        :class="getLineClass(line)"
      >
        <span class="log-line-num">{{ idx + 1 }}</span>
        <span class="log-line-text">{{ line }}</span>
      </div>
      <div v-if="logs.length === 0" class="log-empty">
        <i class="fas fa-check-circle"></i> 暂无异常日志
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useDashboardStore } from '@stores/dashboard.js'

const store = useDashboardStore()
const terminalRef = ref(null)
let scrollTimer = null

const logData = computed(() => store.errorLogs)
const logs = computed(() => logData.value?.logs || [])

function getLineClass(line) {
  const upper = line.toUpperCase()
  if (upper.includes('DELETE') || upper.includes('ERROR')) return 'log-line--error'
  if (upper.includes('WARNING') || upper.includes('WARN')) return 'log-line--warn'
  if (upper.includes('ADD') || upper.includes('CREATE')) return 'log-line--add'
  if (upper.includes('CHANGE')) return 'log-line--change'
  return ''
}

function autoScroll() {
  if (terminalRef.value) {
    terminalRef.value.scrollTop = terminalRef.value.scrollHeight
  }
}

watch(logs, () => {
  nextTick(autoScroll)
}, { deep: true })

onMounted(() => {
  scrollTimer = setInterval(autoScroll, 3000)
})

onUnmounted(() => {
  if (scrollTimer) clearInterval(scrollTimer)
})
</script>
