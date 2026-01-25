# Django + Vue 保密柜「端到端加密」实现方案

**备份状态**: ✅ 已完成 (2026-01-25 20:02)
**备份位置**: `backups/backup_knowledge_project_20260125_200238/`
**备份文件**:
- knowledge_project_dump.sql (166K) - MySQL 完整备份
- knowledge_project_fixtures.json (7.2K) - Django fixtures
- BACKUP_INFO.json - 备份信息

**Phase 1 实现完成**: ✅ 2026-01-25 (Backend Infrastructure)
**实现内容**:
- 创建 VaultEncryption 类: knowledge_project/utils/vault_crypto.py
- 实现信封加密逻辑: AES-256-CBC + PKCS7 padding
- Profile 模型新增字段: encrypted_vault_key, vault_key_iv, vault_initialized
- 数据库迁移: knowledge_project/migrations/0011_profile_encrypted_vault_key_and_more.py
- API 端点实现:
  - POST /api/vault/init/ - 初始化保险柜 (生成 DEK)
  - POST /api/vault/verify/ - 增强验证端点 (返回 DEK + Redis session)
  - GET /api/vault/key/ - 无感恢复密钥 (通过 Redis session)
  - POST /api/vault/export/ - 导出加密备份 (JSON 格式)
  - POST /api/notes/{id}/decrypt/ - 解密笔记内容

**Phase 2 实现完成**: ✅ 2026-01-25 (Frontend Integration)
**实现内容**:
- useVaultEncryption Composable: 密钥管理和 API 调用
- VaultInitDialog.vue: 保险柜初始化对话框
- EncryptedNoteContent.vue: 自动解密显示组件
- EncryptedNoteEditor.vue: 加密切换和编辑组件
- note_decrypt() 后端端点: 笔记解密服务
- 完整的集成指南文档

---

## 📋 实现阶段

### Phase 1: 后端基础设施 (Django)
- [x] 1.1 安装加密库 (cryptography >= 41.0.0)
- [x] 1.2 添加 .env 配置 (VAULT_KEK=TkGduAY/6e1skN+ZvWY7RoLzAsOE6W9E2LPxj7hB/no=)
- [x] 1.3 创建加密工具模块 (knowledge_project/utils/vault_crypto.py)
- [x] 1.4 修改 Profile 模型 (添加 encrypted_vault_key, vault_key_iv, vault_initialized)
- [x] 1.5 实现 vault API 接口 (init, get_key, export + 增强 verify)

### Phase 2: 前端集成 (Vue)
- [x] 2.1 创建加密工具库 (useVaultEncryption.js)
- [x] 2.2 修改笔记编辑器 (EncryptedNoteEditor.vue)
- [x] 2.3 实现密钥获取逻辑 (在 Composable 中)
- [x] 2.4 实现自动解密 (EncryptedNoteContent.vue)

### Phase 3: 数据迁移
- [ ] 3.1 创建迁移脚本
- [ ] 3.2 执行数据加密
- [ ] 3.3 验证数据完整性

### Phase 4: 测试与验证
- [ ] 4.1 功能测试
- [ ] 4.2 安全测试
- [ ] 4.3 性能测试

---

## 🔐 密钥体系设计

```
Layer 1: 密钥加密密钥 (KEK - Key Encryption Key)
   |
   +-- 来源: os.environ['VAULT_MASTER_KEY'] 或 config
   +-- 长度: 32字节 (256位)
   +-- 存储: 仅在内存中，不入库
   +-- 用途: 加密 Master Key

Layer 2: 数据加密密钥 (DEK - Data Encryption Key)
   |
   +-- 生成: 每用户一个随机 32字节密钥
   +-- 存储: AES_Encrypt(Master_Key, KEK) 在 DB
   +-- 用途: 加密笔记内容和标题

Layer 3: 数据
   |
   +-- 标题: AES_Encrypt(title, Master_Key)
   +-- 内容: AES_Encrypt(content, Master_Key)
   +-- 存储: Base64 编码的密文 (UTF-8)
```

---

## 💾 数据库字段设计

### UserProfile 新增字段

```python
# models.py
class UserProfile(models.Model):
    # ... 现有字段 ...

    # 加密相关字段
    encrypted_vault_key = models.BinaryField(
        null=True,
        blank=True,
        verbose_name="加密保险柜密钥"
        help_text="Base64编码的AES加密密钥，用KEK加密"
    )
    vault_key_iv = models.BinaryField(
        null=True,
        blank=True,
        verbose_name="IV向量",
        help_text="加密用的初始化向量"
    )
    vault_initialized = models.BooleanField(
        default=False,
        verbose_name="保险柜已初始化"
    )
```

### Note 字段说明

```python
# models.py - Note 模型
class Note(models.Model):
    # ... 现有字段 ...

    # is_secret=True 时:
    # - title: Base64(AES_Encrypt(title, Master_Key))
    # - content: Base64(AES_Encrypt(content, Master_Key))
    #
    # is_secret=False 时:
    # - title: 明文
    # - content: 明文（仍使用 TinyMCE 富文本）
```

---

## 🔌 API 接口设计

### 1. POST /api/vault/init/
**用途**: 初始化用户保险柜，生成 Master Key

**请求**: None

**响应**:
```json
{
  "status": "success",
  "message": "Vault initialized",
  "vault_initialized": true
}
```

**逻辑**:
1. 检查用户是否已初始化
2. 生成随机 32字节 Master Key
3. 用 KEK 加密 Master Key
4. 保存到 UserProfile.encrypted_vault_key
5. 返回成功响应

---

### 2. POST /api/vault/verify/
**用途**: 验证 2FA 后获取 Master Key

**请求**:
```json
{
  "code": "123456",
  "use_backup": false
}
```

**响应**:
```json
{
  "status": "success",
  "master_key": "base64_encoded_key",
  "expire_time": 1800,
  "message": "2FA verified"
}
```

**逻辑**:
1. 验证 2FA（调用现有的 vault verify API）
2. 验证成功后：
   - 用 KEK 解密 encrypted_vault_key 得到 Master Key
   - 返回 Base64 编码的 Master Key 给前端
   - 在 Redis 中写入 vault_session:{user_id} (TTL: 1800s)
3. 返回响应

---

### 3. GET /api/vault/key/
**用途**: 无感恢复 Master Key（浏览器刷新后）

**请求**: None

**响应**:
```json
{
  "status": "success",
  "master_key": "base64_encoded_key",
  "expire_time": 1800
}
```

**逻辑**:
1. 检查 Redis 中是否有有效的 vault_session:{user_id}
2. 如果有且未过期：
   - 用 KEK 解密得到 Master Key
   - 返回给前端
   - 刷新 Redis TTL
3. 如果无或已过期：返回 403 Forbidden

---

### 4. POST /api/vault/export/
**用途**: 导出加密数据备份

**请求**:
```json
{
  "format": "json",  // 或 "csv"
  "include": ["title", "content", "created_at", "updated_at"]
}
```

**响应**:
```json
{
  "status": "success",
  "file_url": "/media/backups/vault_export_uuid.json",
  "created_at": "2026-01-25T20:02:38Z"
}
```

**逻辑**:
1. 获取用户所有 is_secret=True 的笔记
2. 以原始密文形式导出（不解密）
3. 生成 ZIP 或 JSON 文件
4. 返回下载链接

---

## 🔑 KEK 配置

在 `.env` 中添加：

```env
# 保险柜主密钥（必须是 32 字节的 Base64 编码）
# 生成方法: python -c "import os; import base64; print(base64.b64encode(os.urandom(32)).decode())"
VAULT_MASTER_KEY=your_base64_encoded_32_bytes_key_here

# 或者使用文件路径
VAULT_KEY_FILE=/etc/app/vault.key
```

**生成密钥**:
```bash
python -c "import os; import base64; print(base64.b64encode(os.urandom(32)).decode())"
```

---

## 📦 依赖库

在 `requirements.txt` 中添加：

```
cryptography>=41.0.0
```

安装:
```bash
pip install -r requirements.txt
```

---

## 📝 实现步骤

### Step 1: 创建加密工具模块

**文件**: `knowledge_project/utils/vault_crypto.py`

```python
import os
import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

class VaultEncryption:
    """保险柜加密工具"""

    @staticmethod
    def get_kek():
        """获取密钥加密密钥"""
        kek_str = os.getenv('VAULT_MASTER_KEY')
        if not kek_str:
            raise ValueError("VAULT_MASTER_KEY not set in environment")
        return base64.b64decode(kek_str)

    @staticmethod
    def encrypt_dek(dek):
        """用 KEK 加密数据加密密钥"""
        kek = VaultEncryption.get_kek()
        iv = os.urandom(16)
        cipher = Cipher(algorithms.AES(kek), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()

        # 添加 PKCS7 padding
        padding_len = 16 - (len(dek) % 16)
        padded_dek = dek + bytes([padding_len] * padding_len)

        ciphertext = encryptor.update(padded_dek) + encryptor.finalize()

        return base64.b64encode(ciphertext).decode(), base64.b64encode(iv).decode()

    @staticmethod
    def decrypt_dek(encrypted_dek_b64, iv_b64):
        """用 KEK 解密数据加密密钥"""
        kek = VaultEncryption.get_kek()
        ciphertext = base64.b64decode(encrypted_dek_b64)
        iv = base64.b64decode(iv_b64)

        cipher = Cipher(algorithms.AES(kek), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        padded_dek = decryptor.update(ciphertext) + decryptor.finalize()

        # 移除 PKCS7 padding
        padding_len = padded_dek[-1]
        dek = padded_dek[:-padding_len]

        return dek

    @staticmethod
    def encrypt_data(plaintext, dek):
        """用 DEK 加密数据"""
        iv = os.urandom(16)
        cipher = Cipher(algorithms.AES(dek), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()

        # 字符串转字节
        if isinstance(plaintext, str):
            plaintext = plaintext.encode('utf-8')

        # PKCS7 padding
        padding_len = 16 - (len(plaintext) % 16)
        padded = plaintext + bytes([padding_len] * padding_len)

        ciphertext = encryptor.update(padded) + encryptor.finalize()

        # 返回: iv||ciphertext (base64编码)
        return base64.b64encode(iv + ciphertext).decode()

    @staticmethod
    def decrypt_data(ciphertext_b64, dek):
        """用 DEK 解密数据"""
        data = base64.b64decode(ciphertext_b64)

        # 前16字节是 IV
        iv = data[:16]
        ciphertext = data[16:]

        cipher = Cipher(algorithms.AES(dek), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()

        padded = decryptor.update(ciphertext) + decryptor.finalize()

        # 移除 padding
        padding_len = padded[-1]
        plaintext = padded[:-padding_len]

        return plaintext.decode('utf-8')
```

---

### Step 2: 修改 UserProfile 模型

**文件**: `knowledge_project/models.py`

```python
class UserProfile(models.Model):
    # ... 现有字段 ...

    # Vault encryption fields
    encrypted_vault_key = models.TextField(
        null=True,
        blank=True,
        help_text="Base64 encoded encrypted DEK"
    )
    vault_key_iv = models.TextField(
        null=True,
        blank=True,
        help_text="Base64 encoded IV for DEK encryption"
    )
    vault_initialized = models.BooleanField(
        default=False,
        help_text="Whether vault has been initialized"
    )
```

然后创建迁移:
```bash
python manage.py makemigrations
python manage.py migrate
```

---

### Step 3: 实现 API 接口

**文件**: `knowledge_project/views.py`

[详细 API 实现代码见下文]

---

### Step 4: 前端密钥管理

**文件**: `frontend/src/composables/useVaultEncryption.js`

```javascript
import { ref } from 'vue'

export function useVaultEncryption() {
  const masterKey = ref(null)
  const keyExpireTime = ref(null)

  const getMasterKey = async () => {
    // 如果已有密钥且未过期
    if (masterKey.value && keyExpireTime.value > Date.now()) {
      return masterKey.value
    }

    // 尝试无感恢复
    try {
      const response = await fetch('/api/vault/key/')
      if (response.ok) {
        const data = await response.json()
        masterKey.value = data.master_key
        keyExpireTime.value = Date.now() + (data.expire_time * 1000)
        return masterKey.value
      }
    } catch (e) {
      console.warn('Silent recovery failed:', e)
    }

    // 需要 2FA
    return null
  }

  const requestMasterKey = async () => {
    // 打开 2FA 验证对话框
    // 验证成功后设置 masterKey
  }

  const encrypt = (plaintext) => {
    // 前端使用 TweetNaCl 或 libsodium.js
    // 这里只是调用后端返回的加密结果
  }

  const decrypt = (ciphertext) => {
    // 前端使用 TweetNaCl 或 libsodium.js
    // 用 masterKey 解密
  }

  return {
    masterKey,
    getMasterKey,
    requestMasterKey,
    encrypt,
    decrypt
  }
}
```

---

## ✅ 验证清单

部署前检查:

- [ ] KEK 已在 .env 中配置
- [ ] 依赖库已安装 (cryptography)
- [ ] 数据库迁移已完成
- [ ] API 接口已实现
- [ ] 前端加密库已集成
- [ ] 数据迁移脚本已测试
- [ ] 备份已确认可恢复
- [ ] 2FA 集成已验证

---

## 🚀 下一步

是否继续实现？我可以逐个完成：

1. **立即**: 实现 Phase 1 - 后端基础设施
2. **然后**: 实现 Phase 2 - 前端集成
3. **最后**: 实现 Phase 3 & 4 - 数据迁移和测试

---

**方案版本**: 1.0
**创建时间**: 2026-01-25
**备份确认**: ✅ 已安全备份

