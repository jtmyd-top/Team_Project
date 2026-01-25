from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings

class Command(BaseCommand):
    help = '测试密码重置邮件发送功能'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='要测试的邮箱地址')

    def handle(self, *args, **options):
        email = options['email']

        # 检查邮箱是否存在
        try:
            user = User.objects.get(email=email)
            self.stdout.write(f'找到用户: {user.username} ({email})')
            user_exists = True
        except User.DoesNotExist:
            self.stdout.write(f'邮箱 {email} 不存在于系统中')
            user_exists = False

        if not user_exists:
            self.stdout.write('可用的测试邮箱:')
            users = User.objects.exclude(email='')
            for user in users[:5]:  # 只显示前5个
                self.stdout.write(f'  {user.username}: {user.email}')
            return

        # 创建测试重置链接
        from knowledge_project.models import PasswordResetToken
        import secrets
        import string

        PasswordResetToken.objects.filter(user=user).delete()

        alphabet = string.ascii_letters + string.digits
        test_token = ''.join(secrets.choice(alphabet) for _ in range(64))

        reset_token = PasswordResetToken.objects.create(
            user=user,
            token=test_token
        )

        reset_url = f"http://127.0.0.1:8000/reset-password/{user.pk}/{test_token}/"

        # 发送测试邮件
        subject = '测试 - 重置您的密码'
        message = f'''
您好，{user.username}！

这是一封测试邮件，用于验证忘记密码功能是否正常工作。

测试重置链接: {reset_url}

此链接将在24小时后失效。

如果您收到此邮件，说明忘记密码功能正常工作。

如果这不是您的操作，请忽略此邮件。
        '''

        try:
            result = send_mail(
                subject=subject,
                message=message,
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[email],
                fail_silently=False
            )

            self.stdout.write('测试邮件发送成功！')
            self.stdout.write(f'邮件发送结果: {result}')
            self.stdout.write(f'重置链接: {reset_url}')
            self.stdout.write('请检查邮箱是否收到测试邮件')

        except Exception as e:
            self.stdout.write(f'邮件发送失败: {str(e)}')