# knowledge_project/views.py
from django.contrib.auth import login
from knowledge_project.static.utils.code import check_code
from django.http import HttpResponse
from io import BytesIO
from django.contrib.auth.forms import AuthenticationForm

from django.urls import reverse

from .forms import CustomUserCreationForm
from django.contrib.auth.forms import UserCreationForm
from django import forms
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django.contrib.auth.models import User
from django.conf import settings
from django.core.mail import send_mail

import random
import string
import time
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404

from django.http import JsonResponse
from django.db.models import Q
import json # <--- 确保在文件顶部导入了 json 模块
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from .models import Project, Note
class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, help_text='必填项。')

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('email',)


class SendEmailCodeView(View):
    """
    验证图片验证码，成功后再发送邮箱验证码。
    【包含小时和天级别的IP发送限制】
    """

    def post(self, request, *args, **kwargs):
        # 1. 识别客户端IP
        ip_address = request.META.get('REMOTE_ADDR')

        # 2. 定义不同时间窗口的缓存键
        hourly_key = f"email_attempts_hourly_{ip_address}"
        daily_key = f"email_attempts_daily_{ip_address}"

        # 3. 检查小时限制 (1小时内最多3次)
        hourly_attempts = cache.get(hourly_key, 0)
        if hourly_attempts >= 3:
            return JsonResponse({'status': 'error', 'message': '当前网络环境达到极限，请稍后再试。'}, status=429)

        # 4. 检查天限制 (24小时内最多5次)
        daily_attempts = cache.get(daily_key, 0)
        if daily_attempts >= 5:
            return JsonResponse({'status': 'error', 'message': '当前网络环境达到极限，请稍后再试。'}, status=429)

        # --- 通过所有限制，继续执行原有逻辑 ---

        try:
            data = json.loads(request.body)
            email = data.get('email')
            image_captcha_code = data.get('image_captcha_code', '').upper()
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': '请求格式错误'}, status=400)

        # 验证图片验证码
        session_code = request.session.get('captcha_code', '').upper()
        if 'captcha_code' in request.session:
            del request.session['captcha_code']
        if not session_code or session_code != image_captcha_code:
            return JsonResponse({'status': 'error', 'message': '图片验证码错误'}, status=400)

        # 检查邮箱是否已被注册
        if User.objects.filter(email__iexact=email).exists():
            return JsonResponse({'status': 'error', 'message': '该邮箱已被注册'}, status=400)

        # 生成并发送邮箱验证码
        email_code = ''.join(random.choices(string.digits, k=6))
        try:
            send_mail(
                '注册验证码',
                f'您的注册验证码是：{email_code}。10分钟内有效。',
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
        except Exception as e:
            print(f"邮件发送失败 (IP: {ip_address}, Email: {email}), 错误: {e}")
            return JsonResponse({'status': 'error', 'message': '邮件发送失败，请稍后重试。'}, status=500)

        # --- 邮件发送成功后，更新两个计数器 ---

        # a. 更新小时计数器
        if hourly_attempts == 0:
            cache.set(hourly_key, 1, timeout=3600)  # 3600秒 = 1小时
        else:
            cache.incr(hourly_key)

        # b. 更新天计数器
        if daily_attempts == 0:
            cache.set(daily_key, 1, timeout=86400)  # 86400秒 = 24小时
        else:
            cache.incr(daily_key)

        # 将验证码存入session用于注册
        request.session['registration_verification'] = {
            'code': email_code,
            'email': email,
            'timestamp': time.time()
        }

        return JsonResponse({'status': 'success', 'message': '验证码已发送至您的邮箱'})


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

@login_required
def home(request):
    return render(request, 'home.html')

# --- 视图：实时检查用户名是否存在 (新功能) ---
def check_username(request):
    """一个专门用来检查用户名是否已被占用的API视图"""
    username = request.GET.get('username', None)
    if username:
        # 使用 __iexact 进行不区分大小写的查询
        is_taken = User.objects.filter(username__iexact=username).exists()
        return JsonResponse({'is_taken': is_taken})
    return JsonResponse({'error': 'Username not provided'}, status=400)


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
        return render(request, 'signup.html')

    def post(self, request, *args, **kwargs):
        # 注意：由于您前端使用 FormData，数据在 request.POST 中

        # 【核心修改】使用我们功能更强的自定义表单
        form = CustomUserCreationForm(request.POST)

        email = request.POST.get('email')
        email_code = request.POST.get('emailCode')

        # 1. 验证邮箱验证码 (这部分逻辑保持不变)
        verification_info = request.session.get('registration_verification')
        if not verification_info or verification_info.get('email') != email or verification_info.get(
                'code') != email_code:
            # 返回一个更结构化的错误，方便前端处理
            return JsonResponse({'status': 'error', 'errors': {'emailCode': [{'message': '邮箱验证码错误或已过期'}]}},
                                status=400)

        # 2. 使用表单验证其他所有数据 (用户名、密码、邮箱格式、邮箱是否唯一)
        if form.is_valid():
            # 表单验证通过，直接保存即可创建用户
            # 因为我们的自定义表单已经包含了email字段，所以不再需要手动设置
            user = form.save()
            user.is_active = True
            user.save()

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


@login_required
def knowledge_list(request):
    user = request.user
    sidebar_notes_key = f"sidebar_notes_user_{user.id}"
    sidebar_notes = cache.get(sidebar_notes_key)

    if sidebar_notes is None:
        # 使用 Q 对象来构建更灵活的查询
        user_projects = Project.objects.filter(members=user)

        # 条件A: 笔记在用户的项目中
        condition_in_project = Q(project__in=user_projects)
        # 条件B: 笔记没有项目，但作者是当前用户
        condition_no_project_own_by_user = Q(project__isnull=True, author=user)

        sidebar_notes = list(
            Note.objects.filter(
                condition_in_project | condition_no_project_own_by_user
            )
            .order_by('-created_at')
            .values('id', 'title')
            .distinct()  # 添加 distinct 以防止因JOIN产生重复
        )
        cache.set(sidebar_notes_key, sidebar_notes, timeout=900)

    initial_data = {
        'sidebar_notes': sidebar_notes,
        'has_notes': bool(sidebar_notes),
        'csrf_token': request.COOKIES.get('csrftoken')
    }
    context = {'initial_data': initial_data}
    return render(request, 'knowledge_list.html', context)


@login_required
@require_http_methods(["GET", "PUT"])
def note_detail_api(request, note_id):
    # 在获取笔记时，除了检查项目成员，还要检查是否为作者（以防笔记无项目）
    note = get_object_or_404(Note, pk=note_id)

    # 权限检查：如果笔记有项目，检查用户是否为项目成员；如果笔记无项目，检查用户是否为作者
    has_project_permission = note.project and note.project.members.filter(pk=request.user.pk).exists()
    is_author_of_unassigned_note = not note.project and note.author == request.user

    if not (has_project_permission or is_author_of_unassigned_note):
        return HttpResponseForbidden("您没有权限访问此笔记。")

    if request.method == 'GET':
        data = {
            'id': note.id,
            'title': note.title,
            'content': note.content,
            'is_public': note.is_public,
            'public_url': f"/notes/public/{note.public_id}/" if note.public_id and note.is_public else "",
            'project': {'id': note.project.id, 'title': note.project.title} if note.project else None,
            'created_at': note.created_at.strftime('%Y-%m-%d %H:%M'),
            'author': {'id': note.author.id, 'username': note.author.username}  # 返回作者信息
        }
        return JsonResponse(data)

    if request.method == 'PUT':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': '无效的JSON格式'}, status=400)

        # 更新字段
        note.title = data.get('title', note.title)
        note.content = data.get('content', note.content)
        note.is_public = data.get('is_public', note.is_public)
        # 注意：这里我们不允许API直接修改作者或项目
        note.save()

        cache.delete(f"sidebar_notes_user_{request.user.id}")

        # 返回更新后的完整数据
        updated_data = {
            'id': note.id,
            'title': note.title,
            'content': note.content,
            'is_public': note.is_public,
            'public_url': f"/notes/public/{note.public_id}/" if note.public_id and note.is_public else "",
            'project': {'id': note.project.id, 'title': note.project.title} if note.project else None,
            'created_at': note.created_at.strftime('%Y-%m-%d %H:%M'),
            'author': {'id': note.author.id, 'username': note.author.username}
        }
        return JsonResponse(updated_data)


@login_required
def search_notes_api(request):
    query = request.GET.get('q', '')
    if not query: return JsonResponse([], safe=False)

    user = request.user
    user_projects = Project.objects.filter(members=user)

    # 复用已修正的查询逻辑
    condition_in_project = Q(project__in=user_projects)
    condition_no_project_own_by_user = Q(project__isnull=True, author=user)
    search_condition = Q(title__icontains=query) | Q(content__icontains=query)

    results = Note.objects.filter(
        search_condition & (condition_in_project | condition_no_project_own_by_user)
    ).order_by('-created_at').values('id', 'title').distinct()

    return JsonResponse(list(results), safe=False)


@login_required
def get_all_notes_api(request):
    user = request.user
    sidebar_notes_key = f"sidebar_notes_user_{user.id}"
    all_notes = cache.get(sidebar_notes_key)

    if all_notes is None:
        # 复用已修正的查询逻辑
        user_projects = Project.objects.filter(members=user)
        condition_in_project = Q(project__in=user_projects)
        condition_no_project_own_by_user = Q(project__isnull=True, author=user)

        all_notes = list(
            Note.objects.filter(
                condition_in_project | condition_no_project_own_by_user
            )
            .order_by('-created_at')
            .values('id', 'title')
            .distinct()
        )
        cache.set(sidebar_notes_key, all_notes, timeout=900)

    return JsonResponse(all_notes, safe=False)