# GitHub Actions 自动部署配置指南

## 问题诊断

当前部署失败的原因：**GitHub Secrets 未配置**

错误信息：`DEPLOY_HOST is required`

## 解决方案

### 方法 1: 通过 GitHub 网页界面配置 (推荐)

1. **访问 GitHub 仓库设置页面**
   - 打开浏览器访问: https://github.com/jtmyd-top/Team_Project/settings/secrets/actions
   - 或者：仓库页面 → Settings → Secrets and variables → Actions

2. **添加以下 Secrets**（点击 "New repository secret"）

   | Secret 名称 | Secret 值 | 说明 |
   |------------|----------|------|
   | `DEPLOY_HOST` | `3xui.03vps.cn` | 服务器地址 |
   | `DEPLOY_USER` | `root` | SSH 用户名 |
   | `DEPLOY_PATH` | `/opt/Team_Project` | 项目部署路径 |
   | `DEPLOY_SERVICE` | `team-project.service` | systemd 服务名称 |
   | `DEPLOY_PYTHON` | `python3` | Python 命令 |
   | `DEPLOY_SSH_KEY` | 见下方 👇 | SSH 私钥 |

3. **配置 SSH 私钥 (DEPLOY_SSH_KEY)**

   **在 Windows PowerShell 中运行：**
   ```powershell
   Get-Content "C:\Users\xingrunxie\.ssh\jtmyd.key" | Set-Clipboard
   ```
   
   然后在 GitHub 页面粘贴（Ctrl+V）

   **或者在 Git Bash 中运行：**
   ```bash
   cat "C:\Users\xingrunxie\.ssh\jtmyd.key"
   ```
   
   然后手动复制整个输出（包括 `-----BEGIN` 和 `-----END` 行）

4. **（可选）添加 known_hosts**

   为了避免首次连接时的 SSH 警告，可以添加 `DEPLOY_KNOWN_HOSTS`：

   ```bash
   ssh-keyscan -H 3xui.03vps.cn
   ```
   
   将输出复制到 GitHub Secrets 的 `DEPLOY_KNOWN_HOSTS`

---

### 方法 2: 使用 GitHub CLI (如果你有足够权限的 token)

```bash
cd "D:/Team Project/Team_Project"

# 设置基本配置
gh secret set DEPLOY_HOST --body "3xui.03vps.cn"
gh secret set DEPLOY_USER --body "root"
gh secret set DEPLOY_PATH --body "/opt/Team_Project"
gh secret set DEPLOY_SERVICE --body "team-project.service"
gh secret set DEPLOY_PYTHON --body "python3"

# 设置 SSH 私钥
gh secret set DEPLOY_SSH_KEY < "C:\Users\xingrunxie\.ssh\jtmyd.key"

# （可选）设置 known_hosts
ssh-keyscan -H 3xui.03vps.cn | gh secret set DEPLOY_KNOWN_HOSTS
```

---

## 自动部署工作流程

配置完成后，每次推送到 `main` 分支时：

```
推送代码到 GitHub
    ↓
GitHub Actions: Django CI
    ├─ 安装依赖
    ├─ 运行测试
    ├─ 编译前端
    └─ ✅ 通过
    ↓
GitHub Actions: Deploy (自动触发)
    ├─ SSH 连接到服务器
    ├─ git pull 最新代码
    ├─ 安装 Python 依赖
    ├─ 编译前端 (npm run build)
    ├─ 数据库迁移 (migrate)
    ├─ 收集静态文件 (collectstatic)
    └─ 重启服务 (systemctl restart)
    ↓
✅ 部署完成
```

---

## 手动触发部署

即使没有推送代码，也可以手动触发部署：

1. 访问: https://github.com/jtmyd-top/Team_Project/actions/workflows/deploy.yml
2. 点击右上角 "Run workflow"
3. 点击绿色 "Run workflow" 按钮

---

## 验证配置

### 1. 检查 Secrets 是否配置成功

访问: https://github.com/jtmyd-top/Team_Project/settings/secrets/actions

应该看到以下 secrets（值会被隐藏）：
- ✅ DEPLOY_HOST
- ✅ DEPLOY_USER
- ✅ DEPLOY_PATH
- ✅ DEPLOY_SERVICE
- ✅ DEPLOY_PYTHON
- ✅ DEPLOY_SSH_KEY
- 🔘 DEPLOY_KNOWN_HOSTS (可选)

### 2. 测试部署

提交一个小改动并推送：

```bash
cd "D:/Team Project/Team_Project"
echo "# Test deploy" >> README.md
git add README.md
git commit -m "test: trigger auto deploy"
git push origin main
```

### 3. 查看部署日志

访问: https://github.com/jtmyd-top/Team_Project/actions

点击最新的 "Deploy" workflow，查看详细日志

---

## 常见问题

### Q1: Deploy workflow 显示 "skipped"
**原因**: Django CI 测试失败，Deploy 不会触发

**解决**: 修复测试错误后重新推送

### Q2: SSH 连接失败 "Permission denied"
**原因**: SSH 私钥不正确或权限不足

**解决**: 
1. 检查 `DEPLOY_SSH_KEY` 是否完整复制（包括头尾）
2. 确认私钥与服务器 `~/.ssh/authorized_keys` 匹配
3. 服务器运行: `cat ~/.ssh/authorized_keys`

### Q3: "Host key verification failed"
**原因**: 首次连接未添加 known_hosts

**解决**: 添加 `DEPLOY_KNOWN_HOSTS` secret（见上方配置步骤）

### Q4: "systemctl: command not found"
**原因**: 非 root 用户没有 systemctl 权限

**解决**: 
- 方法1: 使用 root 用户部署
- 方法2: 修改 deploy.yml 使用 `sudo systemctl`

### Q5: 本地推送没有触发部署
**检查清单**:
1. ✅ 推送到的是 `main` 分支
2. ✅ Django CI workflow 成功完成
3. ✅ 所有 secrets 已配置
4. ✅ GitHub Actions 已启用（仓库 Settings → Actions → General）

---

## 部署流程时间估算

- Django CI (测试): ~4-5 分钟
- Deploy (部署): ~2-3 分钟
- **总计**: 约 6-8 分钟自动完成

---

## 服务器端配置检查

如果自动部署仍有问题，在服务器上检查：

```bash
# SSH 连接到服务器
ssh root@3xui.03vps.cn

# 检查项目路径
ls -la /opt/Team_Project

# 检查 Git 仓库状态
cd /opt/Team_Project
git status
git remote -v

# 检查服务状态
systemctl status team-project.service

# 检查 Python 虚拟环境
ls -la /opt/Team_Project/.venv

# 检查日志
journalctl -u team-project.service -n 50
```

---

## 安全建议

1. **不要泄露 SSH 私钥**: GitHub Secrets 是加密存储的，但不要提交到代码仓库
2. **定期轮换密钥**: 建议每 6-12 个月更换一次 SSH 密钥
3. **限制部署用户权限**: 如果可能，使用专门的部署用户而非 root
4. **启用 2FA**: GitHub 账户启用两步验证
5. **审计日志**: 定期检查 Actions 运行日志

---

## 下一步优化

### 1. 添加部署通知

在 `deploy.yml` 末尾添加通知步骤：

```yaml
- name: Notify deployment success
  if: success()
  run: |
    curl -X POST YOUR_WEBHOOK_URL \
      -H "Content-Type: application/json" \
      -d '{"text":"✅ 部署成功：Team_Project"}'
```

### 2. 添加回滚机制

```yaml
- name: Rollback on failure
  if: failure()
  run: |
    ssh -i ~/.ssh/deploy_key "$DEPLOY_USER@$DEPLOY_HOST" \
      'cd /opt/Team_Project && git reset --hard HEAD~1'
```

### 3. 添加部署前备份

```yaml
- name: Backup database
  run: |
    ssh -i ~/.ssh/deploy_key "$DEPLOY_USER@$DEPLOY_HOST" \
      'mysqldump -u root -p"$DB_PASS" knowledge_project > /backup/db_$(date +%Y%m%d_%H%M%S).sql'
```

---

## 联系支持

如果遇到无法解决的问题：
1. 查看 GitHub Actions 日志
2. 查看服务器 systemd 日志: `journalctl -u team-project.service`
3. 检查 Django 应用日志

---

**配置完成后，你将拥有完全自动化的 CI/CD 流程！** 🎉
