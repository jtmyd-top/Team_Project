"""用户注册视图。"""
from ._shared import *
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie


@method_decorator(ensure_csrf_cookie, name='dispatch')
@method_decorator(csrf_protect, name='dispatch')
class SignUpView(View):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        return render(request, 'registration/signup.html')

    def post(self, request, *args, **kwargs):
        # 解析JSON数据
        try:
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': '请求数据格式错误'}, status=400)

        # 提取数据
        email = data.get('email')
        email_code = data.get('email_code') or data.get('emailCode')
        username = data.get('username')
        password = data.get('password')
        confirm_password = data.get('confirm_password') or data.get('confirmPassword')
        agree_terms = data.get('agree_terms') or data.get('agreeTerms')

        # 验证码参数：支持 turnstile 和图形验证码
        turnstile_token = data.get('turnstile_token', '').strip()
        image_captcha = data.get('image_captcha', '').strip()
        captcha_type = data.get('captcha_type', 'turnstile')

        # 【用户体验改进】如果邮箱验证码已发送且正确，可以放宽人机验证要求
        verification_info = request.session.get('registration_verification')

        # 检查是否有有效的邮箱验证码记录（意味着之前已通过人机验证）
        has_valid_verification_record = (
            verification_info and
            verification_info.get('email') == email and
            verification_info.get('code') == email_code and
            verification_info.get('turnstile_verified', False)
        )

        # 如果没有有效的验证记录，则需要验证码验证
        if not has_valid_verification_record:
            # 统一验证码验证
            captcha_valid, captcha_error = verify_captcha_unified(
                request,
                turnstile_token=turnstile_token,
                image_captcha=image_captcha,
                captcha_type=captcha_type
            )
            if not captcha_valid:
                return JsonResponse({'status': 'error', 'message': captcha_error}, status=400)

        # 【核心修改】使用我们功能更强的自定义表单
        form_data = {
            'username': username,
            'email': email,
            'password1': password,
            'password2': confirm_password
        }
        form = CustomUserCreationForm(form_data)

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
            login_with_persistent_session(request, user)

            # 返回成功响应，跳转到知识库
            return JsonResponse({
                'status': 'success',
                'message': '注册成功！即将跳转到您的知识库。',
                'redirect_url': reverse('knowledge_list')
            })
        else:
            # 如果表单验证失败，返回所有错误信息
            return JsonResponse({'status': 'error', 'errors': form.errors.get_json_data()}, status=400)
