from django.core.management.base import BaseCommand
import os

class Command(BaseCommand):
    help = '测试智能邮件发送器'

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, help='测试目标邮箱地址')
        parser.add_argument('--method', type=str, choices=['auto', 'qq', 'outlook', 'django'],
                          default='auto', help='首选发送方法')

    def handle(self, *args, **options):
        target_email = options.get('email', 'test_101@03vps.cn')
        preferred_method = options.get('method', 'auto')

        self.stdout.write('=== 智能邮件发送器测试 ===')
        self.stdout.write(f'目标邮箱: {target_email}')
        self.stdout.write(f'首选方法: {preferred_method}')
        self.stdout.write('')

        # 导入智能邮件发送器
        try:
            from core.mailers.smart_email_sender import SmartEmailSender
        except ImportError as e:
            self.stdout.write(self.style.ERROR(f'导入错误: {e}'))
            return

        # 创建发送器实例
        sender = SmartEmailSender()

        # 显示当前配置
        self.stdout.write('当前邮件配置:')
        self.stdout.write(f'  QQ邮箱: {sender.qq_config["user"]}')
        self.stdout.write(f'  Outlook邮箱: {sender.outlook_config["user"]}')
        self.stdout.write(f'  QQ密码配置: {"[OK]" if sender.qq_config["password"] else "[MISSING]"}')
        self.stdout.write(f'  Outlook密码配置: {"[OK]" if sender.outlook_config["password"] else "[MISSING]"}')
        self.stdout.write('')

        if preferred_method == 'all':
            # 测试所有方法
            self.stdout.write('测试所有邮件发送方法...')
            results = sender.test_all_methods(target_email)

            self.stdout.write('\\n测试结果:')
            for method, result in results.items():
                self.stdout.write(f'  {method}: {result}')

        else:
            # 使用指定方法发送测试邮件
            test_subject = f'[测试] 智能邮件发送器 ({preferred_method})'
            test_message = f'''
这是一封使用智能邮件发送器的测试邮件。

测试详情:
- 发送方法: {preferred_method}
- 发送时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- 发件人: 智能邮件发送器

如果您收到此邮件，说明邮件发送功能正常！

谢谢！
            '''.strip()

            self.stdout.write(f'使用 {preferred_method} 方法发送测试邮件...')
            success, method_used = sender.send_email(
                subject=test_subject,
                message=test_message,
                to_emails=[target_email],
                preferred_method=preferred_method
            )

            if success:
                self.stdout.write(self.style.SUCCESS(f'[SUCCESS] 邮件发送成功！使用方法: {method_used}'))
            else:
                self.stdout.write(self.style.ERROR(f'[FAIL] 邮件发送失败'))

        self.stdout.write('\\n=== 测试完成 ===')
        self.stdout.write('建议:')
        self.stdout.write('1. QQ邮箱配置稳定可靠，推荐使用')
        self.stdout.write('2. Outlook需要启用SMTP基本认证或使用OAuth2')
        self.stdout.write('3. 如果需要切换发件人，修改.env文件中的配置')
