# knowledge_project/vault_views.py
"""保密柜（Vault）相关视图

原属于 views.py 4343-4758 段。抽出后 views.py 底部 re-export 兼容。
"""
import base64
import json
import logging
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from ..decorators import (
    check_vault_access,
    get_vault_access_remaining,
    grant_vault_access,
    revoke_vault_access,
    send_operation_2fa_email,
    verify_vault_2fa,
)
from ..models import Note

logger = logging.getLogger(__name__)


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
        grant_vault_access(request, window_seconds=result['window_seconds'])

        # 2. 尝试用 ECDH 握手包装 DEK 返回给前端
        try:
            from knowledge_project.utils.vault_crypto import VaultEncryption
            from knowledge_project.utils.vault_handshake import (
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
                    'remaining_seconds': result['remaining_seconds']
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
    from ..decorators import check_vault_locked

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


@login_required
@require_http_methods(["GET"])
def vault_notes_list(request):
    """
    获取保密柜中的笔记列表
    需要先通过2FA验证
    """
    user = request.user
    profile = getattr(user, 'profile', None)

    # 检查2FA验证状态
    if profile and profile.two_fa_enabled:
        if not check_vault_access(request):  # 【修复】传 request 而不是 user
            return JsonResponse({
                'status': 'require_vault_2fa',
                'code': 'require_vault_2fa',
                'message': '访问保密柜需要两因素认证验证',
                'method': profile.two_fa_method
            })

    # 获取保密笔记列表
    notes = Note.objects.filter(
        author=user,
        is_secret=True,
        is_trashed=False
    ).order_by('-updated_at')

    notes_data = [{
        'id': note.id,
        'title': note.title,
        'created_at': note.created_at.isoformat(),
        'updated_at': note.updated_at.isoformat(),
        'is_favorited': note.is_favorited,
        'is_secret': note.is_secret,  # 保密标志
        'folder_id': note.folder_id,
        'is_trashed': note.is_trashed
    } for note in notes]

    return JsonResponse({
        'status': 'success',
        'notes': notes_data,
        'remaining_seconds': get_vault_access_remaining(request) if profile and profile.two_fa_enabled else 0  # 【修复】传 request 而不是 user
    })


# ==================== 保险柜加密 API ====================

@login_required
@require_http_methods(["POST"])
def vault_init(request):
    """
    初始化保险柜
    生成用户的 DEK（Data Encryption Key）并用 KEK 加密后存入数据库
    """
    from knowledge_project.utils.vault_crypto import VaultEncryption

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
        logger.error(f"Vault init error: {e}")
        return JsonResponse({
            'status': 'error',
            'message': f'保险柜初始化失败: {str(e)}'
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
    from knowledge_project.utils.vault_crypto import VaultEncryption
    from knowledge_project.utils.vault_handshake import (
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
                'expire_time': remaining_seconds
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


@login_required
@require_http_methods(["POST"])
def vault_export(request):
    """
    导出保险柜备份（加密的笔记数据）

    逻辑：
    1. 获取用户所有 is_secret=True 的笔记
    2. 导出为 JSON 文件（包含加密的内容）
    3. 返回下载链接
    """
    try:
        user = request.user

        # 获取用户的所有保密笔记
        secret_notes = Note.objects.filter(
            author=user,
            is_secret=True,
            is_trashed=False
        ).values('id', 'title', 'content', 'created_at', 'updated_at', 'folder_id')

        # 转换为列表
        notes_data = list(secret_notes)

        # 创建备份数据
        backup_data = {
            'user_id': user.id,
            'username': user.username,
            'exported_at': timezone.now().isoformat(),
            'notes_count': len(notes_data),
            'notes': notes_data
        }

        # 序列化为 JSON
        json_bytes = json.dumps(
            backup_data,
            ensure_ascii=False,
            indent=2,
            default=str
        ).encode('utf-8')

        # 创建文件响应
        file_obj = BytesIO(json_bytes)
        filename = f"vault_export_{user.username}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.json"

        return FileResponse(
            file_obj,
            as_attachment=True,
            filename=filename,
            content_type='application/json'
        )

    except Exception as e:
        logger.error(f"Vault export error: {e}")
        return JsonResponse({
            'status': 'error',
            'message': f'导出失败: {str(e)}'
        }, status=500)
