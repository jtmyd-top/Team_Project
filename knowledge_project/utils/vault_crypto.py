"""
保险柜加密工具模块 - 信封加密 (Envelope Encryption) 实现
==========================================================

密钥体系：
- Layer 1: KEK (Key Encryption Key) - 从环境变量读取，用于加密 DEK
- Layer 2: DEK (Data Encryption Key) - 每用户一个随机密钥，用于加密数据

数据流：
1. 用户初始化保险柜 → 生成随机 32 字节 DEK
2. DEK 用 KEK 加密后存入数据库
3. 用户通过 2FA 验证 → 后端解密 DEK，返回给前端
4. 前端用 DEK 加密笔记数据
5. 加密后的数据存入数据库

安全特性：
- 数据库被脱库但没有 KEK，攻击者无法获得 DEK
- 攻击者获得 DEK 但没有 KEK，也无法解密 (DEK 本身是加密的)
- 支持密钥轮换（未来可实现新的 KEK）
"""

import os
import base64
import secrets
from typing import Tuple

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend


class VaultCryptoError(Exception):
    """保险柜加密错误"""
    pass


class VaultEncryption:
    """
    保险柜加密工具类
    实现信封加密的核心逻辑
    """

    # AES block size (always 128 bits)
    BLOCK_SIZE = 16

    @staticmethod
    def get_kek() -> bytes:
        """
        获取密钥加密密钥 (KEK)

        KEK 来源优先级：
        1. VAULT_KEK 环境变量 (优先)
        2. VAULT_KEY_FILE 文件路径
        3. 若都不存在则抛出异常

        Returns:
            bytes: 32 字节的 KEK

        Raises:
            VaultCryptoError: 如果 KEK 未配置或无效
        """
        # 方法 1: 从环境变量读取 Base64 编码的 KEK
        kek_b64 = os.getenv('VAULT_KEK')
        if kek_b64:
            try:
                kek = base64.b64decode(kek_b64)
                if len(kek) != 32:
                    raise VaultCryptoError(
                        f"VAULT_KEK 必须是 32 字节，当前 {len(kek)} 字节"
                    )
                return kek
            except Exception as e:
                raise VaultCryptoError(f"VAULT_KEK 解码失败: {e}")

        # 方法 2: 从文件读取
        key_file = os.getenv('VAULT_KEY_FILE')
        if key_file and os.path.exists(key_file):
            try:
                with open(key_file, 'rb') as f:
                    kek = f.read()
                if len(kek) != 32:
                    raise VaultCryptoError(
                        f"VAULT_KEY_FILE 必须是 32 字节，当前 {len(kek)} 字节"
                    )
                return kek
            except Exception as e:
                raise VaultCryptoError(f"读取 VAULT_KEY_FILE 失败: {e}")

        # 都未配置
        raise VaultCryptoError(
            "VAULT_KEK 或 VAULT_KEY_FILE 未配置。"
            "生成密钥: python -c \"import os, base64; "
            "print(base64.b64encode(os.urandom(32)).decode())\""
        )

    @staticmethod
    def generate_dek() -> bytes:
        """
        生成数据加密密钥 (DEK)

        Returns:
            bytes: 32 字节的随机密钥
        """
        return secrets.token_bytes(32)

    @staticmethod
    def _add_pkcs7_padding(data: bytes, block_size: int = BLOCK_SIZE) -> bytes:
        """
        添加 PKCS7 填充

        Args:
            data: 原始数据
            block_size: 块大小（默认 16 字节）

        Returns:
            bytes: 填充后的数据
        """
        padding_len = block_size - (len(data) % block_size)
        return data + bytes([padding_len] * padding_len)

    @staticmethod
    def _remove_pkcs7_padding(data: bytes) -> bytes:
        """
        移除 PKCS7 填充

        Args:
            data: 填充后的数据

        Returns:
            bytes: 原始数据

        Raises:
            VaultCryptoError: 如果填充无效
        """
        if not data:
            raise VaultCryptoError("数据为空")

        padding_len = data[-1]
        if padding_len > 16 or padding_len == 0:
            raise VaultCryptoError("无效的 PKCS7 填充")

        # 验证填充字节
        if data[-padding_len:] != bytes([padding_len] * padding_len):
            raise VaultCryptoError("填充验证失败")

        return data[:-padding_len]

    @staticmethod
    def encrypt_dek(dek: bytes) -> Tuple[str, str]:
        """
        用 KEK 加密数据加密密钥 (DEK)

        使用 AES-256-CBC 模式：
        - IV: 随机 16 字节
        - 密文: Base64 编码

        Args:
            dek: 32 字节的数据加密密钥

        Returns:
            Tuple[str, str]: (Base64 编码的密文, Base64 编码的 IV)

        Raises:
            VaultCryptoError: 如果加密失败
        """
        try:
            kek = VaultEncryption.get_kek()

            # 生成随机 IV
            iv = secrets.token_bytes(16)

            # AES-256-CBC 加密
            cipher = Cipher(
                algorithms.AES(kek),
                modes.CBC(iv),
                backend=default_backend()
            )
            encryptor = cipher.encryptor()

            # 添加 PKCS7 填充
            padded_dek = VaultEncryption._add_pkcs7_padding(dek)

            # 加密
            ciphertext = encryptor.update(padded_dek) + encryptor.finalize()

            # Base64 编码返回
            ciphertext_b64 = base64.b64encode(ciphertext).decode('utf-8')
            iv_b64 = base64.b64encode(iv).decode('utf-8')

            return ciphertext_b64, iv_b64

        except VaultCryptoError:
            raise
        except Exception as e:
            raise VaultCryptoError(f"DEK 加密失败: {e}")

    @staticmethod
    def decrypt_dek(encrypted_dek_b64: str, iv_b64: str) -> bytes:
        """
        用 KEK 解密数据加密密钥 (DEK)

        Args:
            encrypted_dek_b64: Base64 编码的密文
            iv_b64: Base64 编码的 IV

        Returns:
            bytes: 32 字节的 DEK

        Raises:
            VaultCryptoError: 如果解密失败
        """
        try:
            kek = VaultEncryption.get_kek()

            # 解码
            ciphertext = base64.b64decode(encrypted_dek_b64)
            iv = base64.b64decode(iv_b64)

            # AES-256-CBC 解密
            cipher = Cipher(
                algorithms.AES(kek),
                modes.CBC(iv),
                backend=default_backend()
            )
            decryptor = cipher.decryptor()

            # 解密
            padded_dek = decryptor.update(ciphertext) + decryptor.finalize()

            # 移除 PKCS7 填充
            dek = VaultEncryption._remove_pkcs7_padding(padded_dek)

            if len(dek) != 32:
                raise VaultCryptoError(
                    f"解密后的 DEK 长度无效: {len(dek)}"
                )

            return dek

        except VaultCryptoError:
            raise
        except Exception as e:
            raise VaultCryptoError(f"DEK 解密失败: {e}")

    @staticmethod
    def encrypt_data(plaintext: str, dek: bytes) -> str:
        """
        用 DEK 加密数据 (笔记标题或内容)

        数据格式: Base64(IV + AES_Encrypt(plaintext, DEK))
        - IV: 随机 16 字节
        - 密文: AES-256-CBC 加密

        Args:
            plaintext: 待加密的字符串 (UTF-8)
            dek: 32 字节的 DEK

        Returns:
            str: Base64 编码的 (IV + 密文)

        Raises:
            VaultCryptoError: 如果加密失败
        """
        try:
            # 字符串转字节
            if isinstance(plaintext, str):
                plaintext_bytes = plaintext.encode('utf-8')
            else:
                plaintext_bytes = plaintext

            # 生成随机 IV
            iv = secrets.token_bytes(16)

            # AES-256-CBC 加密
            cipher = Cipher(
                algorithms.AES(dek),
                modes.CBC(iv),
                backend=default_backend()
            )
            encryptor = cipher.encryptor()

            # 添加 PKCS7 填充
            padded_plaintext = VaultEncryption._add_pkcs7_padding(plaintext_bytes)

            # 加密
            ciphertext = encryptor.update(padded_plaintext) + encryptor.finalize()

            # 组合: IV + ciphertext，然后 Base64 编码
            encrypted_data = base64.b64encode(iv + ciphertext).decode('utf-8')

            return encrypted_data

        except Exception as e:
            raise VaultCryptoError(f"数据加密失败: {e}")

    @staticmethod
    def decrypt_data(encrypted_data_b64: str, dek: bytes) -> str:
        """
        用 DEK 解密数据 (笔记标题或内容)

        Args:
            encrypted_data_b64: Base64 编码的 (IV + 密文)
            dek: 32 字节的 DEK

        Returns:
            str: 解密后的原文本

        Raises:
            VaultCryptoError: 如果解密失败
        """
        try:
            # 解码
            encrypted_data = base64.b64decode(encrypted_data_b64)

            if len(encrypted_data) < 16:
                raise VaultCryptoError("加密数据无效（长度不足）")

            # 提取 IV 和密文
            iv = encrypted_data[:16]
            ciphertext = encrypted_data[16:]

            # AES-256-CBC 解密
            cipher = Cipher(
                algorithms.AES(dek),
                modes.CBC(iv),
                backend=default_backend()
            )
            decryptor = cipher.decryptor()

            # 解密
            padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()

            # 移除 PKCS7 填充
            plaintext_bytes = VaultEncryption._remove_pkcs7_padding(padded_plaintext)

            # 字节转字符串
            plaintext = plaintext_bytes.decode('utf-8')

            return plaintext

        except VaultCryptoError:
            raise
        except Exception as e:
            raise VaultCryptoError(f"数据解密失败: {e}")

    @staticmethod
    def encrypt_field(plaintext: str, dek: bytes) -> str:
        """
        加密单个字段 (标题或内容)

        这是一个便利函数，等同于 encrypt_data

        Args:
            plaintext: 原文本
            dek: DEK

        Returns:
            str: 加密后的密文
        """
        return VaultEncryption.encrypt_data(plaintext, dek)

    @staticmethod
    def decrypt_field(ciphertext_b64: str, dek: bytes) -> str:
        """
        解密单个字段 (标题或内容)

        这是一个便利函数，等同于 decrypt_data

        Args:
            ciphertext_b64: 密文
            dek: DEK

        Returns:
            str: 解密后的原文本
        """
        return VaultEncryption.decrypt_data(ciphertext_b64, dek)


# ==================== 测试函数 ====================

def test_encryption():
    """
    测试加密工具
    """
    print("[*] Testing VaultEncryption...")

    try:
        # 生成 DEK
        print("\n[1] Generating DEK...")
        dek = VaultEncryption.generate_dek()
        print(f"    DEK generated: {len(dek)} bytes")

        # 加密 DEK
        print("\n[2] Encrypting DEK with KEK...")
        encrypted_dek_b64, iv_b64 = VaultEncryption.encrypt_dek(dek)
        print(f"    Encrypted DEK: {encrypted_dek_b64[:50]}...")
        print(f"    IV: {iv_b64}")

        # 解密 DEK
        print("\n[3] Decrypting DEK with KEK...")
        decrypted_dek = VaultEncryption.decrypt_dek(encrypted_dek_b64, iv_b64)
        assert decrypted_dek == dek, "DEK mismatch!"
        print(f"    DEK decrypted and verified: OK")

        # 加密数据
        print("\n[4] Encrypting note title...")
        title = "My Secret Note"
        encrypted_title = VaultEncryption.encrypt_data(title, dek)
        print(f"    Original: {title}")
        print(f"    Encrypted: {encrypted_title[:50]}...")

        # 解密数据
        print("\n[5] Decrypting note title...")
        decrypted_title = VaultEncryption.decrypt_data(encrypted_title, dek)
        assert decrypted_title == title, "Title mismatch!"
        print(f"    Decrypted: {decrypted_title}")

        # 加密内容
        print("\n[6] Encrypting note content...")
        content = "This is a very long secret content with special characters: 中文 日本語 한국어"
        encrypted_content = VaultEncryption.encrypt_data(content, dek)
        print(f"    Original length: {len(content)}")
        print(f"    Encrypted: {encrypted_content[:50]}...")

        # 解密内容
        print("\n[7] Decrypting note content...")
        decrypted_content = VaultEncryption.decrypt_data(encrypted_content, dek)
        assert decrypted_content == content, "Content mismatch!"
        print(f"    Decrypted length: {len(decrypted_content)}")
        print(f"    Content OK: {decrypted_content == content}")

        print("\n[OK] All tests passed!")
        return True

    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    import sys
    success = test_encryption()
    sys.exit(0 if success else 1)
