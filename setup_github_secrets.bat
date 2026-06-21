@echo off
REM GitHub Token 创建和 Secrets 配置脚本

echo ========================================
echo GitHub Actions Secrets 配置脚本
echo ========================================
echo.

echo 第一步：创建 GitHub Token
echo ----------------------------------------
echo 1. 访问: https://github.com/settings/tokens/new
echo 2. Token name: "Deploy Secrets Manager"
echo 3. Expiration: 90 days (或 No expiration)
echo 4. 勾选以下权限:
echo    [x] repo (完整仓库访问)
echo    [x] workflow (更新 workflows)
echo 5. 点击 "Generate token"
echo 6. 复制生成的 token (格式: ghp_xxxxx)
echo.
echo 按任意键继续...
pause > nul

echo.
echo 第二步：登录 gh CLI
echo ----------------------------------------
gh auth login --with-token
echo.

echo 第三步：设置 Secrets
echo ----------------------------------------
gh secret set DEPLOY_HOST --repo jtmyd-top/Team_Project --body "3xui.03vps.cn"
if errorlevel 1 goto error

gh secret set DEPLOY_USER --repo jtmyd-top/Team_Project --body "root"
if errorlevel 1 goto error

gh secret set DEPLOY_PATH --repo jtmyd-top/Team_Project --body "/opt/Team_Project"
if errorlevel 1 goto error

gh secret set DEPLOY_SERVICE --repo jtmyd-top/Team_Project --body "team-project.service"
if errorlevel 1 goto error

gh secret set DEPLOY_PYTHON --repo jtmyd-top/Team_Project --body "python3"
if errorlevel 1 goto error

echo 正在设置 SSH 私钥...
type "C:\Users\xingrunxie\.ssh\jtmyd.key" | gh secret set DEPLOY_SSH_KEY --repo jtmyd-top/Team_Project
if errorlevel 1 goto error

echo.
echo ========================================
echo ✅ 所有 Secrets 配置成功！
echo ========================================
echo.
echo 现在可以推送代码测试自动部署了：
echo   cd "D:/Team Project/Team_Project"
echo   git add .
echo   git commit -m "feat: enable auto-deploy"
echo   git push origin main
echo.
echo 查看部署状态：
echo   https://github.com/jtmyd-top/Team_Project/actions
echo.
pause
exit /b 0

:error
echo.
echo ========================================
echo ❌ 配置失败！
echo ========================================
echo.
echo 可能的原因：
echo 1. Token 权限不足
echo 2. 网络连接问题
echo 3. 仓库名称错误
echo.
echo 建议：使用网页界面配置更简单
echo https://github.com/jtmyd-top/Team_Project/settings/secrets/actions
echo.
pause
exit /b 1
