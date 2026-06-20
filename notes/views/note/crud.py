"""Notes crud views."""
from .common import *  # noqa: F401, F403


@login_required
@require_http_methods(["GET", "PUT", "PATCH", "DELETE"])
def note_detail_api(request, note_id):
    note = get_object_or_404(Note, pk=note_id)
    if request.method == 'GET':
        has_permission = note.has_read_permission(request.user)
    else:
        has_permission = note.has_write_permission(request.user)
    if not has_permission:
        return JsonResponse({'error': '您没有权限访问此笔记'}, status=403)
    # --- 统一进行时区转换 ---
    # 使用 timezone.localtime 将数据库中的UTC时间转换为settings.py中定义的本地时间
    local_updated_at = timezone.localtime(note.updated_at)
    local_created_at = timezone.localtime(note.created_at)
    if request.method == 'GET':
        # 【安全红线】回收站中的保密笔记不返回 content 字段
        # 普通笔记即使在回收站中也可以预览，但保密笔记需要还原后才能查看
        include_content = not (note.is_secret and note.is_trashed)

        if request.GET.get('full_content') == 'true':
            data = {
                'id': note.id,
                'title': note.title,
                'is_public': note.is_public,
                'is_secret': note.is_secret,
                'is_trashed': note.is_trashed,
                'content': note.content if include_content else '',
                'author': {'id': note.author.id, 'username': note.author.username},
                'created_at': local_created_at.strftime('%Y-%m-%d %H:%M'),
                'updated_at': local_updated_at.strftime('%Y-%m-%d %H:%M'),
                'tags': [{'id': tag.id, 'name': tag.name} for tag in note.tags.all()],
                'toc': note.toc or [],
                'public_url': f"/notes/public/{note.public_id}/" if note.public_id and note.is_public else "",
                'folder_id': note.folder.id if note.folder else None,
                'is_favorited': note.is_favorited,
            }
            return JsonResponse(data)

        page_number = request.GET.get('page', 1)
        paginated_content, total_pages = get_paginated_html(note.content or "", page_number)

        data = {
            'id': note.id,
            'title': note.title,
            'is_public': note.is_public,
            'is_secret': note.is_secret,
            'is_trashed': note.is_trashed,
            'content': paginated_content if include_content else '',
            'author': {'id': note.author.id, 'username': note.author.username},
            'created_at': local_created_at.strftime('%Y-%m-%d %H:%M'),
            'updated_at': local_updated_at.strftime('%Y-%m-%d %H:%M'),
            'tags': [{'id': tag.id, 'name': tag.name} for tag in note.tags.all()],
            'toc': note.toc or [],
            'pagination': {
                'current_page': int(page_number),
                'total_pages': total_pages,
            }
        }
        return JsonResponse(data)

    if request.method == 'PUT':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': '无效的JSON格式'}, status=400)

        allowed, error_msg, clear_vault_guard = validate_vault_encryption_content_update(request, note, data)
        if not allowed:
            return JsonResponse({'error': error_msg, 'message': error_msg}, status=409)

        was_public = note.is_public
        note.title = data.get('title', note.title)
        note.content = data.get('content', note.content)
        note.last_modified_by = request.user
        note.save()
        if was_public:
            _invalidate_public_notes_cache()
        if clear_vault_guard:
            _clear_vault_pending_encryption_guard(request, note.id)

        put_local_updated_at = timezone.localtime(note.updated_at)
        put_local_created_at = timezone.localtime(note.created_at)
        paginated_content, total_pages = get_paginated_html(note.content or "", 1)
        updated_data = {
            'id': note.id,
            'title': note.title,
            'is_public': note.is_public,
            'is_secret': note.is_secret,
            'is_trashed': note.is_trashed,
            'content': paginated_content,
            'updated_at': put_local_updated_at.strftime('%Y-%m-%d %H:%M'),
            'author': {'id': note.author.id, 'username': note.author.username},
            'created_at': put_local_created_at.strftime('%Y-%m-%d %H:%M'),
            'tags': [{'id': tag.id, 'name': tag.name} for tag in note.tags.all()],
            'pagination': {
                'current_page': 1,
                'total_pages': total_pages,
            }
        }
        return JsonResponse(updated_data)

    # --- PATCH 请求处理（部分更新）---
    if request.method == 'PATCH':
        # 【新增】安全檢查：回收站保護
        allowed, error_msg = check_note_edit_permission(note)
        if not allowed:
            return JsonResponse({'error': error_msg}, status=403)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': '无效的JSON格式'}, status=400)

        try:
            # 【新增】安全檢查：防止保密柜筆記發布為公開
            if 'is_public' in data and data['is_public']:
                allowed, error_msg = check_public_note_publish_permission(request.user)
                if not allowed:
                    return JsonResponse({'error': error_msg, 'message': error_msg}, status=403)
            if 'is_public' in data and data['is_public'] and note.is_secret:
                allowed, error_msg = check_note_secret_operation_permission(note, 'publish')
                if not allowed:
                    return JsonResponse({'error': error_msg}, status=403)

            # 只更新提供的字段
            was_public = note.is_public
            was_secret = note.is_secret
            will_be_secret = data.get('is_secret', note.is_secret)
            allowed, error_msg, clear_vault_guard = validate_vault_encryption_content_update(
                request,
                note,
                data,
                will_be_secret=will_be_secret,
            )
            if not allowed:
                return JsonResponse({'error': error_msg, 'message': error_msg}, status=409)

            if 'title' in data:
                note.title = data['title']
            if 'is_public' in data:
                note.is_public = data['is_public']
            if 'content' in data:
                note.content = data['content']
            if 'is_secret' in data:
                note.is_secret = data['is_secret']
                # 进入保密柜的笔记不能继续公开访问。
                if note.is_secret and note.is_public:
                    note.is_public = False
            if 'folder_id' in data:
                folder_id = data['folder_id']
                if folder_id is None:
                    note.folder = None
                else:
                    folder = get_object_or_404(Folder, id=folder_id, owner=request.user)
                    note.folder = folder

            note.last_modified_by = request.user

            # 如果设置为公开且没有公开ID，生成一个
            if note.is_public and not note.public_id:
                note.public_id = uuid.uuid4()

            note.save()
            if was_public or note.is_public:
                _invalidate_public_notes_cache()
            if clear_vault_guard:
                _clear_vault_pending_encryption_guard(request, note.id)
            if 'is_secret' in data:
                if not was_secret and note.is_secret and 'content' not in data:
                    _set_vault_pending_encryption_guard(request, note)
                elif was_secret and not note.is_secret:
                    _clear_vault_pending_encryption_guard(request, note.id)

            # 如果更新了内容，自动生成标签
            if 'content' in data and note.content and len(BeautifulSoup(note.content, 'html.parser').get_text()) > 20:
                auto_generate_tags_for_note(Note, note, created=True)

            # 清理缓存
            cache.delete(get_sidebar_cache_key(request.user.id))

            # 发送笔记修改通知（如果有内容或标题变化）
            if 'content' in data or 'title' in data:
                send_note_activity_notification(request, request.user, note.title, 'updated')

            # 返回更新后的数据
            patch_local_updated_at = timezone.localtime(note.updated_at)
            response_data = {
                'id': note.id,
                'title': note.title,
                'is_public': note.is_public,
                'is_secret': note.is_secret,
                'public_url': f"/notes/public/{note.public_id}/" if note.public_id and note.is_public else "",
                'updated_at': patch_local_updated_at.strftime('%Y-%m-%d %H:%M'),
                'toc': note.toc or [],
                'message': '更新成功'
            }
            return JsonResponse(response_data)
        except Exception as e:
            logger.error(f"更新笔记 {note_id} 时发生错误: {e}", exc_info=True)
            return JsonResponse({'error': '更新失败，请稍后重试'}, status=500)

    # --- 4. DELETE 请求处理 (已优化) ---
    if request.method == 'DELETE':
        try:
            note_id_for_log = note.id  # 在删除前保存ID，用于日志记录
            note_title = note.title  # 在删除前保存标题，用于通知
            note.delete()
            # [优化] 使用辅助函数清理缓存
            cache.delete(get_sidebar_cache_key(request.user.id))

            # 发送笔记删除通知
            send_note_activity_notification(request, request.user, note_title, 'deleted')

            # 返回 200 OK 并附带成功信息是常见的做法。
            # 另一种选择是返回 status=204 (No Content)，此时响应体必须为空。
            return JsonResponse({'status': 'success', 'message': '笔记已成功删除'}, status=200)
        except Exception as e:
            # [优化] 使用 logging 记录错误，而不是 print
            logger.error(f"删除笔记 {note_id_for_log} 时发生错误: {e}", exc_info=True)
            return JsonResponse({'error': '删除过程中发生内部错误'}, status=500)

@login_required
@require_http_methods(["POST"])
def create_note_api(request):
    """
    为当前登录用户创建一篇新的空白笔记。
    支持指定 folder_id 将笔记放入特定文件夹。
    支持 is_secret 参数标记为保密笔记。

    【安全】创建保密笔记时，必须先通过 2FA 验证（保密柜已解锁）。
    """
    user = request.user

    try:
        # 解析请求体
        data = json.loads(request.body) if request.body else {}
        title = data.get('title', '无标题笔记')
        content = data.get('content', '')
        folder_id = data.get('folder_id')
        is_secret = data.get('is_secret', False)  # 添加保密参数
        is_public = data.get('is_public', False)

        if is_public:
            allowed, error_msg = check_public_note_publish_permission(user)
            if not allowed:
                return JsonResponse({'error': error_msg, 'message': error_msg}, status=403)

        # 【安全检查】创建保密笔记时，必须已通过 2FA 验证
        if is_secret:
            profile = getattr(user, 'profile', None)
            if profile and profile.two_fa_enabled:
                if not check_vault_access(request):
                    return JsonResponse({
                        'status': 'error',
                        'code': 'vault_locked',
                        'message': '创建保密笔记需要先解锁保密柜'
                    }, status=403)

        # 验证文件夹归属（如果指定了 folder_id）
        folder = None
        if folder_id is not None and folder_id != '':
            # 确保 folder_id 是整数类型
            try:
                folder_id = int(folder_id)
            except (ValueError, TypeError):
                return JsonResponse({'error': '无效的文件夹ID'}, status=400)

            try:
                folder = Folder.objects.get(id=folder_id, owner=user)
            except Folder.DoesNotExist:
                return JsonResponse({'error': '文件夹不存在或无权访问'}, status=400)

        # 创建新的笔记实例
        new_note = Note.objects.create(
            author=user,
            title=title,
            content=content,
            folder=folder,
            is_secret=is_secret,  # 设置保密标志
            is_public=is_public,
        )
        if new_note.is_public and not new_note.public_id:
            new_note.public_id = uuid.uuid4()
            new_note.save(update_fields=['public_id'])

        # 清除侧边栏缓存
        try:
            cache.delete(get_sidebar_cache_key(user.id))
        except Exception:
            pass  # 缓存清除失败不影响主流程

        log_action(user, new_note, 1, f'创建笔记「{new_note.title}」')

        # 发送笔记创建通知
        send_note_activity_notification(request, user, new_note.title, 'created')

        return JsonResponse({
            'id': new_note.id,
            'title': new_note.title,
            'folder_id': folder.id if folder else None,
            'is_secret': new_note.is_secret
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': '无效的请求数据'}, status=400)
    except Http404:
        raise
    except Exception as e:
        logger.error(f"为用户 {user.id} 创建新笔记时出错: {e}", exc_info=True)
        return JsonResponse({'error': '创建笔记时发生内部错误'}, status=500)

@login_required
@require_http_methods(["POST"])
def update_note_api(request, note_id):
    """
    更新指定笔记的标题和内容。

    如果笔记标记为 is_secret，前端已经加密了内容。
    后端不进行任何加密操作，直接存储接收到的内容。
    """
    user = request.user

    try:
        # 获取笔记并验证权限
        try:
            note = Note.objects.get(id=note_id, author=user)
        except Note.DoesNotExist:
            return JsonResponse({'error': '笔记不存在或无权访问'}, status=404)

        # 解析请求体
        data = json.loads(request.body) if request.body else {}
        title = data.get('title')
        content = data.get('content')

        allowed, error_msg, clear_vault_guard = validate_vault_encryption_content_update(request, note, data)
        if not allowed:
            return JsonResponse({'error': error_msg, 'message': error_msg}, status=409)

        was_public = note.is_public

        # 更新笔记（前端已处理加密，后端直接存储）
        if title is not None:
            note.title = title
        if content is not None:
            note.content = content

        note.last_modified_by = user
        note.save()
        if was_public:
            _invalidate_public_notes_cache()
        if clear_vault_guard:
            _clear_vault_pending_encryption_guard(request, note.id)

        # 清除侧边栏缓存
        try:
            cache.delete(get_sidebar_cache_key(user.id))
        except Exception:
            pass

        # 发送笔记修改通知
        send_note_activity_notification(request, user, note.title, 'updated')

        return JsonResponse({
            'status': 'success',
            'id': note.id,
            'title': note.title,
            'toc': note.toc,
            'updated_at': note.updated_at.isoformat()
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': '无效的请求数据'}, status=400)
    except Http404:
        raise
    except Exception as e:
        logger.error(f"为用户 {user.id} 更新笔记 {note_id} 时出错: {e}", exc_info=True)
        return JsonResponse({'error': '更新笔记时发生内部错误'}, status=500)

@login_required
@require_http_methods(["POST"])
def delete_note_api(request, note_id):
    """
    删除指定笔记（移至回收站）。
    """
    user = request.user

    try:
        # 获取笔记并验证权限
        try:
            note = Note.objects.get(id=note_id, author=user)
        except Note.DoesNotExist:
            return JsonResponse({'error': '笔记不存在或无权访问'}, status=404)

        was_public = note.is_public

        # 移至回收站
        note.is_trashed = True
        note.trashed_at = timezone.now()
        note.save()
        if was_public:
            _invalidate_public_notes_cache()

        # 清除侧边栏缓存
        try:
            cache.delete(get_sidebar_cache_key(user.id))
        except Exception:
            pass

        log_action(user, note, 3, f'移入回收站「{note.title}」')

        # 发送笔记删除通知
        send_note_activity_notification(request, user, note.title, 'deleted')

        return JsonResponse({
            'status': 'success',
            'message': '笔记已移至回收站'
        })
    except Http404:
        raise
    except Exception as e:
        logger.error(f"为用户 {user.id} 删除笔记 {note_id} 时出错: {e}", exc_info=True)
        return JsonResponse({'error': '删除笔记时发生内部错误'}, status=500)

@login_required
@csrf_protect
@require_http_methods(["POST"])
def toggle_secret_api(request, note_id):
    """
    切换笔记的保密状态（is_secret 标记）。

    前端E2E加密流程：
    - 当 is_secret=true 时，前端在保存时使用 crypto-js 加密内容
    - 当 is_secret=false 时，前端保存明文内容
    - 后端仅更新标记，不进行任何加密/解密操作
    """
    user = request.user

    try:
        # 获取笔记并验证权限
        try:
            note = Note.objects.get(id=note_id, author=user)
        except Note.DoesNotExist:
            return JsonResponse({'error': '笔记不存在或无权访问'}, status=404)

        # 切换 is_secret 标记
        was_public = note.is_public
        was_secret = note.is_secret
        note.is_secret = not note.is_secret
        if not was_secret and note.is_secret:
            _set_vault_pending_encryption_guard(request, note)
            if note.is_public:
                note.is_public = False
        else:
            _clear_vault_pending_encryption_guard(request, note.id)
        note.save()
        if was_public or note.is_public:
            _invalidate_public_notes_cache()

        # 清除侧边栏缓存
        try:
            cache.delete(get_sidebar_cache_key(user.id))
        except Exception:
            pass

        return JsonResponse({
            'status': 'success',
            'is_secret': note.is_secret,
            'is_public': note.is_public,
            'message': '保密状态已更新'
        })
    except Http404:
        raise
    except Exception as e:
        logger.error(f"为用户 {user.id} 切换笔记 {note_id} 的保密状态时出错: {e}", exc_info=True)
        return JsonResponse({'error': '更新保密状态时发生内部错误'}, status=500)

