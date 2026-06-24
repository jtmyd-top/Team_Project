# 群组加入申请弹窗通知功能实现

## 功能概述

为群主和管理员实现了完整的群组加入申请通知系统，包括：

1. **进入群聊时自动检查** - 群主/管理员进入群聊时，如果有待审核的加入申请，自动弹出提醒
2. **实时 WebSocket 推送** - 当有新的加入申请时，实时推送通知并弹窗提醒
3. **智能提醒控制** - 支持"24小时内不再提醒"和"7天内不再提醒"选项

## 实现的修改

### 1. 后端修改

#### 1.1 扩展 WebSocket 消费者 (`messaging/consumers.py`)

添加了 `group_join_request` 事件处理方法：

```python
async def group_join_request(self, event):
    """处理群组加入申请通知"""
    await self.send(text_data=json.dumps({
        'type': 'group_join_request',
        'group_id': event['group_id'],
        'group_name': event.get('group_name', ''),
        'request_id': event.get('request_id'),
        'user': event.get('user', {}),
        'request_message': event.get('request_message', ''),
    }))
```

#### 1.2 添加实时推送 (`message_groups/views/join_requests.py`)

在 `request_join_group_api` 函数中，添加了 WebSocket 实时推送：

```python
# 实时推送通知
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
channel_layer = get_channel_layer()

for admin_member in admins:
    try:
        # 发送数据库通知
        notify_user(...)
        
        # 实时 WebSocket 推送
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f'chat_user_{admin_member.user.id}',
                {
                    'type': 'group_join_request',
                    'group_id': group.id,
                    'group_name': group.name,
                    'request_id': join_request.id,
                    'user': {
                        'id': request.user.id,
                        'username': request.user.username,
                        'avatar': _get_avatar_url(request.user),
                    },
                    'request_message': request_message,
                }
            )
    except Exception as e:
        logger.warning(f'发送入群申请通知失败: {e}')
```

### 2. 前端修改

#### 2.1 处理实时事件 (`frontend/src/components/messages/MessagesApp/index.vue`)

在 `handleRealtimeEvent` 函数中添加了对 `group_join_request` 事件的处理：

```javascript
if (event.type === 'group_join_request') {
  // 收到新的群组加入申请
  const groupId = event.group_id
  if (!groupId) return

  // 刷新待审核数量
  if (hasAdminPermissions.value) {
    loadPendingApprovals({ silent: true })
  }

  // 如果当前正在查看该群组，立即弹窗提醒
  if (selectedGroupId() === normalizeUserId(groupId)) {
    showJoinRequestNotification(event)
  } else {
    // 否则显示桌面通知
    ElMessage.info({
      message: `${event.user?.username || '用户'} 申请加入群组 ${event.group_name || ''}`,
      duration: 3000,
    })
  }
}
```

#### 2.2 新增弹窗显示函数

添加了 `showJoinRequestNotification` 函数，用于显示实时通知弹窗：

```javascript
function showJoinRequestNotification(event) {
  // 实时收到加入申请时显示弹窗
  const groupId = event.group_id
  if (!groupId) return

  const requestItem = {
    id: event.request_id,
    user: event.user,
    request_message: event.request_message,
    created_at: new Date().toISOString(),
  }

  // 如果弹窗已经打开且是同一个群组，追加到列表
  if (pendingRequestsReminder.value.visible && pendingRequestsReminder.value.groupId === groupId) {
    const exists = pendingRequestsReminder.value.requests.some(r => r.id === requestItem.id)
    if (!exists) {
      pendingRequestsReminder.value.requests.unshift(requestItem)
    }
  } else {
    // 打开新弹窗
    pendingRequestsReminder.value = {
      visible: true,
      groupId: groupId,
      groupName: event.group_name || '群组',
      requests: [requestItem],
    }
  }
}
```

#### 2.3 优化进入群聊检查

修改了 `selectConversation` 函数，确保只有群主/管理员才会看到提醒：

```javascript
// Check for pending join requests when entering a group chat
if (conv.conversation_type === 'group') {
  // 延迟检查，等待群组详情加载后再判断权限
  nextTick(() => {
    // 只有在用户是群主或管理员时才检查待审核申请
    const isAdmin = ['owner', 'admin'].includes(conv.viewer_role)
    if (isAdmin) {
      checkPendingRequestsReminder(conv.group_id)
    }
  })
}
```

#### 2.4 改进提醒检查逻辑

优化了 `checkPendingRequestsReminder` 函数，移动了 snooze 检查的位置，并添加了日志：

```javascript
async function checkPendingRequestsReminder(groupId) {
  if (!groupId) return

  try {
    const r = await fetch(`/api/messages/groups/${groupId}/join-requests/?status=pending`)
    if (!r.ok) return
    const d = await r.json()
    const requests = d.requests || []
    if (requests.length === 0) return

    // 检查是否暂停提醒
    if (isReminderSnoozed(groupId)) {
      console.log(`群组 ${groupId} 的提醒已暂停`)
      return
    }

    const conv = findConversationByKey(`group:${groupId}`)
    pendingRequestsReminder.value = {
      visible: true,
      groupId: groupId,
      groupName: conv?.username || '群组',
      requests: requests.slice(0, 3),
    }
  } catch (e) {
    console.error('检查待审核申请失败:', e)
  }
}
```

## 功能特性

### 1. 权限控制

- **只有群主和管理员**才会收到加入申请通知
- 在对话列表中通过 `viewer_role` 字段判断用户权限
- 实时推送只发送给有管理权限的成员

### 2. 通知触发时机

**场景 A：进入群聊时**
- 群主/管理员点击群对话
- 系统检查是否有待审核申请
- 如果有且未被暂停提醒，弹出提醒窗口

**场景 B：实时收到申请时**
- 用户提交加入申请
- 后端通过 WebSocket 推送给所有群主/管理员
- 如果管理员正在查看该群聊，立即弹窗
- 否则显示桌面消息通知

### 3. 弹窗功能

弹窗提供以下功能：

1. **显示申请详情**
   - 申请人头像和用户名
   - 申请留言
   - 申请时间

2. **快速审批操作**
   - ✅ 通过按钮 - 直接批准加入
   - ❌ 拒绝按钮 - 需填写拒绝原因

3. **暂停提醒选项**
   - 24小时内不再提醒
   - 7天内不再提醒
   - 基于 localStorage 存储

4. **智能合并**
   - 如果弹窗已打开，新申请会追加到列表顶部
   - 审批后自动从列表移除
   - 列表为空时自动关闭弹窗

### 4. 状态同步

- 审批操作后，同步更新"待审核"标签的计数
- 实时刷新群组详情
- 更新对话列表

## 用户体验流程

### 流程 1：进入群聊时的提醒

```
用户（群主/管理员）
  ↓
点击群对话
  ↓
系统检查待审核申请
  ↓
有待审核 → 弹窗提醒（显示前3个）
无待审核 → 正常进入聊天
```

### 流程 2：实时收到申请时的提醒

```
普通用户提交加入申请
  ↓
后端保存申请记录
  ↓
通过 WebSocket 推送给所有群主/管理员
  ↓
管理员正在查看该群 → 立即弹窗
管理员在其他页面 → 显示消息通知
```

### 流程 3：审批操作

```
管理员在弹窗中点击"通过"/"拒绝"
  ↓
调用后端 API 处理申请
  ↓
成功 → 从弹窗列表移除该申请
       刷新待审核数量
       通知申请人结果
  ↓
列表为空 → 自动关闭弹窗
列表还有 → 继续显示
```

## 技术亮点

1. **实时性** - 使用 WebSocket 实现秒级通知推送
2. **权限安全** - 严格限制只有管理员才能看到和处理申请
3. **用户体验** - 支持暂停提醒，避免过度打扰
4. **状态一致性** - 多处状态（弹窗、标签、对话列表）自动同步
5. **错误处理** - 完善的异常捕获和日志记录

## 测试建议

### 测试场景 1：进入群聊时的弹窗

1. 作为普通用户，向群组提交加入申请
2. 作为群主/管理员，点击该群对话
3. **预期结果**：自动弹出待审核提醒窗口

### 测试场景 2：实时推送通知

1. 群主/管理员已登录并打开私信页面
2. 另一个用户提交加入申请
3. **预期结果**：
   - 如果管理员正在查看该群，立即弹窗
   - 如果管理员在其他页面，显示消息提示
   - "待审核"标签的计数自动增加

### 测试场景 3：审批操作

1. 在弹窗中点击"通过"按钮
2. **预期结果**：
   - 该申请从列表移除
   - 申请人收到通过通知
   - 待审核数量减1

### 测试场景 4：暂停提醒

1. 点击"24小时内不再提醒"
2. 关闭弹窗后重新进入该群
3. **预期结果**：不再弹出提醒（控制台有日志）

### 测试场景 5：权限控制

1. 作为普通成员进入群聊
2. **预期结果**：不会检查或显示待审核提醒

## 文件修改清单

### 后端文件
- `messaging/consumers.py` - 添加 `group_join_request` 事件处理
- `message_groups/views/join_requests.py` - 添加实时 WebSocket 推送

### 前端文件
- `frontend/src/components/messages/MessagesApp/index.vue` - 主要修改
  - 添加 `group_join_request` 事件处理
  - 新增 `showJoinRequestNotification` 函数
  - 优化 `selectConversation` 权限检查
  - 改进 `checkPendingRequestsReminder` 逻辑

## 注意事项

1. **WebSocket 连接**
   - 确保 WebSocket 服务正常运行
   - 检查 `channels` 配置正确

2. **权限判断**
   - `viewer_role` 字段必须正确返回
   - 对话列表 API 需要包含角色信息

3. **暂停提醒**
   - 基于 localStorage，清除浏览器数据会重置
   - 跨设备不同步

4. **性能考虑**
   - 待审核列表限制显示前3个
   - API 查询结果已限制最多100条

## 未来改进方向

1. **浏览器原生通知**
   - 添加 Notification API 支持
   - 即使在其他标签页也能收到通知

2. **声音提醒**
   - 可选的声音提示
   - 设置页面中可配置

3. **批量审批**
   - 支持全部通过/拒绝
   - 提高处理效率

4. **审批历史**
   - 查看已处理的申请记录
   - 支持撤销操作

5. **自定义提醒策略**
   - 允许设置自动批准规则
   - 黑白名单机制
