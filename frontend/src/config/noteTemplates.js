/**
 * 内置笔记模板库
 * 供 NoteEditor 空白笔记的"从模板开始"选择条使用。
 * render(now) 返回 TinyMCE 可直接 setContent 的 HTML 字符串。
 */

function pad(n) {
  return String(n).padStart(2, '0')
}

function formatDate(now) {
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

const WEEKDAYS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

function formatDateWithWeekday(now) {
  return `${formatDate(now)} ${WEEKDAYS[now.getDay()]}`
}

function checklist(items) {
  const lis = items
    .map((text) => `<li><input type="checkbox" /> ${text}</li>`)
    .join('')
  return `<ul style="list-style-type: none; padding-left: 20px;">${lis}</ul>`
}

export const NOTE_TEMPLATES = [
  {
    key: 'meeting',
    name: '会议记录',
    icon: 'fas fa-users-rectangle',
    description: '议程、结论与行动项',
    defaultTitle: (now) => `会议记录 ${formatDate(now)}`,
    render: (now) => `
      <h1>会议记录</h1>
      <p><strong>时间：</strong>${formatDateWithWeekday(now)}　<strong>地点：</strong>　<strong>记录人：</strong></p>
      <p><strong>参会人员：</strong></p>
      <h2>议程</h2>
      <ol><li>&nbsp;</li><li>&nbsp;</li></ol>
      <h2>讨论要点</h2>
      <p>&nbsp;</p>
      <h2>结论与决议</h2>
      <ul><li>&nbsp;</li></ul>
      <h2>行动项</h2>
      <table><thead><tr><th>事项</th><th>负责人</th><th>截止时间</th></tr></thead>
      <tbody><tr><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr></tbody></table>
    `,
  },
  {
    key: 'daily',
    name: '日报',
    icon: 'fas fa-sun',
    description: '今日完成、问题与明日计划',
    defaultTitle: (now) => `日报 ${formatDate(now)}`,
    render: (now) => `
      <h1>日报 · ${formatDateWithWeekday(now)}</h1>
      <h2>今日完成</h2>
      ${checklist(['&nbsp;', '&nbsp;'])}
      <h2>遇到的问题</h2>
      <ul><li>&nbsp;</li></ul>
      <h2>明日计划</h2>
      ${checklist(['&nbsp;'])}
    `,
  },
  {
    key: 'weekly',
    name: '周报',
    icon: 'fas fa-calendar-week',
    description: '本周总结与下周计划',
    defaultTitle: (now) => `周报 ${formatDate(now)}`,
    render: (now) => `
      <h1>周报（截至 ${formatDate(now)}）</h1>
      <h2>本周进展</h2>
      <ul><li>&nbsp;</li><li>&nbsp;</li></ul>
      <h2>关键数据 / 指标</h2>
      <table><thead><tr><th>指标</th><th>本周</th><th>上周</th><th>变化</th></tr></thead>
      <tbody><tr><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr></tbody></table>
      <h2>风险与阻塞</h2>
      <ul><li>&nbsp;</li></ul>
      <h2>下周计划</h2>
      ${checklist(['&nbsp;'])}
    `,
  },
  {
    key: 'reading',
    name: '读书笔记',
    icon: 'fas fa-book-open',
    description: '核心观点、摘录与感想',
    defaultTitle: () => '读书笔记：《》',
    render: (now) => `
      <h1>读书笔记</h1>
      <p><strong>书名：</strong>《》　<strong>作者：</strong>　<strong>记录日期：</strong>${formatDate(now)}</p>
      <h2>一句话总结</h2>
      <blockquote><p>&nbsp;</p></blockquote>
      <h2>核心观点</h2>
      <ol><li>&nbsp;</li><li>&nbsp;</li></ol>
      <h2>精彩摘录</h2>
      <blockquote><p>&nbsp;</p></blockquote>
      <h2>我的思考</h2>
      <p>&nbsp;</p>
    `,
  },
  {
    key: 'project',
    name: '项目计划',
    icon: 'fas fa-diagram-project',
    description: '目标、里程碑与风险',
    defaultTitle: () => '项目计划：',
    render: (now) => `
      <h1>项目计划</h1>
      <p><strong>创建日期：</strong>${formatDate(now)}　<strong>负责人：</strong></p>
      <h2>背景与目标</h2>
      <p>&nbsp;</p>
      <h2>范围</h2>
      <ul><li><strong>包含：</strong></li><li><strong>不包含：</strong></li></ul>
      <h2>里程碑</h2>
      <table><thead><tr><th>阶段</th><th>交付物</th><th>时间</th><th>状态</th></tr></thead>
      <tbody><tr><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr></tbody></table>
      <h2>风险与应对</h2>
      <ul><li>&nbsp;</li></ul>
    `,
  },
  {
    key: 'brainstorm',
    name: '头脑风暴',
    icon: 'fas fa-lightbulb',
    description: '自由发散想法并收敛',
    defaultTitle: () => '头脑风暴：',
    render: (now) => `
      <h1>头脑风暴</h1>
      <p><strong>主题：</strong>　<strong>日期：</strong>${formatDate(now)}</p>
      <h2>💡 想法池（先发散，不评判）</h2>
      <ul><li>&nbsp;</li><li>&nbsp;</li><li>&nbsp;</li></ul>
      <h2>⭐ 值得深入的方向</h2>
      <ol><li>&nbsp;</li></ol>
      <h2>✅ 下一步行动</h2>
      ${checklist(['&nbsp;'])}
    `,
  },
]
