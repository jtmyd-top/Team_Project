<template>
  <div class="mod-root">
    <header class="mod-header">
      <div class="mod-title-group">
        <div class="mod-title-icon"><i class="fas fa-gavel"></i></div>
        <div>
          <h1>举报处置中心</h1>
          <p>集中审核私信与附件举报，快速查看证据并执行处置</p>
        </div>
      </div>
      <div class="mod-header-actions">
        <span v-if="pendingCount > 0" class="mod-pending-badge"><i class="fas fa-bell"></i>{{ pendingCount }} 条待处理</span>
        <a href="/" class="mod-back"><i class="fas fa-arrow-left"></i> 返回首页</a>
      </div>
    </header>

    <div class="mod-body">
      <!-- 左：工单列表 -->
      <aside class="mod-list">
        <div class="mod-filters">
          <div class="mod-list-head">
            <div>
              <span>举报队列</span>
              <small>{{ total }} 条记录</small>
            </div>
            <button class="mod-refresh" type="button" title="刷新列表" @click="reload">
              <i class="fas fa-sync-alt"></i>
            </button>
          </div>
          <el-radio-group v-model="filterStatus" size="small" @change="reload">
            <el-radio-button label="pending">待处理</el-radio-button>
            <el-radio-button label="resolved">已处理</el-radio-button>
            <el-radio-button label="dismissed">已驳回</el-radio-button>
            <el-radio-button label="all">全部</el-radio-button>
          </el-radio-group>
          <el-select v-model="filterType" size="small" class="mod-type-select" @change="reload">
            <el-option label="全部类型" value="all" />
            <el-option label="私信举报" value="message" />
            <el-option label="附件举报" value="attachment" />
            <el-option label="文章举报" value="note" />
            <el-option label="评论举报" value="comment" />
          </el-select>
          <el-input v-model="filterQ" size="small" clearable placeholder="搜索原因、内容、用户名" @keyup.enter="reload" @clear="reload" />
          <div class="mod-filter-grid">
            <el-input v-model="filterReporter" size="small" clearable placeholder="举报者" @keyup.enter="reload" @clear="reload" />
            <el-input v-model="filterTarget" size="small" clearable placeholder="被举报者" @keyup.enter="reload" @clear="reload" />
            <el-input v-model="filterObjectId" size="small" clearable placeholder="对象 ID" @keyup.enter="reload" @clear="reload" />
            <el-button size="small" @click="reload">筛选</el-button>
          </div>
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
              <el-tag size="small" :type="typeTagType(t.type)">
                {{ typeShortLabel(t.type) }}
              </el-tag>
              <el-tag v-if="t.duplicate_count > 1" size="small" type="danger" effect="plain">
                {{ t.duplicate_count }} 人举报
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
        <div v-if="!selected" class="mod-empty-workspace">
          <div class="mod-empty-icon"><i class="fas fa-shield-alt"></i></div>
          <h2>选择一条举报开始处置</h2>
          <p>左侧工单列表会展示举报原因、相关用户和最新内容预览。选择后可查看上下文证据、用户状态并执行处置。</p>
        </div>
        <div v-else-if="detailLoading" class="mod-state"><i class="fas fa-spinner fa-spin"></i> 加载详情...</div>
        <div v-else-if="detail" :class="['mod-detail-inner', { 'is-readonly': !canResolveSelected }]">
          <!-- 工单概要 -->
          <div class="mod-section mod-summary">
            <div class="mod-summary-head">
              <el-tag :type="typeTagType(detail.type)">
                {{ typeLabel(detail.type) }} #{{ detail.id }}
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

          <div v-if="detail.reporter_risk && detail.reporter_risk.risk_level !== 'low'" class="mod-section mod-risk">
            <h3><i class="fas fa-triangle-exclamation"></i> 举报者风险提示</h3>
            <p>
              近 7 天发起 {{ detail.reporter_risk.filed_7d }} 次举报，驳回 {{ detail.reporter_risk.dismissed_7d }} 次，
              当前生效处置 {{ detail.reporter_risk.active_sanctions }} 条。
            </p>
          </div>

          <!-- 双方资料卡 -->
          <div class="mod-cards">
            <div class="mod-card">
              <h3><i class="fas fa-flag"></i> 举报者</h3>
              <user-card :user="detail.reporter" @revoke="revokeSanction" @sanction="openManualSanction" />
            </div>
            <div class="mod-card">
              <h3><i class="fas fa-user-slash"></i> 被举报者</h3>
              <user-card :user="detail.reported" @revoke="revokeSanction" @sanction="openManualSanction" />
            </div>
          </div>

          <!-- 附件预览 -->
          <div v-if="detail.attachment" class="mod-section mod-evidence-section">
            <h3><i class="fas fa-paperclip"></i> 被举报附件</h3>
            <div class="mod-attachment">
              <el-image
                v-if="detail.attachment.type === 'image'"
                :src="detail.attachment.preview_url"
                :preview-src-list="[detail.attachment.preview_url]"
                fit="contain"
                class="mod-media-preview"
              />
              <audio v-else-if="detail.attachment.type === 'audio'" controls :src="detail.attachment.preview_url"></audio>
              <video v-else-if="detail.attachment.type === 'video'" controls :src="detail.attachment.preview_url" class="mod-video-preview"></video>
              <a v-else :href="detail.attachment.preview_url" target="_blank" class="mod-file-link">
                <i class="fas fa-file"></i> {{ detail.attachment.name }}（{{ formatSize(detail.attachment.size) }}）
              </a>
              <p class="mod-att-meta">{{ detail.attachment.name }} · {{ detail.attachment.mime_type || '未知类型' }} · {{ formatSize(detail.attachment.size) }}</p>
            </div>
          </div>

          <div v-if="detail.note" class="mod-section mod-evidence-section">
            <h3><i class="fas fa-file-alt"></i> 被举报文章</h3>
            <div class="mod-msg">
              <div class="mod-msg-head">
                <b>{{ detail.note.title }}</b>
                <el-tag size="small" :type="detail.note.is_public ? 'success' : 'info'" effect="plain">
                  {{ detail.note.is_public ? '公开中' : '已下架' }}
                </el-tag>
                <a v-if="detail.note.public_url" :href="detail.note.public_url" target="_blank" class="mod-file-link">打开文章</a>
              </div>
              <div v-if="detail.note.content_preview" class="mod-msg-content">{{ detail.note.content_preview }}</div>
            </div>
          </div>

          <div v-if="detail.comment" class="mod-section mod-evidence-section">
            <h3><i class="fas fa-comment-dots"></i> 被举报评论</h3>
            <div class="mod-msg highlight">
              <div class="mod-msg-head">
                <b>{{ detail.comment.author }}</b>
                <span class="mod-msg-time">{{ formatTime(detail.comment.created_at) }}</span>
              </div>
              <div class="mod-msg-content">{{ detail.comment.content || '（无文本）' }}</div>
            </div>
          </div>

          <div v-if="hasEvidenceSnapshot" class="mod-section mod-evidence-section">
            <h3><i class="fas fa-camera-retro"></i> 举报时证据快照</h3>
            <dl class="mod-snapshot">
              <template v-for="item in evidenceSnapshotEntries" :key="item.key">
                <dt>{{ item.label }}</dt>
                <dd>{{ item.value }}</dd>
              </template>
            </dl>
          </div>

          <!-- 关联消息上下文 -->
          <div v-if="detail.message_context && detail.message_context.length" class="mod-section mod-context-section">
            <h3><i class="fas fa-comments"></i> 关联消息上下文</h3>
            <div class="mod-context">
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
                <div v-if="mergedForwardOf(m)" class="mod-forward-card">
                  <div class="mod-forward-title">
                    <i class="fas fa-layer-group"></i>
                    {{ mergedForwardOf(m).title || '合并转发聊天记录' }}
                    <span>{{ mergedForwardOf(m).count }} 条</span>
                  </div>
                  <div v-if="mergedForwardOf(m).source" class="mod-forward-source">
                    {{ mergedForwardOf(m).source }}
                  </div>
                  <div class="mod-forward-items">
                    <div v-for="item in mergedForwardOf(m).items" :key="item.id || item.time || item.sender + item.content" class="mod-forward-item">
                      <div class="mod-forward-meta">
                        <strong>{{ item.sender }}</strong>
                        <span>{{ item.time }}</span>
                      </div>
                      <div class="mod-forward-content">{{ forwardItemText(item) }}</div>
                      <div v-if="item.attachments && item.attachments.length" class="mod-forward-atts">
                        <span v-for="a in item.attachments" :key="a.id || a.name">
                          <i class="fas fa-paperclip"></i> {{ a.name || '附件' }}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
                <div v-else class="mod-msg-content">{{ m.content || '（无文本）' }}</div>
                <div v-if="m.attachments && m.attachments.length" class="mod-msg-atts">
                  <span v-for="a in m.attachments" :key="a.id" class="mod-msg-att">
                    <i class="fas fa-paperclip"></i>
                    <a :href="a.preview_url" target="_blank">{{ a.name }}</a>
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div v-if="detail.related_reports && detail.related_reports.length > 1" class="mod-section mod-related-section">
            <h3><i class="fas fa-layer-group"></i> 同对象举报</h3>
            <ul class="mod-related">
              <li v-for="r in detail.related_reports" :key="r.id">
                <b>{{ r.reporter.username }}</b>
                <span>{{ r.reason_display }}</span>
                <em>{{ formatTime(r.created_at) }}</em>
              </li>
            </ul>
          </div>

          <!-- 处置历史 -->
          <div v-if="detail.logs && detail.logs.length" class="mod-section mod-logs-section">
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
          <div v-if="canResolveSelected" class="mod-section mod-actions">
            <h3><i class="fas fa-gavel"></i> 执行处置</h3>
            <div class="mod-field">
              <label>处置决定</label>
              <el-radio-group v-model="form.decision" @change="onDecisionChange">
                <el-radio label="uphold">举报成立</el-radio>
                <el-radio label="dismiss">驳回（误报）</el-radio>
              </el-radio-group>
            </div>

            <div v-if="templates.length" class="mod-field">
              <label>处置模板</label>
              <el-select v-model="form.templateId" placeholder="选择模板填充备注" clearable class="mod-template-select" @change="applyTemplate">
                <el-option v-for="t in templates" :key="t.id" :label="t.title" :value="t.id" />
              </el-select>
            </div>

            <div v-if="form.decision === 'uphold'" class="mod-field">
              <label>对被举报者的处置</label>
              <div class="mod-action-row">
                <el-select v-model="reportedAction" placeholder="不处置" clearable class="mod-action-select">
                  <el-option-group v-for="g in sanctionGroupsForSelected" :key="'reported-'+g.value" :label="g.label">
                    <el-option v-for="d in durations" :key="'reported-'+g.value+d.v" :label="g.label + ' · ' + d.l" :value="g.value + ':' + d.v" />
                  </el-option-group>
                </el-select>
              </div>
            </div>

            <div v-if="form.decision === 'dismiss'" class="mod-field">
              <label>对举报者的惩戒（恶意举报时）</label>
              <div class="mod-action-row">
                <el-select v-model="reporterAction" placeholder="不处置" clearable class="mod-action-select">
                  <el-option-group v-for="g in sanctionGroupsForSelected" :key="'reporter-'+g.value" :label="g.label">
                    <el-option v-for="d in durations" :key="'reporter-'+g.value+d.v" :label="g.label + ' · ' + d.l" :value="g.value + ':' + d.v" />
                  </el-option-group>
                </el-select>
              </div>
            </div>

            <div v-if="form.decision === 'uphold'" class="mod-field">
              <el-checkbox v-model="form.removeContent">
                内容处置（{{ removeContentLabel(detail.type) }}）
              </el-checkbox>
            </div>

            <div v-if="detail.duplicate_count > 1" class="mod-field">
              <el-checkbox v-model="form.resolveRelated">
                同步结案同对象的其他 {{ detail.duplicate_count - 1 }} 条待处理举报
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
          <div v-else class="mod-section mod-resolved-notice">
            <h3><i class="fas fa-check-circle"></i> 举报已结案</h3>
            <p>该举报已完成处置，不再重复提交原工单。若用户解除制裁后继续违规，可在上方用户资料卡中点击“重新处置”，无需等待新的举报。</p>
          </div>
        </div>
      </section>
    </div>

    <el-dialog v-model="manualSanction.visible" title="重新处置用户" width="420px">
      <div v-if="manualSanction.user" class="mod-manual-target">
        <i class="fas fa-user-shield"></i>
        <span>{{ manualSanction.user.username }}</span>
      </div>
      <div class="mod-field">
        <label>处置类型</label>
        <el-select v-model="manualSanction.action" placeholder="请选择处置" class="mod-action-select">
          <el-option-group v-for="g in sanctionGroupsForSelected" :key="'manual-'+g.value" :label="g.label">
            <el-option v-for="d in durations" :key="'manual-'+g.value+d.v" :label="g.label + ' · ' + d.l" :value="g.value + ':' + d.v" />
          </el-option-group>
        </el-select>
      </div>
      <div class="mod-field">
        <label>处置备注</label>
        <el-input
          v-model="manualSanction.note"
          type="textarea"
          :rows="3"
          maxlength="2000"
          show-word-limit
          placeholder="记录本次重新处置依据"
        />
      </div>
      <template #footer>
        <el-button @click="manualSanction.visible = false">取消</el-button>
        <el-button type="primary" :loading="manualSubmitting" @click="submitManualSanction">提交处置</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getCsrfToken } from '@utils/csrf'
import { extractApiErrorMessage } from '@utils/apiError'
import { parseMergedForward } from '@utils/mergedForward'
import UserCard from '../UserCard/index.vue'

const durations = [
  { v: '24h', l: '24 小时' },
  { v: '7d', l: '7 天' },
  { v: '30d', l: '30 天' },
  { v: 'permanent', l: '永久' },
]

const sanctionGroupsByReportType = {
  message: [
    { value: 'mute_messages', label: '禁言私信' },
    { value: 'ban_login', label: '封禁登录' },
  ],
  attachment: [
    { value: 'mute_messages', label: '禁言私信' },
    { value: 'ban_login', label: '封禁登录' },
  ],
  note: [
    { value: 'ban_public_notes', label: '禁止发布公开文章' },
    { value: 'ban_login', label: '封禁登录' },
  ],
  comment: [
    { value: 'ban_comments', label: '禁止评论' },
    { value: 'ban_login', label: '封禁登录' },
  ],
}

const filterStatus = ref('pending')
const filterType = ref('all')
const filterQ = ref('')
const filterReporter = ref('')
const filterTarget = ref('')
const filterObjectId = ref('')
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
const manualSubmitting = ref(false)
const templates = ref([])
const form = reactive({ decision: 'uphold', removeContent: false, resolveRelated: true, templateId: '', note: '' })
const manualSanction = reactive({
  visible: false,
  user: null,
  action: '',
  note: '',
})
const canResolveSelected = computed(() => detail.value?.status === 'pending')
const sanctionGroupsForSelected = computed(() => (
  sanctionGroupsByReportType[detail.value?.type || selected.value?.type] || []
))
const hasEvidenceSnapshot = computed(() => Object.keys(detail.value?.evidence_snapshot || {}).length > 0)
const evidenceSnapshotEntries = computed(() => {
  const labels = {
    title: '标题',
    content_preview: '内容片段',
    comment_content: '评论内容',
    message_preview: '消息片段',
    name: '文件名',
    mime_type: '文件类型',
    author_username: '作者',
    sender_username: '发送者',
    uploader_username: '上传者',
    reported_url: '举报入口',
  }
  return Object.entries(detail.value?.evidence_snapshot || {})
    .filter(([, value]) => value !== null && value !== undefined && value !== '')
    .slice(0, 12)
    .map(([key, value]) => ({ key, label: labels[key] || key, value: String(value) }))
})

async function apiGet(url) {
  const r = await fetch(url, { credentials: 'same-origin' })
  const d = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(extractApiErrorMessage(d, `HTTP ${r.status}`))
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
  if (!r.ok) throw new Error(extractApiErrorMessage(d, `HTTP ${r.status}`))
  return d
}

async function loadList(reset = true) {
  listLoading.value = true
  try {
    if (reset) { page.value = 1 }
    const params = new URLSearchParams({
      status: filterStatus.value,
      type: filterType.value,
      page: String(page.value),
    })
    if (filterQ.value) params.set('q', filterQ.value)
    if (filterReporter.value) params.set('reporter', filterReporter.value)
    if (filterTarget.value) params.set('target', filterTarget.value)
    if (filterObjectId.value) params.set('object_id', filterObjectId.value)
    const d = await apiGet(`/api/moderation/reports/?${params.toString()}`)
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
    await loadTemplates()
  } catch (e) {
    ElMessage.error(e.message || '加载详情失败')
  } finally {
    detailLoading.value = false
  }
}

function resetForm() {
  form.decision = 'uphold'
  form.removeContent = false
  form.resolveRelated = true
  form.templateId = ''
  form.note = ''
  reportedAction.value = ''
  reporterAction.value = ''
}

function isSanctionActionAllowed(action) {
  if (!action) return true
  const [type] = action.split(':')
  return sanctionGroupsForSelected.value.some(group => group.value === type)
}

function onDecisionChange(value) {
  form.templateId = ''
  loadTemplates()
  if (value === 'uphold') {
    reporterAction.value = ''
    return
  }
  reportedAction.value = ''
  form.removeContent = false
}

async function loadTemplates() {
  if (!selected.value) return
  try {
    const params = new URLSearchParams({ type: selected.value.type, decision: form.decision })
    const d = await apiGet(`/api/moderation/templates/?${params.toString()}`)
    templates.value = d.templates || []
  } catch {
    templates.value = []
  }
}

function applyTemplate(templateId) {
  const item = templates.value.find(t => t.id === templateId)
  if (item) form.note = item.content
}

function buildSanctions() {
  if (!isSanctionActionAllowed(reportedAction.value)) reportedAction.value = ''
  if (!isSanctionActionAllowed(reporterAction.value)) reporterAction.value = ''
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
  if (!selected.value || !canResolveSelected.value) return
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
      resolve_related: form.resolveRelated,
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

function openManualSanction(user) {
  if (!user) return
  manualSanction.user = user
  manualSanction.action = isSanctionActionAllowed(manualSanction.action) ? manualSanction.action : ''
  manualSanction.note = ''
  manualSanction.visible = true
}

async function submitManualSanction() {
  if (!manualSanction.user) return
  if (!manualSanction.action) {
    ElMessage.warning('请选择处置类型')
    return
  }
  const [type, duration] = manualSanction.action.split(':')
  try {
    if (duration === 'permanent') {
      await ElMessageBox.confirm('本次处置包含「永久」制裁，确认执行？', '确认处置', { type: 'warning' })
    }
  } catch { return }

  manualSubmitting.value = true
  try {
    await apiPost(`/api/moderation/users/${manualSanction.user.id}/sanction/`, {
      type,
      duration,
      note: manualSanction.note,
      source_report_type: selected.value?.type || '',
      source_report_id: selected.value?.id || null,
    })
    ElMessage.success('用户已重新处置')
    manualSanction.visible = false
    if (selected.value) await openDetail(selected.value)
  } catch (e) {
    ElMessage.error(e.message || '重新处置失败')
  } finally {
    manualSubmitting.value = false
  }
}

function statusTagType(s) {
  if (s === 'pending') return 'danger'
  if (s === 'dismissed') return 'info'
  return 'success'
}

function typeShortLabel(t) {
  return ({ message: '私信', attachment: '附件', note: '文章', comment: '评论' }[t]) || t
}

function typeLabel(t) {
  return ({ message: '私信举报', attachment: '附件举报', note: '文章举报', comment: '评论举报' }[t]) || t
}

function typeTagType(t) {
  return ({ message: 'primary', attachment: 'warning', note: 'success', comment: 'info' }[t]) || 'info'
}

function removeContentLabel(t) {
  return ({ attachment: '删除该附件文件', note: '下架该文章', comment: '删除该评论' }[t]) || '撤回该消息'
}

function mergedForwardOf(message) {
  return message?.merged_forward || parseMergedForward(message?.content)
}

function forwardItemText(item) {
  if (!item) return '（无文本）'
  return item.content || item.preview || (item.attachments && item.attachments.length ? '[附件]' : '（无文本）')
}

function actionLabel(a) {
  const map = {
    no_action: '无惩罚结案', dismiss: '驳回', remove_content: '删除违规内容',
  }
  if (map[a]) return map[a]
  if (a.startsWith('manual:')) return '人工处置 · ' + actionLabel(a.slice(7))
  if (a.startsWith('penalize_reporter:')) return '惩戒举报者 · ' + actionLabel(a.split(':')[1])
  if (a.startsWith('mute_')) return '禁言私信 · ' + durationLabel(a.slice(5))
  if (a.startsWith('ban_comments_')) return '禁止评论 · ' + durationLabel(a.slice(13))
  if (a.startsWith('ban_public_notes_')) return '禁止发布公开文章 · ' + durationLabel(a.slice(17))
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
.mod-root {
  --mod-primary: #3b82f6;
  --mod-primary-soft: #eff6ff;
  --mod-danger: #ef4444;
  --mod-warning: #f59e0b;
  --mod-success: #16a34a;
  --mod-text: #0f172a;
  --mod-muted: #64748b;
  --mod-border: rgba(148, 163, 184, 0.24);
  --mod-card: rgba(255, 255, 255, 0.92);
  --mod-shadow: 0 18px 45px rgba(15, 23, 42, 0.08);
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  height: calc(100vh - 64px);
  background:
    radial-gradient(circle at 12% 8%, rgba(59, 130, 246, 0.12), transparent 28%),
    radial-gradient(circle at 85% 18%, rgba(14, 165, 233, 0.12), transparent 30%),
    linear-gradient(135deg, #f8fbff 0%, #eef4fb 100%);
  color: var(--mod-text);
  overflow: hidden;
}

.mod-header {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 18px 24px;
  background: rgba(255, 255, 255, 0.86);
  border-bottom: 1px solid var(--mod-border);
  backdrop-filter: blur(14px);
  box-shadow: 0 8px 28px rgba(15, 23, 42, 0.05);
}
.mod-title-group { display: flex; align-items: center; gap: 14px; min-width: 0; }
.mod-title-icon {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  color: #fff;
  background: linear-gradient(135deg, #2563eb, #06b6d4);
  box-shadow: 0 10px 24px rgba(37, 99, 235, 0.28);
}
.mod-header h1 { font-size: 20px; margin: 0; color: var(--mod-text); letter-spacing: -0.02em; }
.mod-header p { margin: 3px 0 0; color: var(--mod-muted); font-size: 13px; }
.mod-pending-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
  background: linear-gradient(135deg, #fff1f2, #fee2e2);
  color: #b91c1c;
  padding: 7px 12px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 700;
  border: 1px solid rgba(239, 68, 68, 0.18);
}
.mod-back {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--mod-muted);
  text-decoration: none;
  font-size: 14px;
  padding: 8px 10px;
  border-radius: 10px;
  transition: all 0.18s ease;
}
.mod-back:hover { color: var(--mod-primary); background: var(--mod-primary-soft); }

.mod-body {
  display: grid;
  grid-template-columns: 360px minmax(0, 1fr);
  gap: 18px;
  min-height: 0;
  padding: 18px;
}
.mod-list {
  min-height: 0;
  background: var(--mod-card);
  border: 1px solid var(--mod-border);
  border-radius: 20px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: var(--mod-shadow);
}
.mod-filters {
  padding: 16px;
  border-bottom: 1px solid var(--mod-border);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(248, 250, 252, 0.9));
}
.mod-type-select { width: 100%; margin-top: 10px; }
.mod-tickets { flex: 1; overflow: auto; list-style: none; margin: 0; padding: 10px; }
.mod-ticket {
  position: relative;
  padding: 13px 14px 13px 16px;
  margin-bottom: 10px;
  border: 1px solid transparent;
  border-radius: 15px;
  background: rgba(255, 255, 255, 0.76);
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease, background 0.18s ease;
}
.mod-ticket::before {
  content: '';
  position: absolute;
  left: 0;
  top: 14px;
  bottom: 14px;
  width: 3px;
  border-radius: 999px;
  background: transparent;
}
.mod-ticket:hover {
  transform: translateY(-1px);
  background: #fff;
  border-color: rgba(59, 130, 246, 0.16);
  box-shadow: 0 12px 24px rgba(15, 23, 42, 0.07);
}
.mod-ticket.active {
  background: linear-gradient(135deg, #eff6ff, #ffffff);
  border-color: rgba(59, 130, 246, 0.36);
  box-shadow: 0 14px 30px rgba(37, 99, 235, 0.14);
}
.mod-ticket.active::before { background: var(--mod-primary); }
.mod-ticket-top { display: flex; align-items: center; gap: 8px; min-width: 0; }
.mod-reason { flex: 1; min-width: 0; font-size: 13px; font-weight: 700; color: #334155; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mod-ticket-users { font-size: 13px; color: #1e293b; margin: 9px 0 6px; display: flex; align-items: center; gap: 7px; }
.mod-ticket-users strong { font-weight: 700; }
.mod-ticket-users i { color: #94a3b8; font-size: 11px; }
.mod-ticket-preview { font-size: 12px; line-height: 1.55; color: var(--mod-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mod-ticket-time { font-size: 11px; color: #94a3b8; margin-top: 8px; }
.mod-loadmore { text-align: center; padding: 12px 16px 16px; border-top: 1px solid rgba(148, 163, 184, 0.14); }

.mod-detail { min-width: 0; overflow-y: auto; padding: 2px 4px 24px; }
.mod-detail-inner { max-width: 980px; margin: 0 auto; }
.mod-empty-workspace {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 48px 24px;
  color: var(--mod-muted);
}
.mod-empty-icon {
  width: 86px;
  height: 86px;
  display: grid;
  place-items: center;
  margin-bottom: 18px;
  border-radius: 26px;
  color: var(--mod-primary);
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(59, 130, 246, 0.16);
  box-shadow: var(--mod-shadow);
  font-size: 34px;
}
.mod-empty-workspace h2 { margin: 0 0 8px; font-size: 22px; color: #1e293b; }
.mod-empty-workspace p { max-width: 520px; margin: 0; line-height: 1.8; font-size: 14px; }
.mod-section,
.mod-card {
  background: var(--mod-card);
  border-radius: 18px;
  padding: 18px;
  margin-bottom: 16px;
  border: 1px solid var(--mod-border);
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.06);
}
.mod-section h3,
.mod-card h3 { font-size: 15px; margin: 0 0 14px; color: #1e293b; display: flex; align-items: center; gap: 8px; }
.mod-section h3 i,
.mod-card h3 i { color: var(--mod-primary); }
.mod-summary { background: linear-gradient(135deg, rgba(255, 255, 255, 0.96), rgba(239, 246, 255, 0.92)); }
.mod-summary-head { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
.mod-summary p { margin: 8px 0; font-size: 14px; line-height: 1.7; color: #475569; }
.mod-time { color: var(--mod-muted); font-size: 13px; }
.mod-handled { background: #ecfdf5; padding: 10px 12px; border-radius: 12px; color: #047857 !important; border: 1px solid rgba(22, 163, 74, 0.16); }

.mod-cards { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; margin-bottom: 16px; }
.mod-attachment { display: flex; flex-direction: column; gap: 10px; }
.mod-media-preview { max-width: 320px; max-height: 320px; border-radius: 14px; overflow: hidden; border: 1px solid var(--mod-border); }
.mod-video-preview { max-width: 360px; border-radius: 14px; border: 1px solid var(--mod-border); }
.mod-att-meta { font-size: 12px; color: var(--mod-muted); margin: 0; }
.mod-file-link { color: var(--mod-primary); text-decoration: none; font-weight: 700; }

.mod-context { display: flex; flex-direction: column; gap: 10px; }
.mod-msg { padding: 12px 14px; border-radius: 14px; background: #f8fafc; border: 1px solid rgba(148, 163, 184, 0.18); }
.mod-msg.highlight { background: linear-gradient(135deg, #fff7ed, #ffffff); border-color: rgba(245, 158, 11, 0.34); box-shadow: 0 10px 24px rgba(245, 158, 11, 0.1); }
.mod-msg-head { font-size: 12px; color: var(--mod-muted); display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.mod-msg-head b { color: #334155; }
.mod-msg-time { margin-left: auto; }
.mod-msg-content { font-size: 14px; color: #1e293b; margin-top: 7px; line-height: 1.65; white-space: pre-wrap; word-break: break-word; }
.mod-msg-atts { margin-top: 8px; font-size: 12px; }
.mod-msg-att { margin-right: 12px; }
.mod-msg-att a { color: var(--mod-primary); text-decoration: none; }
.mod-forward-card {
  margin-top: 10px;
  border: 1px solid rgba(59, 130, 246, 0.18);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.82);
  overflow: hidden;
}
.mod-forward-title {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 11px 12px;
  color: #1e293b;
  font-weight: 800;
  background: linear-gradient(135deg, #eff6ff, #f8fafc);
  border-bottom: 1px solid rgba(148, 163, 184, 0.18);
}
.mod-forward-title i { color: var(--mod-primary); }
.mod-forward-title span { margin-left: auto; color: var(--mod-muted); font-size: 12px; font-weight: 700; }
.mod-forward-source { padding: 8px 12px 0; color: var(--mod-muted); font-size: 12px; }
.mod-forward-items { padding: 8px; display: flex; flex-direction: column; gap: 8px; }
.mod-forward-item { padding: 10px; border-radius: 12px; background: #f8fafc; border: 1px solid rgba(148, 163, 184, 0.16); }
.mod-forward-meta { display: flex; align-items: center; gap: 10px; color: var(--mod-muted); font-size: 12px; }
.mod-forward-meta strong { color: #334155; }
.mod-forward-meta span { margin-left: auto; }
.mod-forward-content { margin-top: 6px; color: #1e293b; line-height: 1.65; white-space: pre-wrap; word-break: break-word; }
.mod-forward-atts { margin-top: 7px; display: flex; flex-wrap: wrap; gap: 8px; color: var(--mod-primary); font-size: 12px; }

.mod-logs { list-style: none; margin: 0; padding: 0; }
.mod-logs li { padding: 10px 0; border-bottom: 1px dashed rgba(148, 163, 184, 0.32); font-size: 13px; }
.mod-log-action { font-weight: 700; color: #1e293b; margin-right: 10px; }
.mod-log-meta { color: var(--mod-muted); }
.mod-log-note { display: block; color: #475569; margin-top: 4px; }

.mod-actions {
  border-color: rgba(59, 130, 246, 0.24);
  background: linear-gradient(135deg, rgba(239, 246, 255, 0.92), rgba(255, 255, 255, 0.96));
}
.mod-resolved-notice {
  border-color: rgba(34, 197, 94, 0.24);
  background: linear-gradient(135deg, rgba(240, 253, 244, 0.92), rgba(255, 255, 255, 0.96));
}
.mod-resolved-notice h3 i { color: var(--mod-success); }
.mod-resolved-notice p { margin: 0; color: #475569; line-height: 1.8; font-size: 14px; }
.mod-field { margin-bottom: 16px; }
.mod-field > label { display: block; font-size: 13px; font-weight: 700; color: #334155; margin-bottom: 8px; }
.mod-manual-target { display: inline-flex; align-items: center; gap: 8px; margin-bottom: 14px; padding: 8px 10px; border: 1px solid #fed7aa; border-radius: 8px; background: #fff7ed; color: #9a3412; font-size: 13px; font-weight: 700; }
.mod-action-row { display: flex; align-items: center; gap: 10px; }
.mod-action-select { width: 240px; max-width: 100%; }
.mod-submit { text-align: right; padding-top: 2px; }
.mod-muted,
.mod-state { color: var(--mod-muted); font-size: 14px; padding: 16px; }
.mod-state i { margin-right: 6px; }

.mod-root :deep(.el-radio-group) { max-width: 100%; flex-wrap: wrap; }
.mod-root :deep(.el-radio-button__inner) { border-color: rgba(148, 163, 184, 0.28); font-weight: 600; }
.mod-root :deep(.el-radio-button__original-radio:checked + .el-radio-button__inner) {
  background: linear-gradient(135deg, #2563eb, #0ea5e9);
  border-color: transparent;
  box-shadow: 0 8px 18px rgba(37, 99, 235, 0.22);
}
.mod-root :deep(.el-select__wrapper) { border-radius: 10px; box-shadow: 0 0 0 1px rgba(148, 163, 184, 0.24) inset; }
.mod-root :deep(.el-button--primary) {
  border: 0;
  border-radius: 10px;
  background: linear-gradient(135deg, #2563eb, #0ea5e9);
  box-shadow: 0 10px 22px rgba(37, 99, 235, 0.24);
  font-weight: 700;
}
.mod-list :deep(.el-empty) { padding: 46px 16px; }
.mod-list :deep(.el-empty__image) { width: 120px; opacity: 0.72; }
.mod-list :deep(.el-empty__description p) { color: var(--mod-muted); }

@media (max-width: 1100px) {
  .mod-body { grid-template-columns: 300px minmax(0, 1fr); }
  .mod-cards { grid-template-columns: 1fr; }
}
@media (max-width: 760px) {
  .mod-root { height: auto; min-height: calc(100vh - 64px); overflow: visible; }
  .mod-header { align-items: flex-start; flex-wrap: wrap; }
  .mod-pending-badge { margin-left: 0; }
  .mod-body { grid-template-columns: 1fr; padding: 12px; }
  .mod-list { max-height: 45vh; border-radius: 16px; }
  .mod-detail { overflow: visible; padding-bottom: 16px; }
  .mod-msg-time { margin-left: 0; width: 100%; }
}

/* Compact moderation workbench redesign */
.mod-root {
  --mod-primary: #2563eb;
  --mod-primary-soft: #eff6ff;
  --mod-danger: #dc2626;
  --mod-warning: #d97706;
  --mod-success: #059669;
  --mod-text: #111827;
  --mod-muted: #64748b;
  --mod-border: #dbe3ee;
  --mod-panel: #ffffff;
  --mod-subtle: #f7f9fc;
  --mod-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  height: calc(100vh - 64px);
  background: #eef3f8;
  color: var(--mod-text);
  overflow: hidden;
}

.mod-header {
  min-height: 64px;
  padding: 0 24px;
  background: var(--mod-panel);
  border-bottom: 1px solid var(--mod-border);
  box-shadow: none;
}

.mod-title-icon {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  background: #0f7ad8;
  box-shadow: none;
}

.mod-header h1 {
  font-size: 19px;
  letter-spacing: 0;
}

.mod-header p {
  margin-top: 2px;
  color: #5f6f85;
}

.mod-header-actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 10px;
}

.mod-pending-badge,
.mod-back {
  border-radius: 8px;
}

.mod-pending-badge {
  margin-left: 0;
  background: #fff7ed;
  color: #9a3412;
  border-color: #fed7aa;
}

.mod-back {
  padding: 8px 12px;
  border: 1px solid var(--mod-border);
  background: #fff;
  color: #475569;
}

.mod-body {
  grid-template-columns: 390px minmax(0, 1fr);
  gap: 16px;
  padding: 16px;
}

.mod-list,
.mod-section,
.mod-card {
  border-radius: 8px;
  background: var(--mod-panel);
  border: 1px solid var(--mod-border);
  box-shadow: var(--mod-shadow);
}

.mod-list {
  min-height: 0;
}

.mod-filters {
  padding: 14px;
  background: #fff;
}

.mod-list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.mod-list-head span {
  display: block;
  font-size: 15px;
  font-weight: 800;
  color: #172033;
}

.mod-list-head small {
  display: block;
  margin-top: 2px;
  font-size: 12px;
  color: var(--mod-muted);
}

.mod-refresh {
  width: 32px;
  height: 32px;
  border: 1px solid var(--mod-border);
  border-radius: 8px;
  background: #fff;
  color: #64748b;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.mod-refresh:hover {
  color: var(--mod-primary);
  background: var(--mod-primary-soft);
  border-color: #bfdbfe;
}

.mod-type-select {
  margin-top: 12px;
}

.mod-tickets {
  padding: 10px;
  background: #fbfcfe;
}

.mod-ticket {
  margin-bottom: 8px;
  padding: 12px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid #e5ebf3;
  box-shadow: none;
}

.mod-ticket::before {
  top: 10px;
  bottom: 10px;
  width: 3px;
}

.mod-ticket:hover {
  transform: none;
  border-color: #bfdbfe;
  box-shadow: 0 6px 16px rgba(37, 99, 235, 0.08);
}

.mod-ticket.active {
  background: #f5f9ff;
  border-color: #93c5fd;
  box-shadow: 0 8px 18px rgba(37, 99, 235, 0.1);
}

.mod-ticket-top {
  gap: 6px;
}

.mod-reason {
  color: #172033;
}

.mod-ticket-users {
  margin: 10px 0 6px;
  font-size: 14px;
}

.mod-ticket-preview {
  color: #526173;
}

.mod-detail {
  padding: 0 4px 20px 0;
}

.mod-detail-inner {
  max-width: none;
  margin: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 16px;
  align-items: start;
}

.mod-summary,
.mod-cards {
  grid-column: 1 / -1;
}

.mod-evidence-section,
.mod-context-section,
.mod-logs-section {
  grid-column: 1;
}

.mod-detail-inner.is-readonly .mod-evidence-section,
.mod-detail-inner.is-readonly .mod-context-section,
.mod-detail-inner.is-readonly .mod-logs-section {
  grid-column: 1 / -1;
}

.mod-actions {
  grid-column: 2;
  grid-row: 3 / span 5;
  position: sticky;
  top: 0;
}

.mod-resolved-notice {
  grid-column: 1 / -1;
}

.mod-section,
.mod-card {
  margin: 0;
  padding: 16px;
}

.mod-section h3,
.mod-card h3 {
  margin-bottom: 12px;
  font-size: 14px;
}

.mod-summary {
  background: #fff;
}

.mod-summary-head {
  padding-bottom: 12px;
  margin-bottom: 12px;
  border-bottom: 1px solid #eef2f7;
}

.mod-summary p {
  margin: 6px 0;
  color: #334155;
}

.mod-handled {
  border-radius: 8px;
  background: #ecfdf5;
  border-color: #bbf7d0;
}

.mod-cards {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 0;
}

.mod-context {
  gap: 8px;
}

.mod-msg {
  border-radius: 8px;
  background: #f8fafc;
}

.mod-msg.highlight {
  background: #fff7ed;
  border-color: #fdba74;
  box-shadow: none;
}

.mod-forward-card,
.mod-forward-item {
  border-radius: 8px;
}

.mod-actions {
  background: #f8fbff;
  border-color: #bfdbfe;
}

.mod-field {
  margin-bottom: 14px;
}

.mod-action-select {
  width: 100%;
}

.mod-submit {
  padding-top: 4px;
}

.mod-submit .el-button {
  width: 100%;
}

.mod-empty-workspace {
  min-height: calc(100vh - 128px);
}

.mod-empty-icon {
  width: 72px;
  height: 72px;
  border-radius: 8px;
  box-shadow: none;
}

.mod-root :deep(.el-radio-button__inner),
.mod-root :deep(.el-select__wrapper),
.mod-root :deep(.el-button--primary) {
  border-radius: 8px;
}

.mod-root :deep(.el-radio-button__original-radio:checked + .el-radio-button__inner) {
  background: var(--mod-primary);
  box-shadow: none;
}

.mod-root :deep(.el-button--primary) {
  background: var(--mod-primary);
  box-shadow: none;
}

.mod-root :deep(.el-button--primary:hover) {
  background: #1d4ed8;
}

.mod-detail::-webkit-scrollbar,
.mod-tickets::-webkit-scrollbar {
  width: 8px;
}

.mod-detail::-webkit-scrollbar-thumb,
.mod-tickets::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 999px;
}

@media (max-width: 1180px) {
  .mod-body {
    grid-template-columns: 330px minmax(0, 1fr);
  }

  .mod-detail-inner {
    grid-template-columns: 1fr;
  }

  .mod-evidence-section,
  .mod-context-section,
  .mod-logs-section,
  .mod-actions {
    grid-column: 1;
  }

  .mod-actions {
    grid-row: auto;
    position: static;
  }
}

@media (max-width: 760px) {
  .mod-root {
    height: auto;
    min-height: calc(100vh - 64px);
  }

  .mod-header {
    padding: 14px;
    gap: 12px;
  }

  .mod-header-actions {
    width: 100%;
    margin-left: 0;
    justify-content: space-between;
  }

  .mod-body {
    grid-template-columns: 1fr;
    padding: 12px;
  }

  .mod-list {
    max-height: none;
  }

  .mod-cards {
    grid-template-columns: 1fr;
  }
}

.mod-filter-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-top: 8px;
}

.mod-template-select {
  width: 320px;
  max-width: 100%;
}

.mod-risk {
  border-color: #fed7aa;
  background: #fff7ed;
}

.mod-risk h3,
.mod-risk h3 i,
.mod-risk p {
  color: #9a3412;
}

.mod-risk p {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
}

.mod-snapshot {
  display: grid;
  grid-template-columns: 120px minmax(0, 1fr);
  gap: 8px 12px;
  margin: 0;
}

.mod-snapshot dt {
  color: var(--mod-muted);
  font-size: 12px;
  font-weight: 700;
}

.mod-snapshot dd {
  margin: 0;
  color: var(--mod-text);
  font-size: 13px;
  word-break: break-word;
}

.mod-related {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 8px;
}

.mod-related li {
  display: grid;
  grid-template-columns: 110px minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  padding: 8px 10px;
  border: 1px solid var(--mod-border);
  border-radius: 8px;
  background: #fff;
  font-size: 13px;
}

.mod-related em {
  color: var(--mod-muted);
  font-style: normal;
  font-size: 12px;
}
</style>
