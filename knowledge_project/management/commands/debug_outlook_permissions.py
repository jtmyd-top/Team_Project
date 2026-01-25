from django.core.management.base import BaseCommand
import os
import requests
import msal
import json

class Command(BaseCommand):
    help = '调试 Outlook OAuth2 权限问题'

    def handle(self, *args, **options):
        self.stdout.write('=== Outlook OAuth2 权限调试工具 ===')

        client_id = os.getenv('OUTLOOK_CLIENT_ID')
        client_secret = os.getenv('OUTLOOK_CLIENT_SECRET')
        tenant_id = os.getenv('OUTLOOK_TENANT_ID')

        if not all([client_id, client_secret, tenant_id]):
            self.stdout.write('[ERROR] 缺少必要的环境变量')
            return

        # 创建 MSAL 应用
        app = msal.ConfidentialClientApplication(
            client_id=client_id,
            client_credential=client_secret,
            authority=f'https://login.microsoftonline.com/{tenant_id}'
        )

        # 获取访问令牌
        scopes = ['https://graph.microsoft.com/.default']
        result = app.acquire_token_for_client(scopes=scopes)

        if 'access_token' not in result:
            self.stdout.write(f'[FAIL] 无法获取令牌: {result.get("error_description")}')
            return

        access_token = result['access_token']
        self.stdout.write('[OK] 访问令牌获取成功')

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }

        # 调试信息
        self.stdout.write(f'\\n客户端ID: {client_id}')
        self.stdout.write(f'租户ID: {tenant_id}')
        self.stdout.write(f'令牌长度: {len(access_token)} 字符')

        # 测试不同的 API 端点
        tests = [
            {
                'name': '检查应用程序权限',
                'url': 'https://graph.microsoft.com/v1.0/servicePrincipals',
                'method': 'GET'
            },
            {
                'name': '检查用户目录访问权限',
                'url': 'https://graph.microsoft.com/v1.0/users',
                'method': 'GET'
            },
            {
                'name': '检查邮件发送权限',
                'url': 'https://graph.microsoft.com/v1.0/users/$count',
                'method': 'GET'
            },
            {
                'name': '尝试发送测试邮件',
                'url': 'https://graph.microsoft.com/v1.0/me/sendMail',
                'method': 'POST',
                'data': {
                    'message': {
                        'subject': '[DEBUG] 权限测试邮件',
                        'body': {'contentType': 'Text', 'content': '测试邮件'},
                        'toRecipients': [{'emailAddress': {'address': 'test@debug.com'}}]
                    }
                }
            }
        ]

        success_count = 0

        for test in tests:
            self.stdout.write(f'\\n--- {test["name"]} ---')

            try:
                if test['method'] == 'GET':
                    response = requests.get(test['url'], headers=headers)
                else:
                    response = requests.post(test['url'], headers=headers, json=test['data'])

                status = response.status_code

                if status == 200:
                    self.stdout.write(f'[OK] {status}')
                    success_count += 1
                    if 'users' in test['url']:
                        data = response.json()
                        count = len(data.get('value', []))
                        self.stdout.write(f'  找到 {count} 个用户')
                elif status == 202:
                    self.stdout.write('[OK] 202 (邮件发送成功)')
                    success_count += 1
                elif status == 401:
                    self.stdout.write(f'[FAIL] 401 - 认证失败')
                elif status == 403:
                    self.stdout.write(f'[FAIL] 403 - 权限不足')
                    error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                    self.stdout.write(f'  详细错误: {error_data.get("error", {}).get("message", "未知错误")}')
                elif status == 404:
                    self.stdout.write(f'[FAIL] 404 - 资源未找到')
                else:
                    self.stdout.write(f'[PARTIAL] {status}')
                    try:
                        error_data = response.json()
                        message = error_data.get('error', {}).get('message', response.text[:100])
                        self.stdout.write(f'  错误信息: {message}')
                    except:
                        self.stdout.write(f'  响应: {response.text[:100]}')

            except Exception as e:
                self.stdout.write(f'[ERROR] {str(e)}')

        # 总结
        self.stdout.write(f'\\n=== 测试总结 ===')
        self.stdout.write(f'成功测试: {success_count}/{len(tests)}')

        if success_count == 0:
            self.stdout.write('\\n[DIAGNOSIS] 可能的问题:')
            self.stdout.write('1. Azure AD 应用权限配置不正确')
            self.stdout.write('2. 缺少管理员同意')
            self.stdout.write('3. 权限范围设置错误')
            self.stdout.write('4. 用户账户权限问题')

            self.stdout.write('\\n[RECOMMENDATION]')
            self.stdout.write('1. 在 Azure Portal 中检查应用权限:')
            self.stdout.write('   - 访问 https://portal.azure.com')
            self.stdout.write('   - Azure Active Directory -> App registrations')
            self.stdout.write('   - 找到您的应用 -> API permissions')
            self.stdout.write('2. 确保已授予管理员同意')
            self.stdout.write('3. 检查是否选择了正确的权限类型（委托 vs 应用程序）')
            self.stdout.write('4. 考虑使用 QQ 邮箱作为替代方案（已验证可用）')

        elif success_count < len(tests):
            self.stdout.write('\\n[PARTIAL SUCCESS] 部分功能可用，但邮件发送失败')
            self.stdout.write('建议继续使用 QQ 邮箱配置')

        else:
            self.stdout.write('\\n[FULL SUCCESS] Outlook OAuth2 完全配置正确！')

        self.stdout.write('\\n=== 调试完成 ===')