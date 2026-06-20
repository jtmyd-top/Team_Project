"""Vault status views."""
from .common import *  # noqa: F401, F403


@login_required
@require_http_methods(["GET"])
def vault_status(request):
    """
    获取保密柜状态
    返回：是否已启用2FA、是否已验证、剩余时间、保密笔记数量
    【修复】现在使用 session_key 而不是 user_id 来检查验证状态
    """
    user = request.user
    profile = getattr(user, 'profile', None)

    two_fa_enabled = profile.two_fa_enabled if profile else False
    two_fa_method = profile.two_fa_method if profile else None

    # 【修复】检查是否已验证：现在传 request 而不是 user
    is_verified = check_vault_access(request) if two_fa_enabled else True
    remaining_seconds = get_vault_access_remaining(request) if two_fa_enabled else 0

    # 获取保密笔记数量
    secret_notes_count = Note.objects.filter(
        author=user,
        is_secret=True,
        is_trashed=False
    ).count()

    return JsonResponse({
        'status': 'success',
        'two_fa_enabled': two_fa_enabled,
        'two_fa_method': two_fa_method,
        'is_verified': is_verified,
        'remaining_seconds': remaining_seconds,
        'secret_notes_count': secret_notes_count,
        'vault_initialized': bool(profile and profile.vault_initialized)
    })

@login_required
@require_http_methods(["POST"])
def vault_verify(request):
    """
    验证保密柜2FA
    成功后授予时间窗口内的访问权限
    支持速率限制、指数退避和CAPTCHA验证
    成功后返回 DEK 用于解密笔记
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'JSON格式错误'}, status=400)

    code = data.get('code', '').strip()
    use_backup = data.get('use_backup', False)

    # 【新增】提取用户选择的解锁时长（分钟），默认30分钟
    duration_minutes = data.get('duration', 30)

    # 【方案 C】客户端临时 P-256 公钥（SPKI-DER base64），用于 ECDH 包装 DEK
    client_pub = data.get('client_pub')

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
        # 2. 尝试用 ECDH 握手包装 DEK 返回给前端
        try:
            from vault.crypto import VaultEncryption
            from vault.handshake import (
                VaultHandshakeError,
                wrap_dek_for_client,
            )

            profile = request.user.profile
            if (
                client_pub
                and profile.vault_initialized
                and profile.encrypted_vault_key
                and profile.vault_key_iv
            ):
                # 用 KEK 解密 DEK（明文仅在本函数栈内存在）
                dek = VaultEncryption.decrypt_dek(
                    profile.encrypted_vault_key,
                    profile.vault_key_iv
                )
                try:
                    wrapped = wrap_dek_for_client(client_pub, dek)
                finally:
                    # 尽最大努力清除 DEK 明文引用（Python 语义限制，尽力而为）
                    dek = b'\x00' * 32

                return JsonResponse({
                    'status': 'success',
                    'message': '验证成功',
                    **wrapped,
                    'expire_time': result['expire_time'],
                    'remaining_seconds': result['remaining_seconds'],
                    'session_scoped': result.get('session_scoped', False)
                })
        except VaultHandshakeError as e:
            logger.warning(f"Vault handshake failed during verify: {e}")
            return JsonResponse({
                'status': 'error',
                'message': f'握手失败: {e}'
            }, status=400)
        except Exception as e:
            logger.warning(f"Failed to wrap DEK during vault verify: {e}")
            # 继续返回基本成功响应（DEK 可稍后通过 vault/key 获取）

        return JsonResponse({
            'status': 'success',
            'message': '验证成功',
            'expire_time': result['expire_time'],
            'remaining_seconds': result['remaining_seconds'],
            'session_scoped': result.get('session_scoped', False)
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

@login_required
@require_http_methods(["POST"])
def vault_lock(request):
    """
    主动锁定保密柜（撤销访问权限）
    【修复】现在使用 session_key 而不是 user_id
    """
    revoke_vault_access(request)
    return JsonResponse({
        'status': 'success',
        'message': '保密柜已锁定'
    })

@login_required
@require_http_methods(["GET"])
def vault_lock_status(request):
    """
    检查保密柜验证锁定状态
    用于前端显示锁定倒计时
    """
    from vault.services import check_vault_locked

    user = request.user
    is_locked, remaining_seconds, fail_count = check_vault_locked(user.id, request)  # 【修复】传入 request

    return JsonResponse({
        'is_locked': is_locked,
        'remaining_seconds': remaining_seconds,
        'fail_count': fail_count
    })

@login_required
@require_http_methods(["POST"])
def vault_send_email_code(request):
    """
    发送保密柜访问的邮箱验证码
    """
    user = request.user
    profile = getattr(user, 'profile', None)

    if not profile or not profile.two_fa_enabled:
        return JsonResponse({
            'status': 'error',
            'message': '未启用两因素认证'
        }, status=400)

    if profile.two_fa_method != 'email':
        return JsonResponse({
            'status': 'error',
            'message': '当前不是邮箱验证方式'
        }, status=400)

    success, message = send_operation_2fa_email(user, 'vault_access')

    if success:
        return JsonResponse({
            'status': 'success',
            'message': '验证码已发送'
        })

    return JsonResponse({
        'status': 'error',
        'message': message
    }, status=400)
