<template>
  <el-dialog
    :model-value="modelValue"
    class="note-annotations-dialog"
    width="560px"
    title="批注与评论"
    append-to-body
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div v-loading="loading" class="annotations-body">
      <div v-if="selection?.text" class="selection-summary">
        <span>批注选区</span>
        <strong>{{ selection.text }}</strong>
      </div>
      <textarea v-model="draft" class="comment-input" maxlength="2000" placeholder="写下评论或批注…" />
      <div class="compose-actions">
        <span>{{ draft.length }}/2000</span>
        <button class="primary-action" :disabled="!draft.trim() || submitting" @click="submit">
          {{ submitting ? '发送中' : '发布' }}
        </button>
      </div>
      <div v-if="!loading && comments.length === 0" class="comment-empty">还没有评论</div>
      <div v-else class="comment-list">
        <article v-for="comment in comments" :key="comment.id" class="comment-row">
          <header>
            <strong>{{ comment.author }}</strong>
            <time>{{ comment.created_at }}</time>
          </header>
          <blockquote v-if="comment.anchor_text">{{ comment.anchor_text }}</blockquote>
          <p>{{ comment.content }}</p>
          <div v-for="reply in comment.replies || []" :key="reply.id" class="comment-reply">
            <strong>{{ reply.author }}</strong>：{{ reply.content }}
          </div>
        </article>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  noteId: { type: [Number, String], default: null },
  selection: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue', 'submitted'])
const comments = ref([])
const draft = ref('')
const loading = ref(false)
const submitting = ref(false)

function csrfToken() {
  return document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)?.[1] || ''
}

async function load() {
  if (!props.noteId) return
  loading.value = true
  try {
    const response = await fetch(`/api/notes/${props.noteId}/comments/?page_size=100`)
    const data = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(data.error || '评论加载失败')
    comments.value = data.comments || []
  } catch (error) {
    ElMessage.error(error.message || '评论加载失败')
  } finally {
    loading.value = false
  }
}

async function submit() {
  submitting.value = true
  try {
    const selection = props.selection || {}
    const response = await fetch(`/api/notes/${props.noteId}/comments/create/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
      body: JSON.stringify({
        content: draft.value.trim(),
        anchor_text: selection.text || '',
        anchor_start: selection.start,
        anchor_end: selection.end,
        anchor_context: selection.context || '',
      }),
    })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(data.error || '评论发布失败')
    comments.value.push(data)
    draft.value = ''
    emit('submitted', data)
  } catch (error) {
    ElMessage.error(error.message || '评论发布失败')
  } finally {
    submitting.value = false
  }
}

watch(() => props.modelValue, visible => {
  if (visible) load()
})
</script>

<style scoped>
.annotations-body { min-height: 200px; }
.selection-summary { display: grid; gap: 5px; margin-bottom: 12px; padding: 10px 12px; border-left: 3px solid #2563eb; background: #eff6ff; color: #475569; font-size: 13px; }
.selection-summary strong { overflow: hidden; color: #1e3a8a; text-overflow: ellipsis; white-space: nowrap; }
.comment-input { width: 100%; min-height: 86px; box-sizing: border-box; resize: vertical; border: 1px solid #cbd5e1; border-radius: 6px; padding: 10px; color: #0f172a; font: inherit; }
.compose-actions { display: flex; justify-content: space-between; align-items: center; margin: 8px 0 18px; color: #94a3b8; font-size: 12px; }
.primary-action { min-height: 32px; border: 0; border-radius: 6px; padding: 0 13px; color: #fff; background: #2563eb; cursor: pointer; }
.primary-action:disabled { opacity: .55; cursor: not-allowed; }
.comment-list { display: grid; gap: 10px; }
.comment-row { border-top: 1px solid #e2e8f0; padding-top: 12px; }
.comment-row header { display: flex; justify-content: space-between; gap: 10px; color: #64748b; font-size: 12px; }
.comment-row header strong { color: #334155; }
.comment-row p { margin: 8px 0; color: #334155; white-space: pre-wrap; }
.comment-row blockquote { margin: 8px 0; padding: 7px 10px; border-left: 3px solid #94a3b8; color: #64748b; background: #f8fafc; font-size: 13px; }
.comment-reply { margin: 8px 0 0 14px; color: #475569; font-size: 13px; }
.comment-empty { padding: 24px; color: #64748b; text-align: center; }
</style>
