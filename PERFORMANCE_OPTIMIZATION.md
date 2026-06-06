# 网站性能优化方案

## 📊 当前性能问题分析

### 1. **静态资源体积过大**
```
Vite 应用包总大小: 2.7MB
- element-plus.js: 878KB
- echarts-vendor.js: 524KB  
- element.css: 333KB
- vendor.js: 142KB
- knowledge-list.js: 144KB
```
此外，`static/` 完整目录约 **81MB**，主要来自第三方资源：FontAwesome 41MB、CKEditor 14MB、TinyMCE 9MB（瘦身方案见下文第 5 节）。

### 2. **数据库查询性能问题**
- ❌ `note.comments.count()` - 每个笔记都执行一次查询（N+1问题）
- ❌ `BeautifulSoup` 在循环中解析HTML - CPU密集型操作
- ❌ 缺少查询结果缓存
- ✅ 已使用 `select_related` 和 `prefetch_related`（部分优化）

### 3. **缓存策略不足**
- ❌ 公开笔记列表API没有缓存
- ❌ 用户头像没有缓存
- ✅ 侧边栏笔记有15分钟缓存

### 4. **网络配置问题**
- ⚠️ Redis在远程服务器 (111.119.192.253) - 网络延迟
- ⚠️ DEBUG=TRUE - 生产环境应该关闭
- ✅ 已启用 WhiteNoise 压缩静态文件

---

## 🚀 优化方案

### **阶段一：立即优化（无需代码改动）**

#### 1.1 关闭DEBUG模式
```bash
# 修改 .env 文件
DEBUG=FALSE
DJANGO_ENV=production
```

#### 1.2 收集静态文件并启用压缩
```bash
python manage.py collectstatic --noinput
```

#### 1.3 配置生产环境变量
```env
# 添加到 .env
ALLOWED_HOSTS=team.03vps.cn,www.team.03vps.cn
CSRF_TRUSTED_ORIGINS=https://team.03vps.cn,https://www.team.03vps.cn
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_SSL_REDIRECT=True
```

#### 1.4 数据库连接池（已实施）
```python
# settings.py
CONN_MAX_AGE = 600          # 连接复用 10 分钟
CONN_HEALTH_CHECKS = True    # 自动检测死连接
```
**预期效果**：减少 50-80% 数据库连接建立时间。

---

### **阶段二：代码优化（中等难度）**

#### 2.1 优化公开笔记API - 添加缓存和查询优化
**问题**: `public_notes_api` 每次都查询数据库，且有N+1查询问题

**优化方案**:
- 添加Redis缓存（5分钟）
- 使用 `annotate` 预计算评论数
- 缓存BeautifulSoup解析结果

#### 2.2 优化前端资源加载
**问题**: Element Plus和ECharts体积过大

**优化方案**:
- 按需导入Element Plus组件
- 使用ECharts按需加载
- 启用代码分割和懒加载

#### 2.3 数据库索引优化
**问题**: 查询可能缺少索引

**优化方案**:
- 为 `Note.is_public` 和 `Note.updated_at` 添加复合索引
- 为 `NoteComment.note_id` 添加索引

#### 2.4 数据库慢查询排查
```bash
cd /opt/Team_Project
source .venv/bin/activate
python manage.py shell
```
```python
from django.db import connection
from django.conf import settings
settings.DEBUG = True          # 临时启用查询日志
# 执行目标视图逻辑后查看：
print(len(connection.queries))  # 查询次数
for q in connection.queries:
    print(f"{q['time']}s: {q['sql'][:100]}")
```
**常见优化**：`select_related()` 消除 N+1、`prefetch_related()` 优化多对多、补充索引。

---

### **阶段三：架构优化（高级）**

#### 3.1 使用CDN加速静态资源
- 将静态文件上传到CDN（阿里云OSS/腾讯云COS）
- 配置Django使用CDN URL

**免费 CDN 选项**：
- Cloudflare（推荐）：自动缓存静态资源、自动压缩
- 又拍云：国内访问快
- 七牛云：有免费额度

**配置方法**：
1. 在 CDN 提供商添加源站：`111.119.192.253:8000`
2. 设置缓存规则：`/static/*` 缓存 1 年
3. 更新 `settings.py`：
```python
STATIC_URL = 'https://cdn.yourdomain.com/static/'
```

#### 3.2 启用HTTP/2和Brotli压缩
- 配置Nginx启用HTTP/2
- 启用Brotli压缩（比Gzip更高效）

#### 3.3 数据库连接池优化
- 配置MySQL连接池
- 启用持久连接（见阶段一 1.4）

#### 3.4 使用本地Redis
- 将Redis部署到本地服务器
- 减少网络延迟
- Redis 连接池参数微调：
```python
# settings.py 中已有，可按并发量微调
'CONNECTION_POOL_KWARGS': {
    'max_connections': 100,
    'socket_keepalive': True,
    'health_check_interval': 30,
}
```

#### 3.5 应用服务器横向扩展（多 Daphne 进程）
当前仅 1 个 Daphne 进程，可启动多个进程并由 Nginx 负载均衡：
```bash
daphne -b 0.0.0.0 -p 8000 Team_Project.asgi:application
daphne -b 0.0.0.0 -p 8001 Team_Project.asgi:application
daphne -b 0.0.0.0 -p 8002 Team_Project.asgi:application
daphne -b 0.0.0.0 -p 8003 Team_Project.asgi:application
```
```nginx
upstream django_app {
    server 127.0.0.1:8000;
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
    server 127.0.0.1:8003;
    keepalive 32;
}
```
> 建议用 systemd 模板单元（`team-project@.service`）或 Supervisor 管理多实例。

#### 3.6 媒体文件加速（X-Accel-Redirect）
在 `.env` 中启用，由 Nginx 直接回源媒体文件、应用只做鉴权：
```bash
USE_X_ACCEL_REDIRECT=true
X_ACCEL_REDIRECT_PREFIX=/internal-media/
```

---

## 🪶 第三方静态资源瘦身（81MB → ~30MB）

### FontAwesome（41MB → ~2MB）
```text
方案 A：使用 CDN
  https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.7.2/css/all.min.css
方案 B：只保留用到的图标子集
```

### CKEditor / TinyMCE（23MB → ~5MB）
- 只保留使用的语言包
- 删除未使用的插件

---

## 📝 实施步骤

### **第一步：立即优化（预计提升30-40%）**
1. 修改 `.env` 文件
2. 重启服务：`sudo systemctl restart team-project.service`
3. 收集静态文件

### **第二步：代码优化（预计提升40-60%）**
1. 优化 `public_notes_api` 函数
2. 添加数据库索引
3. 优化前端资源导入

### **第三步：架构优化（预计提升60-80%）**
1. 配置CDN
2. 优化Nginx配置（Gzip / 缓存 / HTTP2 / 负载均衡）
3. 部署本地Redis

---

## ⚡ 优化优先级（速查）

### 🔥 高优先级（立即执行）
1. ✅ 数据库连接池（已完成）
2. 🔄 Nginx Gzip 压缩（宝塔面板配置）
3. 🔄 静态文件缓存（宝塔面板配置）

### 🔶 中优先级（本周完成）
4. 减少 FontAwesome 体积或使用 CDN
5. 启用 X-Accel-Redirect
6. 检查并优化数据库查询

### 🔷 低优先级（长期优化）
7. 使用 CDN
8. 增加 Daphne 进程数 + 负载均衡
9. 代码层面的性能优化

---

## 🎯 预期效果

| 优化项 | 当前 | 优化后 | 提升 |
|--------|------|--------|------|
| 首页加载时间 | ~3-5秒 | ~1-2秒 | 60% |
| 二次加载时间 | 3-5秒 | 0.5-1秒 | 80% |
| 静态资源大小（应用包） | 2.7MB | ~800KB | 70% |
| 静态资源传输（含第三方） | 81MB | 24MB (Gzip) | 70% |
| API响应时间 | ~500ms | ~100ms | 80% |
| 数据库查询数 | ~50次/页面 | ~10次/页面 | 80% |
| 并发处理能力 | ~10 req/s | 50+ req/s | 400% |

---

## 🧪 测试方法

### 1. 测试 Gzip 是否生效
```bash
curl -I -H "Accept-Encoding: gzip" \
  https://team.03vps.cn/static/fontawesome-free-6.7.2/css/all.min.css
# 查看响应头：Content-Encoding: gzip
```

### 2. 测试缓存是否生效
```bash
curl -I https://team.03vps.cn/static/css/style.css
# 查看响应头：Cache-Control: public, immutable
```

### 3. 测试页面加载速度
- 打开浏览器开发者工具（F12）→ Network 标签
- 刷新页面，查看 DOMContentLoaded 和 Load 时间

---

## ⚠️ 注意事项

1. **备份数据**: 在执行任何优化前，请备份数据库和代码
2. **测试环境**: 建议先在测试环境验证
3. **监控指标**: 使用Django Debug Toolbar监控性能
4. **逐步实施**: 不要一次性应用所有优化
5. **凭据安全**: Redis/数据库密码一律通过 `.env`（已被 .gitignore 忽略）或密钥服务注入，切勿写入文档或仓库

---

## 📚 相关文档

- `OPTIMIZATION_SUMMARY.md` - 优化完成总结与部署/排查步骤
- `NGINX_OPTIMIZATION.md` - Nginx配置详解
- `nginx_bt_optimized.conf` - 宝塔面板可直接套用的 Nginx 配置
- [Django性能优化官方文档](https://docs.djangoproject.com/en/4.2/topics/performance/)
- [WhiteNoise文档](http://whitenoise.evans.io/)
- [Redis缓存最佳实践](https://redis.io/docs/manual/patterns/)
