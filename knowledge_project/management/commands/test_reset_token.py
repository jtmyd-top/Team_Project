from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth.models import User
from knowledge_project.models import PasswordResetToken

class Command(BaseCommand):
    help = '创建测试密码重置令牌并验证24小时过期设置'

    def handle(self, *args, **options):
        # 删除所有现有的令牌
        PasswordResetToken.objects.all().delete()
        self.stdout.write("已清理所有现有的密码重置令牌")

        # 获取第一个用户进行测试
        try:
            user = User.objects.first()
            if not user:
                self.stdout.write("没有找到用户，请先创建用户")
                return

            # 创建测试令牌
            import secrets
            import string
            alphabet = string.ascii_letters + string.digits
            test_token = ''.join(secrets.choice(alphabet) for _ in range(64))

            reset_token = PasswordResetToken.objects.create(
                user=user,
                token=test_token
            )

            created_hours_ago = (timezone.now() - reset_token.created_at).total_seconds() / 3600
            remaining_time = reset_token.get_remaining_time()

            self.stdout.write(f"""
成功创建测试令牌：

用户: {user.username}
用户ID: {user.id}
Token: {test_token}
完整URL: http://127.0.0.1:8000/reset-password/{user.id}/{test_token}/

时间验证：
创建时间: {reset_token.created_at.strftime('%Y-%m-%d %H:%M:%S')}
过期时间: {reset_token.expires_at.strftime('%Y-%m-%d %H:%M:%S')}
剩余时间: {remaining_time:.1f} 小时 (应该是24小时)

验证结果：
过期时间是否正确设置: {'是' if remaining_time > 23 else '否'}
令牌是否有效: {'是' if not reset_token.is_expired else '否'}
            """)

        except Exception as e:
            self.stdout.write(f"创建测试令牌失败: {str(e)}")