"""保密柜 ECDH 握手工具（方案 C）

消除 /api/vault/verify/ 与 /api/vault/key/ 响应体中 base64 DEK 的明文暴露。

协议：
- 客户端生成 P-256 临时密钥对，发送 SPKI-DER(base64) 公钥
- 服务端生成 P-256 临时密钥对，做 ECDH → HKDF-SHA256(info=b"vault-dek-v1") → 32B wrap_key
- 服务端用 AES-256-GCM(wrap_key, 12B 随机 IV) 封装 DEK
- 响应携带 server_pub / iv / ct（全部 base64）；DEK 明文从不离开服务端

PFS：每次调用都用临时密钥对，完成后即被 GC。

依赖：cryptography>=41（项目已有 43.0.3，支持 X25519/ECDH P-256/HKDF/AESGCM）。
"""
import base64
import os

from cryptography.exceptions import InvalidKey
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


HKDF_INFO = b"vault-dek-v1"
_CURVE = ec.SECP256R1()


class VaultHandshakeError(Exception):
    """握手协议错误（客户端公钥无效、格式错误等）"""


def _derive_wrap_key(shared_secret: bytes) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=HKDF_INFO,
    ).derive(shared_secret)


def wrap_dek_for_client(client_pub_b64: str, dek: bytes) -> dict:
    """用客户端提供的临时公钥对 DEK 做 ECDH 握手包装。

    Args:
        client_pub_b64: 客户端 P-256 临时公钥（SPKI-DER，base64）
        dek: 32 字节 DEK 明文

    Returns:
        dict: {"server_pub": b64, "iv": b64, "ct": b64}

    Raises:
        VaultHandshakeError: 客户端公钥无效、曲线不匹配等
    """
    if not isinstance(client_pub_b64, str) or not client_pub_b64:
        raise VaultHandshakeError("client_pub 缺失")
    if not isinstance(dek, (bytes, bytearray)) or len(dek) != 32:
        raise VaultHandshakeError("DEK 必须是 32 字节")

    try:
        client_pub_der = base64.b64decode(client_pub_b64, validate=True)
    except Exception as e:
        raise VaultHandshakeError(f"client_pub base64 解码失败: {e}")

    try:
        client_pub = serialization.load_der_public_key(client_pub_der)
    except Exception as e:
        raise VaultHandshakeError(f"client_pub SPKI 解析失败: {e}")

    if not isinstance(client_pub, ec.EllipticCurvePublicKey) or \
            client_pub.curve.name != _CURVE.name:
        raise VaultHandshakeError("client_pub 必须是 P-256 ECDH 公钥")

    server_priv = ec.generate_private_key(_CURVE)
    try:
        shared = server_priv.exchange(ec.ECDH(), client_pub)
    except (InvalidKey, ValueError) as e:
        raise VaultHandshakeError(f"ECDH 失败: {e}")

    wrap_key = _derive_wrap_key(shared)
    iv = os.urandom(12)
    ct = AESGCM(wrap_key).encrypt(iv, bytes(dek), associated_data=None)

    server_pub_der = server_priv.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    return {
        "server_pub": base64.b64encode(server_pub_der).decode("ascii"),
        "iv": base64.b64encode(iv).decode("ascii"),
        "ct": base64.b64encode(ct).decode("ascii"),
    }


def _self_test() -> bool:
    """对称自测：客户端侧复现 HKDF + AES-GCM 解密回原 DEK。"""
    import secrets

    client_priv = ec.generate_private_key(_CURVE)
    client_pub_der = client_priv.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    client_pub_b64 = base64.b64encode(client_pub_der).decode("ascii")

    dek = secrets.token_bytes(32)
    wrapped = wrap_dek_for_client(client_pub_b64, dek)

    server_pub = serialization.load_der_public_key(base64.b64decode(wrapped["server_pub"]))
    shared = client_priv.exchange(ec.ECDH(), server_pub)
    wrap_key = _derive_wrap_key(shared)
    iv = base64.b64decode(wrapped["iv"])
    ct = base64.b64decode(wrapped["ct"])
    recovered = AESGCM(wrap_key).decrypt(iv, ct, associated_data=None)

    assert recovered == dek, "DEK 往返不一致"
    print(f"[OK] ECDH handshake self-test passed (DEK {len(recovered)}B)")
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _self_test() else 1)
