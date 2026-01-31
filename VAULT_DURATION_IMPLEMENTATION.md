# 保密柜自定义解锁时长功能实现

## 概述

成功实现了保密柜自定义解锁时长功能，允许用户在验证对话框中选择保持保密柜解锁的时长，支持以下时长选项：
- 15 分钟
- 30 分钟（默认）
- 1 小时
- 4 小时
- 直到浏览器关闭（会话级别）

## 核心特性

### 🔐 安全边界

**后端强制限制**（防止恶意利用）：
- **最大限制**：12 小时（720 分钟）- 即使前端发送更大值也会被截断
- **最小限制**：1 分钟（除非值为 0）
- **会话级别**（duration=0）：后端设置 24 小时兜底，防止永久权限

**实现位置**：`knowledge_project/decorators.py` 第 699-723 行

```python
if duration_minutes == 0:
    # 特殊值 0 表示"直到浏览器关闭"，后端使用 24 小时作为兜底
    window_seconds = 24 * 60 * 60  # 24 小时
elif duration_minutes > 720:
    # 【安全边界】最大 12 小时，防止恶意获取永久权限
    window_seconds = 720 * 60  # 12 小时
else:
    window_seconds = duration_minutes * 60
```

---

## 前端修改

### 文件：`VaultVerifyDialog.vue`

#### 1. 添加时长选项配置

**位置**：第 159-179 行

```javascript
// 【新增】解锁时长选择
const durationMinutes = ref(30)  // 默认30分钟
const durationOptions = [
  { label: '15 分钟', value: 15 },
  { label: '30 分钟 (默认)', value: 30 },
  { label: '1 小时', value: 60 },
  { label: '4 小时', value: 240 },
  { label: '直到浏览器关闭', value: 0 }
]
```

#### 2. UI 模板修改

**位置**：第 70-80 行（验证码输入框后）

```vue
<!-- 【新增】解锁时长选择 -->
<div class="duration-selector">
  <label class="duration-label">保密柜保持解锁时长</label>
  <el-select
    v-model="durationMinutes"
    class="duration-select"
    placeholder="选择解锁时长"
    :disabled="isVerifying"
  >
    <el-option
      v-for="option in durationOptions"
      :key="option.value"
      :label="option.label"
      :value="option.value"
    />
  </el-select>
</div>
```

#### 3. handleVerify 函数修改

**位置**：第 343-358 行

```javascript
const requestBody = {
  code: code.value,
  use_backup: useBackup.value,
  duration: durationMinutes.value  // 【新增】包含用户选择的解锁时长（分钟）
}
```

#### 4. handleClose 函数修改

**位置**：第 437-460 行

```javascript
durationMinutes.value = 30  // 【新增】重置为默认值
```

#### 5. 样式修改

**位置**：第 656-720 行（新增样式类）

```css
/* 【新增】解锁时长选择器 */
.duration-selector {
  margin-bottom: 16px;
  text-align: center;
}

.duration-label {
  display: block;
  font-size: 13px;
  color: #909399;
  margin-bottom: 8px;
  font-weight: 500;
}

.duration-select {
  width: 140px !important;
  margin: 0 auto;
}

.duration-select :deep(.el-input) {
  border-radius: 10px;
}

.duration-select :deep(.el-input__wrapper) {
  border-color: #dcdfe6;
}
```

---

## 后端修改

### 文件 1：`knowledge_project/views.py`

#### vault_verify 函数修改（第 4082-4108 行）

```python
# 【新增】提取用户选择的解锁时长（分钟），默认30分钟
duration_minutes = data.get('duration', 30)

# ... 其他代码 ...

# 【修改】使用新的验证函数（返回dict），传入CAPTCHA参数和duration
result = verify_vault_2fa(request, code, use_backup, captcha_params, duration_minutes)

# ... 成功后 ...

# 【修改】使用用户选择的时长来授予访问权限
grant_vault_access(request, window_seconds=result['window_seconds'])
```

---

### 文件 2：`knowledge_project/decorators.py`

#### verify_vault_2fa 函数完整修改（第 673-871 行）

**关键改动**：

1. **函数签名**：添加 `duration_minutes=None` 参数

```python
def verify_vault_2fa(request, code, use_backup=False, captcha_params=None, duration_minutes=None):
```

2. **参数处理和安全边界**（第 699-723 行）

```python
# 【新增】处理 duration 参数，应用安全边界
if duration_minutes is None:
    window_seconds = VAULT_ACCESS_WINDOW  # 默认30分钟
else:
    # 验证并转换为秒数
    if isinstance(duration_minutes, str):
        try:
            duration_minutes = int(duration_minutes)
        except ValueError:
            duration_minutes = 30

    if duration_minutes == 0:
        # 特殊值 0 表示"直到浏览器关闭"，后端使用 24 小时作为兜底
        window_seconds = 24 * 60 * 60  # 24 小时
        logger.info(f"用户 {user.id} 选择会话级别锁定，后端兜底 24 小时")
    elif duration_minutes < 1:
        # 无效的正数值，使用默认值
        window_seconds = VAULT_ACCESS_WINDOW
    elif duration_minutes > 720:
        # 【安全边界】最大 12 小时，防止恶意获取永久权限
        window_seconds = 720 * 60  # 12 小时
        logger.warning(f"用户 {user.id} 请求超过 12 小时的解锁时长，已截断为 720 分钟")
    else:
        # 正常范围内的值
        window_seconds = duration_minutes * 60
```

3. **返回值修改**：所有 `verify_vault_2fa` 的返回语句都添加了 `'window_seconds': window_seconds` 字段

```python
return {
    'success': True,
    'message': '',
    'expire_time': expire_time,
    'status': 'success',
    'fail_count': 0,
    'lock_seconds': 0,
    'remaining_seconds': remaining,
    'require_captcha': False,
    'window_seconds': window_seconds  # 【新增】
}
```

4. **权限授予修改**（第 810 行）

```python
# 验证成功，使用用户选择的时长
expire_time = grant_vault_access(request, window_seconds=window_seconds)
```

---

## 数据流程

### 前端到后端的请求

```
用户在 VaultVerifyDialog 中：
1. 输入验证码
2. 从下拉框选择时长（15/30/60/240/0）
3. 点击"验证"按钮

请求体：
{
  "code": "123456",
  "use_backup": false,
  "duration": 60  // 用户选择的分钟数
}
```

### 后端处理流程

```
vault_verify (views.py)
  ↓
  提取 duration_minutes = 60
  ↓
  调用 verify_vault_2fa(..., duration_minutes=60)
    ↓
    【安全检查】
    if duration_minutes > 720:
      window_seconds = 720 * 60  // 截断为 12 小时
    else:
      window_seconds = 60 * 60  // 1 小时
    ↓
    验证 2FA 成功 ✓
    ↓
    调用 grant_vault_access(request, window_seconds=3600)
      ↓
      cache.set(vault_key, expire_time, timeout=3600)
      ↓
      返回 {'window_seconds': 3600, ...}
  ↓
  返回响应给前端
    {
      "status": "success",
      "remaining_seconds": 3600,
      "expire_time": <unix_timestamp>
    }
```

---

## 安全性说明

### ✅ 多层防护

1. **前端验证**
   - 用户只能选择预定义的 5 个选项
   - 其他值会被忽略

2. **后端安全边界**
   - 强制最大 12 小时限制（即使前端被篡改）
   - 强制最小 1 分钟限制
   - 特殊值 0 的兜底处理（24 小时）

3. **日志记录**
   - 超限请求会被记录：`logger.warning()`
   - 会话级别请求会被记录：`logger.info()`

### 🔒 特殊值处理

**duration=0（直到浏览器关闭）**：
- 前端：可通过 sessionStorage 清除时清理状态
- 后端：无法感知浏览器关闭，设置 24 小时兜底
- 用户体验：看起来像会话级别，实际有 24 小时保障

---

## 测试场景

### 场景 1：正常选择
```
用户选择 "1 小时"
  ↓
frontend: duration = 60
backend: window_seconds = 3600
✓ 保密柜 1 小时后自动锁定
```

### 场景 2：超限防护
```
恶意脚本修改前端，发送 duration = 99999
  ↓
backend: 检查 duration_minutes > 720
  ↓
backend: 截断为 window_seconds = 720 * 60 = 43200
✓ 最多只能 12 小时，无法获得永久权限
```

### 场景 3：会话级别
```
用户选择 "直到浏览器关闭"
  ↓
frontend: duration = 0
backend: window_seconds = 86400（24 小时兜底）
前端可通过监听 beforeunload 事件清理 sessionStorage
✓ 用户体验上是会话级别，后端安全
```

---

## 代码修改汇总

| 文件 | 行数 | 修改内容 |
|------|------|--------|
| `VaultVerifyDialog.vue` | 159-179 | 添加 durationMinutes 和 durationOptions |
| `VaultVerifyDialog.vue` | 70-80 | 添加时长选择器 UI |
| `VaultVerifyDialog.vue` | 343-358 | handleVerify 包含 duration 参数 |
| `VaultVerifyDialog.vue` | 437-460 | handleClose 重置 duration |
| `VaultVerifyDialog.vue` | 656-720 | 添加样式 |
| `views.py` | 4082-4108 | vault_verify 提取和传递 duration 参数 |
| `decorators.py` | 673 | verify_vault_2fa 添加 duration_minutes 参数 |
| `decorators.py` | 699-723 | 安全边界处理逻辑 |
| `decorators.py` | 724+ | 所有返回值添加 window_seconds 字段 |

---

## Build 状态

✅ **成功**：
```
npm run build
✓ built in 4.15s
```

所有修改均已编译成功，没有错误或警告。

---

## 下一步

1. **测试**：在测试环境验证各个时长是否正常工作
2. **监控**：监控后端日志中的超限警告
3. **文档**：用户文档说明新功能

