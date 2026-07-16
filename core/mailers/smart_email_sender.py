"""
智能邮件发送器
支持多种邮件发送方式，自动选择最佳方案
"""

import smtplib
import requests
import os
import logging
from django.conf import settings
from django.core.mail import get_connection
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from core.mailers.metrics import record_email_delivery

logger = logging.getLogger(__name__)

class SmartEmailSender:
    """
    智能邮件发送器，支持多种发送方式：
    1. QQ邮箱 SMTP（推荐，稳定）
    2. Outlook SMTP（如果启用基本认证）
    3. Outlook OAuth2（如果配置正确）
    """

    def __init__(self):
        self.last_error = ''
        # QQ邮箱配置
        self.qq_config = {
            'host': 'smtp.qq.com',
            'port': 587,
            'use_tls': True,
            'user': os.getenv('QQ_EMAIL_USER', '').strip(),
            'password': os.getenv('QQ_EMAIL_PASSWORD', os.getenv('EMAIL_PASSWORD', '')).strip(),
        }

        # Outlook配置
        self.outlook_config = {
            'host': 'smtp.office365.com',
            'port': 587,
            'use_tls': True,
            'user': os.getenv('OUTLOOK_EMAIL', '').strip(),
            'password': os.getenv('OUTLOOK_PASSWORD', '').strip(),
        }

    def send_email_qq(self, subject, message, to_emails, from_email=None):
        """使用QQ邮箱发送邮件"""
        self.last_error = ''
        if not self.qq_config['user'] or not self.qq_config['password']:
            self.last_error = 'QQ SMTP credentials are not configured'
            logger.warning("QQ SMTP账号或授权码未配置")
            return False
        try:
            msg = MIMEMultipart()
            msg['From'] = from_email or self.qq_config['user']
            msg['To'] = ', '.join(to_emails)
            msg['Subject'] = subject

            # 添加邮件正文
            text_part = MIMEText(message, 'plain', 'utf-8')
            msg.attach(text_part)

            # 连接SMTP服务器
            server = smtplib.SMTP(self.qq_config['host'], self.qq_config['port'])
            server.starttls()
            server.login(self.qq_config['user'], self.qq_config['password'])

            # 发送邮件
            server.send_message(msg)
            server.quit()

            logger.info(f"QQ邮箱发送成功: {', '.join(to_emails)}")
            return True

        except Exception as e:
            self.last_error = str(e)
            logger.error(f"QQ邮箱发送失败: {str(e)}")
            return False

    def send_email_outlook_smtp(self, subject, message, to_emails, from_email=None):
        """使用Outlook SMTP发送邮件"""
        self.last_error = ''
        if not self.outlook_config['user'] or not self.outlook_config['password']:
            self.last_error = 'Outlook SMTP credentials are not configured'
            logger.warning("Outlook SMTP账号或授权码未配置")
            return False

        try:
            msg = MIMEMultipart()
            msg['From'] = from_email or self.outlook_config['user']
            msg['To'] = ', '.join(to_emails)
            msg['Subject'] = subject

            text_part = MIMEText(message, 'plain', 'utf-8')
            msg.attach(text_part)

            server = smtplib.SMTP(self.outlook_config['host'], self.outlook_config['port'])
            server.starttls()
            server.login(self.outlook_config['user'], self.outlook_config['password'])

            server.send_message(msg)
            server.quit()

            logger.info(f"Outlook SMTP发送成功: {', '.join(to_emails)}")
            return True

        except Exception as e:
            self.last_error = str(e)
            logger.error(f"Outlook SMTP发送失败: {str(e)}")
            return False

    def send_email_django(self, subject, message, to_emails, from_email=None):
        """使用Django默认邮件后端发送"""
        self.last_error = ''
        try:
            from django.core.mail import send_mail

            result = send_mail(
                subject=subject,
                message=message,
                from_email=from_email,
                recipient_list=to_emails,
                fail_silently=False
            )

            logger.info(f"Django邮件发送成功: {result} 封邮件")
            return result > 0

        except Exception as e:
            self.last_error = str(e)
            logger.error(f"Django邮件发送失败: {str(e)}")
            return False

    def send_email(self, subject, message, to_emails, from_email=None, preferred_method='auto'):
        """
        智能发送邮件，自动选择最佳发送方式

        Args:
            subject: 邮件主题
            message: 邮件内容
            to_emails: 收件人列表
            from_email: 发件人邮箱
            preferred_method: 首选发送方法 ('qq', 'outlook', 'django', 'auto')

        Returns:
            tuple: (success, method_used)
        """
        if preferred_method == 'qq':
            success = self.send_email_qq(subject, message, to_emails, from_email)
            record_email_delivery(
                subject=subject,
                recipient_count=len(to_emails),
                success=success,
                provider='qq_smtp',
                error_message=self.last_error,
            )
            return success, 'QQ SMTP'

        elif preferred_method == 'outlook':
            success = self.send_email_outlook_smtp(subject, message, to_emails, from_email)
            record_email_delivery(
                subject=subject,
                recipient_count=len(to_emails),
                success=success,
                provider='outlook_smtp',
                error_message=self.last_error,
            )
            return success, 'Outlook SMTP'

        elif preferred_method == 'django':
            success = self.send_email_django(subject, message, to_emails, from_email)
            return success, 'Django SMTP'

        else:  # auto mode
            # 自动选择最佳发送方式
            methods = [
                ('QQ SMTP', lambda: self.send_email_qq(subject, message, to_emails, from_email)),
                ('Django SMTP', lambda: self.send_email_django(subject, message, to_emails, from_email)),
                ('Outlook SMTP', lambda: self.send_email_outlook_smtp(subject, message, to_emails, from_email)),
            ]

            django_attempted = False
            for method_name, method_func in methods:
                try:
                    logger.info(f"尝试使用 {method_name} 发送邮件")
                    if method_name == 'Django SMTP':
                        django_attempted = True
                    success = method_func()
                    if success:
                        logger.info(f"{method_name} 发送成功")
                        if method_name != 'Django SMTP':
                            record_email_delivery(
                                subject=subject,
                                recipient_count=len(to_emails),
                                success=True,
                                provider=method_name.lower().replace(' ', '_'),
                            )
                        return True, method_name
                    else:
                        logger.warning(f"{method_name} 发送失败，尝试下一个方法")
                except Exception as e:
                    logger.warning(f"{method_name} 出现异常: {str(e)}")

            logger.error("所有邮件发送方法都失败")
            # Django SMTP is already tracked by TrackingEmailBackend.
            if not django_attempted:
                record_email_delivery(
                    subject=subject,
                    recipient_count=len(to_emails),
                    success=False,
                    provider='smart_email_auto',
                    error_message=self.last_error,
                )
            return False, None

    def test_all_methods(self, test_email='test_101@03vps.cn'):
        """测试所有邮件发送方法"""
        test_subject = '[测试] 智能邮件发送器测试'
        test_message = f'''
这是一封测试邮件，用于验证不同的邮件发送方式。

测试时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

如果您收到此邮件，说明对应的发送方式工作正常。
        '''.strip()

        results = {}

        # 测试QQ邮箱
        try:
            success = self.send_email_qq(test_subject, test_message, [test_email])
            results['QQ SMTP'] = '✅ 成功' if success else '❌ 失败'
        except Exception as e:
            results['QQ SMTP'] = f'❌ 异常: {str(e)[:50]}'

        # 测试Django邮件
        try:
            success = self.send_email_django(test_subject, test_message, [test_email])
            results['Django SMTP'] = '✅ 成功' if success else '❌ 失败'
        except Exception as e:
            results['Django SMTP'] = f'❌ 异常: {str(e)[:50]}'

        # 测试Outlook SMTP
        try:
            success = self.send_email_outlook_smtp(test_subject, test_message, [test_email])
            results['Outlook SMTP'] = '✅ 成功' if success else '❌ 失败'
        except Exception as e:
            results['Outlook SMTP'] = f'❌ 异常: {str(e)[:50]}'

        return results


# Django邮件后端集成
class SmartEmailBackend:
    """
    Django邮件后端，使用智能邮件发送器
    """
    def __init__(self, fail_silently=False, **kwargs):
        self.fail_silently = fail_silently
        self.sender = SmartEmailSender()

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

                # 发送邮件（使用自动模式选择最佳发送方式）
                success, method_used = self.sender.send_email(
                    subject=subject,
                    message=content,
                    to_emails=to_emails,
                    from_email=message.from_email,
                    preferred_method='auto'
                )

                if success:
                    sent_count += 1
                    logger.info(f"邮件发送成功 (使用: {method_used})")

            except Exception as e:
                if not self.fail_silently:
                    logger.error(f"邮件发送失败: {str(e)}")
                    raise
                else:
                    logger.warning(f"邮件发送失败 (静默): {str(e)}")

        return sent_count
