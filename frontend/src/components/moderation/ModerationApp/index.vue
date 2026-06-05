<template>
  <div class="mod-root">
    <header class="mod-header">
      <h1><i class="fas fa-gavel"></i> 举报处置中心</h1>
      <span v-if="pendingCount > 0" class="mod-pending-badge">{{ pendingCount }} 条待处理</span>
      <a href="/" class="mod-back"><i class="fas fa-arrow-left"></i> 返回首页</a>
    </header>

    <div class="mod-body">
      <!-- 左：工单列表 -->
      <aside class="mod-list">
        <div class="mod-filters">
          <el-radio-group v-model="filterStatus" size="small" @change="reload">
            <el-radio-button label="pending">待处理</el-radio-button>
            <el-radio-button label="resolved">已处理</el-radio-button>
            <el-radio-button label="dismissed">已驳回</el-radio-button>
            <el-radio-button label="all">全部</el-radio-button>
          </el-radio-group>
          <el-select v-model="filterType" size="small" style="width:120px;margin-top:8px" @change="reload">
            <el-option label="全部类型" value="all" />
            <el-option label="私信举报" value="message" />
            <el-option label="附件举报" value="attachment" />
          </el-select>
        </div>

        <div v-if="listLoading" class="mod-state"><i class="fas fa-spinner fa-spin"></i> 加载中...</div>
        <el-empty v-else-if="reports.length === 0" description="暂无举报" />
        <ul v-else class="mod-tickets">
          <li
            v-for="t in reports"
            :key="t.type + '-' + t.id"
            :class="['mod-ticket', { active: selected && selected.type === t.type && selected.id === t.id }]"
            @click="openDetail(t)"
          >
            <div class="mod-ticket-top">
              <el-tag size="small" :type="t.type === 'message' ? '' : 'warning'">
                {{ t.type === 'message' ? '私信' : '附件' }}
              </el-tag>
              <span class="mod-reason">{{ t.reason_display }}</span>
              <el-tag size="small" :type="statusTagType(t.status)" effect="plain">{{ t.status_display }}</el-tag>
            </div>
            <div class="mod-ticket-users">
              <strong>{{ t.reporter.username }}</strong>
              <i class="fas fa-arrow-right"></i>
              <strong>{{ t.reported ? t.reported.username : '—' }}</strong>
            </div>
            <div class="mod-ticket-preview">{{ t.preview || '（无文本）' }}</div>
            <div class="mod-ticket-time">{{ formatTime(t.created_at) }}</div>
          </li>
        </ul>

        <div v-if="hasMore" class="mod-loadmore">
          <el-button size="small" :loading="listLoading" @click="loadMore">加载更多</el-button>
        </div>
      </aside>

      <!-- 右：详情 + 处置 -->
      <section class="mod-detail">
        <el-empty v-if="!selected" description="从左侧选择一条举报进行处置" />
        <div v-else-if="detailLoading" class="mod-state"><i class="fas fa-spinner fa-spin"></i> 加载详情...</div>
        <div v-else-if="detail" class="mod-detail-inner">
          <!-- 工单概要 -->
          <div class="mod-section mod-summary">
            <div class="mod-summary-head">
              <el-tag :type="detail.type === 'message' ? '' : 'warning'">
                {{ detail.type === 'message' ? '私信举报' : '附件举报' }} #{{ detail.id }}
              </el-tag>
              <el-tag :type="statusTagType(detail.status)" effect="plain">{{ detail.status_display }}</el-tag>
              <span class="mod-time">举报于 {{ formatTime(detail.created_at) }}</span>
            </div>
            <p><b>举报原因：</b>{{ detail.reason_display }}</p>
            <p v-if="detail.detail"><b>补充说明：</b>{{ detail.detail }}</p>
            <p v-if="detail.handled_by" class="mod-handled">
              已由 <b>{{ detail.handled_by }}</b> 处理{{ detail.resolved_at ? '（' + formatTime(detail.resolved_at) + '）' : '' }}
              <span v-if="detail.resolution_note">备注：{{ detail.resolution_note }}</span>
            </p>
          </div>

          <!-- 双方资料卡 -->
          <div class="mod-cards">
            <div class="mod-card">
              <h3><i class="fas fa-flag"></i> 举报者</h3>
              <user-card :user="detail.reporter" @revoke="revokeSanction" />
            </div>
            <div class="mod-card">
              <h3><i class="fas fa-user-slash"></i> 被举报者</h3>
              <user-card :user="detail.reported" @revoke="revokeSanction" />
            </div>
          </div>

          <!-- 附件预览 -->
          <div v-if="detail.attachment" class="mod-section">
            <h3><i class="fas fa-paperclip"></i> 被举报附件</h3>
            <div class="mod-attachment">
              <el-image
                v-if="detail.attachment.type === 'image'"
                :src="detail.attachment.preview_url"
                :preview-src-list="[detail.attachment.preview_url]"
                fit="contain"
                style="max-width:280px;max-height:280px"
              />
              <audio v-else-if="detail.attachment.type === 'audio'" controls :src="detail.attachment.preview_url"></audio>
              <video v-else-if="detail.attachment.type === 'video'" controls :src="detail.attachment.preview_url" style="max-width:320px"></video>
              <a v-else :href="detail.attachment.preview_url" target="_blank" class="mod-file-link">
                <i class="fas fa-file"></i> {{ detail.attachment.name }}（{{ formatSize(detail.attachment.size) }}）
              </a>
              <p class="mod-att-meta">{{ detail.attachment.name }} · {{ detail.attachment.mime_type || '未知类型' }} · {{ formatSize(detail.attachment.size) }}</p>
            </div>
          </div>

          <!-- 关联消息上下文 -->
          <div class="mod-section">
            <h3><i class="fas fa-comments"></i> 关联消息上下文</h3>
            <div v-if="detail.message_context.length === 0" class="mod-muted">无关联消息或消息已被清理</div>
            <div v-else class="mod-context">
              <div
                v-for="m in detail.message_context"
                :key="m.id"
                :class="['mod-msg', { highlight: m.is_highlight }]"
              >
                <div class="mod-msg-head">
                  <b>{{ m.sender }}</b> → {{ m.recipient }}
                  <span class="mod-msg-time">{{ formatTime(m.created_at) }}</span>
                  <el-tag v-if="m.is_recalled" size="small" type="info" effect="plain">已撤回</el-tag>
                </div>
                <div class="mod-msg-content">{{ m.content || '（无文本）' }}</div>
                <div v-if="m.attachments && m.attachments.length" class="mod-msg-atts">
                  <span v-for="a in m.attachments" :key="a.id" class="mod-msg-att">
                    <i class="fas fa-paperclip"></i>
                    <a :href="a.preview_url" target="_blank">{{ a.name }}</a>
                  </span>
                </div>
              </div>
            </div>
          </div>

          <!-- 处置历史 -->
          <div v-if="detail.logs && detail.logs.length" class="mod-section">
            <h3><i class="fas fa-history"></i> 处置历史</h3>
            <ul class="mod-logs">
              <li v-for="(l, i) in detail.logs" :key="i">
                <span class="mod-log-action">{{ actionLabel(l.action) }}</span>
                <span class="mod-log-meta">{{ l.moderator || '系统' }} · {{ formatTime(l.created_at) }}<span v-if="l.target_user"> · 对象：{{ l.target_user }}</span></span>
                <span v-if="l.note" class="mod-log-note">{{ l.note }}</span>
              </li>
            </ul>
          </div>

          <!-- 处置面板 -->
          <div class="mod-section mod-actions">
            <h3><i class="fas fa-gavel"></i> 执行处置</h3>
            <div class="mod-field">
              <label>处置决定</label>
              <el-radio-group v-model="form.decision">
                <el-radio label="uphold">举报成立</el-radio>
                <el-radio label="dismiss">驳回（误报）</el-radio>
              </el-radio-group>
            </div>

            <div class="mod-field">
              <label>对被举报者的处置</label>
              <div class="mod-action-row">
                <el-select v-model="reportedAction" placeholder="不处置" clearable style="width:200px">
                  <el-option-group label="禁言私信">
                    <el-option v-for="d in durations" :key="'m'+d.v" :label="'禁言私信 · ' + d.l" :value="'mute_messages:' + d.v" />
                  </el-option-group>
                  <el-option-group label="封禁登录">
                    <el-option v-for="d in durations" :key="'b'+d.v" :label="'封禁登录 · ' + d.l" :value="'ban_login:' + d.v" />
                  </el-option-group>
                </el-select>
              </div>
            </div>

            <div class="mod-field">
              <label>对举报者的惩戒（恶意举报时）</label>
              <div class="mod-action-row">
                <el-select v-model="reporterAction" placeholder="不处置" clearable style="width:200px">
                  <el-option-group label="禁言私信">
                    <el-option v-for="d in durations" :key="'rm'+d.v" :label="'禁言私信 · ' + d.l" :value="'mute_messages:' + d.v" />
                  </el-option-group>
                  <el-option-group label="封禁登录">
                    <el-option v-for="d in durations" :key="'rb'+d.v" :label="'封禁登录 · ' + d.l" :value="'ban_login:' + d.v" />
                  </el-option-group>
                </el-select>
              </div>
            </div>

            <div class="mod-field">
              <el-checkbox v-model="form.removeContent">
                删除违规内容（{{ detail.type === 'attachment' ? '删除该附件文件' : '撤回该消息' }}）
              </el-checkbox>
            </div>

            <div class="mod-field">
              <label>处置备注</label>
              <el-input v-model="form.note" type="textarea" :rows="2" maxlength="2000" show-word-limit
                placeholder="记录处置依据 / 说明，将写入处置日志" />
            </div>

            <div class="mod-submit">
              <el-button type="primary" :loading="submitting" @click="submit">提交处置</el-button>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getCsrfToken } from '@utils/csrf'
import UserCard from '../UserCard/index.vue'

const durations = [
  { v: '24h', l: '24 小时' },
  { v: '7d', l: '7 天' },
  { v: '30d', l: '30 天' },
  { v: 'permanent', l: '永久' },
]

const filterStatus = ref('pending')
const filterType = ref('all')
const reports = ref([])
const total = ref(0)
const page = ref(1)
const hasMore = ref(false)
const pendingCount = ref(0)
const listLoading = ref(false)

const selected = ref(null)
const detail = ref(null)
const detailLoading = ref(false)

const reportedAction = ref('')
const reporterAction = ref('')
const submitting = ref(false)
const form = reactive({ decision: 'uphold', removeContent: false, note: '' })

async function apiGet(url) {
  const r = await fetch(url, { credentials: 'same-origin' })
  const d = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`)
  return d
}

async function apiPost(url, body) {
  const r = await fetch(url, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
    body: JSON.stringify(body || {}),
  })
  const d = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`)
  return d
}

async function loadList(reset = true) {
  listLoading.value = true
  try {
    if (reset) { page.value = 1 }
    const d = await apiGet(`/api/moderation/reports/?status=${filterStatus.value}&type=${filterType.value}&page=${page.value}`)
    reports.value = reset ? d.results : reports.value.concat(d.results)
    total.value = d.total
    hasMore.value = d.has_more
    pendingCount.value = d.pending_count
  } catch (e) {
    ElMessage.error(e.message || '加载举报列表失败')
  } finally {
    listLoading.value = false
  }
}

function reload() { loadList(true) }
function loadMore() { page.value += 1; loadList(false) }

async function openDetail(t) {
  selected.value = { type: t.type, id: t.id }
  detail.value = null
  detailLoading.value = true
  resetForm()
  try {
    const d = await apiGet(`/api/moderation/reports/${t.type}/${t.id}/`)
    detail.value = d.report
  } catch (e) {
    ElMessage.error(e.message || '加载详情失败')
  } finally {
    detailLoading.value = false
  }
}

function resetForm() {
  form.decision = 'uphold'
  form.removeContent = false
  form.note = ''
  reportedAction.value = ''
  reporterAction.value = ''
}

function buildSanctions() {
  const list = []
  if (reportedAction.value) {
    const [type, duration] = reportedAction.value.split(':')
    list.push({ target: 'reported', type, duration })
  }
  if (reporterAction.value) {
    const [type, duration] = reporterAction.value.split(':')
    list.push({ target: 'reporter', type, duration })
  }
  return list
}

async function submit() {
  if (!selected.value) return
  const sanctions = buildSanctions()
  const hasPermanent = sanctions.some(s => s.duration === 'permanent')
  try {
    if (hasPermanent) {
      await ElMessageBox.confirm('本次处置包含「永久」制裁，确认执行？', '确认处置', { type: 'warning' })
    }
  } catch { return }

  submitting.value = true
  try {
    await apiPost(`/api/moderation/reports/${selected.value.type}/${selected.value.id}/resolve/`, {
      decision: form.decision,
      sanctions,
      remove_content: form.removeContent,
      note: form.note,
    })
    ElMessage.success('处置已提交')
    await openDetail(selected.value)
    await loadList(true)
  } catch (e) {
    ElMessage.error(e.message || '处置失败')
  } finally {
    submitting.value = false
  }
}

async function revokeSanction(sanctionId) {
  try {
    await ElMessageBox.confirm('确认提前解除该制裁？', '解除制裁', { type: 'warning' })
  } catch { return }
  try {
    await apiPost(`/api/moderation/sanctions/${sanctionId}/revoke/`, {})
    ElMessage.success('已解除')
    if (selected.value) await openDetail(selected.value)
  } catch (e) {
    ElMessage.error(e.message || '解除失败')
  }
}

function statusTagType(s) {
  if (s === 'pending') return 'danger'
  if (s === 'dismissed') return 'info'
  return 'success'
}

function actionLabel(a) {
  const map = {
    no_action: '无惩罚结案', dismiss: '驳回', remove_content: '删除违规内容',
  }
  if (map[a]) return map[a]
  if (a.startsWith('penalize_reporter:')) return '惩戒举报者 · ' + actionLabel(a.split(':')[1])
  if (a.startsWith('mute_')) return '禁言私信 · ' + durationLabel(a.slice(5))
  if (a.startsWith('ban_login_')) return '封禁登录 · ' + durationLabel(a.slice(10))
  if (a.startsWith('revoke:')) return '解除制裁'
  return a
}

function durationLabel(v) {
  return (durations.find(d => d.v === v) || {}).l || v
}

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', { hour12: false })
}

function formatSize(bytes) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0, n = bytes
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++ }
  return `${n.toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

onMounted(() => loadList(true))
</script>

<style scoped>
.mod-root { display: flex; flex-direction: column; height: calc(100vh - 64px); background: #f5f7fa; }
.mod-header { display: flex; align-items: center; gap: 16px; padding: 14px 24px; background: #fff; border-bottom: 1px solid #e4e7ed; }
.mod-header h1 { font-size: 18px; margin: 0; color: #303133; }
.mod-pending-badge { background: #fef0f0; color: #f56c6c; padding: 2px 10px; border-radius: 10px; font-size: 13px; }
.mod-back { margin-left: auto; color: #909399; text-decoration: none; font-size: 14px; }
.mod-back:hover { color: #409eff; }

.mod-body { flex: 1; display: flex; min-height: 0; }
.mod-list { width: 360px; border-right: 1px solid #e4e7ed; background: #fff; display: flex; flex-direction: column; overflow-y: auto; }
.mod-filters { padding: 12px; border-bottom: 1px solid #f0f0f0; position: sticky; top: 0; background: #fff; z-index: 1; }
.mod-tickets { list-style: none; margin: 0; padding: 0; }
.mod-ticket { padding: 12px 14px; border-bottom: 1px solid #f0f0f0; cursor: pointer; }
.mod-ticket:hover { background: #f5f7fa; }
.mod-ticket.active { background: #ecf5ff; border-left: 3px solid #409eff; }
.mod-ticket-top { display: flex; align-items: center; gap: 8px; }
.mod-reason { font-size: 13px; color: #606266; margin-right: auto; }
.mod-ticket-users { font-size: 13px; color: #303133; margin: 6px 0; display: flex; align-items: center; gap: 6px; }
.mod-ticket-users i { color: #c0c4cc; font-size: 11px; }
.mod-ticket-preview { font-size: 12px; color: #909399; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mod-ticket-time { font-size: 11px; color: #c0c4cc; margin-top: 4px; }
.mod-loadmore { text-align: center; padding: 12px; }

.mod-detail { flex: 1; overflow-y: auto; padding: 20px; }
.mod-detail-inner { max-width: 880px; margin: 0 auto; }
.mod-section { background: #fff; border-radius: 8px; padding: 16px; margin-bottom: 16px; border: 1px solid #ebeef5; }
.mod-section h3 { font-size: 15px; margin: 0 0 12px; color: #303133; }
.mod-summary-head { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; flex-wrap: wrap; }
.mod-summary p { margin: 6px 0; font-size: 14px; color: #606266; }
.mod-time { color: #909399; font-size: 13px; }
.mod-handled { background: #f0f9eb; padding: 8px; border-radius: 6px; color: #67c23a !important; }

.mod-cards { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
.mod-card { background: #fff; border-radius: 8px; padding: 16px; border: 1px solid #ebeef5; }
.mod-card h3 { font-size: 14px; margin: 0 0 12px; color: #303133; }

.mod-attachment { display: flex; flex-direction: column; gap: 8px; }
.mod-att-meta { font-size: 12px; color: #909399; margin: 0; }
.mod-file-link { color: #409eff; text-decoration: none; }

.mod-context { display: flex; flex-direction: column; gap: 8px; }
.mod-msg { padding: 8px 12px; border-radius: 8px; background: #f5f7fa; }
.mod-msg.highlight { background: #fdf6ec; border: 1px solid #f5dab1; }
.mod-msg-head { font-size: 12px; color: #909399; display: flex; align-items: center; gap: 8px; }
.mod-msg-time { margin-left: auto; }
.mod-msg-content { font-size: 14px; color: #303133; margin-top: 4px; white-space: pre-wrap; word-break: break-word; }
.mod-msg-atts { margin-top: 6px; font-size: 12px; }
.mod-msg-att { margin-right: 10px; }

.mod-logs { list-style: none; margin: 0; padding: 0; }
.mod-logs li { padding: 8px 0; border-bottom: 1px dashed #ebeef5; font-size: 13px; }
.mod-log-action { font-weight: 600; color: #303133; margin-right: 10px; }
.mod-log-meta { color: #909399; }
.mod-log-note { display: block; color: #606266; margin-top: 2px; }

.mod-field { margin-bottom: 14px; }
.mod-field > label { display: block; font-size: 13px; color: #606266; margin-bottom: 6px; }
.mod-submit { text-align: right; }
.mod-muted, .mod-state { color: #909399; font-size: 14px; padding: 12px 0; }
.mod-state i { margin-right: 6px; }

@media (max-width: 900px) {
  .mod-cards { grid-template-columns: 1fr; }
  .mod-list { width: 280px; }
}
</style>
