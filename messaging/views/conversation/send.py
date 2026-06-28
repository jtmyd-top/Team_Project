"""Conversation send views."""
from .common import *  # noqa: F401, F403


@require_http_methods(["POST"])
@login_required
def send_message_api(request):
    """发送私信"""
    try:
        from messaging.models import Message, MessageAttachment, NewConversationQuotaLog

        data = json.loads(request.body)
        try:
            recipient_id, content, attachment_ids = _validate_send_message_input(data)
        except ValueError as exc:
            return JsonResponse({'error': str(exc)}, status=400)

        recipient = get_object_or_404(User, id=recipient_id)
        permission_response, _ = _check_send_permissions(request.user, recipient)
        if permission_response is not None:
            return permission_response

        attachments = _load_message_attachments(request.user, attachment_ids)

        # 新对话限流：超出免验证配额时必须通过 Turnstile
        is_new_conv = _is_new_conversation(request.user, recipient)
        try:
            turnstile_passed = _verify_new_conversation_quota(request, data, recipient)
        except PermissionError as exc:
            if str(exc) == 'turnstile_failed':
                return JsonResponse({
                    'error': '人机验证失败，请重试',
                    'need_turnstile': True,
                }, status=403)
            quota_used = _today_new_conv_count(request.user)
            return JsonResponse({
                'error': '今日新对话数量已达上限，请完成人机验证',
                'need_turnstile': True,
                'quota_used': quota_used,
                'quota_limit': NEW_CONV_DAILY_LIMIT,
            }, status=429)

        with transaction.atomic():
            message = Message.objects.create(
                sender=request.user,
                recipient=recipient,
                content=content,
                searchable_text=_message_searchable_text(content, attachments),
            )
            if attachments:
                updated_count = MessageAttachment.objects.filter(
                    id__in=attachment_ids,
                    uploader=request.user,
                    message__isnull=True,
                    group_message__isnull=True,
                ).update(message=message)
                if updated_count != len(attachment_ids):
                    raise ValueError('附件不存在、已发送或无权使用')

            # 记录新对话配额日志（总是记录，便于审计；限流字段标记是否走了 Turnstile）
            if is_new_conv:
                NewConversationQuotaLog.objects.create(
                    user=request.user,
                    peer=recipient,
                    turnstile_passed=turnstile_passed,
                )

            sender_settings = _update_conversation_state(request.user, recipient)

            preview_for_email = content or _attachment_preview(attachments[0] if attachments else None)
            transaction.on_commit(
                lambda: _maybe_send_new_message_email(request.user, recipient, preview_for_email)
            )
            if recipient != request.user:
                transaction.on_commit(
                    lambda: notify_user(
                        recipient,
                        'new_message',
                        f'{request.user.username} 给你发来新消息',
                        preview_for_email,
                        sender_id=request.user.id,
                        sender_username=request.user.username,
                        message_id=message.id,
                    )
                )
            transaction.on_commit(lambda: _push_new_message_events(message))

        # 发送动作也触发一次阅后即焚清理（若发送者或对方有超 TTL 的旧已读消息）
        _apply_disappearing(request.user, recipient, sender_settings)

        return JsonResponse({
            'status': 'success',
            'message': _message_payload(message, viewer=request.user),
        }, status=201)
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except IntegrityError as e:
        logger.warning("发送私信数据库冲突: %s", e, exc_info=True)
        return JsonResponse({'error': '请求冲突，请稍后重试'}, status=409)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('发送私信错误', e)

@require_http_methods(["POST"])
@login_required
def forward_message_api(request):
    """转发单条消息；若原消息包含附件，则为新消息创建新的附件记录并复用同一物理文件路径。"""
    try:
        from messaging.models import GroupMessage, Message, NewConversationQuotaLog
        from message_groups.views.common import _get_active_membership, _visible_group_messages_qs

        data = json.loads(request.body)
        source_message_id = data.get('message_id')
        source_group_message_id = data.get('group_message_id')
        recipient_id = data.get('recipient_id')
        if not recipient_id or not (source_message_id or source_group_message_id):
            return JsonResponse({'error': '缺少 message_id/group_message_id 或 recipient_id'}, status=400)

        source_message = None
        source_group_message = None
        if source_group_message_id:
            source_group_message = get_object_or_404(
                GroupMessage.objects.select_related('sender', 'group').prefetch_related('attachments'),
                id=source_group_message_id,
                is_recalled=False,
            )
            source_membership = _get_active_membership(source_group_message.group, request.user)
            if (
                source_membership is None
                or not _visible_group_messages_qs(source_group_message.group, source_membership)
                .filter(id=source_group_message.id)
                .exists()
            ):
                return JsonResponse({'error': '无权转发该消息'}, status=403)
        else:
            source_message = get_object_or_404(
                Message.objects.select_related('sender', 'recipient').prefetch_related('attachments'),
                id=source_message_id,
            )
            if request.user.id not in (source_message.sender_id, source_message.recipient_id):
                return JsonResponse({'error': '无权转发该消息'}, status=403)

        recipient = get_object_or_404(User, id=recipient_id)
        permission_response, _ = _check_send_permissions(request.user, recipient)
        if permission_response is not None:
            return permission_response

        is_new_conv = _is_new_conversation(request.user, recipient)
        try:
            turnstile_passed = _verify_new_conversation_quota(request, data, recipient)
        except PermissionError as exc:
            if str(exc) == 'turnstile_failed':
                return JsonResponse({'error': '人机验证失败，请重试', 'need_turnstile': True}, status=403)
            quota_used = _today_new_conv_count(request.user)
            return JsonResponse({
                'error': '今日新对话数量已达上限，请完成人机验证',
                'need_turnstile': True,
                'quota_used': quota_used,
                'quota_limit': NEW_CONV_DAILY_LIMIT,
            }, status=429)

        content = _body_string(data, 'content', '').strip()
        if not content and source_message is not None:
            content = source_message.content or _attachment_preview(source_message.attachments.first())
        if not content and source_group_message is not None:
            content = source_group_message.content or _attachment_preview(source_group_message.attachments.first())
        if source_message is not None and not content and not source_message.attachments.exists():
            return JsonResponse({'error': '原消息为空，无法转发'}, status=400)
        if source_group_message is not None and not content and not source_group_message.attachments.exists():
            return JsonResponse({'error': '原消息为空，无法转发'}, status=400)
        _validate_message_content(content)

        with transaction.atomic():
            forwarded_message = Message.objects.create(
                sender=request.user,
                recipient=recipient,
                content=content,
            )
            forwarded_attachments = _clone_forwarded_attachments(source_message, request.user, forwarded_message) if source_message is not None else []
            forwarded_message.searchable_text = _message_searchable_text(content, forwarded_attachments)
            forwarded_message.save(update_fields=['searchable_text'])

            if is_new_conv:
                NewConversationQuotaLog.objects.create(
                    user=request.user,
                    peer=recipient,
                    turnstile_passed=turnstile_passed,
                )

            sender_settings = _update_conversation_state(request.user, recipient)
            preview_for_email = content or _attachment_preview(forwarded_message.attachments.first())
            transaction.on_commit(
                lambda: _maybe_send_new_message_email(request.user, recipient, preview_for_email)
            )
            transaction.on_commit(lambda: _push_new_message_events(forwarded_message))

        _apply_disappearing(request.user, recipient, sender_settings)
        return JsonResponse({
            'status': 'success',
            'message': _message_payload(forwarded_message, viewer=request.user),
        }, status=201)
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except IntegrityError as e:
        logger.warning("转发私信数据库冲突: %s", e, exc_info=True)
        return JsonResponse({'error': '请求冲突，请稍后重试'}, status=409)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('转发私信错误', e)
