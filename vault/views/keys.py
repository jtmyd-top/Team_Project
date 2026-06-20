"""Vault keys views."""
from .common import *  # noqa: F401, F403


@login_required
@require_http_methods(["POST"])
def vault_init(request):
    """
    初始化保险柜
    生成用户的 DEK（Data Encryption Key）并用 KEK 加密后存入数据库
    """
    from vault.crypto import VaultEncryption

    try:
        profile = request.user.profile

        # 检查是否已初始化
        if profile.vault_initialized:
            return JsonResponse({
                'status': 'error',
                'message': '保险柜已初始化'
            }, status=400)

        # 生成 DEK
        dek = VaultEncryption.generate_dek()

        # 用 KEK 加密 DEK
        encrypted_dek_b64, iv_b64 = VaultEncryption.encrypt_dek(dek)

        # 存入数据库
        profile.encrypted_vault_key = encrypted_dek_b64
        profile.vault_key_iv = iv_b64
        profile.vault_initialized = True
        profile.save(update_fields=['encrypted_vault_key', 'vault_key_iv', 'vault_initialized'])

        return JsonResponse({
            'status': 'success',
            'message': '保险柜初始化成功',
            'vault_initialized': True
        })

    except Exception as e:
        logger.error(f"Vault init error: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': '保险柜初始化失败，请稍后重试'
        }, status=500)

@login_required
@require_http_methods(["POST"])
def vault_get_key(request):
    """
    通过 ECDH 握手获取保险柜 DEK（方案 C）

    请求体:
        { "client_pub": "<base64(SPKI-DER P-256)>" }

    逻辑：
    1. 检查 vault_access 状态（使用 session_key）
    2. 未授权 → 403
    3. 已授权 → 用客户端临时公钥包装 DEK 返回

    响应:
        {
            "status": "success",
            "server_pub": "<base64>",
            "iv": "<base64(12B)>",
            "ct": "<base64(AES-GCM wrapped DEK)>",
            "expire_time": <seconds>
        }
    """
    from vault.crypto import VaultEncryption
    from vault.handshake import (
        VaultHandshakeError,
        wrap_dek_for_client,
    )

    try:
        user = request.user

        # 【修复】使用 check_vault_access 检查访问权限（与 grant_vault_access 一致）
        if not check_vault_access(request):
            # 未授权，需要重新验证
            return JsonResponse({
                'status': 'error',
                'message': '需要重新验证'
            }, status=403)

        try:
            payload = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'JSON 格式错误'}, status=400)

        client_pub = payload.get('client_pub')
        if not client_pub:
            return JsonResponse({
                'status': 'error',
                'message': '缺少 client_pub'
            }, status=400)

        # 已授权，用握手包装 DEK 返回
        try:
            profile = user.profile
            if not profile.vault_initialized:
                return JsonResponse({
                    'status': 'error',
                    'message': '保险柜未初始化'
                }, status=400)

            # 用 KEK 解密 DEK
            dek = VaultEncryption.decrypt_dek(
                profile.encrypted_vault_key,
                profile.vault_key_iv
            )
            try:
                wrapped = wrap_dek_for_client(client_pub, dek)
            finally:
                dek = b'\x00' * 32

            # 获取剩余时间
            remaining_seconds = get_vault_access_remaining(request)

            return JsonResponse({
                'status': 'success',
                **wrapped,
                'expire_time': remaining_seconds,
                'remaining_seconds': remaining_seconds,
                'session_scoped': is_vault_access_session_scoped(request)
            })

        except VaultHandshakeError as e:
            logger.warning(f"Vault handshake failed during get_key: {e}")
            return JsonResponse({
                'status': 'error',
                'message': f'握手失败: {e}'
            }, status=400)
        except Exception as e:
            logger.error(f"Vault key decryption error: {e}")
            return JsonResponse({
                'status': 'error',
                'message': '解密密钥失败'
            }, status=500)

    except Exception as e:
        logger.error(f"Vault get_key error: {e}")
        return JsonResponse({
            'status': 'error',
            'message': '获取密钥失败'
        }, status=500)
