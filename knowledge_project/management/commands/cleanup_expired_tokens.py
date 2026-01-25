from django.core.management.base import BaseCommand
from django.utils import timezone
from knowledge_project.models import PasswordResetToken

class Command(BaseCommand):
    help = '清理所有已过期或已使用的密码重置令牌'

    def handle(self, *args, **options):
        # 删除所有令牌（包括过期的和已使用的）
        total_tokens = PasswordResetToken.objects.count()
        PasswordResetToken.objects.all().delete()

        self.stdout.write(f"已清理 {total_tokens} 个密码重置令牌")
        self.stdout.write("现在所有密码重置令牌都使用24小时过期设置")