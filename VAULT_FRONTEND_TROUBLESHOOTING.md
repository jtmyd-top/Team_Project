# 前端保险柜菜单不显示 - 解决指南

**问题**: 右键菜单中没有看到"加入保险柜"选项
**原因**: 前端需要重新编译/刷新

---

## 快速解决方案

### 方案 A: 清除浏览器缓存（立即生效）

**在浏览器中执行：**

1. **按下**: `Ctrl + Shift + Delete`
   - 打开清除浏览数据对话框

2. **选择**:
   - 时间范围: "全部时间"
   - 勾选: "缓存", "Cookie", "已存储的网站数据"
   - 取消勾选: 其他选项

3. **点击**: "清除数据"

4. **关闭浏览器完全重启**

5. **重新打开网站**

**或者使用硬刷新:**

- Windows/Linux: `Ctrl + Shift + R`
- Mac: `Command + Shift + R`

---

### 方案 B: 重新构建前端（完整解决）

**在终端/命令行执行：**

```bash
# 进入前端目录
cd frontend

# 安装依赖（如果未安装）
npm install

# 构建前端（生成最新的 dist 文件）
npm run build
```

**预期输出：**
```
✓ 1234 modules transformed
dist/index.html                    5.12 kb
dist/assets/index-abc123.js       250.15 kb
dist/assets/index-def456.css       45.32 kb

✓ built in 15.23s
```

然后刷新浏览器，应该能看到新的菜单项。

---

### 方案 C: 如果使用开发服务器（npm run dev）

**检查开发服务器状态：**

```bash
# 在前端目录运行
cd frontend
npm run dev
```

**应该看到：**
```
  VITE v5.0.0  ready in 245 ms

  ➜  Local:   http://localhost:5173/
  ➜  press h to show help
```

**然后：**

1. 打开浏览器开发者工具 (F12)
2. 进入 "Console" 标签
3. 执行: `location.reload(true)` 硬刷新
4. 或者直接按 `Ctrl + Shift + R`

---

## 验证代码已正确修改

**所有修改已确认存在：**

✅ NoteContextMenu.vue 第 40 行:
```vue
<div class="menu-item" @click="handleAction('toggle-secret')">
```

✅ NoteContextMenu.vue 第 41-42 行:
```vue
<i class="fas" :class="note?.is_secret ? 'fa-unlock' : 'fa-lock'"></i>
<span>{{ note?.is_secret ? '移出保险柜' : '加入保险柜' }}</span>
```

✅ SecondaryPanel.vue 有处理函数:
```javascript
case 'toggle-secret':
  handleToggleSecret(note)
  break
```

✅ SecondaryPanel.vue 有 API 调用函数:
```javascript
async function handleToggleSecret(note) {
  // ... 完整实现 ...
}
```

---

## 检查清单

进行以下检查以确保一切正常：

- [ ] 已清除浏览器缓存
- [ ] 已硬刷新页面 (Ctrl + Shift + R)
- [ ] 浏览器开发者工具 (F12) → Console 无红色错误
- [ ] 右键点击笔记，菜单出现
- [ ] 菜单中看到"加入保险柜" 或 "移出保险柜" 选项

---

## 如果仍未显示

**请按以下步骤调试：**

### 1. 检查菜单是否显示

```javascript
// 在浏览器 Console 执行
document.querySelectorAll('.menu-item')
```

应该看到多个菜单项。如果只看到几个，说明代码可能没有加载。

### 2. 检查网络请求

打开开发者工具 → Network 标签 → 刷新页面
- 查找 `NoteContextMenu.vue` 相关的 JS 文件
- 查看 Response 中是否包含 `toggle-secret`

### 3. 检查控制台错误

开发者工具 → Console 标签
- 有无红色错误信息？
- 有无黄色警告？

---

## 最后手段

如果上述方法都不行，执行完整清理：

```bash
# 1. 删除 node_modules
cd frontend
rm -rf node_modules

# 2. 删除 lock 文件
rm package-lock.json

# 3. 重新安装依赖
npm install

# 4. 重新构建
npm run build

# 5. 返回项目目录
cd ..
```

然后清除浏览器缓存并硬刷新。

---

## 预期效果

修复后，右键点击任何笔记应该看到：

```
┌─────────────────────────┐
│ 新建笔记                │
├─────────────────────────┤
│ 重命名          F2      │
│ 添加收藏                │
├─────────────────────────┤
│ 加入保险柜       🔒      │  ← 新增菜单项
├─────────────────────────┤
│ 移动到...               │
│ 复制到...               │
├─────────────────────────┤
│ 复制链接                │
│ 在新标签页打开          │
├─────────────────────────┤
│ 移入回收站              │
└─────────────────────────┘
```

---

## 需要帮助？

如果问题仍未解决，请提供：

1. 浏览器控制台中的错误信息截图
2. `npm run build` 的输出信息
3. 网络请求中 NoteContextMenu 相关文件的响应内容

---

**文档版本**: 1.0
**最后更新**: 2026-01-25
