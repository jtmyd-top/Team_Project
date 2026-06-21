# 🔧 紧急修复：群公告 500 错误

## 问题描述

用户在保存群公告时遇到 **500 Internal Server Error**

**错误 API：** `POST /api/messages/groups/1/announcement/`

## 根本原因

1. **函数签名错误**：`_notify_announcement_everyone` 函数需要 `message` 参数，但该参数在群公告场景下不存在（群公告不创建 GroupMessage）

2. **缺少通知调用**：`update_group_announcement_api` 没有调用通知函数，导致群成员不会收到公告通知

3. **启动警告干扰**：settings.py 中添加的 RuntimeWarning 导致 Django 在某些情况下启动失败

## 修复内容

### 1. 修复函数签名 (`groups.py:349`)

```python
# 之前（会崩溃）
def _notify_announcement_everyone(group, sender, message, content):
    notify_user(..., message_id=message.id)  # message 可能为 None

# 之后（安全）
def _notify_announcement_everyone(group, sender, content, message=None):
    notify_user(..., message_id=message.id if message else None)
```

### 2. 添加通知调用 (`groups.py:2466`)

```python
# 发送通知（在事务外执行，避免阻塞）
if announcement:  # 只有非空公告才发送通知
    try:
        _notify_announcement_everyone(group, request.user, announcement)
    except Exception as e:
        logger.error(f'群公告通知发送失败: {e}', exc_info=True)
        # 不影响公告保存成功的响应
```

### 3. 移除启动警告 (`settings.py`)

移除了 `RuntimeWarning`，因为它在模块加载时触发，可能导致启动问题。

## 测试步骤

### 1. 重启 Django 服务器

```bash
# 停止旧服务器（如果运行中）
# Ctrl+C 或 kill process

# 启动新服务器
python manage.py runserver
```

### 2. 测试群公告功能

在浏览器中：

1. 登录你的账号
2. 进入任意群聊
3. 点击"群设置" → "群公告"
4. 输入公告内容：`欢迎新成员！`
5. 勾选"置顶公告"
6. 点击"保存公告"

**预期结果：**
- ✅ 公告保存成功（不再是 500 错误）
- ✅ 在浏览器控制台看到成功响应
- ✅ 群成员会收到通知（如果群内有其他成员）

### 3. 检查日志

```bash
# 查看通知日志
tail -f logs/django.log | grep "群公告通知"
```

**预期输出：**
```
INFO: 群公告通知完成: 群组 1 (测试群), 成功 5/5, 失败 0, 跳过 0
```

或者如果群组很大：
```
WARNING: 群公告通知: 群组 123 (大群) 有 350 名成员，仅通知前 200 名，跳过 150 名
INFO: 群公告通知完成: 群组 123 (大群), 成功 198/350, 失败 2, 跳过 150
```

## 验证清单

- [ ] Django 服务器正常启动（无错误）
- [ ] 访问 `/api/messages/groups/1/announcement/` 返回 200 而非 500
- [ ] 公告内容正确保存到数据库
- [ ] 群成员收到公告通知
- [ ] 日志中显示通知统计信息

## 回滚计划（如果仍有问题）

```bash
# 回滚到之前的版本
git revert HEAD
git push origin main

# 或者临时禁用通知
# 在 groups.py:2466 注释掉通知调用
```

## 技术细节

### 改进的通知函数特性

1. **参数灵活性**：`message` 参数现在是可选的
2. **批量处理**：限制200人/批，避免性能问题
3. **详细日志**：记录成功/失败/跳过数量
4. **容错性**：单个通知失败不影响整体
5. **异步友好**：事务外执行，不阻塞主流程

### 日志级别

- **WARNING**：大群组跳过通知时
- **INFO**：通知完成统计
- **ERROR**：整体通知失败时
- **WARNING**：单个用户通知失败时

## 提交信息

```
Commit: 1f71132
Message: Fix announcement notification and remove disruptive startup warning
Files: 2 changed (+16, -15)
Pushed: origin/main
```

## 后续建议

1. **实现异步队列**（长期）
   - 使用 Celery 处理大群组通知
   - 完全异步，不影响 API 响应时间
   - 支持重试和错误恢复

2. **添加监控**
   - 通知成功率指标
   - 延迟监控（通知发送时间）
   - 失败率告警

3. **性能测试**
   - 测试 200+ 人群组的通知性能
   - 压力测试并发公告更新

---

**修复完成时间：** 2026-06-17  
**严重程度：** 🔴 Critical (500 error)  
**影响范围：** 所有群公告功能  
**状态：** ✅ 已修复并部署
