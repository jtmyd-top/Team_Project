import requests
import logging
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)

# 开发模式开关：设置 TURNSTILE_ENABLED=false 可跳过验证
TURNSTILE_ENABLED = getattr(settings, 'TURNSTILE_ENABLED', True)
if isinstance(TURNSTILE_ENABLED, str):
    TURNSTILE_ENABLED = TURNSTILE_ENABLED.lower() not in ['false', '0', 'no']


class TurnstileValidator:
    """
    Cloudflare Turnstile 验证工具类
    """

    def __init__(self):
        self.site_key = getattr(settings, 'CLOUDFLARE_TURNSTILE_SITE_KEY', None)
        self.secret_key = getattr(settings, 'CLOUDFLARE_TURNSTILE_SECRET_KEY', None)
        self.verify_url = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'

        if not self.site_key or not self.secret_key:
            raise ImproperlyConfigured(
                "CLOUDFLARE_TURNSTILE_SITE_KEY and CLOUDFLARE_TURNSTILE_SECRET_KEY must be set in settings"
            )

    def verify_token(self, token, remote_ip=None):
        """
        验证 Turnstile token

        Args:
            token (str): 前端返回的 token
            remote_ip (str, optional): 用户IP地址，用于额外验证

        Returns:
            dict: 验证结果 {'success': bool, 'error_codes': list, 'message': str}
        """
        if not token:
            return {
                'success': False,
                'error_codes': ['missing-input-response'],
                'message': '验证码token缺失'
            }

        data = {
            'secret': self.secret_key,
            'response': token
        }

        if remote_ip:
            data['remoteip'] = remote_ip

        try:
            response = requests.post(
                self.verify_url,
                data=data,
                timeout=10
            )
            response.raise_for_status()
            result = response.json()

            if result.get('success'):
                return {
                    'success': True,
                    'message': '验证通过'
                }
            else:
                return {
                    'success': False,
                    'error_codes': result.get('error-codes', []),
                    'message': self._get_error_message(result.get('error-codes', []))
                }

        except requests.RequestException as e:
            logger.error(f"Turnstile验证请求失败: {str(e)}")
            return {
                'success': False,
                'error_codes': ['network-error'],
                'message': '验证服务暂时不可用，请稍后重试'
            }
        except Exception as e:
            logger.error(f"Turnstile验证异常: {str(e)}")
            return {
                'success': False,
                'error_codes': ['internal-error'],
                'message': '验证过程出现错误'
            }

    def _get_error_message(self, error_codes):
        """根据错误代码返回用户友好的错误信息"""
        error_messages = {
            'missing-input-secret': '服务器配置错误',
            'invalid-input-secret': '服务器密钥无效',
            'missing-input-response': '请完成验证码验证',
            'invalid-input-response': '验证码验证失败，请重试',
            'bad-request': '请求格式错误',
            'timeout-or-duplicate': '验证码超时或重复使用，请刷新页面重试',
            'internal-error': '服务器内部错误，请稍后重试'
        }

        for code in error_codes:
            if code in error_messages:
                return error_messages[code]

        return '验证失败，请重试'


# 创建全局验证器实例
try:
    turnstile_validator = TurnstileValidator()
except ImproperlyConfigured:
    # 如果配置缺失，创建一个假的验证器用于开发
    logger.warning("Turnstile配置缺失，使用开发模式验证器")
    turnstile_validator = None


def verify_turnstile_token(token, remote_ip=None):
    """
    验证 Turnstile token 的便捷函数

    Args:
        token (str): 前端返回的 token
        remote_ip (str, optional): 用户IP地址

    Returns:
        bool: 验证是否成功
    """
    # 检查是否禁用了 Turnstile
    if not TURNSTILE_ENABLED:
        logger.warning("Turnstile 已禁用：跳过验证")
        return True

    if not turnstile_validator:
        # 开发模式下，如果没有token也返回True
        logger.warning("开发模式：跳过Turnstile验证")
        return True

    result = turnstile_validator.verify_token(token, remote_ip)
    return result['success']


def get_turnstile_verification_detail(token, remote_ip=None):
    """
    获取详细的 Turnstile 验证结果

    Args:
        token (str): 前端返回的 token
        remote_ip (str, optional): 用户IP地址

    Returns:
        dict: 详细的验证结果
    """
    if not TURNSTILE_ENABLED:
        return {
            'success': True,
            'message': 'Turnstile 已禁用'
        }

    if not turnstile_validator:
        return {
            'success': True,
            'message': '开发模式验证通过'
        }

    return turnstile_validator.verify_token(token, remote_ip)


def get_site_key():
    """获取站点密钥"""
    if not TURNSTILE_ENABLED:
        return None
    if not turnstile_validator:
        return None
    return turnstile_validator.site_key


def is_turnstile_enabled():
    """检查 Turnstile 是否启用"""
    return TURNSTILE_ENABLED and turnstile_validator is not None