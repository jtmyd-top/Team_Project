"""
简化版 Outlook 邮件发送工具
使用应用程序权限通过 Graph API 发送邮件
"""

import msal
import requests
import os
import json
import logging

logger = logging.getLogger(__name__)

class SimpleOutlookEmailSender:
    def __init__(self):
        self.client_id = os.getenv('OUTLOOK_CLIENT_ID')
        self.client_secret = os.getenv('OUTLOOK_CLIENT_SECRET')
        self.tenant_id = os.getenv('OUTLOOK_TENANT_ID')
        self.email_address = os.getenv('OUTLOOK_EMAIL')

        # Microsoft Graph API 配置
        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        self.scopes = ["https://graph.microsoft.com/.default"]
        self.graph_url = "https://graph.microsoft.com/v1.0"

        # 创建 MSAL 应用
        self.app = msal.ConfidentialClientApplication(
            client_id=self.client_id,
            client_credential=self.client_secret,
            authority=self.authority
        )

    def get_access_token(self):
        """获取访问令牌"""
        try:
            result = self.app.acquire_token_for_client(scopes=self.scopes)

            if "access_token" in result:
                logger.info("Successfully obtained access token")
                return result["access_token"]
            else:
                logger.error(f"Failed to get access token: {result.get('error_description', 'Unknown error')}")
                return None

        except Exception as e:
            logger.error(f"Error getting access token: {str(e)}")
            return None

    def send_email(self, subject, message, to_emails, from_email=None):
        """
        使用 Graph API 发送邮件（适用于应用程序权限）

        Args:
            subject: 邮件主题
            message: 邮件内容
            to_emails: 收件人列表
            from_email: 发件人邮箱（可选）

        Returns:
            bool: 发送成功返回 True
        """
        if not self.email_address:
            logger.error("OUTLOOK_EMAIL not configured")
            return False

        access_token = self.get_access_token()
        if not access_token:
            logger.error("Failed to get access token")
            return False

        # 使用配置的邮箱作为发件人
        sender_email = from_email or self.email_address

        # 准备邮件数据
        email_data = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "Text",
                    "content": message
                },
                "from": {
                    "emailAddress": {
                        "address": sender_email
                    }
                },
                "toRecipients": [
                    {
                        "emailAddress": {
                            "address": email
                        }
                    } for email in to_emails
                ]
            },
            "saveToSentItems": "false"
        }

        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            # 尝试不同的端点来发送邮件
            endpoints_to_try = [
                f"{self.graph_url}/users/{sender_email}/sendMail",
                f"{self.graph_url}/me/sendMail",  # 可能在某些情况下工作
            ]

            for endpoint in endpoints_to_try:
                try:
                    logger.info(f"尝试端点: {endpoint}")
                    response = requests.post(endpoint, headers=headers, json=email_data, timeout=30)

                    if response.status_code == 202:
                        logger.info(f"邮件发送成功到 {', '.join(to_emails)}")
                        return True
                    else:
                        logger.warning(f"端点 {endpoint} 失败: {response.status_code} - {response.text}")
                        continue

                except Exception as e:
                    logger.warning(f"端点 {endpoint} 异常: {str(e)}")
                    continue

            logger.error("所有端点都失败")
            return False

        except Exception as e:
            logger.error(f"发送邮件时出错: {str(e)}")
            return False

    def test_configuration(self):
        """测试配置是否正确"""
        access_token = self.get_access_token()
        if not access_token:
            return False, "无法获取访问令牌"

        # 检查令牌信息
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            # 尝试获取应用信息来验证权限
            response = requests.get(f"{self.graph_url}/application", headers=headers)

            if response.status_code == 200:
                return True, "配置正确，权限验证成功"
            else:
                return False, f"权限验证失败: {response.status_code} - {response.text}"

        except Exception as e:
            return False, f"配置测试失败: {str(e)}"