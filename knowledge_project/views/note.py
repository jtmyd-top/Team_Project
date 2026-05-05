"""knowledge_project.views.note

笔记 CRUD / 浏览 / 搜索 / 历史 / 活动通知。从 legacy.py 拆出的 20 个函数/辅助。
"""
import json
import logging
import threading
import uuid

from bs4 import BeautifulSoup

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.mail import send_mail
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from ..decorators import check_vault_access
from ..models import (
    Folder,
    Note,
    NoteComment,
    Profile,
    ProfileLike,
    auto_generate_tags_for_note,
)
from ..utils.misc import get_sidebar_cache_key, log_action

logger = logging.getLogger(__name__)

VAULT_PENDING_ENCRYPTION_GUARDS_SESSION_KEY = 'vault_pending_encryption_guards'


# === 共享辅助 ===

def get_paginated_html(html_content, page_number=1, chars_per_page=3000):
    """
    【修正版】
    通过处理顶级HTML块来进行分页，确保图片<img>等无文本标签不会丢失。
    """
    # 1. 处理特殊情况：如果没有内容，或者内容不足一页，直接返回
    if not html_content or len(html_content) <= chars_per_page:
        return html_content, 1

    # 2. 解析HTML
    soup = BeautifulSoup(html_content, 'html.parser')

    # 3. 获取所有顶级的HTML块 (p, div, h1, img 等)
    #    我们只处理标签，过滤掉标签之间的空白换行符等纯文本节点
    content_blocks = [child for child in soup.children if hasattr(child, 'name')]

    if not content_blocks:
        return html_content, 1

    # 4. 基于这些顶级块进行分页
    pages = []
    current_page_blocks = []
    current_page_chars = 0

    for block in content_blocks:
        # 将块转为字符串以计算其长度
        block_str = str(block)
        block_len = len(block_str)

        # 如果当前页有内容，并且加入新块会超长，则结束当前页
        if current_page_blocks and (current_page_chars + block_len > chars_per_page):
            pages.append("".join(map(str, current_page_blocks)))
            # 开始一个新页面
            current_page_blocks = [block]
            current_page_chars = block_len
        else:
            # 否则，将块加入当前页
            current_page_blocks.append(block)
            current_page_chars += block_len

    # 5. 不要忘记添加最后一页
    if current_page_blocks:
        pages.append("".join(map(str, current_page_blocks)))

    # 6. 安全地获取请求的页码
    total_pages = len(pages)
    try:
        page_number = int(page_number)
        page_number = max(1, min(page_number, total_pages))
    except (ValueError, TypeError):
        page_number = 1

    # 7. 返回对应页面的HTML和总页数
    return pages[page_number - 1], total_pages


def check_note_edit_permission(note):
    """
    檢查筆記是否允許編輯操作。

    Return: (allowed: bool, error_message: str or None)
    - 回收站筆記不允許編輯
    """
    if note.is_trashed:
        return False, '回收站中的筆記無法編輯。請先還原筆記。'
    return True, None


def check_note_secret_operation_permission(note, operation):
    """
    檢查筆記是否允許特定操作（針對保密柜）。

    Args:
        note: Note 模型實例
        operation: 'share', 'favorite', 'publish' 等操作名稱

    Return: (allowed: bool, error_message: str or None)
    - 保密柜筆記不允許分享、收藏和發布
    """
    if note.is_secret:
        messages = {
            'share': '保密柜的筆記無法分享。請先移出保密柜。',
            'favorite': '保密柜的筆記無法收藏。請先移出保密柜。',
            'publish': '保密柜的筆記無法發布為公開。請先移出保密柜。'
        }
        return False, messages.get(operation, f'保密柜的筆記無法執行 {operation} 操作。')
    return True, None


def _coerce_non_negative_int(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def _get_vault_pending_encryption_guards(request):
    guards = request.session.get(VAULT_PENDING_ENCRYPTION_GUARDS_SESSION_KEY)
    return guards if isinstance(guards, dict) else {}


def _set_vault_pending_encryption_guard(request, note):
    guards = _get_vault_pending_encryption_guards(request).copy()
    guards[str(note.id)] = {
        'original_content_length': len(note.content or ""),
        'created_at': timezone.now().isoformat(),
    }
    request.session[VAULT_PENDING_ENCRYPTION_GUARDS_SESSION_KEY] = guards
    request.session.modified = True


def _clear_vault_pending_encryption_guard(request, note_id):
    guards = _get_vault_pending_encryption_guards(request).copy()
    if str(note_id) in guards:
        del guards[str(note_id)]
        request.session[VAULT_PENDING_ENCRYPTION_GUARDS_SESSION_KEY] = guards
        request.session.modified = True


def validate_vault_encryption_content_update(request, note, data, will_be_secret=None):
    """
    Server-side guard for the first encrypted save after a note enters the vault.
    The server cannot decrypt E2E ciphertext, so it enforces the conversion
    protocol: the client must declare the plaintext source length it encrypted,
    and that length must not be shorter than the server-side pre-toggle snapshot.
    """
    if 'content' not in data:
        return True, None, False

    if will_be_secret is None:
        will_be_secret = note.is_secret

    guard = _get_vault_pending_encryption_guards(request).get(str(note.id))
    direct_secret_conversion = (not note.is_secret and data.get('is_secret') is True)

    if not guard and not direct_secret_conversion:
        return True, None, False

    original_length = None
    if isinstance(guard, dict):
        original_length = _coerce_non_negative_int(guard.get('original_content_length'))

    client_original_length = _coerce_non_negative_int(data.get('vault_original_content_length'))
    if original_length is None:
        original_length = client_original_length
    elif client_original_length is not None:
        original_length = max(original_length, client_original_length)

    if original_length is None:
        original_length = len(note.content or "")

    source_length = _coerce_non_negative_int(data.get('vault_source_content_length'))

    if will_be_secret and source_length is None:
        return False, '安全中止：缺少待加密内容长度校验信息。为避免笔记内容丢失，已取消纳入保密柜。', False

    current_length = len(note.content or "")
    if current_length < original_length:
        return False, (
            f'安全中止：待加密内容长度异常变短（当前 {current_length}，原始 {original_length}）。'
            '为避免笔记内容丢失，已取消纳入保密柜。'
        ), False

    if will_be_secret and source_length < original_length:
        return False, (
            f'安全中止：待加密内容长度异常变短（当前 {source_length}，原始 {original_length}）。'
            '为避免笔记内容丢失，已取消纳入保密柜。'
        ), False

    return True, None, bool(guard or direct_secret_conversion)


def build_note_response_data(note, include_content=True, include_all_fields=True):
    """
    構建筆記 API 響應數據，支持字段過濾。

    Args:
        note: Note 模型實例
        include_content: 是否包含 content 字段
        include_all_fields: 是否包含所有字段（True），或僅包含必要字段（False）

    Return: dict - 完整的應答數據結構

    說明：
    - 當 is_secret=True AND is_trashed=True 時，自動不包含 content
    - 前端可根據需要傳遞 include_content 參數
    """
    # 數據最小化：不傳輸敏感組合的加密內容
    if note.is_secret and note.is_trashed:
        include_content = False

    local_updated_at = timezone.localtime(note.updated_at)
    local_created_at = timezone.localtime(note.created_at)

    data = {
        'id': note.id,
        'title': note.title,
        'is_public': note.is_public,
        'is_secret': note.is_secret,
        'is_trashed': note.is_trashed,
        'public_url': f"/notes/public/{note.public_id}/" if note.public_id and note.is_public else "",
        'updated_at': local_updated_at.strftime('%Y-%m-%d %H:%M'),
        'created_at': local_created_at.strftime('%Y-%m-%d %H:%M'),
    }

    if include_content:
        data['content'] = note.content or ""

    if include_all_fields:
        data['author'] = {'id': note.author.id, 'username': note.author.username}
        data['last_modified_by'] = {'username': note.last_modified_by.username} if note.last_modified_by else None
        data['tags'] = [{'id': tag.id, 'name': tag.name} for tag in note.tags.all()]
        data['toc'] = note.toc or []

    return data


# === 笔记活动通知 ===

def send_note_activity_notification(request, user, note_title, action_type):
    """
    发送笔记活动通知邮件

    参数:
        request: HTTP请求对象
        user: 用户对象
        note_title: 笔记标题
        action_type: 操作类型 ('created', 'updated', 'deleted')
    """
    try:
        # 检查用户是否启用了笔记活动通知
        profile = getattr(user, 'profile', None)
        if not profile or not profile.notify_note_activities:
            return  # 用户未启用笔记活动通知

        # 获取操作信息
        ip_address = request.META.get('HTTP_X_FORWARDED_FOR')
        if ip_address:
            ip_address = ip_address.split(',')[0].strip()
        else:
            ip_address = request.META.get('HTTP_X_REAL_IP')
            if not ip_address:
                ip_address = request.META.get('REMOTE_ADDR', '未知')

        user_agent = request.META.get('HTTP_USER_AGENT', '未知设备')
        # CustomLoginView + _send_email_async_helper 住在 auth 模块
        from .auth import CustomLoginView, _send_email_async_helper
        device_info = CustomLoginView().parse_user_agent(user_agent)
        operation_time = timezone.localtime(timezone.now())

        # 根据操作类型设置邮件内容
        action_map = {
            'created': '创建',
            'updated': '修改',
            'deleted': '删除'
        }
        action_text = action_map.get(action_type, '操作')

        email_subject = f'笔记{action_text}通知'
        email_body = f"""
尊敬的 {user.username}：

您于 {operation_time.strftime('%Y年%m月%d日 %H:%M:%S')} {action_text}了笔记「{note_title}」。

操作详情：
- 操作IP地址：{ip_address}
- 操作设备：{device_info}
- 笔记标题：{note_title}

如果这不是您本人的操作，请立即检查您的账户安全。

此邮件为系统自动发送，请勿回复。

知识管理系统
        """

        # 异步发送邮件
        threading.Thread(
            target=_send_email_async_helper,
            args=(email_subject, email_body, [user.email]),
            daemon=True
        ).start()

        logger.info(f"Note {action_type} notification queued for user {user.id}, note: {note_title}")

    except Exception as e:
        # 通知发送失败不应影响正常操作
        logger.error(f"Failed to send note {action_type} notification for user {user.id}: {e}")


# === 公开笔记视图 ===

def public_note_view(request, public_id):
    try:
        note = Note.objects.get(public_id=public_id, is_public=True)
        # 增加查看次数
        note.views += 1
        note.save(update_fields=['views'])

        # 获取所有公开文章的导航数据
        all_public_notes = Note.objects.filter(
            is_public=True
        ).select_related('author').order_by('-updated_at')

        # 构建导航列表
        navigation_list = []
        for nav_note in all_public_notes:
            navigation_list.append({
                'public_id': str(nav_note.public_id),
                'title': nav_note.title,
                'public_url': f"/notes/public/{nav_note.public_id}/"
            })

        # 找到当前文章在列表中的位置
        current_index = -1
        for i, nav_item in enumerate(navigation_list):
            if nav_item['public_id'] == str(note.public_id):
                current_index = i
                break

        # 获取上一篇文章和下一篇文章
        previous_note = None
        next_note = None

        if current_index > 0:
            previous_note = navigation_list[current_index - 1]
        if current_index < len(navigation_list) - 1:
            next_note = navigation_list[current_index + 1]

        # 获取作者头像信息
        author_avatar_url = None
        if note.author:
            try:
                profile = note.author.profile
                if profile.avatar:
                    author_avatar_url = profile.avatar.url
            except Profile.DoesNotExist:
                pass

        # 获取用户点赞状态和总点赞数
        user_has_liked = False
        total_likes = 0
        if request.user.is_authenticated:
            user_has_liked = ProfileLike.objects.filter(liker=request.user, profile__user=note.author).exists()
        total_likes = ProfileLike.objects.filter(profile__user=note.author).count()

        # 获取标签
        note_tags = [tag.name for tag in note.tags.all()]

        # 获取评论数
        comment_count = NoteComment.objects.filter(note=note).count()

        # 获取作者笔记数
        author_note_count = Note.objects.filter(author=note.author, is_public=True).count()

        context = {
            'note_data': {
                'id': note.id,
                'public_id': str(note.public_id),
                'title': note.title,
                'author': {
                    'id': note.author.id if note.author else None,
                    'username': note.author.username if note.author else '匿名作者',
                    'avatar_url': author_avatar_url,
                    'note_count': author_note_count,
                },
                'created_at': note.created_at.strftime('%Y-%m-%d %H:%M'),
                'views': note.views,
                'likes': total_likes,
                'user_has_liked': user_has_liked,
                'tags': note_tags,
                'toc': note.toc or [],
                'comment_count': comment_count,
            },
            'full_content_data': note.content or "",
            'navigation_data': {
                'previous_note': previous_note,
                'next_note': next_note,
                'navigation_list': navigation_list[:5],
                'likes': total_likes,
                'user_has_liked': user_has_liked,
                'is_authenticated': request.user.is_authenticated
            }
        }
        return render(request, 'knowledge/public_note_view.html', context)

    except Note.DoesNotExist:
        # 如果笔记不存在或非公开，返回一个提示页面
        return render(request, 'knowledge/public_note_view.html', {'error_message': '抱歉，这篇笔记不存在或未公开分享。'})
    except Exception as e:
        # 记录未预料到的错误
        print(f"Error in public_note_view for public_id {public_id}: {e}")
        return render(request, 'knowledge/public_note_view.html', {'error_message': '加载笔记时发生了一个错误，请稍后重试。'})


@login_required
def toggle_note_like(request):
    """
    切换笔记作者点赞状态
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': '仅支持POST请求'}, status=405)

    try:
        data = json.loads(request.body)
        note_id = data.get('note_id')

        if not note_id:
            return JsonResponse({'status': 'error', 'message': '笔记ID缺失'}, status=400)

        note = Note.objects.get(id=note_id)

        # 获取作者的profile
        try:
            author_profile = note.author.profile
        except Profile.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': '作者资料不存在'}, status=404)

        # 检查用户是否已经点赞过
        existing_like = ProfileLike.objects.filter(
            liker=request.user,
            profile=author_profile
        ).first()

        if existing_like:
            # 如果已点赞，则取消点赞
            existing_like.delete()
            action = 'unliked'
            user_has_liked = False
        else:
            # 如果未点赞，则添加点赞
            ProfileLike.objects.create(
                liker=request.user,
                profile=author_profile
            )
            action = 'liked'
            user_has_liked = True

        # 计算新的点赞数
        total_likes = ProfileLike.objects.filter(profile__user=note.author).count()

        return JsonResponse({
            'status': 'success',
            'action': action,
            'total_likes': total_likes,
            'user_has_liked': user_has_liked
        })

    except Note.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '笔记不存在'}, status=404)
    except Exception as e:
        print(f"Error in toggle_note_like: {e}")
        return JsonResponse({'status': 'error', 'message': '服务器内部错误'}, status=500)


def home_view(request):
    """
    首页视图 - 展示所有公开的文章
    """
    # 获取所有公开的文章，按更新时间倒序排列
    articles = Note.objects.filter(
        is_public=True
    ).select_related('author').prefetch_related('tags').order_by('-updated_at')[:20]

    context = {
        'articles': articles
    }
    return render(request, 'home.html', context)


@login_required
def knowledge_list(request):
    """【核心修改】此视图现在只加载当前用户作为作者的笔记。"""
    user = request.user
    # 使用辅助函数生成缓存键 (函数本身无需修改)
    sidebar_notes_key = get_sidebar_cache_key(user.id)
    sidebar_notes = cache.get(sidebar_notes_key)

    if sidebar_notes is None:
        # 【修改点】查询逻辑极大简化：只获取当前用户是作者的笔记
        sidebar_notes = list(
            Note.objects.filter(author=user)
            .order_by('-updated_at')  # 按更新时间排序更实用
            .values('id', 'title')
        )
        # 缓存结果
        cache.set(sidebar_notes_key, sidebar_notes, timeout=900)  # 缓存15分钟

    initial_data = {
        'sidebar_notes': sidebar_notes,
        'has_notes': bool(sidebar_notes),
        'csrf_token': request.COOKIES.get('csrftoken')
    }
    context = {'initial_data': initial_data}
    return render(request, 'knowledge/knowledge_list.html', context)


@login_required
@require_http_methods(["GET", "PUT", "PATCH", "DELETE"])
def note_detail_api(request, note_id):
    note = get_object_or_404(Note, pk=note_id)
    if not note.has_permission(request.user):
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
                'is_trashed': note.is_trashed,  # 【新增】返回回收站状态
                'public_url': f"/notes/public/{note.public_id}/" if note.public_id and note.is_public else "",
                'updated_at': local_updated_at.strftime('%Y-%m-%d %H:%M'),  # 使用转换后的时间
                'author': {'id': note.author.id, 'username': note.author.username},
                'last_modified_by': {'username': note.last_modified_by.username} if note.last_modified_by else None,
                'tags': [{'id': tag.id, 'name': tag.name} for tag in note.tags.all()],
                'toc': note.toc or [],  # 添加目录数据
            }
            # 【新增】條件性包含 content
            if include_content:
                data['content'] = note.content or ""
            else:
                data['content_locked'] = True
                data['lock_reason'] = '此笔记位于回收站中，内容已锁定。'
            return JsonResponse(data)

        page = request.GET.get('page', 1)
        paginated_content, total_pages = get_paginated_html(note.content, page) if include_content else ("", 1)
        data = {
            'id': note.id,
            'title': note.title,
            'is_public': note.is_public,
            'is_secret': note.is_secret,
            'is_trashed': note.is_trashed,  # 【新增】返回回收站状态
            'public_url': f"/notes/public/{note.public_id}/" if note.public_id and note.is_public else "",
            # 【已移除】不再返回 project 信息
            #'project': {'id': note.project.id, 'title': note.project.title} if note.project else None,
            'created_at': local_created_at.strftime('%Y-%m-%d %H:%M'),  # 使用转换后的时间
            'author': {'id': note.author.id, 'username': note.author.username},
            'updated_at': local_updated_at.strftime('%Y-%m-%d %H:%M'),  # 使用转换后的时间
            'last_modified_by': {'username': note.last_modified_by.username} if note.last_modified_by else None,
            'tags': [{'id': tag.id, 'name': tag.name} for tag in note.tags.all()],
            'pagination': {
                'current_page': int(page),
                'total_pages': total_pages,
            }
        }
        # 【新增】條件性包含 content 和分页信息
        if include_content:
            data['content'] = paginated_content
        else:
            data['content_locked'] = True
            data['lock_reason'] = '此笔记位于回收站中，内容已锁定。'
        return JsonResponse(data)

    if request.method == 'PUT':
        # 【新增】安全檢查：回收站保護
        allowed, error_msg = check_note_edit_permission(note)
        if not allowed:
            return JsonResponse({'error': error_msg}, status=403)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': '无效的JSON格式'}, status=400)

        # 【新增】安全檢查：防止保密柜筆記發布為公開
        if data.get('is_public') and note.is_secret:
            allowed, error_msg = check_note_secret_operation_permission(note, 'publish')
            if not allowed:
                return JsonResponse({'error': error_msg}, status=403)

        allowed, error_msg, clear_vault_guard = validate_vault_encryption_content_update(request, note, data)
        if not allowed:
            return JsonResponse({'error': error_msg, 'message': error_msg}, status=409)

        note.title = data.get('title', note.title)
        note.is_public = data.get('is_public', note.is_public)
        if 'content' in data:
            note.content = data['content']
        note.last_modified_by = request.user
        if note.is_public and not note.public_id:
            note.public_id = uuid.uuid4()
        note.save()
        if clear_vault_guard:
            _clear_vault_pending_encryption_guard(request, note.id)
        if note.content and len(BeautifulSoup(note.content, 'html.parser').get_text()) > 20:

            auto_generate_tags_for_note(Note, note, created=True)
        cache.delete(get_sidebar_cache_key(request.user.id))

        # 发送笔记修改通知
        send_note_activity_notification(request, request.user, note.title, 'updated')
        # --- 在PUT响应中也进行时区转换 ---
        put_local_updated_at = timezone.localtime(note.updated_at)
        put_local_created_at = timezone.localtime(note.created_at)

        paginated_content, total_pages = get_paginated_html(note.content, 1)
        updated_data = {
            'id': note.id,
            'title': note.title,
            'content': paginated_content,
            'is_public': note.is_public,
            'is_secret': note.is_secret,
            'public_url': f"/notes/public/{note.public_id}/" if note.public_id and note.is_public else "",
            'updated_at': put_local_updated_at.strftime('%Y-%m-%d %H:%M'),  # 使用转换后的时间
            'last_modified_by': {'username': note.last_modified_by.username},
            'author': {'id': note.author.id, 'username': note.author.username},
            'created_at': put_local_created_at.strftime('%Y-%m-%d %H:%M'),  # 使用转换后的时间
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
            if 'is_public' in data and data['is_public'] and note.is_secret:
                allowed, error_msg = check_note_secret_operation_permission(note, 'publish')
                if not allowed:
                    return JsonResponse({'error': error_msg}, status=403)

            # 只更新提供的字段
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
def search_notes_api(request):
    """【核心修改】搜索逻辑现在只在当前用户的笔记中进行。"""
    query = request.GET.get('q', '')
    if not query:
        return JsonResponse([], safe=False)

    user = request.user
    # 【修改点】查询条件简化：标题或内容包含查询字符串，并且作者是当前用户
    search_condition = Q(title__icontains=query) | Q(content__icontains=query)
    results = Note.objects.filter(search_condition, author=user, is_secret=False).order_by('-updated_at').values('id', 'title')

    return JsonResponse(list(results), safe=False)


@login_required
def get_all_notes_api(request):
    """获取所有笔记（排除保密柜笔记）"""
    user = request.user

    # 直接查询数据库，不依赖缓存
    # 这样可以确保 is_secret 过滤总是准确的
    all_notes = list(
        Note.objects.filter(
            author=user,
            is_secret=False,  # 排除保密柜笔记
            is_trashed=False
        )
        .order_by('-updated_at')
        .values('id', 'title', 'is_secret', 'folder_id', 'is_favorited')
    )

    return JsonResponse(all_notes, safe=False)


# --- 【新增】创建新笔记的 API 视图 ---

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
            is_secret=is_secret  # 设置保密标志
        )

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

        # 更新笔记（前端已处理加密，后端直接存储）
        if title is not None:
            note.title = title
        if content is not None:
            note.content = content

        note.last_modified_by = user
        note.save()
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

        # 移至回收站
        note.is_trashed = True
        note.trashed_at = timezone.now()
        note.save()

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
    except Exception as e:
        logger.error(f"为用户 {user.id} 删除笔记 {note_id} 时出错: {e}", exc_info=True)
        return JsonResponse({'error': '删除笔记时发生内部错误'}, status=500)


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
        was_secret = note.is_secret
        note.is_secret = not note.is_secret
        if not was_secret and note.is_secret:
            _set_vault_pending_encryption_guard(request, note)
            if note.is_public:
                note.is_public = False
        else:
            _clear_vault_pending_encryption_guard(request, note.id)
        note.save()

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
    except Exception as e:
        logger.error(f"为用户 {user.id} 切换笔记 {note_id} 的保密状态时出错: {e}", exc_info=True)
        return JsonResponse({'error': '更新保密状态时发生内部错误'}, status=500)


# 【新增】公开笔记列表视图
def public_notes_api(request):
    """
    一次性返回所有公开笔记的核心数据，用于前端动态渲染。
    """
    notes_qs = Note.objects.filter(is_public=True).order_by('-updated_at').select_related('author', 'author__profile').prefetch_related('tags')

    # 预加载当前用户的点赞记录
    user_liked_profile_ids = set()
    if request.user.is_authenticated:
        user_liked_profile_ids = set(
            ProfileLike.objects.filter(liker=request.user).values_list('profile_id', flat=True)
        )

    notes_data = []
    for note in notes_qs:
        # 使用BeautifulSoup安全地提取纯文本摘要
        soup = BeautifulSoup(note.content or "", 'html.parser')
        excerpt = soup.get_text()[:150] + '...'  # 截取前150个字符作为摘要

        # 获取作者头像URL
        author_avatar = None
        if note.author:
            try:
                profile = note.author.profile
                if profile.avatar:
                    author_avatar = profile.avatar.url
            except:
                pass

        # 获取点赞数据
        likes_count = 0
        author_profile_id = None
        if note.author:
            try:
                likes_count = note.author.profile.likes_count
                author_profile_id = note.author.profile.id
            except:
                pass

        notes_data.append({
            'id': note.id,
            'title': note.title,
            'public_url': f"/notes/public/{note.public_id}/",
            'author': note.author.username if note.author else "匿名作者",
            'author_avatar': author_avatar,
            'updated_at': note.updated_at.strftime("%Y年%m月%d日"),
            'created_at': note.updated_at.isoformat(),
            'excerpt': excerpt,
            'tags': [tag.name for tag in note.tags.all()],
            'views': note.views,
            'likes': likes_count,
            'user_has_liked': author_profile_id in user_liked_profile_ids if author_profile_id else False,
            'comments_count': note.comments.count(),
            'is_favorited': note.is_favorited,
        })

    return JsonResponse(notes_data, safe=False)


@login_required
@require_http_methods(["GET"])
def note_history_api(request):
    """获取用户的笔记浏览历史"""
    from ..models import NoteHistory

    user = request.user
    history = NoteHistory.objects.filter(user=user).select_related('note', 'note__author', 'note__author__profile').prefetch_related('note__tags').order_by('-viewed_at')[:100]

    history_data = []
    for item in history:
        note = item.note
        # 使用BeautifulSoup安全地提取纯文本摘要
        soup = BeautifulSoup(note.content or "", 'html.parser')
        excerpt = soup.get_text()[:150] + '...'

        # 获取作者头像URL
        author_avatar = None
        if note.author:
            try:
                profile = note.author.profile
                if profile.avatar:
                    author_avatar = profile.avatar.url
            except:
                pass

        history_data.append({
            'id': note.id,
            'title': note.title,
            'public_url': f"/notes/public/{note.public_id}/",
            'author': note.author.username if note.author else "匿名作者",
            'author_avatar': author_avatar,
            'created_at': note.created_at.isoformat(),
            'excerpt': excerpt,
            'tags': [tag.name for tag in note.tags.all()],
            'views': note.views,
            'comments_count': note.comments.count(),
            'is_favorited': note.is_favorited,
            'user_has_liked': False,
        })

    return JsonResponse(history_data, safe=False)


@login_required
@require_http_methods(["POST"])
def record_note_history_api(request):
    """记录用户浏览笔记的历史"""
    from ..models import NoteHistory

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': '无效的 JSON 格式'}, status=400)

    note_id = data.get('note_id')
    if not note_id:
        return JsonResponse({'error': '缺少 note_id 参数'}, status=400)

    try:
        note = Note.objects.get(id=note_id, is_public=True)
    except Note.DoesNotExist:
        return JsonResponse({'error': '笔记不存在或不是公开笔记'}, status=404)

    user = request.user
    # 使用 update_or_create 来更新或创建历史记录
    history, created = NoteHistory.objects.update_or_create(
        user=user,
        note=note,
        defaults={'viewed_at': timezone.now()}
    )

    return JsonResponse({
        'status': 'success',
        'message': '浏览历史已记录'
    })


# 【修改】简化原有的 public_notes_list_view
def public_notes_list_view(request):
    """
    【修正版】
    此视图现在只负责渲染承载Vue应用的HTML空壳，所有数据由JS通过API加载。
    """
    # 不再需要进行分页或查询数据，直接渲染模板
    return render(request, 'knowledge/public_notes_list.html')
