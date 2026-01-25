from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
import os

class Command(BaseCommand):
    help = '发送测试密码重置邮件到多个邮箱地址'

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, help='主要测试邮箱')
        parser.add_argument('--alternative', type=str, help='备用邮箱地址')

    def handle(self, *args, **options):
        primary_email = options.get('email')
        alternative_email = options.get('alternative')

        # 测试邮箱列表
        test_emails = []
        if primary_email:
            test_emails.append(primary_email)
        if alternative_email:
            test_emails.append(alternative_email)

        # 添加一些默认的测试邮箱
        test_emails.extend([
            '13017172851@qq.com',  # 发件人QQ邮箱
        ])

        # 去重
        test_emails = list(set(test_emails))

        self.stdout.write('=== 发送测试密码重置邮件 ===')

        for email in test_emails:
            try:
                # 检查邮箱对应的用户
                try:
                    user = User.objects.get(email=email)
                    self.stdout.write(f'找到用户: {user.username} ({email})')
                except User.DoesNotExist:
                    self.stdout.write(f'邮箱 {email} 不在系统中，但仍然发送测试邮件')

                # 发送测试邮件
                subject = '🧪 密码重置功能测试邮件'
                message = f'''
亲爱的用户，

这是一封测试邮件，用于验证密码重置功能是否正常工作。

测试详情:
- 目标邮箱: {email}
- 发送时间: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
- 发件服务器: QQ邮箱 SMTP (smtp.qq.com:587)
- 状态: 系统运行正常

如果您收到此邮件，说明邮件发送功能工作正常。
如果您之前无法收到密码重置邮件，问题可能出在:
1. 邮件被归类为垃圾邮件
2. 邮件服务商的拦截策略
3. Cloudflare邮件路由配置问题

建议:
1. 将发件人(13017172851@qq.com)添加到联系人/白名单
2. 检查垃圾邮件文件夹
3. 如使用Cloudflare邮件路由，请检查上游邮件服务器配置

谢谢！

技术团队
                '''.strip()

                result = send_mail(
                    subject=subject,
                    message=message,
                    from_email=os.getenv('EMAIL_HOST_USER'),
                    recipient_list=[email],
                    fail_silently=False
                )

                self.stdout.write(f'[OK] {email}: 发送成功 (返回值: {result})')

            except Exception as e:
                self.stdout.write(f'[FAIL] {email}: 发送失败 - {str(e)}')

        self.stdout.write('\n=== 测试完成 ===')
        self.stdout.write('如果大部分邮箱都能收到邮件，说明系统功能正常。')
        self.stdout.write('如果特定邮箱收不到，问题可能出在收件方邮件服务器或配置上。')

from django.utils import timezone