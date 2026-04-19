"""登录视图：CustomLoginView(表单) + login_api(JSON)。"""
from ._shared import *


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
                    # 检查登录2FA邮件的发送次数限制
                    ip_address = request.META.get('REMOTE_ADDR')
                    user_identifier = f"user_{user.id}"

                    # 每小时发送次数限制（登录2FA每小时最多3次）
                    purpose_hourly_key = f"email_code_hourly_login_2fa_{user_identifier}"
                    purpose_hourly_attempts = cache.get(purpose_hourly_key, 0)

                    if purpose_hourly_attempts >= 3:
                        return JsonResponse({
                            'status': 'error',
                            'message': '登录验证码每小时发送已达上限（3次），请稍后再试。'
                        }, status=429)

                    # 每天发送次数限制（登录2FA每天最多5次）
                    purpose_daily_key = f"email_code_daily_login_2fa_{user_identifier}"
                    purpose_daily_attempts = cache.get(purpose_daily_key, 0)

                    if purpose_daily_attempts >= 5:
                        return JsonResponse({
                            'status': 'error',
                            'message': '登录验证码每天发送已达上限（5次），请明天再试。'
                        }, status=429)

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

                        # 发送成功后，更新计数
                        # 更新每小时发送次数
                        if purpose_hourly_attempts == 0:
                            cache.set(purpose_hourly_key, 1, timeout=3600)   # 1小时
                        else:
                            cache.incr(purpose_hourly_key)

                        # 更新每天发送次数
                        if purpose_daily_attempts == 0:
                            import datetime
                            now = timezone.now()
                            tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
                            seconds_until_tomorrow = int((tomorrow - now).total_seconds())
                            cache.set(purpose_daily_key, 1, timeout=seconds_until_tomorrow)
                        else:
                            cache.incr(purpose_daily_key)

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
        发送登录通知邮件（智能版）

        参考大厂实践的智能策略：
        1. 不是每次登录都发送通知，减少邮件骚扰
        2. 只在以下情况发送通知：
           - 首次登录（账号激活后第一次登录）
           - 新设备登录（从未在此设备登录过）
           - 新位置登录（IP地址从未登录过）
           - 可疑登录（深夜登录、频繁切换设备等）
        3. 频率限制：
           - 同一设备24小时内只发送1次
           - 每天最多发送3次通知
           - 每周最多发送10次通知
        4. 防止恶意登录/退出：
           - 记录登录设备指纹，建立信任设备库
           - 检测异常登录模式（短时间多次登录）
           - IP黑名单机制
        """
        try:
            # 检查用户是否启用了登录通知
            profile = getattr(user, 'profile', None)
            if not profile or not profile.notify_login:
                return  # 用户未启用登录通知

            # 获取登录信息
            ip_address = request.META.get('HTTP_X_FORWARDED_FOR')
            if ip_address:
                ip_address = ip_address.split(',')[0].strip()
            else:
                ip_address = request.META.get('HTTP_X_REAL_IP') or request.META.get('REMOTE_ADDR', '未知')

            user_agent = request.META.get('HTTP_USER_AGENT', '未知设备')
            device_fingerprint = self._generate_device_fingerprint(user_agent, ip_address)

            # === 核心：智能判断是否需要发送通知 ===
            should_notify, reason = self._should_send_login_notification(
                user, device_fingerprint, ip_address, user_agent
            )

            if not should_notify:
                # 虽然不发送通知，但仍然记录登录设备信息
                self._record_login_device(user, device_fingerprint, ip_address, user_agent)
                return

            # === 需要发送通知，获取详细信息 ===

            # 获取IP归属地（使用缓存减少API调用）
            cache_key = f"ip_location_{ip_address}"
            ip_location = cache.get(cache_key)

            if not ip_location:
                ip_location = self._get_ip_location(ip_address)
                # 缓存24小时
                cache.set(cache_key, ip_location, 86400)

            # 解析设备信息
            device_info = self.parse_user_agent(user_agent)
            login_time = timezone.localtime(timezone.now())

            # 记录登录设备信息
            device = self._record_login_device(user, device_fingerprint, ip_address, user_agent)

            # 构建邮件内容（根据通知原因定制）
            email_subject, email_body = self._build_login_notification_email(
                user, login_time, ip_address, ip_location, device_info, login_method, reason
            )

            # 记录通知发送（防止重复发送）
            from ...models import LoginNotification
            LoginNotification.objects.create(
                user=user,
                device=device,
                ip_address=ip_address,
                reason=reason,
                email_sent=False  # 异步发送，初始为False
            )

            # 异步发送邮件
            def send_and_mark():
                try:
                    self._send_email_async(email_subject, email_body, [user.email])
                    # 标记为已发送
                    LoginNotification.objects.filter(
                        user=user, device=device, email_sent=False
                    ).update(email_sent=True)
                except Exception as e:
                    logger.error(f"发送登录通知邮件失败: {e}")

            threading.Thread(target=send_and_mark, daemon=True).start()

            logger.info(f"登录通知已加入队列: user={user.id}, reason={reason}, IP={ip_address}")

        except Exception as e:
            logger.error(f"登录通知处理失败 (user={user.id}): {e}")

    def _generate_device_fingerprint(self, user_agent, ip_address):
        """
        生成设备指纹（用于识别唯一设备）
        """
        fingerprint_data = f"{user_agent}|{ip_address}"
        return hashlib.sha256(fingerprint_data.encode()).hexdigest()

    def _should_send_login_notification(self, user, device_fingerprint, ip_address, user_agent):
        """
        智能判断是否需要发送登录通知

        返回: (should_notify: bool, reason: str)
        """
        from ...models import LoginDevice, LoginNotification
        from datetime import timedelta

        now = timezone.now()

        # 1. 检查频率限制
        # 每天最多3次
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        daily_count = LoginNotification.objects.filter(
            user=user,
            sent_at__gte=today_start
        ).count()

        if daily_count >= 3:
            logger.info(f"用户 {user.id} 今日登录通知已达上限")
            return False, None

        # 每周最多10次
        week_start = now - timedelta(days=7)
        weekly_count = LoginNotification.objects.filter(
            user=user,
            sent_at__gte=week_start
        ).count()

        if weekly_count >= 10:
            logger.info(f"用户 {user.id} 本周登录通知已达上限")
            return False, None

        # 2. 查找或创建设备记录
        try:
            device = LoginDevice.objects.get(
                user=user,
                device_fingerprint=device_fingerprint
            )

            # 现有设备
            # 检查：24小时内是否已通知过
            last_notification = LoginNotification.objects.filter(
                user=user,
                device=device,
                sent_at__gte=now - timedelta(hours=24)
            ).first()

            if last_notification:
                logger.info(f"设备 {device.id} 24小时内已发送过通知")
                return False, None

            # 检查：IP地址是否变化（新位置）
            if device.ip_address != ip_address:
                # IP地址变化，可能是新位置
                # 但如果设备是信任设备，且IP变化不大，不发送
                if device.is_trusted:
                    # 简单判断：如果IP前缀相同（同一运营商/地区），不发送
                    if self._is_same_network(device.ip_address, ip_address):
                        return False, None

                return True, 'new_location'

            # 现有设备，现有位置，不发送通知
            return False, None

        except LoginDevice.DoesNotExist:
            # 新设备
            # 检查：是否是用户的首次登录
            existing_devices = LoginDevice.objects.filter(user=user).count()
            if existing_devices == 0:
                return True, 'first_login'

            return True, 'new_device'

    def _is_same_network(self, ip1, ip2):
        """
        简单判断两个IP是否在同一网络（C类网段）
        """
        try:
            parts1 = ip1.split('.')[:3]
            parts2 = ip2.split('.')[:3]
            return parts1 == parts2
        except:
            return False

    def _record_login_device(self, user, device_fingerprint, ip_address, user_agent):
        """
        记录或更新登录设备信息
        """
        from ...models import LoginDevice

        device_info = self.parse_user_agent(user_agent)

        device, created = LoginDevice.objects.get_or_create(
            user=user,
            device_fingerprint=device_fingerprint,
            defaults={
                'ip_address': ip_address,
                'user_agent': user_agent,
                'device_info': device_info,
                'login_count': 1
            }
        )

        if not created:
            # 更新现有设备
            device.ip_address = ip_address
            device.user_agent = user_agent
            device.device_info = device_info
            device.login_count += 1
            device.last_login_at = timezone.now()

            # 自动信任：如果登录次数 >= 5次，自动设为信任设备
            if device.login_count >= 5 and not device.is_trusted:
                device.is_trusted = True
                device.trusted_at = timezone.now()
                logger.info(f"设备 {device.id} 已自动标记为信任设备")

            device.save()

        return device

    def _get_ip_location(self, ip_address):
        """
        获取IP归属地（带容错）
        """
        if ip_address == '未知' or ip_address.startswith('127.') or ip_address.startswith('192.168.'):
            return "本地网络"

        try:
            response = requests.get(
                f"http://ip-api.com/json/{ip_address}?lang=zh-CN",
                timeout=3
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    country = data.get('country', '')
                    region = data.get('regionName', '')
                    city = data.get('city', '')
                    return f"{country} {region} {city}".strip() or "未知"
        except:
            pass

        return "未知"

    def _build_login_notification_email(self, user, login_time, ip_address,
                                       ip_location, device_info, login_method, reason):
        """
        构建登录通知邮件内容
        """
        reason_texts = {
            'first_login': '这是您账号激活后的首次登录',
            'new_device': '检测到新设备登录',
            'new_location': '检测到新位置登录',
            'suspicious': '检测到可疑登录行为'
        }

        alert_text = reason_texts.get(reason, '账户登录通知')

        if reason in ['new_device', 'new_location', 'suspicious']:
            email_subject = f'⚠️ 安全提醒：{alert_text}'
            security_warning = """
⚠️ 安全提醒：
如果这不是您本人的操作，您的账户可能存在安全风险。请立即：
1. 修改您的密码
2. 启用或检查两因素认证设置
3. 检查账户的登录设备列表（在"设置-安全"中查看）
"""
        else:
            email_subject = f'账户登录通知'
            security_warning = ""

        email_body = f"""
尊敬的 {user.username}：

{alert_text}

登录详情：
━━━━━━━━━━━━━━━━━━━━━━━━━━
• 登录时间：{login_time.strftime('%Y年%m月%d日 %H:%M:%S')}
• 登录方式：{login_method}
• IP地址：{ip_address}
• IP归属地：{ip_location}
• 登录设备：{device_info}
━━━━━━━━━━━━━━━━━━━━━━━━━━

{security_warning}

💡 温馨提示：
- 如果您不希望每次登录都收到通知，可以在"设置-通知"中调整通知偏好
- 常用设备会在多次登录后自动标记为信任设备，减少通知频率

此邮件为系统自动发送，请勿回复。

知识管理系统
        """

        return email_subject, email_body

    def parse_user_agent(self, user_agent):
        """
        解析User-Agent，提取设备和浏览器信息
        """
        user_agent_lower = user_agent.lower()

        # 检测操作系统
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
        else:
            os_info = "未知系统"

        # 检测浏览器
        if 'edg' in user_agent_lower:  # Edge
            browser_info = "Edge"
        elif 'chrome' in user_agent_lower:
            browser_info = "Chrome"
        elif 'firefox' in user_agent_lower:
            browser_info = "Firefox"
        elif 'safari' in user_agent_lower:
            browser_info = "Safari"
        elif 'opera' in user_agent_lower:
            browser_info = "Opera"
        else:
            browser_info = "未知浏览器"

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


@require_http_methods(["POST"])
def login_api(request):
    """
    API端点：处理JSON格式的登录请求
    支持两因素认证，支持 Turnstile 和图形验证码双模式
    """
    try:
        # 解析JSON数据
        data = json.loads(request.body)
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()

        # 验证码参数：支持 turnstile 和图形验证码
        turnstile_token = data.get('turnstile_token', '').strip()
        image_captcha = data.get('image_captcha', '').strip()
        captcha_type = data.get('captcha_type', 'turnstile')  # 默认使用 turnstile

        if not username or not password:
            return JsonResponse({'error': '用户名和密码不能为空'}, status=400)

        # 统一验证码验证
        captcha_valid, captcha_error = verify_captcha_unified(
            request,
            turnstile_token=turnstile_token,
            image_captcha=image_captcha,
            captcha_type=captcha_type
        )
        if not captcha_valid:
            return JsonResponse({'error': captcha_error}, status=400)

        # 验证用户名和密码
        user = authenticate(request, username=username, password=password)

        if user is None:
            return JsonResponse({'error': '用户名或密码错误'}, status=400)

        # 检查用户是否激活
        if not user.is_active:
            return JsonResponse({'error': '账户已被禁用'}, status=400)

        # === 检查账户是否被冻结 ===
        user_lock_key = f'vault_user_lock:{user.id}'
        user_lock_expire = cache.get(user_lock_key)
        if user_lock_expire:
            remaining = user_lock_expire - int(time.time())
            if remaining > 0:
                remaining_minutes = remaining // 60
                return JsonResponse({
                    'error': f'账户已被冻结，请在 {remaining_minutes} 分钟后重试'
                }, status=403)

        # === 检查 IP 是否被封禁 ===
        ip_address = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '127.0.0.1'))
        if ',' in ip_address:
            ip_address = ip_address.split(',')[0].strip()
        ban_key = f'banned_ip:{ip_address}'
        if cache.get(ban_key):
            return JsonResponse({
                'error': '您的 IP 已被封禁，请联系管理员'
            }, status=403)

        # 检查是否启用了2FA
        profile = getattr(user, 'profile', None)
        if profile and profile.two_fa_enabled:
            # === 检查信任设备令牌 ===
            from ...models import TrustedDevice
            trust_token = request.COOKIES.get('trust_device_token')
            if trust_token:
                device = TrustedDevice.get_by_token(trust_token)
                if device and device.user_id == user.id:
                    # 信任设备有效，跳过2FA，直接登录
                    login(request, user)

                    # 获取当前IP并续期
                    ip_address = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '127.0.0.1'))
                    if ',' in ip_address:
                        ip_address = ip_address.split(',')[0].strip()
                    device.renew(ip_address)

                    # 发送登录通知
                    CustomLoginView().send_login_notification(request, user, login_method="信任设备免2FA登录")

                    # 构建响应并续期cookie
                    response = JsonResponse({
                        'success': True,
                        'message': '登录成功（信任设备）',
                        'require_2fa': False
                    })
                    response.set_cookie(
                        'trust_device_token',
                        device.device_token,
                        max_age=30 * 24 * 3600,  # 30天
                        httponly=True,
                        samesite='Lax',
                        secure=request.is_secure()
                    )
                    return response

            # 将用户ID临时存入session，等待2FA验证
            request.session['pending_2fa_user_id'] = user.id
            request.session['pending_2fa_method'] = profile.two_fa_method

            # 生成临时token
            import secrets
            temporary_token = secrets.token_urlsafe(32)
            request.session['temporary_2fa_token'] = temporary_token

            # 如果是邮箱验证方式，立即发送验证码
            if profile.two_fa_method == 'email':
                # 检查登录2FA邮件的发送次数限制
                ip_address = request.META.get('REMOTE_ADDR')
                user_identifier = f"user_{user.id}"

                # 每小时发送次数限制（登录2FA每小时最多3次）
                purpose_hourly_key = f"email_code_hourly_login_2fa_{user_identifier}"
                purpose_hourly_attempts = cache.get(purpose_hourly_key, 0)

                if purpose_hourly_attempts >= 3:
                    return JsonResponse({
                        'error': '登录验证码每小时发送已达上限（3次），请稍后再试。'
                    }, status=429)

                # 每天发送次数限制（登录2FA每天最多5次）
                purpose_daily_key = f"email_code_daily_login_2fa_{user_identifier}"
                purpose_daily_attempts = cache.get(purpose_daily_key, 0)

                if purpose_daily_attempts >= 5:
                    return JsonResponse({
                        'error': '登录验证码每天发送已达上限（5次），请明天再试。'
                    }, status=429)

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

                    # 更新计数
                    # 更新每小时发送次数
                    if purpose_hourly_attempts == 0:
                        cache.set(purpose_hourly_key, 1, timeout=3600)   # 1小时
                    else:
                        cache.incr(purpose_hourly_key)

                    # 更新每天发送次数
                    if purpose_daily_attempts == 0:
                        import datetime
                        now = timezone.now()
                        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
                        seconds_until_tomorrow = int((tomorrow - now).total_seconds())
                        cache.set(purpose_daily_key, 1, timeout=seconds_until_tomorrow)
                    else:
                        cache.incr(purpose_daily_key)

                except Exception as e:
                    logger.error(f"发送2FA邮件失败: {e}")
                    return JsonResponse({'error': '验证码发送失败，请稍后重试'}, status=500)

            return JsonResponse({
                'require_2fa': True,
                'two_fa_method': profile.two_fa_method,
                'temporary_token': temporary_token
            })

        # 没有2FA，直接登录
        login(request, user)

        # 发送登录通知
        CustomLoginView().send_login_notification(request, user, login_method="API密码登录")

        return JsonResponse({
            'success': True,
            'message': '登录成功',
            'require_2fa': False
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Exception as e:
        logger.error(f"登录API错误: {e}")
        return JsonResponse({'error': '服务器内部错误'}, status=500)
