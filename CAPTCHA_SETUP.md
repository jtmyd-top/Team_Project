# 验证码系统配置说明

## 概述

系统现已支持双验证码方案：
1. **Cloudflare Turnstile** - 智能人机验证（主方案）
2. **django-simple-captcha** - 传统图形验证码（备选方案）

## 配置方式

在 `.env` 文件中设置 `CAPTCHA_BACKEND` 参数：

```env
# 验证码方案选择
CAPTCHA_BACKEND=auto  # 可选值: turnstile, simple_captcha, auto

# Turnstile 配置（如果使用）
CLOUDFLARE_TURNSTILE_SITE_KEY=your_site_key
CLOUDFLARE_TURNSTILE_SECRET_KEY=your_secret_key
TURNSTILE_ENABLED=true
```

### 配置选项说明

- **`auto`** (推荐): 自动选择，优先使用 Turnstile，如果未配置则降级到 simple_captcha
- **`turnstile`**: 强制使用 Cloudflare Turnstile
- **`simple_captcha`**: 强制使用 django-simple-captcha

## Admin 登录界面特性

### 现代化设计
- ✨ 浮动光球背景动画
- 🌓 深色/浅色模式切换
- 📱 响应式设计，支持移动端
- 🎨 Material Design 图标
- 🔄 平滑过渡动画

### 安全特性
- 🔐 人机验证（Turnstile 或图形验证码）
- 🛡️ 两因素认证（2FA）
- 🚫 IP 封禁检查
- ❄️ 账户冻结检查

## 验证码工作流程

### Turnstile 模式
1. 页面加载时自动显示 Turnstile 组件
2. 用户完成人机验证
3. 提交表单时自动携带验证令牌

### Simple Captcha 模式
1. 页面加载时通过 AJAX 获取验证码图片
2. 用户输入验证码
3. 点击刷新按钮可重新获取验证码
4. 提交表单时验证输入的验证码

## 前端用户登录

前端登录页面使用的是现有的 `CaptchaWidget` 组件，它已经支持：
- Turnstile 验证
- 自定义图形验证码（ImageCaptcha）
- 自动降级机制

## 测试建议

1. **测试 Turnstile 模式**:
   ```env
   CAPTCHA_BACKEND=turnstile
   CLOUDFLARE_TURNSTILE_SITE_KEY=your_key
   ```
   访问 http://127.0.0.1:8000/admin/

2. **测试 Simple Captcha 模式**:
   ```env
   CAPTCHA_BACKEND=simple_captcha
   ```
   访问 http://127.0.0.1:8000/admin/

3. **测试自动降级**:
   ```env
   CAPTCHA_BACKEND=auto
   # 不设置 TURNSTILE_SITE_KEY，应自动使用 simple_captcha
   ```

## 数据库迁移

django-simple-captcha 需要数据库表，已自动完成迁移：
```bash
python manage.py migrate captcha
```

## 依赖包

已安装的新依赖：
- `django-simple-captcha==0.6.3`
- `django-ranged-response==0.2.0`
- `pillow` (已存在)

## 故障排除

### 验证码图片不显示
- 检查 `/captcha/` URL 是否正确配置
- 确认 Pillow 库已安装
- 查看浏览器控制台是否有 AJAX 错误

### Turnstile 不显示
- 检查 `CLOUDFLARE_TURNSTILE_SITE_KEY` 是否正确
- 确认网络可以访问 Cloudflare CDN
- 查看浏览器控制台是否有加载错误

### 验证码验证失败
- Simple Captcha: 检查验证码是否过期（默认5分钟）
- Turnstile: 检查 SECRET_KEY 是否正确配置
- 查看 Django 日志获取详细错误信息

## 安全建议

1. 生产环境建议使用 Turnstile（更安全，用户体验更好）
2. Simple Captcha 作为备选方案，适用于无法访问 Cloudflare 的环境
3. 定期更新验证码库以获取安全补丁
4. 配合 2FA 使用，提供多层安全保护
