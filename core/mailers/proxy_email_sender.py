"""
支持代理的邮件发送器
当直连失败时，自动使用代理重新发送
"""

import smtplib
import os
import socket
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from django.core.mail import get_connection
from django.core.mail.message import EmailMessage
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)


class ProxyEmailBackend:
    """
    支持代理的Django邮件后端
    当直连失败时，自动使用代理重新发送
    """

    def __init__(self, fail_silently=False, **kwargs):
        self.fail_silently = fail_silently
        self.connection = None

        # 从环境变量读取代理配置
        self.proxy_host = os.getenv('SMTP_PROXY_HOST')
        self.proxy_port = int(os.getenv('SMTP_PROXY_PORT', '1080'))
        self.proxy_username = os.getenv('SMTP_PROXY_USERNAME')
        self.proxy_password = os.getenv('SMTP_PROXY_PASSWORD')
        self.proxy_type = os.getenv('SMTP_PROXY_TYPE', 'socks5').lower()  # socks5 或 http

        # SMTP配置
        self.host = os.getenv('EMAIL_HOST')
        self.port = int(os.getenv('EMAIL_PORT', '587'))
        self.username = os.getenv('EMAIL_HOST_USER')
        self.password = os.getenv('EMAIL_PASSWORD')
        self.use_tls = os.getenv('EMAIL_USE_TLS', 'True').lower() in ['true', '1', 't']
        self.use_ssl = os.getenv('EMAIL_USE_SSL', 'False').lower() in ['true', '1', 't']
        self.timeout = int(os.getenv('EMAIL_TIMEOUT', '30'))

        # 连接失败后是否尝试使用代理
        self.fallback_to_proxy = os.getenv('EMAIL_FALLBACK_TO_PROXY', 'True').lower() in ['true', '1', 't']

        logger.info(f"[ProxyEmailBackend] 初始化 - 代理: {self.proxy_host}:{self.proxy_port} "
                   f"({self.proxy_type}), 回退代理: {self.fallback_to_proxy}")

    def open(self):
        """建立连接，失败时尝试使用代理"""
        if self.connection:
            return False

        # 首先尝试直连
        try:
            logger.info(f"[ProxyEmailBackend] 尝试直连 SMTP: {self.host}:{self.port}")
            self.connection = self._create_connection(use_proxy=False)
            logger.info("[ProxyEmailBackend] 直连成功 ✓")
            return False  # 新连接已创建
        except (socket.timeout, OSError) as e:
            logger.warning(f"[ProxyEmailBackend] 直连失败: {e}")

            # 如果配置了代理且允许回退，尝试使用代理
            if self.proxy_host and self.fallback_to_proxy:
                try:
                    logger.info(f"[ProxyEmailBackend] 尝试通过代理连接: {self.proxy_host}:{self.proxy_port}")
                    self.connection = self._create_connection(use_proxy=True)
                    logger.info("[ProxyEmailBackend] 代理连接成功 ✓")
                    return False  # 新连接已创建
                except Exception as proxy_error:
                    logger.error(f"[ProxyEmailBackend] 代理连接也失败: {proxy_error}")
                    if not self.fail_silently:
                        raise
                    return True
            else:
                logger.error("[ProxyEmailBackend] 未配置代理或不允许回退，连接失败")
                if not self.fail_silently:
                    raise
                return True
        except Exception as e:
            logger.error(f"[ProxyEmailBackend] 连接异常: {e}")
            if not self.fail_silently:
                raise
            return True

    def _create_connection(self, use_proxy=False):
        """创建SMTP连接，可选使用代理"""
        if use_proxy:
            return self._create_proxy_connection()
        else:
            return self._create_direct_connection()

    def _create_direct_connection(self):
        """创建直连SMTP连接"""
        if self.use_ssl:
            conn = smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout)
        else:
            conn = smtplib.SMTP(self.host, self.port, timeout=self.timeout)
            if self.use_tls:
                conn.starttls()

        conn.login(self.username, self.password)
        return conn

    def _create_proxy_connection(self):
        """通过代理创建SMTP连接"""
        try:
            # 导入 PySocks
            import socks as pysocks
        except ImportError:
            raise ImportError(
                "需要安装 PySocks 库来支持代理连接。请运行: pip install PySocks"
            )

        # 设置代理类型
        if self.proxy_type == 'socks5':
            proxy_type = pysocks.PROXY_TYPE_SOCKS5
        elif self.proxy_type == 'socks4':
            proxy_type = pysocks.PROXY_TYPE_SOCKS4
        elif self.proxy_type == 'http':
            proxy_type = pysocks.PROXY_TYPE_HTTP
        else:
            raise ValueError(f"不支持的代理类型: {self.proxy_type}")

        # 设置代理认证（如果提供）
        if self.proxy_username and self.proxy_password:
            logger.debug(f"[ProxyEmailBackend] 使用带认证的代理")

        # 创建代理包装的socket
        sock = pysocks.socksocket()
        sock.set_proxy(
            proxy_type=proxy_type,
            addr=self.proxy_host,
            port=self.proxy_port,
            username=self.proxy_username,
            password=self.proxy_password,
            rdns=True
        )
        sock.settimeout(self.timeout)

        # 连接到SMTP服务器
        logger.info(f"[ProxyEmailBackend] 通过代理连接到 {self.host}:{self.port}")
        sock.connect((self.host, self.port))

        # 使用自定义socket创建SMTP连接
        if self.use_ssl:
            # SSL模式下需要包装socket
            import ssl
            context = ssl.create_default_context()
            ssl_sock = context.wrap_socket(sock, server_hostname=self.host)
            conn = smtplib.SMTP_SSL()
            conn.sock = ssl_sock
        else:
            conn = smtplib.SMTP()
            conn.sock = sock

        # 启动TLS并登录
        if not self.use_ssl and self.use_tls:
            conn.starttls()

        conn.login(self.username, self.password)
        return conn

    def close(self):
        """关闭连接"""
        if self.connection:
            try:
                self.connection.quit()
            except Exception:
                pass
            self.connection = None

    def send_messages(self, email_messages: List[EmailMessage]) -> int:
        """
        发送邮件消息列表

        Args:
            email_messages: Django EmailMessage 对象列表

        Returns:
            int: 成功发送的邮件数量
        """
        if not email_messages:
            return 0

        # 打开连接
        new_conn_created = self.open()

        try:
            sent_count = 0
            for message in email_messages:
                try:
                    # 从EmailMessage对象构建消息
                    from_email = message.from_email
                    to_emails = [email.addr_spec for email in message.to]
                    cc_emails = [email.addr_spec for email in message.cc]
                    bcc_emails = [email.addr_spec for email in message.bcc]

                    # 构建MIME消息
                    msg = MIMEMultipart()
                    msg['From'] = from_email
                    msg['To'] = ', '.join(to_emails)
                    if cc_emails:
                        msg['Cc'] = ', '.join(cc_emails)
                    msg['Subject'] = message.subject

                    # 添加邮件正文
                    if message.body:
                        msg.attach(MIMEText(message.body, 'plain', 'utf-8'))

                    # 发送邮件
                    self.connection.send_message(msg)

                    logger.info(f"[ProxyEmailBackend] 邮件发送成功: {to_emails}")
                    sent_count += 1

                except Exception as e:
                    logger.error(f"[ProxyEmailBackend] 邮件发送失败: {e}")
                    if not self.fail_silently:
                        raise

            return sent_count

        except smtplib.SMTPException as e:
            # SMTP错误时，尝试重连
            logger.error(f"[ProxyEmailBackend] SMTP错误: {e}")
            if not self.fail_silently:
                self.close()
                raise
            return sent_count

        finally:
            # 如果创建了新连接，发送后关闭
            if new_conn_created:
                self.close()


class ProxySMTP:
    """
    独立的代理SMTP发送器，可直接使用
    """

    def __init__(self):
        self.proxy_host = os.getenv('SMTP_PROXY_HOST')
        self.proxy_port = int(os.getenv('SMTP_PROXY_PORT', '1080'))
        self.proxy_username = os.getenv('SMTP_PROXY_USERNAME')
        self.proxy_password = os.getenv('SMTP_PROXY_PASSWORD')
        self.proxy_type = os.getenv('SMTP_PROXY_TYPE', 'socks5').lower()

        self.smtp_host = os.getenv('EMAIL_HOST')
        self.smtp_port = int(os.getenv('EMAIL_PORT', '587'))
        self.smtp_user = os.getenv('EMAIL_HOST_USER')
        self.smtp_password = os.getenv('EMAIL_PASSWORD')
        self.use_tls = os.getenv('EMAIL_USE_TLS', 'True').lower() in ['true', '1', 't']
        self.timeout = int(os.getenv('EMAIL_TIMEOUT', '30'))
        self.fallback_to_proxy = os.getenv('EMAIL_FALLBACK_TO_PROXY', 'True').lower() in ['true', '1', 't']

    def send(
        self,
        subject: str,
        body: str,
        to_emails: List[str],
        from_email: Optional[str] = None,
        html: bool = False
    ) -> Tuple[bool, str]:
        """
        发送邮件

        Args:
            subject: 邮件主题
            body: 邮件正文
            to_emails: 收件人列表
            from_email: 发件人（可选）
            html: 是否为HTML格式

        Returns:
            tuple: (success, message)
        """
        from_email = from_email or self.smtp_user

        # 构建邮件
        msg = MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = ', '.join(to_emails)
        msg['Subject'] = subject

        # 添加正文
        mime_type = 'html' if html else 'plain'
        msg.attach(MIMEText(body, mime_type, 'utf-8'))

        # 首先尝试直连
        try:
            logger.info(f"[ProxySMTP] 尝试直连发送")
            conn = self._create_connection(use_proxy=False)
            conn.send_message(msg)
            conn.quit()
            logger.info(f"[ProxySMTP] 直连发送成功 ✓")
            return True, "直连发送成功"
        except (socket.timeout, OSError) as e:
            logger.warning(f"[ProxySMTP] 直连失败: {e}")

            # 尝试使用代理
            if self.proxy_host and self.fallback_to_proxy:
                try:
                    logger.info(f"[ProxySMTP] 尝试通过代理发送")
                    conn = self._create_connection(use_proxy=True)
                    conn.send_message(msg)
                    conn.quit()
                    logger.info(f"[ProxySMTP] 代理发送成功 ✓")
                    return True, "代理发送成功"
                except Exception as proxy_error:
                    logger.error(f"[ProxySMTP] 代理发送失败: {proxy_error}")
                    return False, f"代理发送失败: {proxy_error}"
            else:
                logger.error(f"[ProxySMTP] 未配置代理，发送失败")
                return False, f"直连失败且未配置代理: {e}"
        except Exception as e:
            logger.error(f"[ProxySMTP] 发送异常: {e}")
            return False, f"发送异常: {e}"

    def _create_connection(self, use_proxy=False):
        """创建SMTP连接"""
        if use_proxy:
            return self._create_proxy_connection()
        else:
            return self._create_direct_connection()

    def _create_direct_connection(self):
        """创建直连"""
        conn = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=self.timeout)
        if self.use_tls:
            conn.starttls()
        conn.login(self.smtp_user, self.smtp_password)
        return conn

    def _create_proxy_connection(self):
        """创建代理连接"""
        try:
            import socks as pysocks
        except ImportError:
            raise ImportError("需要安装 PySocks: pip install PySocks")

        # 设置代理
        if self.proxy_type == 'socks5':
            proxy_type = pysocks.PROXY_TYPE_SOCKS5
        elif self.proxy_type == 'socks4':
            proxy_type = pysocks.PROXY_TYPE_SOCKS4
        elif self.proxy_type == 'http':
            proxy_type = pysocks.PROXY_TYPE_HTTP
        else:
            raise ValueError(f"不支持的代理类型: {self.proxy_type}")

        # 创建socket
        sock = pysocks.socksocket()
        sock.set_proxy(
            proxy_type=proxy_type,
            addr=self.proxy_host,
            port=self.proxy_port,
            username=self.proxy_username,
            password=self.proxy_password,
            rdns=True
        )
        sock.settimeout(self.timeout)
        sock.connect((self.smtp_host, self.smtp_port))

        # 创建SMTP
        conn = smtplib.SMTP()
        conn.sock = sock

        if self.use_tls:
            conn.starttls()

        conn.login(self.smtp_user, self.smtp_password)
        return conn


def send_mail_with_proxy(
    subject: str,
    message: str,
    recipient_list: List[str],
    from_email: Optional[str] = None,
    html: bool = False
) -> Tuple[bool, str]:
    """
    便捷函数：发送支持代理的邮件

    Args:
        subject: 邮件主题
        message: 邮件内容
        recipient_list: 收件人列表
        from_email: 发件人（可选）
        html: 是否为HTML格式

    Returns:
        tuple: (success, message)
    """
    sender = ProxySMTP()
    return sender.send(subject, message, recipient_list, from_email, html)
