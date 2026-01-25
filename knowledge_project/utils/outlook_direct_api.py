"""
尝试直接使用 Outlook REST API
绕过 Graph API，直接使用 Outlook API
"""

import requests
import msal
import os
import logging

logger = logging.getLogger(__name__)

def test_outlook_direct_api():
    """测试直接使用 Outlook REST API"""

    client_id = os.getenv('OUTLOOK_CLIENT_ID')
    client_secret = os.getenv('OUTLOOK_CLIENT_SECRET')
    tenant_id = os.getenv('OUTLOOK_TENANT_ID')
    email_address = os.getenv('OUTLOOK_EMAIL')

    print('=== 测试 Outlook 直接 API ===')
    print(f'客户端ID: {client_id[:10]}...')
    print(f'邮箱: {email_address}')

    # 使用 Microsoft Graph API 获取令牌
    app = msal.ConfidentialClientApplication(
        client_id=client_id,
        client_credential=client_secret,
        authority=f'https://login.microsoftonline.com/{tenant_id}'
    )

    # 获取访问令牌
    scopes = ['https://graph.microsoft.com/.default']
    result = app.acquire_token_for_client(scopes=scopes)

    if 'access_token' not in result:
        print(f'[FAIL] 无法获取令牌: {result.get("error_description")}')
        return False

    access_token = result['access_token']
    print('[OK] 令牌获取成功')

    # 尝试不同的 API 端点
    endpoints = [
        {
            'name': 'Outlook REST API (v1.0)',
            'url': 'https://outlook.office.com/api/v1.0/me/sendmail',
            'headers': {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json;odata=verbose'
            }
        },
        {
            'name': 'Outlook REST API (v2.0)',
            'url': 'https://outlook.office.com/api/v2.0/me/sendmail',
            'headers': {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json;odata=verbose'
            }
        },
        {
            'name': 'Graph API (beta)',
            'url': 'https://graph.microsoft.com/beta/me/sendMail',
            'headers': {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
        }
    ]

    # 邮件数据
    email_data = {
        'Message': {
            'Subject': '[TEST] Outlook Direct API 测试',
            'Body': {
                'ContentType': 'Text',
                'Content': '这是通过直接 Outlook API 发送的测试邮件。如果您收到此邮件，说明直接 API 配置成功！'
            },
            'ToRecipients': [
                {
                    'EmailAddress': {
                        'Address': 'test_101@03vps.cn'
                    }
                }
            ]
        },
        'SaveToSentItems': False
    }

    for endpoint in endpoints:
        print(f'\\n--- 测试 {endpoint["name"]} ---')

        try:
            response = requests.post(
                endpoint['url'],
                headers=endpoint['headers'],
                json=email_data,
                timeout=30
            )

            print(f'状态码: {response.status_code}')

            if response.status_code == 202:
                print('🎉 [SUCCESS] 邮件发送成功！')
                print('请检查 test_101@03vps.cn 邮箱')
                return True
            elif response.status_code == 200:
                print('🎉 [SUCCESS] 邮件发送成功！')
                print('请检查 test_101@03vps.cn 邮箱')
                return True
            else:
                print(f'[FAIL] {response.status_code}')
                print(f'响应: {response.text[:300]}...')

        except Exception as e:
            print(f'[ERROR] {e}')

    return False

def test_mail_send_endpoint():
    """测试 Graph API 的 /mail/send 端点"""

    client_id = os.getenv('OUTLOOK_CLIENT_ID')
    client_secret = os.getenv('OUTLOOK_CLIENT_SECRET')
    tenant_id = os.getenv('OUTLOOK_TENANT_ID')

    print('\\n=== 测试 Graph API /mail/send 端点 ===')

    app = msal.ConfidentialClientApplication(
        client_id=client_id,
        client_credential=client_secret,
        authority=f'https://login.microsoftonline.com/{tenant_id}'
    )

    scopes = ['https://graph.microsoft.com/.default']
    result = app.acquire_token_for_client(scopes=scopes)

    if 'access_token' not in result:
        print(f'[FAIL] 无法获取令牌')
        return False

    access_token = result['access_token']
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    # 尝试不同的邮件发送端点
    endpoints = [
        'https://graph.microsoft.com/v1.0/me/microsoft.graph.sendMail',
        'https://graph.microsoft.com/beta/me/microsoft.graph.sendMail',
    ]

    email_data = {
        'message': {
            'subject': '[ALTERNATIVE] Graph API 发送测试',
            'body': {
                'contentType': 'Text',
                'content': '这是通过替代 Graph API 端点发送的测试邮件。'
            },
            'toRecipients': [
                {
                    'emailAddress': {
                        'address': 'test_101@03vps.cn'
                    }
                }
            ]
        },
        'saveToSentItems': 'false'
    }

    for endpoint in endpoints:
        print(f'\\n测试端点: {endpoint}')

        try:
            response = requests.post(endpoint, headers=headers, json=email_data)
            print(f'状态码: {response.status_code}')

            if response.status_code == 202:
                print('🎉 [SUCCESS] 邮件发送成功！')
                return True
            else:
                print(f'[FAIL] {response.text[:300]}...')

        except Exception as e:
            print(f'[ERROR] {e}')

    return False

if __name__ == '__main__':
    print('尝试不同的 Outlook API 方法...')

    # 测试直接 Outlook API
    if test_outlook_direct_api():
        print('\\n✅ 成功！直接 Outlook API 可用')
    else:
        print('\\n❌ 直接 Outlook API 不可用')

        # 测试替代 Graph API 端点
        if test_mail_send_endpoint():
            print('\\n✅ 成功！替代 Graph API 端点可用')
        else:
            print('\\n❌ 所有方法都失败')