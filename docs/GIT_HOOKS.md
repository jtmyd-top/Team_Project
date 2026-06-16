# Git Pre-commit Hook 使用说明

## 安装

Pre-commit hook 已经安装到 `.git/hooks/pre-commit`

### Windows 用户注意

如果在 Windows 上使用，需要确保 Git Bash 或 WSL 环境。或者使用 Python 版本的 hook：

```bash
# 安装 pre-commit 工具
pip install pre-commit

# 使用 .pre-commit-config.yaml 配置
pre-commit install
```

## 功能

该 hook 会在每次 `git commit` 时自动检查：

1. **防止提交 .env 文件**
   - 阻止 `.env` 文件被提交到仓库
   
2. **扫描敏感信息模式**
   - SECRET_KEY（超过20字符）
   - PASSWORD（超过3字符）
   - API_KEY（超过10字符）
   - PRIVATE_KEY
   - AWS 密钥
   - MySQL 密码
   - Redis 连接字符串（包含密码）

3. **检测大文件**
   - 警告超过 10MB 的文件
   - 建议使用 Git LFS

## 使用

正常执行 `git commit` 即可：

```bash
git add .
git commit -m "提交信息"
```

如果检测到问题，提交会被阻止：

```
❌ 错误: 不允许提交 .env 文件！
❌ 发现可能的敏感信息: SECRET_KEY
❌ 提交被阻止：发现敏感信息
```

## 绕过检查

如果确认是误报，可以跳过检查：

```bash
git commit --no-verify -m "提交信息"
```

**警告：** 仅在确认没有敏感信息时使用 `--no-verify`！

## 更新 Hook

如果需要修改检查规则，编辑 `.git/hooks/pre-commit` 文件。

修改后的 hook 只影响本地仓库。如果需要团队共享，考虑使用 `pre-commit` 工具。

## 团队共享 Hook（可选）

创建 `.pre-commit-config.yaml`：

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: check-added-large-files
        args: ['--maxkb=10240']
      - id: check-yaml
      - id: check-json
      - id: detect-private-key
      - id: trailing-whitespace
      - id: end-of-file-fixer

  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
```

安装并启用：

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files  # 首次运行
```

## 故障排查

### Hook 未执行

```bash
# 检查权限
ls -la .git/hooks/pre-commit

# 如果没有执行权限
chmod +x .git/hooks/pre-commit
```

### Windows 权限问题

```bash
# 使用 Git Bash
bash .git/hooks/pre-commit

# 或者安装 Python 版本
pip install pre-commit
```

## 最佳实践

1. **永远不要提交 .env 文件**
   - 使用 `.env.example` 作为模板
   - 在部署文档中说明配置方法

2. **使用环境变量**
   - 所有密钥、密码都通过环境变量配置
   - 代码中只引用环境变量名

3. **定期审查提交历史**
   ```bash
   git log --all --full-history -- .env
   ```

4. **如果意外提交了敏感信息**
   ```bash
   # 从历史中彻底删除
   git filter-branch --force --index-filter \
     "git rm --cached --ignore-unmatch .env" \
     --prune-empty --tag-name-filter cat -- --all
   
   # 强制推送（需要团队协调）
   git push origin --force --all
   
   # 立即轮换所有暴露的密钥
   ```

## 参考资源

- [Git Hooks 文档](https://git-scm.com/book/en/v2/Customizing-Git-Git-Hooks)
- [Pre-commit 工具](https://pre-commit.com/)
- [Detect Secrets](https://github.com/Yelp/detect-secrets)
