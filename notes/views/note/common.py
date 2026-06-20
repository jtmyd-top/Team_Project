"""Notes view shared helpers."""
import json
import logging
import threading
import uuid

from bs4 import BeautifulSoup

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.mail import send_mail
from django.db.models import Count, F, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from accounts.models import Profile, ProfileLike
from moderation.models import UserSanction
from notes.models import (
    Folder,
    Note,
    NoteComment,
    auto_generate_tags_for_note,
)
from vault.services import check_vault_access
from notifications.services import notify_user
from core.utils.misc import get_sidebar_cache_key, log_action

logger = logging.getLogger(__name__)

VAULT_PENDING_ENCRYPTION_GUARDS_SESSION_KEY = 'vault_pending_encryption_guards'
PUBLIC_NOTES_CACHE_VERSION_KEY = 'public_notes_api:version'



def _get_public_notes_cache_version():
    return cache.get(PUBLIC_NOTES_CACHE_VERSION_KEY) or 1

def _invalidate_public_notes_cache():
    try:
        cache.incr(PUBLIC_NOTES_CACHE_VERSION_KEY)
    except Exception:
        cache.set(PUBLIC_NOTES_CACHE_VERSION_KEY, int(timezone.now().timestamp()), timeout=None)

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

def check_public_note_publish_permission(user):
    sanction = UserSanction.is_public_note_banned(user)
    if sanction is None:
        return True, None
    if sanction.expires_at is None:
        return False, '你已被禁止发布公开文章。'
    expire_str = timezone.localtime(sanction.expires_at).strftime('%Y-%m-%d %H:%M')
    return False, f'你已被禁止发布公开文章，限制将于 {expire_str} 解除。'

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
        ip_address = get_client_ip(request)

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

    except Http404:
        raise
    except Exception as e:
        # 通知发送失败不应影响正常操作
        logger.error(f"Failed to send note {action_type} notification for user {user.id}: {e}")
