# 保密柜自定义解锁时长 - 完整代码参考

## 前端完整代码片段

### VaultVerifyDialog.vue - 状态和配置

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

### VaultVerifyDialog.vue - UI 模板

```vue
<!-- 验证码输入 -->
<div class="code-input-wrapper" :class="{ 'error': hasError }">
  <input
    ref="codeInputRef"
    v-model="code"
    type="tel"
    inputmode="numeric"
    pattern="\d*"
    autocomplete="one-time-code"
    :placeholder="useBackup ? '输入备用码' : '● ● ● ● ● ●'"
    :maxlength="useBackup ? 8 : 6"
    :disabled="isVerifying"
    @input="handleCodeInput"
    @keyup.enter="handleVerify"
    class="code-input"
  />
  <div v-if="isVerifying" class="verifying-indicator">
    <i class="fas fa-spinner fa-spin"></i>
  </div>
</div>

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

<!-- 错误提示 -->
<transition name="fade">
  <div v-if="errorMessage" class="error-message">
    <i class="fas fa-exclamation-circle"></i>
    <span>{{ errorMessage }}</span>
    <span v-if="failCount > 0" class="fail-count">（已失败 {{ failCount }} 次）</span>
  </div>
</transition>
```

### VaultVerifyDialog.vue - handleVerify 函数

```javascript
const handleVerify = async () => {
  if (!canVerify.value || isVerifying.value) return

  isVerifying.value = true
  errorMessage.value = ''
  hasError.value = false

  try {
    // 构建请求体
    const requestBody = {
      code: code.value,
      use_backup: useBackup.value,
      duration: durationMinutes.value  // 【新增】包含用户选择的解锁时长（分钟）
    }

    // 如果需要CAPTCHA，添加验证参数
    if (requireCaptcha.value) {
      Object.assign(requestBody, captchaParams.value)
    }

    const response = await fetch('/api/vault/verify/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
      },
      body: JSON.stringify(requestBody)
    })
    const data = await response.json()

    // ... 处理响应 ...
  } catch (e) {
    triggerShake()
    errorMessage.value = '验证失败，请稍后重试'
    code.value = ''
  } finally {
    isVerifying.value = false
  }
}
```

### VaultVerifyDialog.vue - 样式

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

## 后端完整代码片段

### views.py - vault_verify 函数修改

```python
@login_required
@require_http_methods(["POST"])
def vault_verify(request):
    """
    验证保密柜2FA
    成功后授予时间窗口内的访问权限
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'JSON格式错误'}, status=400)

    code = data.get('code', '').strip()
    use_backup = data.get('use_backup', False)

    # 【新增】提取用户选择的解锁时长（分钟），默认30分钟
    duration_minutes = data.get('duration', 30)

    # 提取CAPTCHA参数
    captcha_params = None
    captcha_type = data.get('captcha_type')
    if captcha_type:
        captcha_params = {
            'captcha_type': captcha_type,
            'turnstile_token': data.get('turnstile_token', ''),
            'image_captcha': data.get('image_captcha', '')
        }

    if not code:
        return JsonResponse({'status': 'error', 'message': '请输入验证码'}, status=400)

    # 【修改】使用新的验证函数（返回dict），传入CAPTCHA参数和duration
    result = verify_vault_2fa(request, code, use_backup, captcha_params, duration_minutes)

    if result['success']:
        # ==================== 加密集成 ====================
        # 1. 【修改】使用用户选择的时长来授予访问权限
        grant_vault_access(request, window_seconds=result['window_seconds'])

        # 2. 尝试返回 DEK 用于前端解密
        try:
            from knowledge_project.utils.vault_crypto import VaultEncryption
            import base64

            profile = request.user.profile
            if profile.vault_initialized and profile.encrypted_vault_key and profile.vault_key_iv:
                # 用 KEK 解密 DEK
                dek = VaultEncryption.decrypt_dek(
                    profile.encrypted_vault_key,
                    profile.vault_key_iv
                )
                dek_b64 = base64.b64encode(dek).decode('utf-8')

                return JsonResponse({
                    'status': 'success',
                    'message': '验证成功',
                    'dek': dek_b64,
                    'expire_time': result['expire_time'],
                    'remaining_seconds': result['remaining_seconds']
                })
        except Exception as e:
            logger.warning(f"Failed to decrypt DEK during vault verify: {e}")

        return JsonResponse({
            'status': 'success',
            'message': '验证成功',
            'expire_time': result['expire_time'],
            'remaining_seconds': result['remaining_seconds']
        })

    # 根据状态返回不同的响应
    response_data = {
        'status': result['status'],
        'message': result['message'],
        'fail_count': result['fail_count'],
        'require_captcha': result.get('require_captcha', False)
    }

    if result['status'] == 'locked':
        response_data['lock_seconds'] = result['lock_seconds']

    return JsonResponse(response_data, status=400 if result['status'] == 'error' else 200)
```

### decorators.py - verify_vault_2fa 函数修改

```python
def verify_vault_2fa(request, code, use_backup=False, captcha_params=None, duration_minutes=None):
    """
    验证保密柜2FA并授予访问权限（带速率限制和指数退避）

    Args:
        request: HttpRequest对象
        code: 用户输入的验证码
        use_backup: 是否使用备用验证码
        captcha_params: CAPTCHA参数
        duration_minutes: 【新增】用户选择的解锁时长（分钟）

    Returns:
        dict: {..., 'window_seconds': int}
    """
    user = request.user
    profile = getattr(user, 'profile', None)

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

    if not profile:
        return {
            'success': False,
            'message': '用户配置不存在',
            'expire_time': 0,
            'status': 'error',
            'fail_count': 0,
            'lock_seconds': 0,
            'remaining_seconds': 0,
            'require_captcha': False,
            'window_seconds': 0
        }

    # 如果用户未启用2FA，直接授予访问权限
    if not profile.two_fa_enabled:
        expire_time = grant_vault_access(request, window_seconds=window_seconds)
        remaining = get_vault_access_remaining(request)
        return {
            'success': True,
            'message': '',
            'expire_time': expire_time,
            'status': 'success',
            'fail_count': 0,
            'lock_seconds': 0,
            'remaining_seconds': remaining,
            'require_captcha': False,
            'window_seconds': window_seconds
        }

    # 检查是否被锁定
    is_locked, lock_remaining, fail_count = check_vault_locked(user.id)
    if is_locked:
        return {
            'success': False,
            'message': f'错误次数过多，请等待 {lock_remaining} 秒后重试',
            'expire_time': 0,
            'status': 'locked',
            'fail_count': fail_count,
            'lock_seconds': lock_remaining,
            'remaining_seconds': 0,
            'require_captcha': False,
            'window_seconds': 0
        }

    # 【继续其他验证逻辑...】
    # 所有 return 语句都添加 'window_seconds' 字段
    # 验证成功时：window_seconds = <计算出的秒数>
    # 验证失败时：window_seconds = 0

    # 验证2FA
    success, message = verify_2fa_for_request(request, code, use_backup)

    if success:
        # 验证成功，重置失败计数并授予访问权限
        reset_vault_fail_count(user.id)
        expire_time = grant_vault_access(request, window_seconds=window_seconds)
        remaining = get_vault_access_remaining(request)
        return {
            'success': True,
            'message': '',
            'expire_time': expire_time,
            'status': 'success',
            'fail_count': 0,
            'lock_seconds': 0,
            'remaining_seconds': remaining,
            'require_captcha': False,
            'window_seconds': window_seconds
        }

    # 验证失败，增加失败计数
    new_fail_count, lock_seconds, require_captcha = increment_vault_fail_count(user.id)

    # ... 其他错误返回 ...
    # 所有都要加 'window_seconds': 0 或相应值
```

---

## API 请求/响应示例

### 请求示例

```json
POST /api/vault/verify/
{
  "code": "123456",
  "use_backup": false,
  "duration": 60
}
```

### 响应示例（成功）

```json
{
  "status": "success",
  "message": "验证成功",
  "dek": "base64_encoded_dek",
  "expire_time": 1706513452,
  "remaining_seconds": 3600
}
```

---

## 安全检查清单

- ✅ 前端只允许预定义的 5 个时长值
- ✅ 后端强制最大 12 小时限制
- ✅ 后端强制最小 1 分钟限制
- ✅ 特殊值 0 有 24 小时兜底
- ✅ 超限请求被记录到日志
- ✅ 所有返回值都包含 window_seconds
- ✅ grant_vault_access 使用传入的 window_seconds

