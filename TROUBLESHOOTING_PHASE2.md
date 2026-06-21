# Phase 2 功能问题排查与修复

## 已修复的问题 ✅

### 1. ✅ MIME 类型错误（Django 模板语法错误）

**错误信息：**
```
Refused to apply style from 'https://192.168.1.6/static/dist/assets/element.css' 
because its MIME type ('text/html') is not a supported stylesheet MIME type
```

**原因：**
`messages.html` 模板中使用了 `{{ realtime_enabled|yesno:"true,false" }}` 会输出字符串 `"True"` 或 `"False"`（首字母大写），导致 JavaScript 解析错误。

**修复方式：**
```django
<!-- 错误写法 -->
enabled: {{ realtime_enabled|yesno:"true,false" }},

<!-- 正确写法 -->
enabled: {% if realtime_enabled %}true{% else %}false{% endif %},
```

**修复文件：** `knowledge_project/templates/messages/messages.html` (第 23 行)

---

## 待验证的功能

### 2. ⚠️ @提及选择器未显示

**可能原因：**
1. 群组成员数据未正确加载
2. `currentGroupMembers` computed 返回空数组
3. 需要先打开"群设置"面板加载成员列表

**诊断步骤：**

#### 步骤 1：检查群组成员数据
打开浏览器开发者工具，在群组对话中执行：
```javascript
// 检查是否是群组对话
console.log('isCurrentGroup:', selectedConversation.value?.conversation_type === 'group')

// 检查群组面板数据
console.log('groupPanel.detail:', groupPanel.value.detail)

// 检查成员列表
console.log('members:', groupPanel.value.detail?.members)
```

#### 步骤 2：测试 @提及触发
1. 在群组对话输入框中输入 `@`
2. 观察浏览器控制台是否有错误
3. 检查 `mentionPicker.value.visible` 是否变为 `true`

#### 步骤 3：手动触发群组信息加载
在输入 `@` 之前，先点击群组对话顶部的"群设置"按钮，这会触发 `openGroupInfo()` 加载成员列表：
```javascript
async function openGroupInfo() {
  // 这个函数会加载 groupPanel.value.detail.members
  const r = await fetch(`/api/messages/groups/${groupId}/`)
  groupPanel.value.detail = d.group // 包含 members 数组
}
```

---

### 3. ⚠️ 录音和附件功能不可用

**已知限制：**
- 录音功能：仅私聊可用，群组暂不支持
- 附件功能：仅私聊可用，群组暂不支持

**验证方法：**
1. 在**私聊对话**中测试录音按钮（应该可以点击）
2. 在**私聊对话**中测试附件按钮（应该可以选择文件）
3. 在**群组对话**中，这两个按钮应该是禁用状态（灰色）

**代码逻辑：**
```vue
<!-- 录音按钮 -->
<button
  class="tool-btn"
  :disabled="isCurrentGroup || isUploadingAttachment || pendingAttachments.length >= maxPendingAttachments"
  @click="toggleVoiceRecording"
  :title="isCurrentGroup ? '群组暂不支持语音' : (isRecordingVoice ? '停止录音' : '语音消息')"
>
  <i :class="isRecordingVoice ? 'fas fa-stop' : 'fas fa-microphone'"></i>
</button>

<!-- 附件按钮 -->
<button
  class="tool-btn"
  :disabled="isCurrentGroup || isUploadingAttachment || pendingAttachments.length >= maxPendingAttachments"
  @click="openFilePicker"
  :title="isCurrentGroup ? '群组暂不支持附件' : '添加图片或文件'"
>
  <i v-if="!isUploadingAttachment" class="fas fa-paperclip"></i>
  <i v-else class="fas fa-spinner fa-spin"></i>
</button>
```

---

## 完整测试流程

### 测试 @提及功能

1. **进入群组对话**
   ```
   导航：私信页面 → 选择一个群组对话
   ```

2. **打开群设置（重要！）**
   ```
   点击：聊天框顶部 → "群设置"按钮（齿轮图标）
   目的：触发加载 groupPanel.value.detail.members
   ```

3. **关闭群设置面板**
   ```
   点击：设置面板右上角的 ×
   ```

4. **输入 @ 字符**
   ```
   焦点：消息输入框
   输入：@
   预期：弹出成员选择器（浮动在输入框上方）
   ```

5. **过滤成员**
   ```
   继续输入：@us
   预期：列表显示包含 "us" 的成员
   ```

6. **选择成员**
   ```
   方式1：点击成员
   方式2：用键盘上下键 + Enter
   预期：输入框中插入 "@username "
   ```

7. **发送消息**
   ```
   输入：其他消息内容
   点击：发送按钮
   预期：后端收到 mentions 数组
   ```

---

### 测试表情回应功能

1. **进入群组对话**
   ```
   必须是群组，私聊不支持表情回应
   ```

2. **悬停在消息上**
   ```
   预期：消息气泡右侧出现"添加表情"按钮（笑脸图标）
   ```

3. **点击"添加表情"**
   ```
   预期：弹出 16 个常用表情选择器
   ```

4. **选择表情**
   ```
   点击：任意表情（如 👍）
   预期：消息下方显示表情 + 数量 "1"，高亮显示（蓝色背景）
   ```

5. **再次点击已添加的表情**
   ```
   预期：表情移除，数量变为 0
   ```

---

### 测试消息引用功能

1. **右键点击任意消息**
   ```
   预期：弹出上下文菜单
   ```

2. **选择"引用"**
   ```
   预期：输入框上方出现引用预览条（显示原消息发送者和内容摘要）
   ```

3. **输入新消息并发送**
   ```
   输入：回复内容
   点击：发送
   预期：新消息上方显示引用的消息预览卡片
   ```

4. **点击引用预览**
   ```
   预期：页面滚动到原消息位置，原消息短暂高亮 2 秒
   ```

---

## 调试命令

### 检查前端构建版本
```bash
cd "D:\Team Project\Team_Project\frontend"
npm run build
```

### 检查静态文件
```bash
ls -lh "D:\Team Project\Team_Project\static\dist\messages.js"
ls -lh "D:\Team Project\Team_Project\static\dist\assets\messages.css"
```

### 清除 Django 缓存
```bash
cd "D:\Team Project\Team_Project"
python manage.py collectstatic --noinput
```

### 重启开发服务器
```bash
python manage.py runserver
```

---

## 浏览器开发者工具调试

### 检查 JavaScript 错误
打开浏览器控制台（F12），查看：
- **Console** 标签：JavaScript 错误
- **Network** 标签：静态资源加载状态
- **Vue Devtools**：组件状态

### 检查关键变量
在 Console 中执行：
```javascript
// 检查群组状态
console.log('isCurrentGroup:', isCurrentGroup.value)
console.log('currentGroupMembers:', currentGroupMembers.value)
console.log('groupPanel.detail:', groupPanel.value.detail)

// 检查 @提及状态
console.log('mentionPicker:', mentionPicker.value)
console.log('mentionedUsers:', mentionedUsers.value)

// 检查消息列表
console.log('messages:', messages.value)
console.log('selectedConversation:', selectedConversation.value)
```

---

## 已知问题和解决方案

### 问题 1：@提及选择器位置不正确
**症状：** 选择器显示在屏幕外或位置不合适

**临时解决方案：**
修改 `handleMentionKeyDown` 函数中的位置计算：
```javascript
const pickerHeight = 320
const pickerX = Math.max(20, rect.left)
const pickerY = rect.top - pickerHeight - 10 // 调整这个偏移量
```

---

### 问题 2：成员列表为空
**症状：** 输入 `@` 后选择器显示"没有找到匹配的成员"

**解决方案：**
1. 确保在输入 `@` 之前打开过"群设置"面板
2. 检查后端 API `/api/messages/groups/<group_id>/` 是否返回 `members` 数组
3. 检查 `currentGroupMembers` computed 是否正确获取数据

**API 请求示例：**
```bash
curl -X GET "http://localhost:8000/api/messages/groups/1/" \
  -H "Cookie: sessionid=YOUR_SESSION_ID"
```

**预期响应：**
```json
{
  "group": {
    "id": 1,
    "name": "测试群组",
    "members": [
      {
        "user_id": 1,
        "username": "user1",
        "avatar": "/static/img/default-avatar.png",
        "role": "owner"
      },
      {
        "user_id": 2,
        "username": "user2",
        "avatar": "/static/img/default-avatar.png",
        "role": "member"
      }
    ]
  }
}
```

---

## 构建信息

**最后构建时间：** 刚刚完成  
**messages.js 大小：** 110.23 KB (gzip: 35.54 KB)  
**messages.css 大小：** 78.94 KB (gzip: 12.14 KB)  
**构建状态：** ✅ 成功

---

## 下一步

如果问题仍然存在，请提供：
1. 浏览器控制台的完整错误信息
2. Network 标签中 `/api/messages/groups/<group_id>/` 的响应内容
3. Vue Devtools 中 `groupPanel.value` 和 `currentGroupMembers.value` 的值

这将帮助我们更精确地定位问题！
