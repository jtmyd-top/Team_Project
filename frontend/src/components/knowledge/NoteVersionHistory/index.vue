<template>
  <el-dialog
    :model-value="modelValue"
    class="note-version-dialog"
    width="760px"
    title="版本历史"
    append-to-body
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div v-loading="loading" class="history-body">
      <div class="history-actions">
        <span>选择两个版本查看差异</span>
        <button class="history-action" :disabled="selectedIds.length !== 2 || comparing" @click="compareSelected">
          <i :class="comparing ? 'fas fa-spinner fa-spin' : 'fas fa-code-compare'"></i>
          对比
        </button>
      </div>
      <div v-if="!loading && revisions.length === 0" class="history-empty">暂无可用版本</div>
      <div v-else class="revision-list">
        <label v-for="revision in revisions" :key="revision.id" class="revision-row">
          <input v-model="selectedIds" type="checkbox" :value="revision.id" :disabled="!selectedIds.includes(revision.id) && selectedIds.length >= 2" />
          <div class="revision-main">
            <strong>v{{ revision.version_number }}</strong>
            <span>{{ actionLabel(revision.action) }}</span>
            <span>{{ revision.created_by.username }}</span>
            <time>{{ revision.created_at }}</time>
          </div>
          <button
            v-if="canRestore"
            class="restore-action"
            :disabled="restoringId === revision.id"
            @click.prevent="restoreRevision(revision)"
          >
            {{ restoringId === revision.id ? '恢复中' : '恢复此版本' }}
          </button>
        </label>
      </div>
      <div v-if="comparison" class="comparison-panel">
        <header>
          <strong>v{{ comparison.from.version_number }} → v{{ comparison.to.version_number }}</strong>
          <span v-if="comparison.title_changed">标题已变化</span>
        </header>
        <pre>{{ comparison.diff || '内容没有文字差异' }}</pre>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElDialog, ElMessage, ElMessageBox } from 'element-plus'
import 'element-plus/es/components/dialog/style/css'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  noteId: { type: [Number, String], default: null },
})
const emit = defineEmits(['update:modelValue', 'restored'])

const revisions = ref([])
const loading = ref(false)
const comparing = ref(false)
const restoringId = ref(null)
const canRestore = ref(false)
const selectedIds = ref([])
const comparison = ref(null)

function csrfToken() {
  return document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)?.[1] || ''
}

async function loadRevisions() {
  if (!props.noteId) return
  loading.value = true
  comparison.value = null
  selectedIds.value = []
  try {
    const response = await fetch(`/api/notes/${props.noteId}/revisions/`)
    const data = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(data.error || '版本历史加载失败')
    revisions.value = data.revisions || []
    canRestore.value = Boolean(data.can_restore)
  } catch (error) {
    ElMessage.error(error.message || '版本历史加载失败')
  } finally {
    loading.value = false
  }
}

async function compareSelected() {
  if (selectedIds.value.length !== 2) return
  comparing.value = true
  try {
    const params = new URLSearchParams({ from: selectedIds.value[0], to: selectedIds.value[1] })
    const response = await fetch(`/api/notes/${props.noteId}/revisions/compare/?${params}`)
    const data = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(data.error || '版本比较失败')
    comparison.value = data
  } catch (error) {
    ElMessage.error(error.message || '版本比较失败')
  } finally {
    comparing.value = false
  }
}

async function restoreRevision(revision) {
  try {
    await ElMessageBox.confirm(`恢复到 v${revision.version_number} 会保留当前内容为新版本。`, '恢复版本', {
      type: 'warning',
      confirmButtonText: '恢复',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  restoringId.value = revision.id
  try {
    const response = await fetch(`/api/notes/${props.noteId}/revisions/${revision.id}/restore/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': csrfToken() },
    })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(data.error || '恢复失败')
    ElMessage.success('已恢复版本')
    emit('restored', data.note)
    await loadRevisions()
  } catch (error) {
    ElMessage.error(error.message || '恢复失败')
  } finally {
    restoringId.value = null
  }
}

function actionLabel(action) {
  return { created: '创建', updated: '保存', restored: '恢复' }[action] || '保存'
}

watch(() => props.modelValue, visible => {
  if (visible) loadRevisions()
})
</script>

<style scoped>
.history-body { min-height: 220px; }
.history-actions { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 14px; color: #64748b; font-size: 14px; }
.history-action, .restore-action { min-height: 32px; border: 1px solid #cbd5e1; border-radius: 6px; background: #fff; color: #334155; cursor: pointer; padding: 0 10px; }
.history-action:disabled, .restore-action:disabled { opacity: .55; cursor: not-allowed; }
.revision-list { border-top: 1px solid #e2e8f0; }
.revision-row { display: flex; align-items: center; gap: 12px; min-height: 52px; border-bottom: 1px solid #e2e8f0; cursor: pointer; }
.revision-main { flex: 1; min-width: 0; display: flex; gap: 10px; align-items: center; color: #64748b; font-size: 13px; }
.revision-main strong { color: #0f172a; }
.revision-main time { margin-left: auto; white-space: nowrap; }
.history-empty { padding: 36px 0; color: #64748b; text-align: center; }
.comparison-panel { margin-top: 18px; border: 1px solid #dbe3ef; border-radius: 8px; overflow: hidden; }
.comparison-panel header { display: flex; justify-content: space-between; padding: 10px 12px; color: #334155; background: #f8fafc; font-size: 13px; }
.comparison-panel pre { max-height: 260px; margin: 0; overflow: auto; padding: 12px; color: #334155; background: #fff; font: 12px/1.55 ui-monospace, SFMono-Regular, Menlo, monospace; white-space: pre-wrap; }
@media (max-width: 680px) { .revision-main { flex-wrap: wrap; } .revision-main time { margin-left: 0; width: 100%; } }
</style>
