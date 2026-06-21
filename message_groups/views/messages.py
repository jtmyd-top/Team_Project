from .common import *  # noqa: F401,F403

@require_http_methods(["GET"])
@login_required
def get_group_messages_api(request, group_id):
    try:
        from messaging.models import MessageGroup
        query = request.GET.get('q', '').strip()
        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error

        qs = _visible_group_messages_qs(group, membership)
        if query:
            qs = qs.filter(Q(content__icontains=query) | Q(searchable_text__icontains=query))
        messages = list(qs)
        current_announcement = _latest_active_announcement(group)

        membership.last_read_at = timezone.now()
        membership.force_unread = False
        membership.save(update_fields=['last_read_at', 'force_unread'])

        return JsonResponse({
            'status': 'success',
            'conversation_type': 'group',
            'group': {
                'id': group.id,
                'name': group.name,
                'avatar': _group_avatar_url(group),
                'description': group.description,
                'announcement': group.announcement,
                'announcement_pinned_at': group.announcement_pinned_at.isoformat() if group.announcement_pinned_at else None,
                'announcement_message_id': current_announcement.message_id if current_announcement else None,
                'announcement_updated_at': current_announcement.updated_at.isoformat() if current_announcement else None,
                'mute_mode': group.mute_mode,
            },
            'messages': [_group_message_payload(message, viewer=request.user) for message in messages],
            'settings': _group_settings_payload(membership),
        })
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('获取群组消息错误', e)


@require_http_methods(["POST"])
@login_required
def send_group_message_api(request, group_id):
    try:
        from messaging.models import GroupMessage, GroupMessageMention, MessageAttachment, MessageGroup, MessageGroupMember
        from moderation.models import UserSanction
        from message_groups.security import check_group_message_security

        # ===== 安全检查：频率限制 + 熔断机制 =====
        allowed, error_response = check_group_message_security(request.user.id, group_id)
        if not allowed:
            return error_response

        data = json.loads(request.body)
        content = _body_string(data, 'content')
        try:
            attachment_ids = _normalize_attachment_ids(data.get('attachment_ids'))
        except ValueError as exc:
            return JsonResponse({'error': str(exc)}, status=400)
        if not content and not attachment_ids:
            return JsonResponse({'error': '消息内容不能为空'}, status=400)
        if len(content) > MESSAGE_CONTENT_MAX_LENGTH:
            return JsonResponse({'error': f'消息内容不能超过{MESSAGE_CONTENT_MAX_LENGTH}字'}, status=400)
        if False and data.get('attachment_ids'):
            return JsonResponse({'error': '群组暂不支持阅后即焚或附件消息'}, status=400)

        # Phase 2: 获取回复和转发参数
        reply_to_id = data.get('reply_to')
        forwarded_from_id = data.get('forwarded_from')
        raw_mentions = data.get('mentions', [])  # @提及的用户名列表
        mentioned_usernames = [
            str(username).strip()
            for username in raw_mentions
            if isinstance(username, str) and str(username).strip()
        ] if isinstance(raw_mentions, list) else []
        mention_everyone = bool(data.get('mention_all')) or '@全体' in content or '@all' in content.lower()

        mute = UserSanction.is_muted(request.user)
        if mute is not None:
            return JsonResponse({'error': '你已被禁止发送私信'}, status=403)

        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error
        send_error = _can_send_group_message(group, membership)
        if send_error is not None:
            return send_error
        if mention_everyone and membership.role not in ('owner', 'admin'):
            return JsonResponse({'error': '当前群组仅群主或管理员可以 @全体成员'}, status=403)

        # Phase 2: 验证回复消息
        reply_to_message = None
        if reply_to_id:
            try:
                reply_to_message = GroupMessage.objects.select_related('sender').get(id=reply_to_id, group=group, is_recalled=False)
            except GroupMessage.DoesNotExist:
                return JsonResponse({'error': '回复的消息不存在或已撤回'}, status=400)

        if mentioned_usernames and not _can_view_group_members(group, membership):
            allowed_quoted_mentions = set()
            if reply_to_message and reply_to_message.sender_id != request.user.id:
                quoted_username = reply_to_message.sender.username
                if f'@{quoted_username}' in content:
                    allowed_quoted_mentions.add(quoted_username)
            invalid_mentions = [
                username for username in mentioned_usernames
                if username not in allowed_quoted_mentions
            ]
            if invalid_mentions:
                return JsonResponse({'error': '当前群组未开放成员列表，不能主动 @ 群成员'}, status=403)

        if (
            reply_to_message
            and reply_to_message.sender_id != request.user.id
            and f'@{reply_to_message.sender.username}' in content
            and reply_to_message.sender.username not in mentioned_usernames
        ):
            mentioned_usernames.append(reply_to_message.sender.username)

        # Phase 2: 验证转发消息
        forwarded_message = None
        try:
            attachments = _load_message_attachments(request.user, attachment_ids)
        except ValueError as exc:
            return JsonResponse({'error': str(exc)}, status=400)
        if forwarded_from_id:
            try:
                forwarded_message = GroupMessage.objects.get(id=forwarded_from_id, is_recalled=False)
            except GroupMessage.DoesNotExist:
                return JsonResponse({'error': '转发的消息不存在或已撤回'}, status=400)

        with transaction.atomic():
            message = GroupMessage.objects.create(
                group=group,
                sender=request.user,
                content=content,
                searchable_text=_message_searchable_text(content, attachments),
                reply_to=reply_to_message,
                forwarded_from=forwarded_message,
            )
            if attachments:
                updated_count = MessageAttachment.objects.filter(
                    id__in=attachment_ids,
                    uploader=request.user,
                    message__isnull=True,
                    group_message__isnull=True,
                ).update(group_message=message)
                if updated_count != len(attachment_ids):
                    raise ValueError('附件不存在、已发送或无权使用')

            if mention_everyone:
                mentioned_members = (
                    MessageGroupMember.objects
                    .filter(group=group, left_at__isnull=True)
                    .exclude(user=request.user)
                    .select_related('user')[:200]
                )
                for member in mentioned_members:
                    try:
                        notify_user(
                            member.user,
                            'group_mention_all',
                            f'{request.user.username} 在群组中 @全体成员',
                            f'在 {group.name} 中：{content[:80]}',
                            group_id=group.id,
                            message_id=message.id,
                        )
                    except Exception as e:
                        logger.warning(f'发送@全体通知失败: {e}')
                    transaction.on_commit(
                        lambda recipient=member.user, group=group, content=content: _maybe_send_group_mention_email(
                            request.user,
                            recipient,
                            group,
                            content,
                        )
                    )
                _create_group_audit_log(
                    group,
                    request.user,
                    'mention_all',
                    metadata={'message_id': message.id},
                )

            # Phase 2: 创建@提及记录
            if mentioned_usernames:
                # 获取群成员中被提及的用户
                mentioned_members = MessageGroupMember.objects.filter(
                    group=group,
                    user__username__in=mentioned_usernames,
                    left_at__isnull=True
                ).select_related('user')

                for member in mentioned_members:
                    GroupMessageMention.objects.create(
                        message=message,
                        mentioned_user=member.user
                    )
                    # 可选：发送通知给被提及的用户
                    if member.user.id != request.user.id:  # 不通知自己
                        try:
                            notify_user(
                                member.user,
                                'group_mention',
                                f'{request.user.username} 在群组中提到了你',
                                f'在 {group.name} 中: {content[:50]}...' if len(content) > 50 else content,
                                group_id=group.id,
                                message_id=message.id,
                            )
                        except Exception as e:
                            logger.warning(f'发送提及通知失败: {e}')
                        transaction.on_commit(
                            lambda recipient=member.user, group=group, content=content: _maybe_send_group_mention_email(
                                request.user,
                                recipient,
                                group,
                                content,
                            )
                        )

            group.updated_at = timezone.now()
            group.save(update_fields=['updated_at'])
            membership.force_unread = False
            membership.last_read_at = timezone.now()
            membership.save(update_fields=['force_unread', 'last_read_at'])

        message = GroupMessage.objects.select_related('sender', 'group').prefetch_related('attachments').get(id=message.id)
        return JsonResponse({
            'status': 'success',
            'message': _group_message_payload(message, viewer=request.user),
        }, status=201)
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('发送群组消息错误', e)


@require_http_methods(["POST"])
@login_required
def pin_group_message_api(request, group_id, message_id):
    try:
        from messaging.models import GroupMessage, MessageGroup
        data = json.loads(request.body or '{}')
        action = data.get('action', 'pin')
        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error
        manager_error = _require_group_manager(membership)
        if manager_error is not None:
            return manager_error

        message = get_object_or_404(GroupMessage, id=message_id, group=group, is_recalled=False)
        if action == 'unpin' or group.pinned_message_id == message.id:
            group.pinned_message = None
            audit_action = 'group_message_unpin'
        else:
            group.pinned_message = message
            audit_action = 'group_message_pin'
        group.updated_at = timezone.now()
        group.save(update_fields=['pinned_message', 'updated_at'])
        _create_group_audit_log(
            group,
            request.user,
            audit_action,
            target_user=message.sender,
            metadata={'message_id': message.id},
        )
        return JsonResponse({
            'status': 'success',
            'group': _group_detail_payload(group, membership),
            'message': _group_message_payload(message, viewer=request.user),
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('更新群消息置顶错误', e)


@require_http_methods(["GET"])
@login_required
def group_shared_items_api(request, group_id):
    try:
        from messaging.models import MessageGroup
        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error

        def _shared_attachment_payload(attachment, message):
            payload = _attachment_payload(attachment)
            payload.update({
                'sender': _user_payload(message.sender),
                'message_id': message.id,
                'group_id': group.id,
                'created_at': message.created_at.isoformat() if message.created_at else None,
                'category': 'media' if attachment.attachment_type in ('image', 'video') else 'file',
            })
            return payload

        links = []
        media = []
        files = []
        seen = set()
        qs = _visible_group_messages_qs(group, membership).order_by('-created_at')[:200]
        for message in qs:
            for attachment in message.attachments.all():
                item = _shared_attachment_payload(attachment, message)
                if attachment.attachment_type in ('image', 'video'):
                    if len(media) < 60:
                        media.append(item)
                elif len(files) < 60:
                    files.append(item)

            for url in _extract_links_from_text(message.content):
                if url in seen:
                    continue
                seen.add(url)
                links.append({
                    'url': url,
                    'sender': _user_payload(message.sender),
                    'message_id': message.id,
                    'created_at': message.created_at.isoformat() if message.created_at else None,
                })
                if len(links) >= 50:
                    break
            if len(links) >= 50:
                break

        return JsonResponse({
            'status': 'success',
            'links': links,
            'media': media,
            'files': files,
            'images': [item for item in media if item.get('type') == 'image'],
        })
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('获取群资料聚合错误', e)


@require_http_methods(["POST"])
@login_required
def edit_group_message_api(request, group_id, message_id):
    try:
        from messaging.models import GroupMessage, MessageGroup
        data = json.loads(request.body)
        content = _body_string(data, 'content')
        if not content:
            return JsonResponse({'error': '消息内容不能为空'}, status=400)
        if len(content) > MESSAGE_CONTENT_MAX_LENGTH:
            return JsonResponse({'error': f'消息内容不能超过{MESSAGE_CONTENT_MAX_LENGTH}字'}, status=400)

        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error
        message = get_object_or_404(GroupMessage, id=message_id, group=group, is_recalled=False)
        if message.sender_id != request.user.id:
            return JsonResponse({'error': '只能编辑自己发送的消息'}, status=403)

        message.content = content
        message.searchable_text = _message_searchable_text(content)
        message.is_edited = True
        message.edited_at = timezone.now()
        message.save(update_fields=['content', 'searchable_text', 'is_edited', 'edited_at'])
        group.updated_at = timezone.now()
        group.save(update_fields=['updated_at'])
        return JsonResponse({
            'status': 'success',
            'message': _group_message_payload(message, viewer=request.user),
            'settings': _group_settings_payload(membership),
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('编辑群组消息错误', e)


@require_http_methods(["POST", "DELETE"])
@login_required
def delete_group_message_api(request, group_id, message_id):
    try:
        from messaging.models import GroupMessage, GroupMessageDeletion, MessageGroup
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            data = {}
        scope = data.get('scope', 'self')
        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error
        message = get_object_or_404(GroupMessage, id=message_id, group=group)

        if scope == 'both':
            if message.sender_id != request.user.id:
                return JsonResponse({'error': '只有发送者可以撤回'}, status=403)
            if message.created_at < timezone.now() - timedelta(seconds=RECALL_WINDOW_SECONDS):
                return JsonResponse({'error': f'发送超过 {RECALL_WINDOW_SECONDS // 60} 分钟的消息不能撤回'}, status=403)
            message.is_recalled = True
            message.recalled_at = timezone.now()
            message.save(update_fields=['is_recalled', 'recalled_at'])
            return JsonResponse({'status': 'success', 'scope': 'both'})

        GroupMessageDeletion.objects.get_or_create(message=message, user=request.user)
        return JsonResponse({'status': 'success', 'scope': 'self'})
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('删除群组消息错误', e)


@require_http_methods(["POST"])
@login_required
def report_group_message_api(request, group_id, message_id):
    try:
        from messaging.models import GroupMessage, MessageGroup
        from moderation.models import MessageReport
        data = json.loads(request.body)
        reason = data.get('reason', 'other')
        detail = (data.get('detail') or '').strip()[:1000]
        if reason not in dict(MessageReport.REASON_CHOICES):
            return JsonResponse({'error': '无效的举报原因'}, status=400)

        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        _, error = _require_group_member(group, request.user)
        if error is not None:
            return error
        message = get_object_or_404(GroupMessage, id=message_id, group=group)
        if message.sender_id == request.user.id:
            return JsonResponse({'error': '不能举报自己发送的消息'}, status=400)

        report = MessageReport.objects.create(
            reporter=request.user,
            reported_user=message.sender,
            group_message=message,
            reason=reason,
            detail=detail,
            evidence_snapshot=message_report_snapshot(group_message=message, request=request),
        )
        notify_user(
            request.user,
            'report_received',
            '举报已收到',
            '你的群消息举报已提交，管理员会尽快处理。',
            report_type='message',
            report_id=report.id,
        )
        if not message.was_reported:
            message.was_reported = True
            message.save(update_fields=['was_reported'])
        return JsonResponse({'status': 'success', 'message': '举报已提交，我们会尽快处理'})
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('举报群组消息错误', e)
