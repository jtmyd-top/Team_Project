"""knowledge_project.views.auth 包：认证 / 登录 / 注册 / 2FA / 密码重置 / 邮箱验证 / 限流辅助。

原 auth.py 按职责拆分为 6 个子模块。对外保持 `from knowledge_project.views.auth import X` 的兼容。
"""
from ._shared import (
    USERNAME_REGEX,
    CustomUserCreationForm,
    logger,
)

from .email_verify import (
    _check_email_availability,
    SendEmailCodeView,
    check_username,
    check_email,
)

from .login import (
    CustomLoginView,
    login_api,
)

from .signup import (
    SignUpView,
)

from .two_factor import (
    send_operation_2fa_code,
    enable_2fa,
    verify_2fa_setup,
    disable_2fa,
    regenerate_backup_codes,
    generate_backup_codes_list,
    start_update_totp,
    verify_update_totp,
    verify_2fa_login,
    resend_2fa_email,
)

from .password_reset import (
    _send_email_async_helper,
    send_password_change_notification,
    change_password,
    forgot_password_view,
    password_reset_api,
    reset_password_view,
)

from .rate_limit import (
    get_client_fingerprint,
    get_client_ip,
    check_rate_limit,
)

__all__ = [
    'USERNAME_REGEX', 'CustomUserCreationForm', 'logger',
    '_check_email_availability', 'SendEmailCodeView', 'check_username', 'check_email',
    'CustomLoginView', 'login_api',
    'SignUpView',
    'send_operation_2fa_code', 'enable_2fa', 'verify_2fa_setup', 'disable_2fa',
    'regenerate_backup_codes', 'generate_backup_codes_list',
    'start_update_totp', 'verify_update_totp',
    'verify_2fa_login', 'resend_2fa_email',
    '_send_email_async_helper', 'send_password_change_notification', 'change_password',
    'forgot_password_view', 'password_reset_api', 'reset_password_view',
    'get_client_fingerprint', 'get_client_ip', 'check_rate_limit',
]
