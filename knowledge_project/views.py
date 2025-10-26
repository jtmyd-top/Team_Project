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
import requests
from bs4 import BeautifulSoup, Tag,NavigableString
from django.db.models import Q
import json # <--- 确保在文件顶部导入了 json 模块
from django.core.paginator import Paginator  # 添加这行导入
from django.core.cache import cache
from .models import  Note,Asset ,Tag, ProfileLike, Profile
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
from django.db import transaction  # 添加事务支持
import threading  # 用于延迟删除文件
import pyotp  # 用于 TOTP 两因素认证
import qrcode  # 用于生成 QR 码
import base64  # 用于编码 QR 码图片
from .decorators import verify_2fa_for_request, require_2fa_verified  # 导入装饰器

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

# 延迟删除文件的辅助函数
def _delayed_delete_file(file_path, delay=3):
    """
    延迟删除文件，避免 Windows 文件占用问题
    delay: 延迟秒数
    """
    def delete_file():
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"延迟删除文件成功: {file_path}")
        except OSError as e:
            logger.warning(f"延迟删除文件仍然失败: {file_path}, 错误: {e}")

    # 使用 Timer 延迟删除
    timer = threading.Timer(delay, delete_file)
    timer.daemon = True  # 设置为守护线程，主程序退出时自动结束
    timer.start()

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
    兼容三种业务：
    - 注册: purpose='register'（默认）
    - 修改邮箱: purpose='change'
    - 修改密码: purpose='password_change'
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
        purpose = (data.get('purpose') or 'register').strip()  # 'register' | 'change' | 'password_change'

        # 4) 校验图片验证码（并单次使用）
        session_code = (request.session.get('captcha_code') or '').upper()
        if 'captcha_code' in request.session:
            del request.session['captcha_code']
        if not session_code or session_code != image_captcha_code:
            return JsonResponse({'status': 'error', 'message': '图片验证码错误'}, status=400)

        # 5) 业务区分 & 邮箱可用性检查（共用工具函数）
        if purpose == 'password_change':
            # 修改密码：发送验证码到当前邮箱，验证是本人操作
            if not request.user.is_authenticated:
                return JsonResponse({'status': 'error', 'message': '请先登录'}, status=403)

            # 使用当前用户的邮箱，不需要检查可用性
            email = request.user.email
            mail_subject = '密码修改验证码'
            ok_message   = '验证码已发送至您的邮箱'

        elif purpose == 'email_change':
            # 修改邮箱:发送验证码到新邮箱,验证新邮箱的所有权
            if not request.user.is_authenticated:
                return JsonResponse({'status': 'error', 'message': '未登录用户无法修改邮箱'}, status=403)

            # 禁止把新邮箱改成当前邮箱(防止滥发验证码)
            if email and request.user.email and email.lower() == request.user.email.lower():
                return JsonResponse({'status': 'error', 'message': '该邮箱与当前绑定邮箱一致,无需修改'}, status=400)

            # 修改邮箱:排除自己判断占用
            check = _check_email_availability(request, email, exclude_self=True)
            if not check['ok']:
                return JsonResponse({'status': 'error', 'message': check['message']}, status=400)

            mail_subject = '邮箱修改验证码'
            ok_message   = '验证码已发送至您的新邮箱'

        else:
            # 注册：谁绑了都算占用
            check = _check_email_availability(request, email, exclude_self=False)
            if not check['ok']:
                # 为了与之前前端体验一致，文案使用"已被注册"
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

        # 8) 把验证码写入 session，使用不同的 key 避免冲突
        # 根据不同用途使用不同的 session key，避免被覆盖
        if purpose == 'email_change':
            # 修改邮箱专用 key
            session_key = 'email_change_verification'
        elif purpose == 'password_change':
            # 修改密码专用 key
            session_key = 'password_change_verification'
        else:
            # 注册专用 key
            session_key = 'registration_verification'

        request.session[session_key] = {
            'code': email_code,
            'email': email,
            'timestamp': time.time(),
            'purpose': purpose,  # 记录用途，方便后续需要时校验
        }

        # 确保 session 立即保存
        request.session.modified = True

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
    支持两因素认证的自定义登录视图。

    登录流程：
    1. 验证用户名和密码
    2. 如果用户启用了2FA，要求输入验证码
    3. 验证2FA码后完成登录
    """
    template_name = 'registration/login.html'
    next_page = reverse_lazy('home')

    def dispatch(self, request, *args, **kwargs):
        # 如果用户已登录，直接重定向到首页
        if request.user.is_authenticated:
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        form = AuthenticationForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request, *args, **kwargs):
        """第一步：验证用户名和密码"""
        form = AuthenticationForm(request, data=request.POST)

        if form.is_valid():
            user = form.get_user()
            profile = getattr(user, 'profile', None)

            # 检查是否启用了2FA
            if profile and profile.two_fa_enabled:
                # 将用户ID临时存入session，等待2FA验证
                request.session['pending_2fa_user_id'] = user.id
                request.session['pending_2fa_method'] = profile.two_fa_method

                # 如果是邮箱验证方式，立即发送验证码
                if profile.two_fa_method == 'email':
                    email_code = ''.join(random.choices(string.digits, k=6))
                    request.session['2fa_email_code'] = email_code
                    request.session['2fa_email_timestamp'] = time.time()

                    try:
                        send_mail(
                            '登录验证码',
                            f'您的登录验证码是：{email_code}。5分钟内有效。',
                            settings.DEFAULT_FROM_EMAIL,
                            [user.email],
                            fail_silently=False,
                        )
                    except Exception as e:
                        logger.error(f"发送2FA邮件失败: {e}")
                        return JsonResponse({
                            'status': 'error',
                            'message': '发送验证码失败，请稍后重试'
                        }, status=500)

                return JsonResponse({
                    'status': 'require_2fa',
                    'message': '请输入两因素验证码',
                    'method': profile.two_fa_method,
                    'email_sent': profile.two_fa_method == 'email'
                })
            else:
            # 没有启用2FA，直接登录
                login(request, user)

                # 发送登录通知
                self.send_login_notification(request, user, login_method="标准密码登录")

                return JsonResponse({
                    'status': 'success',
                    'message': '登录成功！',
                    'redirect_url': reverse('home')
                })

        # 表单验证失败
        return JsonResponse({
            'status': 'error',
            'message': '用户名或密码不正确'
        }, status=400)

    def send_login_notification(self, request, user, login_method="未知"):
        """
        发送登录通知邮件
        包含登录时间、IP地址、设备信息、IP归属地、登录方式等
        """
        try:
            # 检查用户是否启用了登录通知
            profile = getattr(user, 'profile', None)
            if not profile or not profile.notify_login:
                return  # 用户未启用登录通知，直接返回

            # 获取登录信息
            # 优先从 X-Forwarded-For 获取 IP，适用于大多数反向代理
            ip_address = request.META.get('HTTP_X_FORWARDED_FOR')
            if ip_address:
                # X-Forwarded-For 可能包含多个IP，取第一个
                ip_address = ip_address.split(',')[0].strip()
            else:
                # 其次尝试 X-Real-IP，一些代理软件使用这个头
                ip_address = request.META.get('HTTP_X_REAL_IP')
                if not ip_address:
                    # 最后回退到 REMOTE_ADDR
                    ip_address = request.META.get('REMOTE_ADDR', '未知')

            # 获取IP归属地
            ip_location = "未知"
            try:
                # 使用 ip-api.com 查询IP地址信息，设置超时
                # 注意：在生产环境中，建议使用更可靠的、有API密钥的商业服务
                response = requests.get(f"http://ip-api.com/json/{ip_address}?lang=zh-CN", timeout=3)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status') == 'success':
                        country = data.get('country', '')
                        region = data.get('regionName', '')
                        city = data.get('city', '')
                        ip_location = f"{country} {region} {city}".strip()
            except requests.RequestException:
                # 如果API请求失败，则保持为“未知”
                pass


            # 获取User-Agent信息
            user_agent = request.META.get('HTTP_USER_AGENT', '未知设备')

            # 简单解析设备和浏览器信息
            device_info = self.parse_user_agent(user_agent)

            # 获取登录时间（使用本地时区）
            login_time = timezone.localtime(timezone.now())

            # 构建邮件内容
            email_subject = '账户登录通知'
            email_body = f"""
尊敬的 {user.username}：

您的账户刚刚成功登录，以下是登录详情：

登录时间：{login_time.strftime('%Y年%m月%d日 %H:%M:%S')}
登录IP地址：{ip_address}
IP所在地：{ip_location}
登录设备：{device_info}
登录方式：{login_method}

如果这不是您本人的操作，请立即：
1. 修改您的密码
2. 启用两因素认证以增强账户安全性

此邮件为系统自动发送，请勿回复。

知识管理系统
            """

            # 异步发送邮件，避免阻塞登录流程
            threading.Thread(
                target=self._send_email_async,
                args=(email_subject, email_body, [user.email]),
                daemon=True
            ).start()

            logger.info(f"Login notification queued for user {user.id} from IP {ip_address}")

        except Exception as e:
            # 登录通知发送失败不应影响正常登录
            logger.error(f"Failed to send login notification for user {user.id}: {e}")

    def parse_user_agent(self, user_agent):
        """
        简单解析User-Agent字符串，提取设备和浏览器信息
        """
        user_agent_lower = user_agent.lower()

        # 检测操作系统
        os_info = "未知系统"
        if 'windows' in user_agent_lower:
            os_info = "Windows"
        elif 'mac' in user_agent_lower:
            os_info = "macOS"
        elif 'linux' in user_agent_lower:
            os_info = "Linux"
        elif 'android' in user_agent_lower:
            os_info = "Android"
        elif 'iphone' in user_agent_lower or 'ipad' in user_agent_lower:
            os_info = "iOS"

        # 检测浏览器
        browser_info = "未知浏览器"
        if 'chrome' in user_agent_lower and 'edge' not in user_agent_lower:
            browser_info = "Chrome"
        elif 'firefox' in user_agent_lower:
            browser_info = "Firefox"
        elif 'safari' in user_agent_lower and 'chrome' not in user_agent_lower:
            browser_info = "Safari"
        elif 'edge' in user_agent_lower:
            browser_info = "Edge"
        elif 'opera' in user_agent_lower:
            browser_info = "Opera"

        return f"{os_info} - {browser_info}"

    def _send_email_async(self, subject, body, recipients):
        """
        异步发送邮件的辅助方法
        """
        try:
            send_mail(
                subject,
                body,
                settings.DEFAULT_FROM_EMAIL,
                recipients,
                fail_silently=False,
            )
            logger.info(f"Email sent to {recipients} with subject '{subject}'")
        except Exception as e:
            logger.error(f"Failed to send email: {e}")


# ==================== 笔记活动通知辅助函数 ====================
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


def _send_email_async_helper(subject, body, recipients):
    """
    异步发送邮件的辅助函数（用于笔记活动通知）
    """
    try:
        send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            recipients,
            fail_silently=False,
        )
        logger.info(f"Email sent to {recipients} with subject '{subject}'")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")


def send_password_change_notification(request, user):
    """
    发送密码修改成功通知邮件（独立函数版本）
    """
    try:
        profile = getattr(user, 'profile', None)
        if not profile or not profile.notify_password_change:
            return

        # 获取IP地址
        ip_address = request.META.get('HTTP_X_FORWARDED_FOR')
        if ip_address:
            ip_address = ip_address.split(',')[0].strip()
        else:
            ip_address = request.META.get('HTTP_X_REAL_IP')
            if not ip_address:
                ip_address = request.META.get('REMOTE_ADDR', '未知')
        
        # 解析User-Agent
        user_agent = request.META.get('HTTP_USER_AGENT', '未知设备')
        device_info = CustomLoginView().parse_user_agent(user_agent)
        
        change_time = timezone.localtime(timezone.now())

        email_subject = '账户密码修改通知'
        email_body = f"""
尊敬的 {user.username}：

您的账户密码已于 {change_time.strftime('%Y年%m月%d日 %H:%M:%S')} 被成功修改。

操作详情：
- 操作IP地址：{ip_address}
- 操作设备：{device_info}

如果这不是您本人的操作，您的账户可能存在安全风险。请立即通过"忘记密码"功能重置您的密码，并检查您的账户安全设置。

此邮件为系统自动发送，请勿回复。

知识管理系统
        """

        threading.Thread(
            target=_send_email_async_helper,
            args=(email_subject, email_body, [user.email]),
            daemon=True
        ).start()

        logger.info(f"Password change notification queued for user {user.id}")

    except Exception as e:
        logger.error(f"Failed to send password change notification for user {user.id}: {e}")


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

        # 发送笔记创建通知
        send_note_activity_notification(request, user, new_note.title, 'created')

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
    """
    user = request.user

    # 确保 profile 存在
    try:
        profile = user.profile
    except Profile.DoesNotExist:
        # 如果 profile 不存在，创建一个
        profile = Profile.objects.create(user=user)
        logger.info(f"Created profile for user {user.id} in settings_view")

    # 获取当前用户的笔记数量
    notes_count = Note.objects.filter(author=user).count()

    # 检查当前用户是否已经点赞过自己的资料
    is_liked = ProfileLike.objects.filter(liker=user, profile=profile).exists()

    context = {
        "avatar_url": profile.avatar.url if profile.avatar else "/static/img/default-avatar.png",
        "nickname": user.username,
        "email": user.email,
        "bio": profile.bio if profile.bio else "",
        "likes_count": profile.likes_count,
        "notes_count": notes_count,
        "views_count": 0,  # 暂时默认为0，后续可以添加访问统计功能
        "is_liked": is_liked,
        # ✅ 添加 2FA 状态 - 现在 profile 一定存在
        "two_fa_enabled": profile.two_fa_enabled,
        "two_fa_method": profile.two_fa_method or 'totp',
    }

    # 添加调试日志
    logger.info(f"Settings view for user {user.id}: 2FA enabled={profile.two_fa_enabled}, method={profile.two_fa_method}")

    return render(request, "settings/setting.html", context)
@login_required
@require_http_methods(["POST"])
def upload_avatar(request):
    """上传并更新用户头像或横幅图"""
    # 检测是头像还是横幅
    avatar_file = request.FILES.get("avatar")
    banner_file = request.FILES.get("banner")

    user = request.user

    try:
        # 横幅图/视频上传
        if banner_file:
            # 验证文件类型（支持图片和视频）
            allowed_image_types = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']
            allowed_video_types = ['video/mp4', 'video/webm']
            allowed_types = allowed_image_types + allowed_video_types

            if banner_file.content_type not in allowed_types:
                return JsonResponse({
                    "status": "error",
                    "message": "只支持 JPG、PNG、WebP、GIF、MP4 和 WebM 格式"
                }, status=400)

            # 验证文件大小（图片最大 5MB，视频最大 15MB）
            is_video = banner_file.content_type in allowed_video_types
            max_size = 1500 * 1024 * 1024 if is_video else 5 * 1024 * 1024
            max_size_mb = 1500 if is_video else 5

            if banner_file.size > max_size:
                return JsonResponse({
                    "status": "error",
                    "message": f"{'视频' if is_video else '图片'}大小不能超过 {max_size_mb}MB"
                }, status=400)

            # 【修复】先保存旧文件的路径，然后删除
            old_banner_path = None
            if user.profile.banner_image:
                try:
                    # 获取旧文件的完整路径
                    old_banner_path = user.profile.banner_image.path
                except (ValueError, AttributeError):
                    pass  # 如果文件不存在，忽略错误

            # 保存新横幅（先保存）
            user.profile.banner_image.save(banner_file.name, banner_file, save=True)

            # 【修复】获取新文件路径，只删除路径不同的旧文件
            try:
                new_banner_path = user.profile.banner_image.path
                # 只有当旧文件路径存在且与新文件路径不同时，才延迟删除
                if old_banner_path and old_banner_path != new_banner_path and os.path.exists(old_banner_path):
                    _delayed_delete_file(old_banner_path, delay=5)
            except (ValueError, AttributeError):
                pass

            return JsonResponse({
                "status": "success",
                "message": "横幅上传成功",
                "banner_url": request.build_absolute_uri(user.profile.banner_image.url),
                "is_video": is_video
            })

        # 头像上传
        elif avatar_file:
            # 【修复】先保存旧文件的路径，然后删除
            old_avatar_path = None
            if user.profile.avatar:
                try:
                    # 获取旧文件的完整路径
                    old_avatar_path = user.profile.avatar.path
                except (ValueError, AttributeError):
                    pass  # 如果文件不存在，忽略错误

            # 保存新头像（先保存）
            user.profile.avatar.save(avatar_file.name, avatar_file, save=True)

            # 【修复】获取新文件路径，只删除路径不同的旧文件
            try:
                new_avatar_path = user.profile.avatar.path
                # 只有当旧文件路径存在且与新文件路径不同时，才延迟删除
                if old_avatar_path and old_avatar_path != new_avatar_path and os.path.exists(old_avatar_path):
                    _delayed_delete_file(old_avatar_path, delay=5)
            except (ValueError, AttributeError):
                pass

            return JsonResponse({
                "status": "success",
                "message": "头像上传成功",
                "avatar_url": request.build_absolute_uri(user.profile.avatar.url)
            })

        else:
            return JsonResponse({
                "status": "error",
                "message": "未选择文件"
            }, status=400)

    except Exception as e:
        logger.error(f"上传文件失败: {str(e)}", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def update_profile(request):
    """
    通用更新接口：可以单独更新昵称或 bio。
    前端通过发送不同字段决定更新内容。
    """
    try:
        data = json.loads(request.body)
        profile = request.user.profile
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "请求格式错误"}, status=400)

    user = request.user
    profile = getattr(user, "profile", None)

    updated_fields = []
    response_data = {"status": "success"}

    # 更新昵称
    nickname = data.get("nickname")
    if nickname is not None:
        if len(nickname) < 6:
            return JsonResponse({"status": "error", "message": "昵称至少6位"}, status=400)
        user.username = nickname
        updated_fields.append("username")
        response_data["nickname"] = nickname

    # 更新个性签名
    bio = data.get("bio")

    if bio is not None:
        if len(bio) > 160:
            return JsonResponse({"status": "error", "message": "个性签名不能超过160字"}, status=400)
        profile.bio = bio
        updated_fields.append("bio")
        response_data["bio"] = bio

    if updated_fields:
        if "username" in updated_fields:
            user.save(update_fields=["username"])
        if "bio" in updated_fields:
            profile.save(update_fields=["bio"])
        print(response_data)
        return JsonResponse(response_data)

    return JsonResponse({"status": "error", "message": "没有任何更新字段"}, status=400)


@login_required
@require_http_methods(["POST"])
@require_2fa_verified
def update_email(request):
    """
    修改邮箱
    需要验证：当前密码、新邮箱验证码、2FA验证码
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "JSON 格式错误"}, status=400)

    current_password = data.get("password", "")
    new_email = data.get("new_email", "").strip()
    code = data.get("code", "").strip()

    if not current_password or not new_email or not code:
        return JsonResponse({"status": "error", "message": "缺少必要参数"}, status=400)

    # 1) 校验当前密码
    if not request.user.check_password(current_password):
        return JsonResponse({"status": "error", "message": "密码错误"}, status=400)

    # 2) 校验邮箱验证码（验证新邮箱所有权）
    # 使用专门的 session key 避免被其他操作覆盖
    info = request.session.get("email_change_verification")
    
    # 先检查验证码是否存在和有效期
    if not info:
        logger.info("Email verification info not found in session")
        return JsonResponse({"status": "error", "message": "邮箱验证码已失效，请重新获取"}, status=400)
    
    # 有效期 15 分钟（增加到15分钟，给用户更多时间）
    elapsed_time = time.time() - float(info.get("timestamp", 0))
    if elapsed_time > 900:  # 15分钟 = 900秒
        logger.info(f"Email verification code expired - Elapsed time: {elapsed_time} seconds")
        # 验证码过期后清除session
        if "email_change_verification" in request.session:
            del request.session["email_change_verification"]
        return JsonResponse({"status": "error", "message": "邮箱验证码已过期，请重新获取"}, status=400)
    
    # 验证邮箱和验证码是否匹配
    if info.get("email") != new_email or info.get("code") != code:
        # 【关键修复】验证失败时不要删除session，允许用户重试
        logger.info(f"Email verification failed - Session email: {info.get('email')}, Expected: {new_email}, Session code: {info.get('code')}, Provided: {code}")
        return JsonResponse({"status": "error", "message": "邮箱验证码错误或邮箱不匹配"}, status=400)

    # 3) 检查邮箱是否已被占用（再兜底）
    if User.objects.filter(email__iexact=new_email).exclude(pk=request.user.pk).exists():
        return JsonResponse({"status": "error", "message": "该邮箱已被绑定"}, status=400)

    # 4) 更新邮箱
    user = request.user
    user.email = new_email
    user.save(update_fields=["email"])

    # 作废验证码 session
    if "email_change_verification" in request.session:
        del request.session["email_change_verification"]

    return JsonResponse({"status": "success", "email": user.email, "message": "邮箱修改成功"})


# ==================== 点赞功能 API ====================
@login_required
@require_http_methods(["POST"])
def toggle_profile_like(request):
    """
    切换对当前用户资料的点赞状态
    - 如果已点赞，则取消点赞
    - 如果未点赞，则添加点赞
    """
    user = request.user
    profile = user.profile

    try:
        # 检查是否已经点赞过
        like_record = ProfileLike.objects.filter(liker=user, profile=profile).first()

        if like_record:
            # 已点赞，执行取消点赞操作
            like_record.delete()
            profile.likes_count = max(0, profile.likes_count - 1)  # 确保不会小于0
            profile.save(update_fields=['likes_count'])
            is_liked = False
        else:
            # 未点赞，执行点赞操作
            ProfileLike.objects.create(liker=user, profile=profile)
            profile.likes_count += 1
            profile.save(update_fields=['likes_count'])
            is_liked = True

        return JsonResponse({
            "status": "success",
            "is_liked": is_liked,
            "likes_count": profile.likes_count
        })

    except Exception as e:
        logger.error(f"点赞操作失败 (用户: {user.id}): {str(e)}", exc_info=True)
        return JsonResponse({"status": "error", "message": "操作失败，请稍后重试"}, status=500)


# ==================== 账户安全功能 API ====================

@login_required
@require_http_methods(["POST"])
def send_operation_2fa_code(request):
    """
    为敏感操作发送2FA验证码
    - TOTP用户：不需要发送邮件，直接使用验证器应用
    - Email用户：发送6位验证码到当前邮箱（5分钟有效期）

    使用场景：修改密码、修改邮箱等敏感操作
    """
    user = request.user
    profile = getattr(user, 'profile', None)

    # 检查用户是否启用了2FA
    if not profile or not profile.two_fa_enabled:
        return JsonResponse({
            'status': 'success',
            'message': '未启用两因素认证，无需验证',
            'requires_2fa': False
        })

    # TOTP用户不需要发送邮件
    if profile.two_fa_method == 'totp':
        return JsonResponse({
            'status': 'success',
            'message': '请使用验证器应用生成验证码',
            'requires_2fa': True,
            'method': 'totp'
        })

    # Email用户：生成并发送验证码
    elif profile.two_fa_method == 'email':
        email_code = ''.join(random.choices(string.digits, k=6))
        request.session['operation_2fa_email_code'] = email_code
        request.session['operation_2fa_email_time'] = time.time()

        try:
            send_mail(
                '操作验证码',
                f'您正在进行敏感操作，验证码是：{email_code}。5分钟内有效。',
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            return JsonResponse({
                'status': 'success',
                'message': '验证码已发送至您的邮箱',
                'requires_2fa': True,
                'method': 'email'
            })
        except Exception as e:
            logger.error(f"发送操作验证码失败: {e}")
            return JsonResponse({
                'status': 'error',
                'message': '发送验证码失败，请稍后重试'
            }, status=500)

    return JsonResponse({
        'status': 'error',
        'message': '未知的2FA验证方式'
    }, status=400)


@login_required
@require_http_methods(["POST"])
@require_2fa_verified
def change_password(request):
    """
    修改密码
    需要验证：当前密码、2FA验证码
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "JSON 格式错误"}, status=400)

    current_password = data.get("current_password", "")
    new_password = data.get("new_password", "")
    confirm_password = data.get("confirm_password", "")

    # 1) 验证必要参数
    if not all([current_password, new_password, confirm_password]):
        return JsonResponse({"status": "error", "message": "缺少必要参数"}, status=400)

    # 2) 验证当前密码
    if not request.user.check_password(current_password):
        return JsonResponse({"status": "error", "message": "当前密码错误"}, status=400)

    # 3) 验证新密码和确认密码
    if new_password != confirm_password:
        return JsonResponse({"status": "error", "message": "两次输入的新密码不一致"}, status=400)

    # 4) 验证密码强度（至少8位）
    if len(new_password) < 8:
        return JsonResponse({"status": "error", "message": "新密码长度至少为8位"}, status=400)

    # 5) 更新密码
    user = request.user
    user.set_password(new_password)
    user.save()

    # 重新登录用户（因为密码已更改）
    from django.contrib.auth import update_session_auth_hash
    update_session_auth_hash(request, user)

    # 发送密码修改通知
    send_password_change_notification(request, user)

    return JsonResponse({"status": "success", "message": "密码修改成功"})


@login_required
@require_http_methods(["POST"])
@transaction.atomic  # 添加事务装饰器
def enable_2fa(request):
    """
    启用两因素认证
    - TOTP方式：生成密钥和二维码
    - Email方式：直接启用邮箱验证
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "JSON 格式错误"}, status=400)

    method = data.get("method", "totp")  # 'totp' 或 'email'

    # 确保profile存在
    try:
        profile = request.user.profile
    except Profile.DoesNotExist:
        # 如果profile不存在，创建一个
        profile = Profile.objects.create(user=request.user)
        logger.info(f"Created profile for user {request.user.id}")

    # 如果已经启用2FA，不允许重复启用
    if profile.two_fa_enabled:
        return JsonResponse({"status": "error", "message": "两因素认证已启用"}, status=400)

    if method == "totp":
        # 生成 TOTP 密钥
        secret = pyotp.random_base32()

        # 生成 QR 码 URI
        totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=request.user.email,
            issuer_name="知识管理系统"
        )

        # 生成 QR 码图片
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(totp_uri)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()

        # 临时保存密钥到 session，等待验证后再写入数据库
        request.session['temp_totp_secret'] = secret
        request.session['temp_2fa_method'] = 'totp'

        return JsonResponse({
            "status": "success",
            "message": "请扫描二维码并输入验证码",
            "qr_code": f"data:image/png;base64,{qr_code_base64}",
            "secret": secret,  # 也返回密钥文本，方便手动输入
            "requires_verification": True
        })

    elif method == "email":
        # 邮箱验证方式，直接启用（不需要额外验证步骤）
        profile.two_fa_enabled = True
        profile.two_fa_method = 'email'
        profile.save(update_fields=['two_fa_enabled', 'two_fa_method'])

        # 强制提交事务
        transaction.commit()

        # 添加日志记录，确认保存成功
        logger.info(f"Email 2FA enabled for user {request.user.id}: enabled={profile.two_fa_enabled}, method={profile.two_fa_method}")

        # 重新查询确认已保存
        profile.refresh_from_db()
        logger.info(f"After refresh: enabled={profile.two_fa_enabled}, method={profile.two_fa_method}")

        # 验证确实已保存到数据库
        verified_profile = Profile.objects.get(user=request.user)
        logger.info(f"Verified from DB: enabled={verified_profile.two_fa_enabled}, method={verified_profile.two_fa_method}")

        return JsonResponse({
            "status": "success",
            "message": "邮箱两因素认证已启用",
            "two_fa_enabled": verified_profile.two_fa_enabled,  # 返回数据库中的实际值
            "two_fa_method": verified_profile.two_fa_method,    # 返回数据库中的实际方式
            "requires_verification": False  # 邮箱方式不需要额外验证步骤
        })

    else:
        return JsonResponse({"status": "error", "message": "不支持的验证方式"}, status=400)


@login_required
@require_http_methods(["POST"])
def verify_2fa_setup(request):
    """
    验证并完成 2FA 设置
    - 对于 TOTP：验证用户输入的验证码是否正确
    - 验证成功后，正式启用 2FA
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "JSON 格式错误"}, status=400)

    code = data.get("code", "").strip()
    profile = request.user.profile

    # 检查是否有待验证的2FA设置
    temp_method = request.session.get('temp_2fa_method')
    if not temp_method:
        return JsonResponse({"status": "error", "message": "未找到待验证的2FA设置"}, status=400)

    if temp_method == "totp":
        # 从 session 获取临时密钥
        temp_secret = request.session.get('temp_totp_secret')
        if not temp_secret:
            return JsonResponse({"status": "error", "message": "密钥已过期，请重新设置"}, status=400)

        # 验证 TOTP 码
        totp = pyotp.TOTP(temp_secret)
        if not totp.verify(code, valid_window=1):  # valid_window=1 允许前后30秒的时间差
            return JsonResponse({"status": "error", "message": "验证码错误"}, status=400)

        # 验证成功，保存密钥并启用2FA
        profile.totp_secret = temp_secret
        profile.two_fa_method = 'totp'
        profile.two_fa_enabled = True

        # 生成备用码
        backup_codes = generate_backup_codes_list()
        profile.backup_codes = [hashlib.sha256(code.encode()).hexdigest() for code in backup_codes]

        profile.save(update_fields=['totp_secret', 'two_fa_method', 'two_fa_enabled', 'backup_codes'])

        # 清除 session 中的临时数据
        if 'temp_totp_secret' in request.session:
            del request.session['temp_totp_secret']
        if 'temp_2fa_method' in request.session:
            del request.session['temp_2fa_method']

        return JsonResponse({
            "status": "success",
            "message": "TOTP 两因素认证已成功启用",
            "backup_codes": backup_codes  # 返回明文备用码供用户保存
        })

    elif temp_method == "email":
        # 邮箱方式直接启用
        profile.two_fa_method = 'email'
        profile.two_fa_enabled = True
        profile.save(update_fields=['two_fa_method', 'two_fa_enabled'])

        # 清除 session
        if 'temp_2fa_method' in request.session:
            del request.session['temp_2fa_method']

        return JsonResponse({
            "status": "success",
            "message": "邮箱两因素认证已成功启用"
        })

    return JsonResponse({"status": "error", "message": "未知错误"}, status=500)


@login_required
@require_http_methods(["POST"])
def disable_2fa(request):
    """
    禁用两因素认证
    需要验证当前密码
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "JSON 格式错误"}, status=400)

    password = data.get("password", "")
    profile = request.user.profile

    # 验证密码
    if not request.user.check_password(password):
        return JsonResponse({"status": "error", "message": "密码错误"}, status=400)

    # 禁用2FA并清除相关数据
    profile.two_fa_enabled = False
    profile.totp_secret = ""
    profile.backup_codes = []
    profile.save(update_fields=['two_fa_enabled', 'totp_secret', 'backup_codes'])

    return JsonResponse({
        "status": "success",
        "message": "两因素认证已禁用"
    })


@login_required
@require_http_methods(["POST"])
def regenerate_backup_codes(request):
    """
    重新生成备用验证码
    需要验证当前密码或2FA验证码
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "JSON 格式错误"}, status=400)

    password = data.get("password", "")
    profile = request.user.profile

    # 必须已启用2FA
    if not profile.two_fa_enabled:
        return JsonResponse({"status": "error", "message": "未启用两因素认证"}, status=400)

    # 验证密码
    if not request.user.check_password(password):
        return JsonResponse({"status": "error", "message": "密码错误"}, status=400)

    # 生成新的备用码
    backup_codes = generate_backup_codes_list()
    profile.backup_codes = [hashlib.sha256(code.encode()).hexdigest() for code in backup_codes]
    profile.save(update_fields=['backup_codes'])

    return JsonResponse({
        "status": "success",
        "message": "备用验证码已重新生成",
        "backup_codes": backup_codes
    })


def generate_backup_codes_list():
    """
    生成5个8位数字+字母的备用验证码
    """
    codes = []
    for _ in range(5):
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        codes.append(code)
    return codes


# ==================== 两因素认证登录验证 API ====================

@require_http_methods(["POST"])
def verify_2fa_login(request):
    """
    验证2FA登录码
    支持三种验证方式：
    1. TOTP验证器码
    2. 邮箱验证码
    3. 备用验证码
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'JSON格式错误'}, status=400)

    code = data.get('code', '').strip()
    use_backup = data.get('use_backup', False)  # 是否使用备用码

    # 从session获取待验证的用户ID
    pending_user_id = request.session.get('pending_2fa_user_id')
    if not pending_user_id:
        return JsonResponse({'status': 'error', 'message': '会话已过期，请重新登录'}, status=400)

    try:
        user = User.objects.get(id=pending_user_id)
        profile = user.profile
    except User.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '用户不存在'}, status=400)

    # 验证2FA码
    if use_backup:
        # 使用备用验证码
        if not profile.backup_codes:
            return JsonResponse({'status': 'error', 'message': '没有可用的备用验证码'}, status=400)

        # 检查备用码是否匹配
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        if code_hash in profile.backup_codes:
            # 备用码验证成功，删除已使用的备用码
            profile.backup_codes.remove(code_hash)
            profile.save(update_fields=['backup_codes'])
        else:
            return JsonResponse({'status': 'error', 'message': '备用验证码错误'}, status=400)

    elif profile.two_fa_method == 'totp':
        # TOTP验证器
        if not profile.totp_secret:
            return JsonResponse({'status': 'error', 'message': '2FA配置错误'}, status=400)

        totp = pyotp.TOTP(profile.totp_secret)
        if not totp.verify(code, valid_window=1):
            return JsonResponse({'status': 'error', 'message': '验证码错误'}, status=400)

    elif profile.two_fa_method == 'email':
        # 邮箱验证码
        session_code = request.session.get('2fa_email_code')
        session_timestamp = request.session.get('2fa_email_timestamp')

        if not session_code or not session_timestamp:
            return JsonResponse({'status': 'error', 'message': '验证码已过期'}, status=400)

        # 检查有效期（5分钟）
        if time.time() - float(session_timestamp) > 300:
            return JsonResponse({'status': 'error', 'message': '验证码已过期'}, status=400)

        if session_code != code:
            return JsonResponse({'status': 'error', 'message': '验证码错误'}, status=400)

        # 清除已使用的邮箱验证码
        if '2fa_email_code' in request.session:
            del request.session['2fa_email_code']
        if '2fa_email_timestamp' in request.session:
            del request.session['2fa_email_timestamp']

    # 2FA验证成功，构建登录方式描述
    login_method_detail = "两因素认证 (验证码)"
    if use_backup:
        # 备用码脱敏处理：显示前3位和后3位
        masked_code = f"{code[:3]}***{code[-3:]}" if len(code) > 6 else f"{code[:3]}***"
        login_method_detail = f"两因素认证 (备用码: {masked_code}，该备用码已失效)"


    # 2FA验证成功，完成登录
    login(request, user)

    # 发送登录通知（使用CustomLoginView的静态方法）
    CustomLoginView().send_login_notification(request, user, login_method=login_method_detail)

    # 清除session中的临时数据
    if 'pending_2fa_user_id' in request.session:
        del request.session['pending_2fa_user_id']
    if 'pending_2fa_method' in request.session:
        del request.session['pending_2fa_method']

    return JsonResponse({
        'status': 'success',
        'message': '登录成功',
        'redirect_url': reverse('home')
    })


@require_http_methods(["POST"])
def resend_2fa_email(request):
    """
    重新发送2FA邮箱验证码
    """
    pending_user_id = request.session.get('pending_2fa_user_id')
    if not pending_user_id:
        return JsonResponse({'status': 'error', 'message': '会话已过期'}, status=400)

    try:
        user = User.objects.get(id=pending_user_id)
        profile = user.profile
    except User.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '用户不存在'}, status=400)

    if profile.two_fa_method != 'email':
        return JsonResponse({'status': 'error', 'message': '当前不是邮箱验证方式'}, status=400)

    # 生成并发送新的验证码
    email_code = ''.join(random.choices(string.digits, k=6))
    request.session['2fa_email_code'] = email_code
    request.session['2fa_email_timestamp'] = time.time()

    try:
        send_mail(
            '登录验证码',
            f'您的登录验证码是：{email_code}。5分钟内有效。',
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        return JsonResponse({'status': 'success', 'message': '验证码已重新发送'})
    except Exception as e:
        logger.error(f"重新发送2FA邮件失败: {e}")
        return JsonResponse({'status': 'error', 'message': '发送失败，请稍后重试'}, status=500)


# ==================== 通知偏好设置 API ====================
@login_required
@require_http_methods(["GET", "POST"])
def notification_preferences(request):
    """
    获取或更新用户的通知偏好设置
    GET: 返回当前通知偏好
    POST: 更新通知偏好
    """
    user = request.user

    # 确保profile存在
    try:
        profile = user.profile
    except Profile.DoesNotExist:
        profile = Profile.objects.create(user=user)
        logger.info(f"Created profile for user {user.id} in notification_preferences")

    if request.method == "GET":
        # 返回当前的通知偏好设置
        return JsonResponse({
            "status": "success",
            "preferences": {
                "notify_login": profile.notify_login,
                "notify_password_change": profile.notify_password_change,
                "notify_password_reset": profile.notify_password_reset,
                "notify_note_activities": profile.notify_note_activities,
                "notify_profile_likes": profile.notify_profile_likes,
            }
        })

    elif request.method == "POST":
        # 更新通知偏好设置
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"status": "error", "message": "JSON 格式错误"}, status=400)

        # 更新各个通知选项（只更新前端传递的字段）
        update_fields = []

        if "notify_login" in data:
            profile.notify_login = bool(data["notify_login"])
            update_fields.append("notify_login")

        if "notify_password_change" in data:
            profile.notify_password_change = bool(data["notify_password_change"])
            update_fields.append("notify_password_change")

        if "notify_password_reset" in data:
            profile.notify_password_reset = bool(data["notify_password_reset"])
            update_fields.append("notify_password_reset")

        if "notify_note_activities" in data:
            profile.notify_note_activities = bool(data["notify_note_activities"])
            update_fields.append("notify_note_activities")

        if "notify_profile_likes" in data:
            profile.notify_profile_likes = bool(data["notify_profile_likes"])
            update_fields.append("notify_profile_likes")

        # 保存更新
        if update_fields:
            profile.save(update_fields=update_fields)
            logger.info(f"Updated notification preferences for user {user.id}: {update_fields}")

            return JsonResponse({
                "status": "success",
                "message": "通知偏好设置已更新",
                "updated_fields": update_fields
            })
        else:
            return JsonResponse({
                "status": "warning",
                "message": "没有需要更新的字段"
            })


# ==================== 主题设置 API ====================
@login_required
@require_http_methods(["GET", "POST"])
def theme_settings(request):
    """
    获取或更新用户的主题设置
    GET: 返回当前主题设置
    POST: 更新主题设置
    """
    user = request.user

    # 确保profile存在
    try:
        profile = user.profile
    except Profile.DoesNotExist:
        profile = Profile.objects.create(user=user)
        logger.info(f"Created profile for user {user.id} in theme_settings")

    if request.method == "GET":
        # 返回当前的主题设置
        return JsonResponse({
            "status": "success",
            "theme_settings": {
                "mode": profile.theme.get('mode', 'system'),
                "primary_color": profile.theme.get('primary_color', '#2196F3'),
                "layout": profile.layout_mode,
            }
        })

    elif request.method == "POST":
        # 更新主题设置
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"status": "error", "message": "JSON 格式错误"}, status=400)

        # 更新theme字段（JSONField）
        theme_updated = False
        if "mode" in data:
            profile.theme['mode'] = data['mode']
            theme_updated = True

        if "primaryColor" in data:
            profile.theme['primary_color'] = data['primaryColor']
            theme_updated = True

        # 更新layout_mode字段
        layout_updated = False
        if "layout" in data:
            profile.layout_mode = data['layout']
            layout_updated = True

        # 保存更新
        update_fields = []
        if theme_updated:
            update_fields.append('theme')
            update_fields.append('last_theme_update')
        if layout_updated:
            update_fields.append('layout_mode')

        if update_fields:
            profile.save(update_fields=update_fields)
            logger.info(f"Updated theme settings for user {user.id}")

            return JsonResponse({
                "status": "success",
                "message": "主题设置已保存"
            })
        else:
            return JsonResponse({
                "status": "warning",
                "message": "没有需要更新的字段"
            })
