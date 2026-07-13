from .common import *  # noqa: F401,F403

@require_http_methods(["GET"])
@login_required
def get_group_messages_api(request, group_id):
    try:
        from messaging.models import MessageGroup
        query = request.GET.get('q', '').strip()
        sender_id_raw = request.GET.get('sender_id', '').strip()
        date_from_raw = request.GET.get('date_from', '').strip()
        date_to_raw = request.GET.get('date_to', '').strip()
        has_attachment = request.GET.get('has_attachment') == '1'
        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error

        qs = _visible_group_messages_qs(group, membership)
        if query:
            qs = qs.filter(Q(content__icontains=query) | Q(searchable_text__icontains=query))
        if sender_id_raw:
            try:
                sender_id = int(sender_id_raw)
            except (TypeError, ValueError):
                return JsonResponse({'error': 'sender_id 必须是正整数'}, status=400)
            if sender_id <= 0:
                return JsonResponse({'error': 'sender_id 必须是正整数'}, status=400)
            qs = qs.filter(sender_id=sender_id)

        date_from = None
        date_to = None
        try:
            if date_from_raw:
                date_from = datetime.strptime(date_from_raw, '%Y-%m-%d').date()
            if date_to_raw:
                date_to = datetime.strptime(date_to_raw, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'error': '日期格式必须为 YYYY-MM-DD'}, status=400)
        if date_from and date_to and date_from > date_to:
            return JsonResponse({'error': '开始日期不能晚于结束日期'}, status=400)
        if date_from:
            start_at = timezone.make_aware(datetime.combine(date_from, datetime.min.time()))
            qs = qs.filter(created_at__gte=start_at)
        if date_to:
            end_at = timezone.make_aware(datetime.combine(date_to + timedelta(days=1), datetime.min.time()))
            qs = qs.filter(created_at__lt=end_at)
        if has_attachment:
            qs = qs.filter(attachments__isnull=False).distinct()

        limit, offset = _parse_message_page(request)
        messages, pagination = _slice_latest_page(qs, limit, offset)
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
                'allow_new_members_view_history': group.allow_new_members_view_history,
            },
            'messages': [_group_message_payload(message, viewer=request.user) for message in messages],
            'settings': _group_settings_payload(membership),
            'pagination': pagination,
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
        from messaging.note_share_forwarding import (
            NoteShareForwardingError,
            create_group_note_share_from_forward,
            ensure_note_share_is_forwardable,
            get_note_share,
        )
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
        forwarded_private_from_id = data.get('forwarded_private_from')
        if forwarded_from_id and forwarded_private_from_id:
            return JsonResponse({'error': '一次只能转发一条来源消息'}, status=400)
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
                reply_to_message = _visible_group_messages_qs(group, membership).get(id=reply_to_id)
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
        source_note_share = None
        try:
            attachments = _load_message_attachments(request.user, attachment_ids)
        except ValueError as exc:
            return JsonResponse({'error': str(exc)}, status=400)
        if forwarded_from_id:
            try:
                forwarded_message = GroupMessage.objects.select_related(
                    'group',
                    'note_share__note',
                ).get(id=forwarded_from_id, is_recalled=False)
            except GroupMessage.DoesNotExist:
                return JsonResponse({'error': '转发的消息不存在或已撤回'}, status=400)
            source_membership = _get_active_membership(forwarded_message.group, request.user)
            if (
                source_membership is None
                or not _visible_group_messages_qs(forwarded_message.group, source_membership)
                .filter(id=forwarded_message.id)
                .exists()
            ):
                return JsonResponse({'error': '无权转发该消息'}, status=403)
            source_note_share = get_note_share(forwarded_message)
            try:
                ensure_note_share_is_forwardable(source_note_share)
            except NoteShareForwardingError as exc:
                return JsonResponse({'error': str(exc)}, status=403)
        if forwarded_private_from_id:
            from messaging.models import Message
            try:
                private_message = Message.objects.select_related(
                    'sender',
                    'recipient',
                    'note_share__note',
                ).get(id=forwarded_private_from_id)
            except Message.DoesNotExist:
                return JsonResponse({'error': '转发的消息不存在或已撤回'}, status=400)
            if request.user.id not in (private_message.sender_id, private_message.recipient_id):
                return JsonResponse({'error': '无权转发该消息'}, status=403)
            source_note_share = get_note_share(private_message)
            try:
                ensure_note_share_is_forwardable(source_note_share)
            except NoteShareForwardingError as exc:
                return JsonResponse({'error': str(exc)}, status=403)
            if not content:
                content = private_message.content or _attachment_preview(private_message.attachments.first())
            if not content:
                return JsonResponse({'error': '原消息为空，无法转发'}, status=400)

        with transaction.atomic():
            message = GroupMessage.objects.create(
                group=group,
                sender=request.user,
                content=content,
                searchable_text=_message_searchable_text(content, attachments),
                reply_to=reply_to_message,
                forwarded_from=forwarded_message,
            )
            create_group_note_share_from_forward(
                source_note_share,
                message,
                request.user,
                group,
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

        message = (
            GroupMessage.objects
            .select_related(
                'sender',
                'group',
                'note_share__note__author',
                'note_share__shared_by',
            )
            .prefetch_related('attachments', 'mentions__mentioned_user', 'reactions__user')
            .get(id=message.id)
        )
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
def share_note_to_group_api(request, group_id):
    try:
        from messaging.models import GroupMessage, GroupNoteShare, MessageGroup
        from moderation.models import UserSanction
        from notes.models import Note
        from message_groups.security import check_group_message_security

        allowed, error_response = check_group_message_security(request.user.id, group_id)
        if not allowed:
            return error_response

        data = json.loads(request.body or '{}')
        note_id = data.get('note_id')
        if not note_id:
            return JsonResponse({'error': '缺少 note_id'}, status=400)

        note = get_object_or_404(Note, id=note_id, author=request.user, is_trashed=False)
        if note.is_secret:
            return JsonResponse({
                'error': '保密笔记不能通过普通群聊分享',
                'code': 'secret_note_share_forbidden',
            }, status=400)

        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error
        send_error = _can_send_group_message(group, membership)
        if send_error is not None:
            return send_error
        if UserSanction.is_muted(request.user) is not None:
            return JsonResponse({'error': '你已被禁止发送私信'}, status=403)

        title = (note.title or '未命名笔记').strip()[:255]
        raw_content = _body_string(data, 'content')
        content = raw_content or f'[笔记] {title}'
        if len(content) > MESSAGE_CONTENT_MAX_LENGTH:
            return JsonResponse({'error': f'消息内容不能超过{MESSAGE_CONTENT_MAX_LENGTH}字'}, status=400)

        with transaction.atomic():
            message = GroupMessage.objects.create(
                group=group,
                sender=request.user,
                content=content,
                searchable_text=f'{content}\n{title}'.strip(),
            )
            GroupNoteShare.objects.create(
                group=group,
                message=message,
                note=note,
                shared_by=request.user,
                title_snapshot=title,
                was_public_at_share=note.is_public,
            )
            group.updated_at = timezone.now()
            group.save(update_fields=['updated_at'])
            membership.force_unread = False
            membership.last_read_at = timezone.now()
            membership.save(update_fields=['force_unread', 'last_read_at'])

        message = (
            GroupMessage.objects
            .select_related('sender', 'group', 'note_share__note__author', 'note_share__shared_by')
            .prefetch_related('attachments', 'mentions__mentioned_user', 'reactions__user')
            .get(id=message.id)
        )
        return JsonResponse({
            'status': 'success',
            'message': _group_message_payload(message, viewer=request.user),
        }, status=201)
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('分享群笔记错误', e)


@require_http_methods(["GET"])
@login_required
def get_group_note_share_api(request, group_id, share_id):
    try:
        from django.db.models import F
        from messaging.models import GroupNoteShare, GroupNoteShareRead, MessageGroup
        from notes.views.note.common import build_note_response_data

        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error

        share = get_object_or_404(
            GroupNoteShare.objects.select_related('note__author', 'shared_by', 'message', 'group'),
            id=share_id,
            group=group,
        )
        if share.revoked_at is not None:
            return JsonResponse({'error': '该笔记分享已撤销'}, status=404)
        if not _visible_group_messages_qs(group, membership).filter(id=share.message_id).exists():
            return JsonResponse({'error': '无权访问该笔记分享'}, status=403)

        note = share.note
        if note.is_trashed:
            return JsonResponse({'error': '该笔记已不可用'}, status=404)
        if note.is_secret:
            return JsonResponse({
                'error': '保密笔记需要通过保密柜访问',
                'code': 'secret_note_requires_vault',
            }, status=403)

        if request.user.id != share.shared_by_id:
            record, _ = GroupNoteShareRead.objects.update_or_create(
                share=share,
                reader=request.user,
                defaults={'last_read_at': timezone.now()},
            )
            GroupNoteShareRead.objects.filter(id=record.id).update(
                view_count=F('view_count') + 1,
                last_read_at=timezone.now(),
            )

        return JsonResponse({
            'status': 'success',
            'share': {
                'id': share.id,
                'group_id': group.id,
                'message_id': share.message_id,
                'shared_by': _user_payload(share.shared_by),
                'created_at': share.created_at.isoformat() if share.created_at else None,
                'allow_forwarding': share.allow_forwarding,
                'requires_group_membership': not note.is_public,
                'view_url': f'/messages/groups/{group.id}/note-shares/{share.id}/view/',
            },
            'note': build_note_response_data(note, include_content=True, include_all_fields=True),
        })
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('读取群笔记分享错误', e)


@require_http_methods(["GET"])
@login_required
def group_note_share_view(request, group_id, share_id):
    try:
        from django.db.models import F
        from messaging.models import GroupNoteShare, GroupNoteShareRead, MessageGroup
        from messaging.views.note_share_reader import render_note_share_error, render_note_share_reader

        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return render_note_share_error(request, '你需要先加入该群，才能阅览这篇笔记分享。', status=403)

        share = get_object_or_404(
            GroupNoteShare.objects.select_related('note__author', 'shared_by', 'message', 'group'),
            id=share_id,
            group=group,
        )
        if share.revoked_at is not None:
            return render_note_share_error(request, '这篇笔记分享已被撤销。', status=404)
        if not _visible_group_messages_qs(group, membership).filter(id=share.message_id).exists():
            return render_note_share_error(request, '你无权阅览这篇笔记分享。', status=403)

        note = share.note
        if note.is_trashed:
            return render_note_share_error(request, '这篇笔记已不可用。', status=404)
        if note.is_secret:
            return render_note_share_error(request, '保密笔记需要通过保密柜访问，暂不支持消息窗口阅览。', status=403)

        if request.user.id != share.shared_by_id:
            record, _ = GroupNoteShareRead.objects.update_or_create(
                share=share,
                reader=request.user,
                defaults={'last_read_at': timezone.now()},
            )
            GroupNoteShareRead.objects.filter(id=record.id).update(
                view_count=F('view_count') + 1,
                last_read_at=timezone.now(),
            )

        return render_note_share_reader(request, note, {
            'scope': 'group',
            'label': '群聊笔记分享',
            'group_name': group.name,
            'shared_by': share.shared_by.username,
            'created_at': share.created_at,
            'requires_group_membership': not note.is_public,
        })
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('打开群聊笔记分享页面错误', e)


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

        message = get_object_or_404(_visible_group_messages_qs(group, membership), id=message_id)
        if (
            action != 'unpin'
            and message.visibility_scope != GroupMessage.VISIBILITY_ALL
        ):
            return JsonResponse({'error': 'Private moderation notices cannot be pinned'}, status=400)
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
@rate_limit('group_shared_items', max_requests=20, window_seconds=60)
def group_shared_items_api(request, group_id):
    try:
        from messaging.models import MessageGroup
        import logging
        logger = logging.getLogger(__name__)

        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error

        cleared_marker = membership.cleared_before.timestamp() if membership.cleared_before else 'none'
        cache_key = (
            f'group_shared_items:{group_id}:{request.user.id}:'
            f'{group.updated_at.timestamp()}:{cleared_marker}'
        )
        cached_data = cache.get(cache_key)

        if cached_data:
            logger.info(f'[群文件] 从缓存返回群组 {group_id} 的共享文件')
            return JsonResponse(cached_data)

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

        logger.info(f'[群文件] 开始处理群组 {group_id} 的共享文件，共 {qs.count()} 条消息')

        for message in qs:
            attachment_count = message.attachments.count()
            if attachment_count > 0:
                logger.info(f'[群文件] 消息 {message.id} 有 {attachment_count} 个附件')

            for attachment in message.attachments.all():
                logger.info(f'[群文件] 处理附件: ID={attachment.id}, 类型={attachment.attachment_type}, 名称={attachment.original_name}')
                item = _shared_attachment_payload(attachment, message)
                # 图片、视频、音频都归类为媒体
                if attachment.attachment_type in ('image', 'video', 'audio'):
                    if len(media) < 60:
                        media.append(item)
                        logger.info(f'[群文件] 添加媒体文件: {attachment.original_name}')
                elif len(files) < 60:
                    files.append(item)
                    logger.info(f'[群文件] 添加普通文件: {attachment.original_name}')

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

        logger.info(f'[群文件] 最终结果: {len(media)} 个媒体, {len(files)} 个文件, {len(links)} 个链接')

        response_data = {
            'status': 'success',
            'links': links,
            'media': media,
            'files': files,
            'images': [item for item in media if item.get('type') == 'image'],
        }

        # 缓存结果5分钟
        cache.set(cache_key, response_data, 300)

        return JsonResponse(response_data)
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
        message = get_object_or_404(_visible_group_messages_qs(group, membership), id=message_id)
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
        message = get_object_or_404(_visible_group_messages_qs(group, membership), id=message_id)

        if scope == 'both':
            # 检查撤回权限
            is_sender = message.sender_id == request.user.id
            is_manager = membership.role in ('owner', 'admin')

            # 普通成员只能撤回自己的消息
            if not is_sender and not is_manager:
                return JsonResponse({'error': '只有发送者或群管理员可以撤回此消息'}, status=403)

            # 普通成员撤回自己的消息有时间限制
            if is_sender and not is_manager:
                if message.created_at < timezone.now() - timedelta(seconds=RECALL_WINDOW_SECONDS):
                    return JsonResponse({'error': f'发送超过 {RECALL_WINDOW_SECONDS // 60} 分钟的消息不能撤回'}, status=403)

            # 群主/管理员撤回任何消息无时间限制
            message.is_recalled = True
            message.recalled_at = timezone.now()
            message.save(update_fields=['is_recalled', 'recalled_at'])

            # 如果是管理员撤回他人消息，记录审计日志
            if is_manager and not is_sender:
                _create_group_audit_log(
                    group,
                    request.user,
                    'message_recall_by_admin',
                    target_user=message.sender,
                    metadata={'message_id': message.id, 'content_preview': message.content[:50]},
                )

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
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error
        message = get_object_or_404(_visible_group_messages_qs(group, membership), id=message_id)
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
