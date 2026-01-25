from django.core.management.base import BaseCommand
from django.conf import settings
import os

class Command(BaseCommand):
    help = '测试 Outlook OAuth2 邮件发送配置'

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, help='测试目标邮箱地址')

    def handle(self, *args, **options):
        target_email = options.get('email')

        self.stdout.write('=== Outlook OAuth2 邮件测试 ===')

        # 检查环境变量
        required_vars = ['OUTLOOK_CLIENT_ID', 'OUTLOOK_CLIENT_SECRET', 'OUTLOOK_TENANT_ID', 'OUTLOOK_EMAIL']
        missing_vars = []

        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)

        if missing_vars:
            self.stdout.write(self.style.ERROR(f'缺少环境变量: {", ".join(missing_vars)}'))
            self.stdout.write('请按照 docs/azure_ad_setup_guide.md 配置 Azure AD 应用')
            return

        # 导入 OAuth2 发送器
        try:
            from knowledge_project.utils.outlook_oauth2 import OutlookOAuth2EmailSender
        except ImportError as e:
            self.stdout.write(self.style.ERROR(f'导入错误: {e}'))
            self.stdout.write('请确保已安装必要的库: pip install msal requests')
            return

        # 创建发送器实例
        sender = OutlookOAuth2EmailSender()

        self.stdout.write(f'发件人: {sender.email_address}')
        self.stdout.write(f'客户端ID: {sender.client_id[:10]}...' if sender.client_id else '未设置')
        self.stdout.write(f'租户ID: {sender.tenant_id[:10]}...' if sender.tenant_id else '未设置')

        # 测试连接
        self.stdout.write('\\n测试 OAuth2 连接...')
        success, message = sender.test_connection()

        if success:
            self.stdout.write(self.style.SUCCESS(f'✓ 连接测试成功: {message}'))
        else:
            self.stdout.write(self.style.ERROR(f'✗ 连接测试失败: {message}'))
            return

        # 如果指定了目标邮箱，发送测试邮件
        if target_email:
            self.stdout.write(f'\\n发送测试邮件到: {target_email}')

            success = sender.send_email(
                subject='[测试] Outlook OAuth2 邮件发送',
                message=f'''
这是一封测试邮件，验证 Outlook OAuth2 邮件发送功能。

测试详情:
- 发送时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- 发件人: {sender.email_address}
- 收件人: {target_email}
- 认证方式: OAuth2

如果您收到此邮件，说明 OAuth2 配置成功！

谢谢！
                '''.strip(),
                to_emails=[target_email]
            )

            if success:
                self.stdout.write(self.style.SUCCESS('✓ 测试邮件发送成功！'))
            else:
                self.stdout.write(self.style.ERROR('✗ 测试邮件发送失败'))

        self.stdout.write('\\n=== 测试完成 ===')

        # 提供切换到 OAuth2 的指导
        self.stdout.write('\\n要启用 OAuth2 邮件发送，请:')
        self.stdout.write('1. 取消注释 .env 中的 OUTLOOK_* 变量')
        self.stdout.write('2. 注释掉当前的 EMAIL_* 变量')
        self.stdout.write('3. 在 settings.py 中设置 EMAIL_BACKEND')
        self.stdout.write('   EMAIL_BACKEND = "knowledge_project.utils.outlook_oauth2.OutlookOAuth2EmailBackend"')