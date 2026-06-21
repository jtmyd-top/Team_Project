"""
Outlook OAuth2 邮件发送工具
使用 Microsoft Graph API 和 OAuth2 进行身份验证
"""

import msal
import requests
import json
import os
from datetime import datetime, timedelta
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class OutlookOAuth2EmailSender:
    def __init__(self):
        self.client_id = os.getenv('OUTLOOK_CLIENT_ID')
        self.client_secret = os.getenv('OUTLOOK_CLIENT_SECRET')
        self.tenant_id = os.getenv('OUTLOOK_TENANT_ID')
        self.email_address = os.getenv('OUTLOOK_EMAIL')

        # Microsoft Graph API 端点
        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        # 使用应用程序权限
        self.scopes = ["https://graph.microsoft.com/.default"]
        self.graph_url = "https://graph.microsoft.com/v1.0"

        # 创建 MSAL 应用
        self.app = msal.ConfidentialClientApplication(
            client_id=self.client_id,
            client_credential=self.client_secret,
            authority=self.authority
        )

        # 缓存访问令牌
        self.access_token = None
        self.token_expiry = None

    def get_access_token(self):
        """获取或刷新访问令牌"""
        # 检查是否需要刷新令牌
        if (self.access_token and self.token_expiry and
            datetime.now() < self.token_expiry):
            return self.access_token

        try:
            # 获取新的访问令牌
            result = self.app.acquire_token_for_client(scopes=self.scopes)

            if "access_token" in result:
                self.access_token = result["access_token"]
                # 令牌通常有效期为1小时，我们提前5分钟刷新
                self.token_expiry = datetime.now() + timedelta(minutes=55)

                logger.info("Successfully obtained access token")
                return self.access_token
            else:
                logger.error(f"Failed to get access token: {result.get('error_description', 'Unknown error')}")
                return None

        except Exception as e:
            logger.error(f"Error getting access token: {str(e)}")
            return None

    def send_email(self, subject, message, to_emails, from_email=None, html_content=None):
        """
        使用 OAuth2 SMTP 发送邮件

        Args:
            subject: 邮件主题
            message: 邮件内容 (纯文本)
            to_emails: 收件人列表
            from_email: 发件人邮箱 (可选，默认使用配置的邮箱)
            html_content: HTML格式的邮件内容 (可选)

        Returns:
            bool: 发送成功返回True，失败返回False
        """
        if not self.email_address:
            logger.error("OUTLOOK_EMAIL not configured")
            return False

        access_token = self.get_access_token()
        if not access_token:
            logger.error("Failed to get access token")
            return False

        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            # 连接到 Office 365 SMTP 服务器
            smtp_server = "smtp.office365.com"
            smtp_port = 587

            # 创建邮件
            msg = MIMEMultipart()
            msg['From'] = from_email or self.email_address
            msg['To'] = ', '.join(to_emails)
            msg['Subject'] = subject

            # 添加邮件正文
            if html_content:
                # 如果有HTML内容，同时添加纯文本和HTML版本
                text_part = MIMEText(message, 'plain', 'utf-8')
                html_part = MIMEText(html_content, 'html', 'utf-8')
                msg.attach(text_part)
                msg.attach(html_part)
            else:
                text_part = MIMEText(message, 'plain', 'utf-8')
                msg.attach(text_part)

            # 使用 OAuth2 认证连接 SMTP
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()

            # 使用 OAuth2 令牌进行认证
            auth_string = f"user={self.email_address}\x01auth=Bearer {access_token}\x01\x01"
            server.docmd('AUTH', 'XOAUTH2')
            server.docmd('', auth_string)

            # 发送邮件
            server.send_message(msg)
            server.quit()

            logger.info(f"Email sent successfully to {', '.join(to_emails)}")
            return True

        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            return False

    def test_connection(self):
        """测试OAuth2连接和权限"""
        access_token = self.get_access_token()
        if not access_token:
            return False, "Failed to get access token"

        try:
            # 测试发送到自己的邮箱
            result = self.send_email(
                subject="OAuth2 Connection Test",
                message="This is a test email to verify OAuth2 configuration.",
                to_emails=[self.email_address]
            )

            if result:
                return True, "Connection test successful"
            else:
                return False, "Failed to send test email"

        except Exception as e:
            return False, f"Connection test failed: {str(e)}"


# Django邮件后端集成
class OutlookOAuth2EmailBackend:
    """
    Django 邮件后端，使用 Outlook OAuth2
    """
    def __init__(self, fail_silently=False, **kwargs):
        self.fail_silently = fail_silently
        self.sender = OutlookOAuth2EmailSender()

    def send_messages(self, email_messages):
        """
        发送邮件消息列表

        Args:
            email_messages: Django EmailMessage 对象列表

        Returns:
            int: 成功发送的邮件数量
        """
        sent_count = 0

        for message in email_messages:
            try:
                # 提取邮件信息
                to_emails = [email.addr_spec for email in message.to]
                subject = message.subject
                content = message.body

                # 确定内容类型
                html_content = None
                if message.content_subtype == 'html':
                    html_content = content
                    # 提取纯文本版本
                    import re
                    content = re.sub('<[^<]+?>', '', content)

                # 发送邮件
                success = self.sender.send_email(
                    subject=subject,
                    message=content,
                    to_emails=to_emails,
                    from_email=message.from_email,
                    html_content=html_content
                )

                if success:
                    sent_count += 1

            except Exception as e:
                if not self.fail_silently:
                    logger.error(f"Failed to send email: {str(e)}")
                    raise

        return sent_count