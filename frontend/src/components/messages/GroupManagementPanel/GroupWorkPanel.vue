<template>
  <div class="group-work-panel">
    <div class="work-toolbar">
      <p>在这里安排群任务、收集投票，不会打断日常聊天。</p>
      <button type="button" class="work-refresh" :disabled="loading" title="刷新" @click="loadAll">
        <i :class="loading ? 'fas fa-spinner fa-spin' : 'fas fa-rotate'"></i>
      </button>
    </div>

    <div v-if="error" class="work-error">{{ error }}</div>

    <section class="work-section">
      <header>
        <h3><i class="fas fa-square-poll-vertical"></i> 群投票</h3>
        <button v-if="isManager" type="button" class="primary-action" @click="showPollForm = !showPollForm">
          {{ showPollForm ? '取消' : '新建投票' }}
        </button>
      </header>

      <form v-if="showPollForm" class="work-form" @submit.prevent="createPoll">
        <input v-model.trim="pollForm.question" maxlength="240" placeholder="投票问题" required>
        <div v-for="(_, index) in pollForm.options" :key="index" class="option-field">
          <input v-model.trim="pollForm.options[index]" maxlength="160" :placeholder="`选项 ${index + 1}`" required>
          <button v-if="pollForm.options.length > 2" type="button" title="删除选项" @click="pollForm.options.splice(index, 1)">
            <i class="fas fa-xmark"></i>
          </button>
        </div>
        <div class="form-options">
          <button type="button" class="text-action" :disabled="pollForm.options.length >= 10" @click="pollForm.options.push('')">添加选项</button>
          <label><input v-model="pollForm.allow_multiple" type="checkbox"> 可多选</label>
        </div>
        <label class="date-field">截止时间（可选）<input v-model="pollForm.closes_at" type="datetime-local"></label>
        <button class="primary-action" :disabled="submitting" type="submit">{{ submitting ? '创建中…' : '创建投票' }}</button>
      </form>

      <div v-if="!polls.length" class="empty-work">暂无投票。</div>
      <article v-for="poll in polls" :key="poll.id" class="poll-card">
        <div class="poll-heading">
          <div>
            <strong>{{ poll.question }}</strong>
            <small>{{ poll.total_votes }} 票 · {{ poll.is_open ? (poll.closes_at ? `截止 ${formatTime(poll.closes_at)}` : '进行中') : '已结束' }}</small>
          </div>
          <button v-if="isManager && poll.is_open" type="button" class="text-action" @click="closePoll(poll)">结束</button>
        </div>
        <button
          v-for="option in poll.options"
          :key="option.id"
          type="button"
          class="poll-option"
          :class="{ selected: option.selected }"
          :disabled="!poll.is_open || votingId === poll.id"
          @click="vote(poll, option)"
        >
          <span>{{ option.text }}</span>
          <b>{{ option.votes }}</b>
        </button>
      </article>
    </section>

    <section class="work-section">
      <header>
        <h3><i class="fas fa-list-check"></i> 群任务</h3>
        <button v-if="isManager" type="button" class="primary-action" @click="showTaskForm = !showTaskForm">
          {{ showTaskForm ? '取消' : '新建任务' }}
        </button>
      </header>

      <form v-if="showTaskForm" class="work-form" @submit.prevent="createTask">
        <input v-model.trim="taskForm.title" maxlength="180" placeholder="任务标题" required>
        <textarea v-model.trim="taskForm.description" maxlength="1200" rows="3" placeholder="任务说明（可选）"></textarea>
        <label class="date-field">截止时间（可选）<input v-model="taskForm.due_at" type="datetime-local"></label>
        <button class="primary-action" :disabled="submitting" type="submit">{{ submitting ? '创建中…' : '创建任务' }}</button>
      </form>

      <div v-if="!tasks.length" class="empty-work">暂无任务。</div>
      <article v-for="task in tasks" :key="task.id" class="task-row" :class="{ completed: task.status === 'completed' }">
        <button
          type="button"
          class="task-toggle"
          :disabled="togglingId === task.id || !canComplete(task)"
          :title="task.status === 'completed' ? '重新打开任务' : '完成任务'"
          @click="toggleTask(task)"
        >
          <i :class="task.status === 'completed' ? 'fas fa-circle-check' : 'far fa-circle'"></i>
        </button>
        <div>
          <strong>{{ task.title }}</strong>
          <p v-if="task.description">{{ task.description }}</p>
          <small>创建者 {{ task.created_by.username }}<template v-if="task.due_at"> · 截止 {{ formatTime(task.due_at) }}</template></small>
        </div>
      </article>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getCsrfToken } from '../../../utils/csrf'

const props = defineProps({
  groupId: { type: Number, required: true },
  currentUserId: { type: Number, required: true },
})

const polls = ref([])
const tasks = ref([])
const role = ref('member')
const loading = ref(false)
const submitting = ref(false)
const votingId = ref(null)
const togglingId = ref(null)
const error = ref('')
const showPollForm = ref(false)
const showTaskForm = ref(false)
const pollForm = ref({ question: '', options: ['', ''], allow_multiple: false, closes_at: '' })
const taskForm = ref({ title: '', description: '', due_at: '' })

const isManager = computed(() => ['owner', 'admin'].includes(role.value))

function payloadDate(value) {
  return value ? new Date(value).toISOString() : null
}

function formatTime(value) {
  return new Date(value).toLocaleString()
}

function canComplete(task) {
  return isManager.value || !task.assignee || task.assignee.id === props.currentUserId
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken(), ...(options.headers || {}) },
    ...options,
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok || data.status !== 'success') throw new Error(data.message || data.error || '请求失败')
  return data
}

async function loadAll() {
  loading.value = true
  error.value = ''
  try {
    const [group, pollData, taskData] = await Promise.all([
      request(`/api/messages/groups/${props.groupId}/`),
      request(`/api/messages/groups/${props.groupId}/polls/`),
      request(`/api/messages/groups/${props.groupId}/tasks/`),
    ])
    role.value = group.membership?.role || 'member'
    polls.value = pollData.polls || []
    tasks.value = taskData.tasks || []
  } catch (err) {
    error.value = err?.message || '加载群工作项失败'
  } finally {
    loading.value = false
  }
}

function resetPoll() {
  pollForm.value = { question: '', options: ['', ''], allow_multiple: false, closes_at: '' }
  showPollForm.value = false
}

async function createPoll() {
  submitting.value = true
  try {
    const data = await request(`/api/messages/groups/${props.groupId}/polls/`, {
      method: 'POST',
      body: JSON.stringify({
        ...pollForm.value,
        closes_at: payloadDate(pollForm.value.closes_at),
      }),
    })
    polls.value.unshift(data.poll)
    resetPoll()
    ElMessage.success('投票已创建')
  } catch (err) {
    ElMessage.error(err?.message || '创建投票失败')
  } finally {
    submitting.value = false
  }
}

async function vote(poll, option) {
  votingId.value = poll.id
  try {
    const optionIds = poll.allow_multiple
      ? poll.options.filter(item => item.selected || item.id === option.id).filter(item => item.id !== option.id || !option.selected).map(item => item.id)
      : [option.id]
    const data = await request(`/api/messages/groups/${props.groupId}/polls/${poll.id}/vote/`, {
      method: 'POST',
      body: JSON.stringify({ option_ids: optionIds }),
    })
    polls.value = polls.value.map(item => item.id === poll.id ? data.poll : item)
  } catch (err) {
    ElMessage.error(err?.message || '投票失败')
  } finally {
    votingId.value = null
  }
}

async function closePoll(poll) {
  try {
    const data = await request(`/api/messages/groups/${props.groupId}/polls/${poll.id}/close/`, { method: 'POST' })
    polls.value = polls.value.map(item => item.id === poll.id ? data.poll : item)
  } catch (err) {
    ElMessage.error(err?.message || '结束投票失败')
  }
}

function resetTask() {
  taskForm.value = { title: '', description: '', due_at: '' }
  showTaskForm.value = false
}

async function createTask() {
  submitting.value = true
  try {
    const data = await request(`/api/messages/groups/${props.groupId}/tasks/`, {
      method: 'POST',
      body: JSON.stringify({ ...taskForm.value, due_at: payloadDate(taskForm.value.due_at) }),
    })
    tasks.value.push(data.task)
    resetTask()
    ElMessage.success('任务已创建')
  } catch (err) {
    ElMessage.error(err?.message || '创建任务失败')
  } finally {
    submitting.value = false
  }
}

async function toggleTask(task) {
  togglingId.value = task.id
  try {
    const data = await request(`/api/messages/groups/${props.groupId}/tasks/${task.id}/complete/`, { method: 'POST' })
    tasks.value = tasks.value.map(item => item.id === task.id ? data.task : item)
  } catch (err) {
    ElMessage.error(err?.message || '更新任务失败')
  } finally {
    togglingId.value = null
  }
}

onMounted(loadAll)
</script>

<style scoped>
.group-work-panel { display: grid; gap: 24px; padding: 4px 0; }
.work-toolbar, .work-section > header, .poll-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.work-toolbar p { margin: 0; color: #64748b; font-size: 13px; line-height: 1.55; }
.work-refresh, .text-action, .task-toggle { border: 0; background: transparent; cursor: pointer; }
.work-refresh { width: 32px; height: 32px; border: 1px solid #dbe3ee; border-radius: 6px; color: #475569; }
.work-section { display: grid; gap: 10px; }
.work-section h3 { margin: 0; color: #1f2937; font-size: 15px; }
.work-section h3 i { margin-right: 7px; color: #2563eb; }
.primary-action { padding: 7px 10px; border: 0; border-radius: 6px; color: #fff; background: #2563eb; cursor: pointer; }
.primary-action:disabled { opacity: .55; cursor: not-allowed; }
.text-action { padding: 5px; color: #2563eb; font-size: 13px; }
.work-form { display: grid; gap: 9px; padding: 12px; border: 1px solid #dbeafe; border-radius: 8px; background: #f8fbff; }
.work-form input, .work-form textarea { box-sizing: border-box; width: 100%; padding: 8px 9px; border: 1px solid #cbd5e1; border-radius: 6px; color: #1f2937; background: #fff; font: inherit; }
.option-field { display: flex; gap: 7px; }
.option-field button { width: 33px; border: 0; border-radius: 6px; color: #64748b; background: #e2e8f0; cursor: pointer; }
.form-options { display: flex; align-items: center; justify-content: space-between; gap: 12px; color: #475569; font-size: 13px; }
.form-options label { display: flex; gap: 5px; align-items: center; }
.date-field { display: grid; gap: 5px; color: #475569; font-size: 12px; }
.empty-work, .work-error { padding: 14px; border: 1px dashed #cbd5e1; border-radius: 8px; color: #64748b; font-size: 13px; text-align: center; }
.work-error { color: #b91c1c; border-color: #fecaca; }
.poll-card, .task-row { padding: 12px; border: 1px solid #e2e8f0; border-radius: 8px; background: #fff; }
.poll-card { display: grid; gap: 7px; }
.poll-heading strong, .task-row strong { display: block; color: #1f2937; font-size: 14px; }
.poll-heading small, .task-row small, .task-row p { color: #64748b; font-size: 12px; }
.poll-heading small { display: block; margin-top: 4px; }
.poll-option { display: flex; justify-content: space-between; gap: 12px; padding: 8px 9px; border: 1px solid #e2e8f0; border-radius: 6px; color: #334155; background: #fff; text-align: left; cursor: pointer; }
.poll-option:hover:not(:disabled), .poll-option.selected { border-color: #93c5fd; background: #eff6ff; }
.poll-option:disabled { cursor: default; }
.poll-option b { color: #2563eb; }
.task-row { display: flex; align-items: flex-start; gap: 10px; }
.task-toggle { padding: 0; color: #64748b; font-size: 20px; }
.task-toggle:disabled { cursor: default; opacity: .6; }
.task-row > div { min-width: 0; flex: 1; }
.task-row p { margin: 5px 0; line-height: 1.5; white-space: pre-wrap; }
.task-row.completed strong, .task-row.completed p { color: #94a3b8; text-decoration: line-through; }
.task-row.completed .task-toggle { color: #16a34a; }
</style>
