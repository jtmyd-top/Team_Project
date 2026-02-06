from django.core.management.base import BaseCommand
from django.test import RequestFactory
from knowledge_project.views import reset_password_view
from django.contrib.auth.models import User
from knowledge_project.models import PasswordResetToken

class Command(BaseCommand):
    help = '测试特定的密码重置令牌'

    def add_arguments(self, parser):
        parser.add_argument('token', type=str, help='要测试的令牌')
        parser.add_argument('user_id', type=int, help='用户ID')

    def handle(self, *args, **options):
        token = options['token']
        user_id = options['user_id']

        self.stdout.write(f"测试令牌: {token}")
        self.stdout.write(f"用户ID: {user_id}")

        # 检查用户是否存在
        try:
            user = User.objects.get(id=user_id)
            self.stdout.write(f"用户: {user.username}")
        except User.DoesNotExist:
            self.stdout.write("错误: 用户不存在")
            return

        # 检查我们的自定义令牌模型
        try:
            reset_token = PasswordResetToken.objects.get(user=user, token=token)
            self.stdout.write(f"找到自定义令牌:")
            self.stdout.write(f"  创建时间: {reset_token.created_at}")
            self.stdout.write(f"  过期时间: {reset_token.expires_at}")
            self.stdout.write(f"  是否已过期: {reset_token.is_expired}")
            self.stdout.write(f"  是否已使用: {reset_token.is_used}")
        except PasswordResetToken.DoesNotExist:
            self.stdout.write("未找到自定义令牌")

        # 模拟访问重置密码页面
        factory = RequestFactory()
        request = factory.get(f'/reset-password/{user_id}/{token}/')

        # 尝试调用视图
        try:
            response = reset_password_view(request, user_id, token)
            self.stdout.write(f"视图响应状态码: {response.status_code}")
            if hasattr(response, 'context_data'):
                error = response.context_data.get('error', '无错误')
                self.stdout.write(f"视图返回错误: {error}")
        except Exception as e:
            self.stdout.write(f"视图调用出错: {str(e)}")