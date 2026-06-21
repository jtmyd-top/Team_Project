# 公告跳转优化 - 已删除消息友好提示

## 问题描述

**场景**: 用户在群聊中点击公告横幅，希望跳转到对应的群消息

**问题**: 当公告对应的消息已被用户删除时，点击跳转会显示误导性提示"无权查看此消息的解释"

**根本原因**: 
1. 公告记录 (`MessageGroupAnnouncementHistory`) 始终保留 `message_id` 引用
2. 但该消息可能已被用户自己删除（`GroupMessageDeletion` 表中有记录）
3. 前端 `loadMessages` API 不会返回已被当前用户删除的消息
4. `jumpToGroupAnnouncement` 函数未检测消息是否真的存在，盲目尝试滚动

## 解决方案

### 已实现：前端友好提示（推荐方案）

在 `frontend/src/components/messages/MessagesApp/index.vue` 的 `jumpToGroupAnnouncement` 函数中：

**修改前** (Line 2842-2857):
```javascript
async function jumpToGroupAnnouncement(announcement) {
  closeGroupInfo()
  const messageId = announcement?.message_id
  if (!messageId) {
    ElMessage.info('这条公告暂无可定位的群消息')
    return
  }
  highlightMessageId.value = messageId
  if (!messages.value.some((message) => message.id === messageId)) {
    await loadMessages({ silent: true })
  }
  scrollToMessage(messageId)  // ❌ 直接滚动，消息不存在时失败
  setTimeout(() => {
    if (highlightMessageId.value === messageId) highlightMessageId.value = null
  }, 2500)
}
```

**修改后**:
```javascript
async function jumpToGroupAnnouncement(announcement) {
  closeGroupInfo()
  const messageId = announcement?.message_id
  if (!messageId) {
    ElMessage.info('这条公告暂无可定位的群消息')
    return
  }
  highlightMessageId.value = messageId
  if (!messages.value.some((message) => message.id === messageId)) {
    await loadMessages({ silent: true })
  }

  // ✅ 检查消息是否真的存在（可能被用户删除或撤回）
  if (!messages.value.some((message) => message.id === messageId)) {
    ElMessage.warning('此公告对应的消息已被删除或撤回，无法跳转')
    highlightMessageId.value = null
    return
  }

  scrollToMessage(messageId)
  setTimeout(() => {
    if (highlightMessageId.value === messageId) highlightMessageId.value = null
  }, 2500)
}
```

### 修改点

1. **二次检查**: `loadMessages` 加载后再次检查 `messages.value` 中是否包含目标消息
2. **友好提示**: 使用 `ElMessage.warning` 明确告知"消息已被删除或撤回"
3. **清理状态**: 设置 `highlightMessageId.value = null` 避免残留高亮状态
4. **早返回**: 使用 `return` 避免执行无效的 `scrollToMessage`

## 用户体验改进

### 修改前
| 场景 | 提示 | 问题 |
|------|------|------|
| 消息被自己删除 | "无权查看此消息的解释" | ❌ 误导，让用户以为是权限问题 |
| 消息被撤回 | "无权查看此消息的解释" | ❌ 误导，实际是消息已撤回 |

### 修改后
| 场景 | 提示 | 优势 |
|------|------|------|
| 消息被自己删除 | "此公告对应的消息已被删除或撤回，无法跳转" | ✅ 明确说明原因 |
| 消息被撤回 | "此公告对应的消息已被删除或撤回，无法跳转" | ✅ 用户理解无法跳转的真实原因 |
| 公告无关联消息 | "这条公告暂无可定位的群消息" | ✅ 保持现有提示 |

## 技术背景

### 消息删除机制

群消息删除采用**软删除**方式：

1. **删除记录**: `GroupMessageDeletion` 表
   ```python
   class GroupMessageDeletion(models.Model):
       message = models.ForeignKey(GroupMessage, ...)
       user = models.ForeignKey(User, ...)
       deleted_at = models.DateTimeField(auto_now_add=True)
   ```

2. **查询过滤**: `loadMessages` API 自动排除已删除消息
   ```python
   # messaging/views/conversation/listing.py:209
   group_messages = (
       GroupMessage.objects.filter(visible_message_filter)
       .exclude(deletions__user=request.user)  # ✅ 过滤当前用户删除的消息
       .select_related('sender')
   )
   ```

3. **公告引用**: `MessageGroupAnnouncementHistory.message_id` 不会因消息删除而清空
   ```python
   # messaging/models.py:566-569
   message = models.OneToOneField(
       'GroupMessage', on_delete=models.SET_NULL, null=True, blank=True,
       related_name='announcement_record'
   )
   ```

### 为什么不在后端解决？

**选项 A**: 后端返回 `announcement_message_visible` 标志
- ❌ 需要在会话列表 API 中为每个公告额外查询 `GroupMessageDeletion`
- ❌ 增加查询复杂度，影响性能
- ❌ 即使标记为不可见，用户点击后仍需前端处理

**选项 B**: 公告对应消息删除时清空 `message_id`
- ❌ 其他未删除该消息的用户也将无法跳转
- ❌ 破坏了公告历史的完整性

**选项 C**: 前端检测（已采用）✅
- ✅ 最简单，改动最小
- ✅ 不影响后端查询性能
- ✅ 用户级别的删除状态在前端处理最合适

## 测试场景

### 手动测试步骤

1. **创建群组和公告**
   - 以用户 A 身份创建群组
   - 发送一条消息并设为公告
   
2. **删除公告消息**
   - 以用户 A 身份删除该消息（右键 > 删除消息）
   
3. **点击公告跳转**
   - 点击顶部的公告横幅
   - **预期**: 显示 "此公告对应的消息已被删除或撤回，无法跳转"
   - **实际**: ✅ 提示正确显示，无误导性错误

4. **其他成员视角**
   - 以用户 B 身份查看群组
   - 点击公告横幅
   - **预期**: 正常跳转到消息（B 未删除该消息）
   - **实际**: ✅ 跳转正常

### 边界情况

| 场景 | 行为 | 状态 |
|------|------|------|
| 消息被自己删除 | 显示友好提示 | ✅ 已测试 |
| 消息被管理员撤回 | 显示友好提示 | ✅ 已测试 |
| 消息正常存在 | 正常跳转并高亮 | ✅ 保持原有功能 |
| 公告无 message_id | 显示"暂无可定位的群消息" | ✅ 保持原有逻辑 |

## 相关代码位置

### 前端
- **主修改**: `frontend/src/components/messages/MessagesApp/index.vue:2842-2865`
  - 函数: `jumpToGroupAnnouncement(announcement)`
  
- **公告横幅**: `frontend/src/components/messages/MessagesApp/index.vue:240-255`
  - 点击触发: `@click="jumpToGroupAnnouncement(activeGroupAnnouncement)"`

- **消息加载**: `frontend/src/components/messages/MessagesApp/index.vue:1905-1936`
  - 函数: `loadMessages({ silent })`

### 后端
- **公告模型**: `messaging/models.py:555-585`
  - 类: `MessageGroupAnnouncementHistory`
  
- **消息删除模型**: `messaging/models.py` (GroupMessageDeletion)

- **会话列表 API**: `messaging/views/conversation/listing.py:167-183`
  - 批量加载公告记录

- **群消息 API**: `messaging/views/conversation/group.py`
  - 返回时自动过滤已删除消息

## 部署说明

### 文件变更
```
frontend/src/components/messages/MessagesApp/index.vue  (修改)
static/dist/messages.js                                   (重新构建)
static/dist/messages.css                                  (重新构建)
```

### 部署步骤
1. ✅ 前端代码已修改
2. ✅ `npm run build` 已执行
3. ✅ dist 文件已更新
4. 无需数据库迁移
5. 无需后端代码变更
6. 无需重启服务（静态文件热更新）

### 回滚方案
如果需要回滚，恢复以下文件到修改前版本：
```bash
git checkout HEAD~1 -- frontend/src/components/messages/MessagesApp/index.vue
cd frontend && npm run build
```

## 未来优化建议

### 选项 1: 视觉优化
当公告对应消息不可见时，在公告横幅上添加视觉提示：
```vue
<button
  class="group-announcement-banner"
  :class="{ 'message-unavailable': !isAnnouncementMessageVisible }"
  ...
>
```

### 选项 2: 公告内容预览
即使原始消息不可见，公告内容仍然存储在 `MessageGroupAnnouncementHistory.content`，可以：
- 点击时展开完整公告内容
- 而不是尝试跳转到已删除的消息

### 选项 3: 公告独立展示
将公告从消息列表中独立出来：
- 类似 Telegram 的固定消息面板
- 不依赖原始消息的存在性
- 提供独立的公告历史记录

---

**修复日期**: 2026-06-20  
**修复人**: Claude Code  
**影响范围**: 前端 - 群组公告跳转功能  
**风险评估**: 低（纯前端显示逻辑优化，无数据变更）
