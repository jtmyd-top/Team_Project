from django.core.management.base import BaseCommand
from django.utils import timezone
from knowledge_project.models import PasswordResetToken

class Command(BaseCommand):
    help = '检查密码重置令牌的状态和过期时间'

    def handle(self, *args, **options):
        tokens = PasswordResetToken.objects.all()

        self.stdout.write(f"总共找到 {tokens.count()} 个密码重置令牌：")

        for token in tokens:
            created_hours_ago = (timezone.now() - token.created_at).total_seconds() / 3600
            remaining_time = token.get_remaining_time()

            status = []
            if token.is_used:
                status.append("已使用")
            if token.is_expired:
                status.append("已过期")
            if not token.is_used and not token.is_expired:
                status.append("有效")

            self.stdout.write(f"""
用户: {token.user.username}
Token: {token.token[:8]}...
创建时间: {token.created_at.strftime('%Y-%m-%d %H:%M:%S')}
过期时间: {token.expires_at.strftime('%Y-%m-%d %H:%M:%S')}
创建时长: {created_hours_ago:.1f} 小时前
剩余时间: {remaining_time:.1f} 小时
状态: {', '.join(status)}
{'-' * 50}
            """)