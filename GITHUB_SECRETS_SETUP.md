# GitHub Secrets 配置 - 复制粘贴指南

## 第一步：打开 GitHub Secrets 设置页面

**直接点击这个链接：**
https://github.com/jtmyd-top/Team_Project/settings/secrets/actions

或者手动导航：
1. 打开 https://github.com/jtmyd-top/Team_Project
2. 点击 Settings 标签
3. 左侧菜单找到 "Secrets and variables" → "Actions"

---

## 第二步：添加以下 6 个 Secrets

对于每个 Secret，点击 "New repository secret" 按钮，然后：

### 1. DEPLOY_HOST
**Name:** `DEPLOY_HOST`  
**Secret:** 
```
3xui.03vps.cn
```

---

### 2. DEPLOY_USER
**Name:** `DEPLOY_USER`  
**Secret:** 
```
root
```

---

### 3. DEPLOY_PATH
**Name:** `DEPLOY_PATH`  
**Secret:** 
```
/opt/Team_Project
```

---

### 4. DEPLOY_SERVICE
**Name:** `DEPLOY_SERVICE`  
**Secret:** 
```
team-project.service
```

---

### 5. DEPLOY_PYTHON
**Name:** `DEPLOY_PYTHON`  
**Secret:** 
```
python3
```

---

### 6. DEPLOY_SSH_KEY (重要！)

**Name:** `DEPLOY_SSH_KEY`

**如何获取 Secret 值：**

#### 方法 A - PowerShell (推荐):
在 PowerShell 中运行下面的命令，会自动复制到剪贴板：
```powershell
Get-Content "C:\Users\xingrunxie\.ssh\jtmyd.key" -Raw | Set-Clipboard
Write-Host "✅ SSH 私钥已复制到剪贴板，现在在 GitHub 页面按 Ctrl+V 粘贴"
```

#### 方法 B - 手动复制:
1. 打开文件: `C:\Users\xingrunxie\.ssh\jtmyd.key`
2. 全选内容 (Ctrl+A)
3. 复制 (Ctrl+C)
4. 在 GitHub Secret 输入框粘贴 (Ctrl+V)

**注意**: 必须包含完整内容，从 `-----BEGIN OPENSSH PRIVATE KEY-----` 到 `-----END OPENSSH PRIVATE KEY-----`

---

## 第三步：验证配置

配置完成后，你应该看到 6 个绿色的 secrets:
- ✅ DEPLOY_HOST
- ✅ DEPLOY_USER  
- ✅ DEPLOY_PATH
- ✅ DEPLOY_SERVICE
- ✅ DEPLOY_PYTHON
- ✅ DEPLOY_SSH_KEY

---

## 第四步：测试自动部署

现在推送代码就会自动部署了！

### 快速测试命令:
```bash
cd "D:/Team Project/Team_Project"
git add .
git commit -m "feat: add group security features and auto-deploy"
git push origin main
```

### 查看部署进度:
https://github.com/jtmyd-top/Team_Project/actions

---

## 常见问题

### Q: 为什么需要这么做？
A: GitHub Secrets 是加密存储的敏感信息，只能通过网页界面或有特殊权限的 API token 设置。你当前的 `gh` token 没有 "secrets" 写入权限。

### Q: 这样安全吗？
A: 非常安全！GitHub Secrets:
- ✅ 加密存储，GitHub 员工也看不到
- ✅ 在日志中自动屏蔽（显示为 `***`）
- ✅ 只有 Actions workflow 可以访问

### Q: SSH 私钥会泄露吗？
A: 不会！私钥只在 GitHub Actions 的临时容器中使用，使用后立即销毁。

---

## 如果你想给 `gh` CLI 添加权限（可选）

如果你以后想用命令行管理 secrets，可以这样做：

1. 访问: https://github.com/settings/tokens
2. 点击 "Generate new token" → "Generate new token (classic)"
3. 勾选以下权限:
   - ✅ `repo` (完整仓库访问)
   - ✅ `workflow` (更新 GitHub Actions workflows)
   - ✅ `admin:org` → `read:org` (如果是组织仓库)
4. 生成 token 并复制
5. 运行: `gh auth login`
6. 选择 "Paste an authentication token"
7. 粘贴你的新 token

但对于一次性配置，直接用网页界面更简单！
