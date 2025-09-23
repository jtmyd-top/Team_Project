# knowledge_project/views.py
from django.contrib.auth import login
from .utils.code import check_code
from django.http import HttpResponse
from io import BytesIO
from django.contrib.auth.forms import AuthenticationForm
from django.utils import timezone
from django.urls import reverse
import hashlib
from .forms import CustomUserCreationForm
from django.contrib.auth.forms import UserCreationForm
from django import forms
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django.contrib.auth.models import User
from .models import auto_generate_tags_for_note
from django.core.mail import send_mail
import random
import string
import time
import re
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from bs4 import BeautifulSoup, Tag,NavigableString
from django.db.models import Q
import json # <--- 确保在文件顶部导入了 json 模块
from django.core.paginator import Paginator  # 添加这行导入
from django.core.cache import cache
from .models import  Note,Asset ,Tag
from django.shortcuts import render, redirect
from django.contrib import messages
import subprocess
import hashlib
from .utils.avatars import save_user_avatar
from django.conf import settings
from django.http import JsonResponse, HttpResponseForbidden, Http404, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from .models import Asset
import mimetypes
import os
import uuid  # 确保导入 uuid
from django.shortcuts import render, get_object_or_404
import logging
from .utilt import get_sidebar_cache_key
from django.core.files.base import ContentFile
from collections import deque
# 导入 F 对象用于精细化内容切片
import math # 导入 math 用于计算总页数
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth.hashers import check_password

# 定义富文本分页函数
# 定义富文本分页函数
# --- 分页辅助函数 ---
from bs4 import BeautifulSoup # 确保已导入

# --- vvv 用下面的代码替换旧的 get_paginated_html 函数 vvv ---
USERNAME_REGEX = re.compile(r'^[a-z][a-z0-9_]{5,}$')
def get_paginated_html(html_content, page_number=1, chars_per_page=500):
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


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, help_text='必填项。')

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('email',)
logger = logging.getLogger(__name__)
def _check_email_availability(request, email: str, *, exclude_self: bool = False):
    """
    统一的邮箱可用性检查逻辑（供多个视图共用）
    - 返回 dict: {'ok': True/False, 'reason': 'invalid'/'taken'/'ok', 'message': str}
    - exclude_self=True 时，会排除当前登录用户（用于“修改邮箱”场景）
    """
    email = (email or "").strip()
    if not email:
        return {'ok': False, 'reason': 'invalid', 'message': '邮箱不能为空'}

    try:
        validate_email(email)
    except ValidationError:
        return {'ok': False, 'reason': 'invalid', 'message': '邮箱格式不正确'}

    qs = User.objects.filter(email__iexact=email)
    # if exclude_self and request.user.is_authenticated:
    #     qs = qs.exclude(pk=request.user.pk)

    if qs.exists():
        return {'ok': False, 'reason': 'taken', 'message': '该邮箱已被绑定'}
    return {'ok': True, 'reason': 'ok', 'message': ''}
class SendEmailCodeView(View):
    """
    验证图片验证码 -> 发送邮箱验证码
    兼容两种业务：
    - 注册: purpose='register'（默认）
    - 修改邮箱: purpose='change'
    """
    def post(self, request, *args, **kwargs):
        # 1) 识别客户端 IP，用于限流
        ip_address = request.META.get('REMOTE_ADDR')
        hourly_key = f"email_attempts_hourly_{ip_address}"
        daily_key  = f"email_attempts_daily_{ip_address}"

        # 2) 限流（维持你现有阈值）
        hourly_attempts = cache.get(hourly_key, 0)
        if hourly_attempts >= 30:
            return JsonResponse({'status': 'error', 'message': '当前网络环境达到极限，请稍后再试。'}, status=429)

        daily_attempts = cache.get(daily_key, 0)
        if daily_attempts >= 50:
            return JsonResponse({'status': 'error', 'message': '当前网络环境达到极限，请稍后再试。'}, status=429)

        # 3) 解析参数
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': '请求格式错误'}, status=400)

        email = (data.get('email') or '').strip()
        image_captcha_code = (data.get('image_captcha_code') or '').strip().upper()
        purpose = (data.get('purpose') or 'register').strip()  # 'register' | 'change'

        # 4) 校验图片验证码（并单次使用）
        session_code = (request.session.get('captcha_code') or '').upper()
        if 'captcha_code' in request.session:
            del request.session['captcha_code']
        if not session_code or session_code != image_captcha_code:
            return JsonResponse({'status': 'error', 'message': '图片验证码错误'}, status=400)

        # 5) 业务区分 & 邮箱可用性检查（共用工具函数）
        if purpose == 'change':
            # 未登录不能走“修改邮箱”
            if not request.user.is_authenticated:
                return JsonResponse({'status': 'error', 'message': '未登录用户无法修改邮箱'}, status=403)

            # 禁止把新邮箱改成当前邮箱（防止滥发验证码）
            if email and request.user.email and email.lower() == request.user.email.lower():
                return JsonResponse({'status': 'error', 'message': '该邮箱与当前绑定邮箱一致，无需修改'}, status=400)

            # 修改邮箱：排除自己判断占用
            check = _check_email_availability(request, email, exclude_self=True)
            if not check['ok']:
                return JsonResponse({'status': 'error', 'message': check['message']}, status=400)

            mail_subject = '邮箱修改验证码'
            ok_message   = '验证码已发送至您的新邮箱'
        else:
            # 注册：谁绑了都算占用
            check = _check_email_availability(request, email, exclude_self=False)
            if not check['ok']:
                # 为了与之前前端体验一致，文案使用“已被注册”
                msg = '该邮箱已被注册' if check['reason'] == 'taken' else check['message']
                return JsonResponse({'status': 'error', 'message': msg}, status=400)

            mail_subject = '注册验证码'
            ok_message   = '验证码已发送至您的邮箱'

        # 6) 生成并发送邮件
        email_code = ''.join(random.choices(string.digits, k=6))
        try:
            send_mail(
                mail_subject,
                f'您的{mail_subject}是：{email_code}。10分钟内有效。',
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
        except Exception as e:
            print(f"邮件发送失败 (IP: {ip_address}, Email: {email}), 错误: {e}")
            return JsonResponse({'status': 'error', 'message': '邮件发送失败，请稍后重试。'}, status=500)

        # 7) 发送成功后，更新限流计数
        if hourly_attempts == 0:
            cache.set(hourly_key, 1, timeout=3600)   # 1小时
        else:
            cache.incr(hourly_key)

        if daily_attempts == 0:
            cache.set(daily_key, 1, timeout=86400)  # 24小时
        else:
            cache.incr(daily_key)

        # 8) 把验证码写入 session，沿用你现有的 key
        request.session['registration_verification'] = {
            'code': email_code,
            'email': email,
            'timestamp': time.time(),
            'purpose': purpose,  # 记录用途，方便后续需要时校验
        }

        return JsonResponse({'status': 'success', 'message': ok_message})

def captcha_image(request):
    """
    生成验证码图片并将其存储在 session 中
    """
    # 调用工具函数生成验证码图片和随机码
    img, code = check_code()

    # 将验证码保存到 session，用于后续验证
    request.session['captcha_code'] = code

    # 使用 BytesIO 将图像写入内存字节流
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    image_data = buffer.getvalue()

    # 返回 HTTP 响应，设置 content_type 为 image/png
    return HttpResponse(image_data, content_type='image/png')



# --- 视图：实时检查用户名是否存在 (新功能) ---
def check_username(request):
    """检查用户名是否可用"""
    username = request.GET.get("username", "").strip()
    if not username:
        return JsonResponse({"error": "Username not provided"}, status=400)
    # 正则检查
    if not USERNAME_REGEX.match(username):
        return JsonResponse({
            "is_taken": True,
            "message": "用户名至少6位，以小写字母开头，只能包含字母数字下划线"
        })
    # 查重
    is_taken = User.objects.filter(username__iexact=username).exists()
    return JsonResponse({"is_taken": is_taken})
def check_email(request):
    """
    实时检查邮箱是否已被绑定
    - GET /check-email/?email=xxx[&exclude_self=1]
    - 返回：{'is_taken': bool, 'message': '...'(可选)}
    """
    email = request.GET.get('email', '').strip()
    exclude_self = request.GET.get('exclude_self') == '1'

    result = _check_email_availability(request, email, exclude_self=exclude_self)

    # 为了兼容你之前的前端，沿用 is_taken 字段
    # invalid 视为 is_taken=True，并返回 message（这样前端可以统一提示）
    if not result['ok']:
        return JsonResponse({'is_taken': True, 'message': result['message']})
    return JsonResponse({'is_taken': False})

class CustomLoginView(View):
    """
    一个完全自定义的登录视图，用于处理 /login/ 路径。
    """
    template_name = 'registration/login.html'

    # 登录成功后的默认跳转地址
    next_page = reverse_lazy('home')
    def dispatch(self, request, *args, **kwargs):
        # 核心逻辑：如果用户已登录，直接重定向到首页
        if request.user.is_authenticated:
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        form = AuthenticationForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request, *args, **kwargs):
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            # 【关键修正】使用 form.get_user() 来获取认证成功的用户
            user = form.get_user()
            login(request, user)  # 为用户创建登录会话

            # 【建议修正】返回的 message 应该与登录行为匹配
            return JsonResponse({
                'status': 'success',
                'message': '登录成功！即将跳转到首页。',
                'redirect_url': reverse('home')
            })

        # 如果表单无效，重新渲染页面并显示错误
        return render(request, self.template_name, {'form': form})


class SignUpView(View):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        return render(request, 'registration/signup.html')

    def post(self, request, *args, **kwargs):
        # 注意：由于您前端使用 FormData，数据在 request.POST 中

        # 【核心修改】使用我们功能更强的自定义表单
        form = CustomUserCreationForm(request.POST)

        email = request.POST.get('email')
        email_code = request.POST.get('emailCode')

        # 1. 验证邮箱验证码 (这部分逻辑保持不变)
        verification_info = request.session.get('registration_verification')
        if not verification_info or verification_info.get('email') != email or verification_info.get('code') != email_code:
            # 返回一个更结构化的错误，方便前端处理
            return JsonResponse({'status': 'error', 'errors': {'emailCode': [{'message': '邮箱验证码错误或已过期'}]}},status=400)

        # 2. 使用表单验证其他所有数据 (用户名、密码、邮箱格式、邮箱是否唯一)
        if form.is_valid():
            # 表单验证通过，直接保存即可创建用户
            # 因为我们的自定义表单已经包含了email字段，所以不再需要手动设置
            user = form.save()
            user.is_active = True
            user.save()

            avatar_path, avatar_source = save_user_avatar(user.email, user.username)
            if avatar_path and os.path.exists(avatar_path):
                with open(avatar_path, "rb") as f:
                    user.profile.avatar.save(os.path.basename(avatar_path), ContentFile(f.read()), save=False)
                    user.profile.avatar_source = avatar_source
                    user.profile.save(update_fields=["avatar", "avatar_source"])
            # 清理 session
            del request.session['registration_verification']

            # 注册成功后自动登录 (可选，但极大提升用户体验)
            from django.contrib.auth import login
            login(request, user)

            # 返回成功响应，跳转到知识库
            return JsonResponse({
                'status': 'success',
                'message': '注册成功！即将跳转到您的知识库。',
                'redirect_url': reverse('knowledge_list')
            })
        else:
            # 如果表单验证失败，返回所有错误信息
            return JsonResponse({'status': 'error', 'errors': form.errors.get_json_data()}, status=400)


# knowledge_project/views.py (public_note_view 部分)

def public_note_view(request, public_id):
    try:
        note = Note.objects.get(public_id=public_id, is_public=True)
        context = {
            'note_data': {
                'id': note.id,
                'public_id': str(note.public_id), # <--- 【新增】将 public_id 加入数据
                'title': note.title,
                'author': {'username': note.author.username if note.author else '匿名作者'},
                'created_at': note.created_at.strftime('%Y-%m-%d %H:%M')
            },
            'full_content_data': note.content or "",
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
            .order_by('-updated_at') # 按更新时间排序更实用
            .values('id', 'title')
        )
        # 缓存结果
        cache.set(sidebar_notes_key, sidebar_notes, timeout=900) # 缓存15分钟

    initial_data = {
        'sidebar_notes': sidebar_notes,
        'has_notes': bool(sidebar_notes),
        'csrf_token': request.COOKIES.get('csrftoken')
    }
    context = {'initial_data': initial_data}
    return render(request, 'knowledge/knowledge_list.html', context)


@login_required
@require_http_methods(["GET", "PUT", "DELETE"])
def note_detail_api(request, note_id):
    note = get_object_or_404(Note, pk=note_id)
    if not note.has_permission(request.user):
        return HttpResponseForbidden("您没有权限访问此笔记。")
    # --- 统一进行时区转换 ---
    # 使用 timezone.localtime 将数据库中的UTC时间转换为settings.py中定义的本地时间
    local_updated_at = timezone.localtime(note.updated_at)
    local_created_at = timezone.localtime(note.created_at)
    if request.method == 'GET':
        if request.GET.get('full_content') == 'true':
            data = {
                'id': note.id,
                'title': note.title,
                'content': note.content or "",
                'is_public': note.is_public,
                'public_url': f"/notes/public/{note.public_id}/" if note.public_id and note.is_public else "",
                'updated_at': local_updated_at.strftime('%Y-%m-%d %H:%M'),  # 使用转换后的时间
                'last_modified_by': {'username': note.last_modified_by.username} if note.last_modified_by else None,
                'tags': [{'id': tag.id, 'name': tag.name} for tag in note.tags.all()],
            }
            return JsonResponse(data)

        page = request.GET.get('page', 1)
        paginated_content, total_pages = get_paginated_html(note.content, page)
        data = {
            'id': note.id,
            'title': note.title,
            'content': paginated_content,
            'is_public': note.is_public,
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
        return JsonResponse(data)

    if request.method == 'PUT':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': '无效的JSON格式'}, status=400)

        note.title = data.get('title', note.title)
        note.is_public = data.get('is_public', note.is_public)
        if 'content' in data:
            note.content = data['content']
        note.last_modified_by = request.user
        if note.is_public and not note.public_id:
            note.public_id = uuid.uuid4()
        note.save()
        if note.content and len(BeautifulSoup(note.content, 'html.parser').get_text()) > 20:

            auto_generate_tags_for_note(Note, note, created=True)
        cache.delete(get_sidebar_cache_key(request.user.id))
        # --- 在PUT响应中也进行时区转换 ---
        put_local_updated_at = timezone.localtime(note.updated_at)
        put_local_created_at = timezone.localtime(note.created_at)

        paginated_content, total_pages = get_paginated_html(note.content, 1)
        updated_data = {
            'id': note.id,
            'title': note.title,
            'content': paginated_content,
            'is_public': note.is_public,
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

    # --- 4. DELETE 请求处理 (已优化) ---
    if request.method == 'DELETE':
        try:
            note_id_for_log = note.id  # 在删除前保存ID，用于日志记录
            note.delete()
            # [优化] 使用辅助函数清理缓存
            cache.delete(get_sidebar_cache_key(request.user.id))
            # 返回 200 OK 并附带成功信息是常见的做法。
            # 另一种选择是返回 status=204 (No Content)，此时响应体必须为空。
            return JsonResponse({'status': 'success', 'message': '笔记已成功删除'}, status=200)
        except Exception as e:
            # [优化] 使用 logging 记录错误，而不是 print
            logger .error(f"删除笔记 {note_id_for_log} 时发生错误: {e}", exc_info=True)
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
    results = Note.objects.filter(search_condition, author=user).order_by('-updated_at').values('id', 'title')

    return JsonResponse(list(results), safe=False)


@login_required
def get_all_notes_api(request):
    user = request.user
    sidebar_notes_key = f"sidebar_notes_user_{user.id}"
    all_notes = cache.get(sidebar_notes_key)

    if all_notes is None:
        # 【修改点】查询逻辑与 knowledge_list 视图保持一致
        all_notes = list(
            Note.objects.filter(author=user)
            .order_by('-updated_at')
            .values('id', 'title')
        )
        cache.set(sidebar_notes_key, all_notes, timeout=900)

    return JsonResponse(all_notes, safe=False)
# --- 【新增】哈希计算辅助函数 ---
def calculate_file_hash(file):
    """高效计算文件的 SHA256 哈希值"""
    hasher = hashlib.sha256()
    # 以块的形式读取，防止大文件撑爆内存
    for chunk in file.chunks():
        hasher.update(chunk)
    # 将文件指针移回开头，以便 Django 后续可以正常保存文件
    file.seek(0)
    return hasher.hexdigest()
# --- 【新增】TinyMCE 图片上传视图 ---
# 我提供的、已移除 Project 依赖的 views.py 中的函数
@login_required
@require_http_methods(["POST"])
def image_upload_view(request):
    """
    处理图片上传，并包含用户级去重功能。
    此版本已移除对 Project 的依赖。
    """
    if 'file' not in request.FILES:
        return JsonResponse({'error': '没有找到上传的文件。'}, status=400)

    image_file = request.FILES['file']
    current_user = request.user

    # 1. 计算文件哈希值 (这部分逻辑与您原来的一样)
    try:
        file_hash = calculate_file_hash(image_file)
    except Exception as e:
        logger.error(f"为用户 {current_user.id} 计算哈希值时出错: {e}", exc_info=True)
        return JsonResponse({'error': '无法处理该文件。'}, status=500)

    # --- 核心去重逻辑在这里，完全保留 ---
    # 2. 检查当前用户是否已上传过相同内容的文件
    try:
        # 这个查询与您原始代码中的查询完全相同！
        existing_asset = Asset.objects.filter(uploader=current_user, image_hash=file_hash).first()

        # 如果找到了重复的文件，就直接返回现有文件的URL
        if existing_asset and existing_asset.file:
            logger.info(f"为用户 {current_user.id} 检测到重复图片。")
            return JsonResponse({'location': existing_asset.get_protected_url()})

    except Exception as e:
        logger.error(f"查询重复图片时出错: {e}", exc_info=True)
        # 即使查询出错，我们也可以继续尝试保存，而不是中断流程

    # --- 如果不是重复文件，则执行保存逻辑 ---
    # 3. 采用“两阶段保存”策略，保存新文件
    try:
        # 创建一个不包含文件的实例
        new_asset = Asset(
            uploader=current_user,
            asset_type='image',
            image_hash=file_hash,
            name=image_file.name
            # 注意：project=None 已经不再需要，因为模型里没有这个字段了
        )
        new_asset.save()  # 第一次保存

        # 关联并保存文件
        new_asset.file = image_file
        new_asset.save()  # 第二次保存

        logger.info(f"为用户 {current_user.id} 上传了新图片。")
        return JsonResponse({'location': new_asset.get_protected_url()})

    except Exception as e:
        logger.error(f"为用户 {current_user.id} 保存新图片失败: {e}", exc_info=True)
        # 清理可能产生的孤立记录
        if 'new_asset' in locals() and new_asset.pk:
            new_asset.delete()
        return JsonResponse({'error': '服务器保存文件时出错。'}, status=500)
@login_required
def protected_media_view(request, file_path):
    """【核心修改】权限检查现在只验证上传者。"""
    try:
        asset = Asset.objects.get(file=file_path)
    except Asset.DoesNotExist:
        raise Http404

    # 【修改点】权限检查逻辑简化，移除了对项目的检查
    # 只有文件的上传者才能访问
    if asset.uploader != request.user:
        return HttpResponseForbidden("您无权访问此文件。")

    # 文件服务逻辑保持不变
    file_full_path = os.path.join(settings.MEDIA_ROOT, file_path)
    try:
        with open(file_full_path, 'rb') as f:
            content_type, _ = mimetypes.guess_type(file_full_path)
            return HttpResponse(f.read(), content_type=content_type or 'application/octet-stream')
    except FileNotFoundError:
        raise Http404


@login_required
@require_http_methods(["POST"])
def ckeditor_image_upload_view(request):
    """
    处理 django-ckeditor-5 的图片上传请求。
    【最终修复版】：
    - 强制使用“两阶段保存”，确保用户文件夹路径正确。
    - 返回受保护的 URL (get_protected_url)，确保前端能正确显示。
    """
    if 'upload' not in request.FILES:
        return JsonResponse({'error': {'message': '没有找到上传的文件。'}}, status=400)

    image_file = request.FILES['upload']
    current_user = request.user

    # 1. 计算哈希值 (逻辑不变)
    try:
        file_hash = calculate_file_hash(image_file)
    except Exception as e:
        logger.error(f"[CKEditor] 为用户 {current_user.id} 计算哈希值时出错: {e}", exc_info=True)
        return JsonResponse({'error': {'message': '无法处理该文件。'}}, status=500)

    # 2. 检查重复 (逻辑不变，但返回的 URL 需要修改)
    try:
        existing_asset = Asset.objects.filter(uploader=current_user, image_hash=file_hash).first()
        if existing_asset and existing_asset.file:
            logger.info(f"[CKEditor] 为用户 {current_user.id} 检测到重复图片。")
            # 【核心修改】直接返回 get_protected_url() 生成的相对路径
            return JsonResponse({'url': existing_asset.get_protected_url()})
    except Exception as e:
        logger.error(f"[CKEditor] 查询重复图片时出错: {e}", exc_info=True)

    # 3. 采用“两阶段保存” (逻辑不变)
    try:
        # 阶段一：保存元数据
        new_asset = Asset(
            uploader=current_user,
            project=None,
            asset_type='image',
            image_hash=file_hash,
            name=image_file.name
        )
        new_asset.save()

        # 阶段二：关联并保存文件
        new_asset.file = image_file
        new_asset.save()

        logger.info(f"[CKEditor] 为用户 {current_user.id} 上传了新图片。")
        # 【核心修改】直接返回新建资产的、受保护的相对URL
        return JsonResponse({'url': new_asset.get_protected_url()})

    except Exception as e:
        logger.error(f"[CKEditor] 为用户 {current_user.id} 保存新图片失败: {e}", exc_info=True)
        if 'new_asset' in locals() and new_asset.pk:
            new_asset.delete()
        return JsonResponse({'error': {'message': '服务器保存文件时出错。'}}, status=500)


# --- 【新增】创建新笔记的 API 视图 ---
# knowledge_project/views.py

@login_required
@require_http_methods(["POST"])
def create_note_api(request):
    """
    为当前登录用户创建一篇新的空白笔记。
    【修正版】：笔记不关联任何项目
    """
    user = request.user

    try:
        # 创建新的笔记实例，不关联任何项目
        new_note = Note.objects.create(
            author=user,
            title="无标题笔记",
            content="",

        )

        # 清除侧边栏缓存
        cache.delete(get_sidebar_cache_key(user.id))

        return JsonResponse({
            'id': new_note.id,
            'title': new_note.title
        })
    except Exception as e:
        logger.error(f"为用户 {user.id} 创建新笔记时出错: {e}", exc_info=True)
        return JsonResponse({'error': '创建笔记时发生内部错误'}, status=500)
# 【新增】公开笔记列表视图
def public_notes_api(request):
    """
    一次性返回所有公开笔记的核心数据，用于前端动态渲染。
    """
    notes_qs = Note.objects.filter(is_public=True).order_by('-updated_at').select_related('author').prefetch_related(
        'tags')

    notes_data = []
    for note in notes_qs:
        # 使用BeautifulSoup安全地提取纯文本摘要
        soup = BeautifulSoup(note.content or "", 'html.parser')
        excerpt = soup.get_text()[:150] + '...'  # 截取前150个字符作为摘要

        notes_data.append({
            'id': note.id,
            'title': note.title,
            'public_url': f"/notes/public/{note.public_id}/",
            'author': note.author.username if note.author else "匿名作者",
            'updated_at': note.updated_at.strftime("%Y年%m月%d日"),
            'excerpt': excerpt,
            'tags': [tag.name for tag in note.tags.all()]  # 【新增】获取并添加标签列表
        })

    return JsonResponse(notes_data, safe=False)


# 【修改】简化原有的 public_notes_list_view
def public_notes_list_view(request):
    """
    【修正版】
    此视图现在只负责渲染承载Vue应用的HTML空壳，所有数据由JS通过API加载。
    """
    # 不再需要进行分页或查询数据，直接渲染模板
    return render(request, 'knowledge/public_notes_list.html')
@login_required
def settings_view(request):
    """
    用户个人设置页面
    - 后续可以扩展：处理POST请求修改头像、用户名、邮箱、密码
    """
    return render(request, 'settings/setting.html')
@login_required
@require_http_methods(["POST"])
def upload_avatar(request):
    """上传并更新用户头像"""
    avatar_file = request.FILES.get("avatar")
    if not avatar_file:
        return JsonResponse({"status": "error", "message": "未选择文件"}, status=400)

    user = request.user
    try:
        # 删除旧头像（可选）
        if user.profile.avatar:
            user.profile.avatar.delete(save=False)

        # 保存新头像
        user.profile.avatar.save(avatar_file.name, avatar_file, save=True)

        return JsonResponse({
            "status": "success",
             "avatar_url": request.build_absolute_uri(user.profile.avatar.url)
        })
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)



@login_required
@require_http_methods(["POST"])
def update_profile(request):
    """更新昵称，增加正则校验 + 重名检查"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "JSON 格式错误"}, status=400)

    nickname = data.get("nickname", "").strip()
    if not nickname:
        return JsonResponse({"status": "error", "message": "昵称不能为空"}, status=400)

    # ✅ 正则校验
    if not USERNAME_REGEX.match(nickname):
        return JsonResponse({
            "status": "error",
            "message": "用户名必须至少6位，以小写字母开头，只能包含字母数字下划线"
        }, status=400)

    # ✅ 检查重名
    if User.objects.filter(username=nickname).exclude(pk=request.user.pk).exists():
        return JsonResponse({"status": "error", "message": "该用户名已存在"}, status=400)

    user = request.user
    user.username = nickname
    user.save(update_fields=["username"])

    return JsonResponse({"status": "success", "nickname": user.username})


@login_required
@require_http_methods(["POST"])
def update_email(request):
    """验证密码、图形验证码、邮箱验证码后修改邮箱"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "JSON 格式错误"}, status=400)

    current_password = data.get("password", "")
    new_email = data.get("new_email", "").strip()
    code = data.get("code", "").strip()
    image_captcha_code = data.get("image_captcha_code", "").upper().strip()

    if not current_password or not new_email or not code or not image_captcha_code:
        return JsonResponse({"status": "error", "message": "缺少必要参数"}, status=400)

    # 1) 校验当前密码
    if not request.user.check_password(current_password):
        return JsonResponse({"status": "error", "message": "密码错误"}, status=400)

    # 2) 校验图形验证码（建议与“发送验证码”时使用同一个 /captcha/ 接口，确认时再刷一次）
    session_captcha = request.session.get("captcha_code", "").upper()
    if not session_captcha or session_captcha != image_captcha_code:
        return JsonResponse({"status": "error", "message": "图形验证码错误"}, status=400)
    # 用一次就作废，防复用
    if "captcha_code" in request.session:
        del request.session["captcha_code"]

    # 3) 校验邮箱验证码（含有效期）
    info = request.session.get("registration_verification")
    if not info or info.get("email") != new_email or info.get("code") != code:
        return JsonResponse({"status": "error", "message": "邮箱验证码错误或邮箱不匹配"}, status=400)

    # 有效期 10 分钟
    if time.time() - float(info.get("timestamp", 0)) > 600:
        return JsonResponse({"status": "error", "message": "邮箱验证码已过期，请重新获取"}, status=400)

    # 4) 检查邮箱是否已被占用（再兜底）
    if User.objects.filter(email__iexact=new_email).exclude(pk=request.user.pk).exists():
        return JsonResponse({"status": "error", "message": "该邮箱已被绑定"}, status=400)

    # 5) 更新邮箱
    user = request.user
    user.email = new_email
    user.save(update_fields=["email"])

    # 作废验证码 session
    if "registration_verification" in request.session:
        del request.session["registration_verification"]

    return JsonResponse({"status": "success", "email": user.email, "message": "邮箱修改成功"})


