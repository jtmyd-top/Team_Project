# 加密兼容性说明 - 旧新数据混合支持

**日期**: 2026-01-26
**问题**: 旧的后端加密方式与新的前端加密方式不兼容
**解决方案**: 实现双格式兼容解密层

---

## 问题诊断

### 旧数据格式（迁移时使用）

迁移期间使用的是 **后端加密** (`vault_crypto.py`)：

```
算法:    AES-256-CBC
IV:      16字节随机（嵌入在密文中）
填充:    PKCS7
格式:    Base64(IV + ciphertext)
```

**Python实现**:
```python
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

# 加密
iv = secrets.token_bytes(16)
cipher = Cipher(algorithms.AES(dek), modes.CBC(iv))
ciphertext = cipher.encryptor().update(padded_data)
result = base64.b64encode(iv + ciphertext)
```

### 新数据格式（现在使用）

新实现使用 **前端加密** (`crypto-js`)：

```
算法:    AES（crypto-js内部实现）
格式:    CryptoJS序列化格式
```

**JavaScript实现**:
```javascript
import CryptoJS from 'crypto-js'

const encrypted = CryptoJS.AES.encrypt(plaintext, dek)
const ciphertext = encrypted.toString()  // CryptoJS格式
```

### 问题

**两种格式完全不兼容**：
- 旧数据无法用crypto-js解密
- 新数据无法用Python的VaultEncryption解密

---

## 解决方案：双格式兼容层

### 工作流程

```
用户查看加密笔记
    ↓
检查是否为密文
    ↓
尝试前端解密（crypto-js）
    ├─ 成功 ✅ → 返回明文
    │
    └─ 失败 ❌ → 调用后端兼容API
        ↓
    后端识别为旧格式（VaultEncryption）
        ↓
    后端使用 VaultEncryption.decrypt_data() 解密
        ↓
    返回明文给前端
```

### 前端解密流程（NoteShadowViewer.vue）

```javascript
async function decryptNoteContent() {
  try {
    // 1. 首先尝试前端解密（新数据）
    const plaintext = decryptContent(props.content, dek.value)
    return plaintext
  } catch (frontendError) {
    // 2. 如果失败，调用后端兼容API（旧数据）
    const response = await fetch(`/api/notes/{id}/decrypt/`, {
      method: 'POST',
      body: JSON.stringify({ dek: dek.value })
    })
    const plaintext = response.json().content
    return plaintext
  }
}
```

### 后端兼容API（views.py）

新增 `decrypt_note_content_api()` 函数：
- 接收 Base64 编码的 DEK
- 调用 `VaultEncryption.decrypt_data()`
- 返回明文内容

```python
@login_required
@require_http_methods(["POST"])
def decrypt_note_content_api(request, note_id):
    """兼容旧的 VaultEncryption 加密数据"""
    dek_b64 = request.json.get('dek')
    dek = base64.b64decode(dek_b64)
    plaintext = VaultEncryption.decrypt_data(note.content, dek)
    return JsonResponse({'status': 'success', 'content': plaintext})
```

### URL 路由

```python
path('api/notes/<int:note_id>/decrypt/',
     views.decrypt_note_content_api,
     name='decrypt_note_content_api')
```

---

## 使用场景

### 场景1：查看旧的加密笔记（迁移期间加密）

1. 用户点击保险柜中的笔记
2. 前端接收到密文（旧的 VaultEncryption 格式）
3. **前端解密失败** → 自动调用后端API
4. **后端解密成功** → 返回明文
5. 前端显示明文

**日志**:
```
[Vault] Starting decryption process...
[Vault] Frontend decryption failed
[Vault] Content decrypted successfully via backend (legacy format)
```

### 场景2：查看新的加密笔记（现在保存）

1. 用户点击保险柜中的笔记
2. 前端接收到密文（新的 crypto-js 格式）
3. **前端解密成功** → 立即显示明文
4. 不调用后端API

**日志**:
```
[Vault] Starting decryption process...
[Vault] Content decrypted successfully in browser (crypto-js format)
```

### 场景3：编辑旧笔记并重新保存

1. 用户查看旧加密笔记（自动用后端解密）
2. 点击编辑
3. 修改内容后保存
4. **前端自动使用新的加密方式加密**
5. 笔记转换为新格式存储

---

## 向后兼容性表

| 数据格式 | 创建时间 | 加密方式 | 解密方式 |
|---------|---------|---------|---------|
| 旧数据 | 迁移期间 | 后端(VaultEncryption) | 后端API |
| 新数据 | 现在 | 前端(crypto-js) | 前端(crypto-js) |
| 编辑后 | 现在 | 前端(crypto-js) | 前端(crypto-js) |

---

## 数据格式检测

### 前端 `looksLikeEncrypted()` 函数

```javascript
function looksLikeEncrypted(text) {
  // Base64 检查：所有格式都是 Base64
  const base64Regex = /^[A-Za-z0-9+/]*={0,2}$/
  return text.length > 50 && base64Regex.test(text)
}
```

这个函数对两种格式都有效，因为两者都使用 Base64 编码。

### 格式识别方式

在解密失败时，通过 **尝试的顺序** 来识别格式：

1. **首先尝试 crypto-js 解密**
   - 成功 → 是新格式
   - 失败 → 继续

2. **然后尝试后端API解密**
   - 成功 → 是旧格式
   - 失败 → 数据损坏或密钥错误

---

## 错误处理

### 如果两种解密都失败

```
[Vault] Frontend decryption failed
[Vault] Backend decryption also failed
Error: "两种解密方式都失败了。可能是：
  1) 密钥错误
  2) 数据损坏
  3) 数据格式不受支持"
```

**可能原因**：
1. ❌ DEK 过期或无效
2. ❌ 笔记内容被损坏
3. ❌ 使用了完全不同的加密方式

**解决方案**：
- 重新完成 2FA 验证获得新的 DEK
- 检查数据库中内容是否正确
- 如果都不行，笔记可能已损坏

---

## DEK 格式说明

### DEK 的两种形式

1. **Base64 形式**（在网络传输和 API 中）
   ```
   类型: 字符串
   来自: 2FA 验证 API 返回
   用于: 发送给前端 JavaScript、传送到后端API
   示例: "U2FsdGVkX1..." (Base64 字符串)
   ```

2. **字节形式**（在 Python 代码中）
   ```
   类型: bytes (32字节)
   来自: base64.b64decode(dek_base64)
   用于: crypto-js.AES.encrypt() 参数
   示例: b'\x3a\x42...' (32字节)
   ```

### 转换

```python
# Base64 → 字节
dek_bytes = base64.b64decode(dek_b64)

# 字节 → Base64
dek_b64 = base64.b64encode(dek_bytes).decode('utf-8')
```

---

## 未来数据迁移（可选）

### 完全迁移到新格式的方法

如果想要完全废弃旧格式，可以：

1. **创建迁移脚本**
   ```python
   for note in Note.objects.filter(is_secret=True):
       # 使用旧 DEK 解密
       plaintext = VaultEncryption.decrypt_data(note.content, dek)
       # 使用新方式重新加密
       new_ciphertext = CryptoJS.encrypt(plaintext, dek)
       note.content = new_ciphertext
       note.save()
   ```

2. **后期可以删除兼容API**
   - 一段时间后（如3个月）
   - 确认所有旧数据已迁移
   - 删除 `decrypt_note_content_api()`

---

## 测试方法

### 验证旧数据解密

1. 在数据库中找一个 `is_secret=true` 的笔记
2. 打开浏览器 DevTools → Console
3. 完成 2FA 验证获得 DEK
4. 点击该笔记
5. **查看控制台日志**：
   ```
   [Vault] Frontend decryption failed
   [Vault] Content decrypted successfully via backend (legacy format)
   ```
   → 说明兼容层工作正常

### 验证新数据加密

1. 创建新笔记
2. 移到保险柜
3. 编辑并保存
4. 重新打开
5. **查看控制台日志**：
   ```
   [Vault] Content decrypted successfully in browser (crypto-js format)
   ```
   → 说明使用新的加密方式

---

## 总结

| 方面 | 旧方式 | 新方式 | 兼容性 |
|-----|-------|-------|--------|
| 加密位置 | 后端 | 前端 | ⚠️ 需要转换 |
| 加密库 | Python cryptography | crypto-js | ❌ 不兼容 |
| 解密方式 | 后端API | 前端JavaScript | ✅ 自动检测 |
| 数据格式 | Base64(IV+密文) | CryptoJS格式 | ✅ 都是Base64 |
| 运行方式 | 每次都需要后端 | 离线可用 | ✅ 前端优先 |

**现在**：✅ 两种格式都能工作
**未来**：可选择完全迁移到新格式
