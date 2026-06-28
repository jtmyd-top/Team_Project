from __future__ import annotations

from dataclasses import dataclass
import inspect
from typing import Iterable

from django.core.management.base import BaseCommand
from django.urls import URLPattern, URLResolver, get_resolver


PUBLIC_NAME_PREFIXES = (
    'api_2fa',
    'api_captcha',
)

PUBLIC_NAMES = {
    'blocked_message_attachment_media_api',
    'captcha_generate',
    'captcha_init',
    'check_email',
    'check_username',
    'follow_status_api',
    'forgot_password',
    'get_user_public_profile_api',
    'healthz',
    'home_stats_api',
    'home',
    'login',
    'login_api',
    'note_comments_api',
    'password_reset_api',
    'public_profile_media_view',
    'public_note_view',
    'public_notes_api',
    'readyz',
    'resend_2fa_email',
    'reset_password',
    'resolve_qqmusic_share_api',
    'send_email_code',
    'search_users_api',
    'signup',
    'turnstile_config',
    'user_public_profile',
    'verify_2fa_login',
}

PUBLIC_PATH_PREFIXES = (
    'api/captcha/',
    'api/turnstile/',
    'api/ubb/',
    'check-email/',
    'check-username/',
    'forgot-password/',
    'healthz',
    'login/',
    'password-reset/',
    'readyz',
    'reset-password/',
    'signup/',
)

PROJECT_SOURCE_DIRS = {
    'accounts',
    'assets',
    'message_groups',
    'messaging',
    'moderation',
    'notes',
    'notifications',
    'ops',
    'Team_Project',
    'vault',
    'knowledge_project',
}


@dataclass(frozen=True)
class RouteFinding:
    name: str
    pattern: str
    view: str
    reason: str


class Command(BaseCommand):
    help = 'Audit URL patterns that look protected but are not wrapped by login_required.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fail',
            action='store_true',
            help='Exit with a non-zero status when findings are detected.',
        )

    def handle(self, *args, **options):
        findings = list(audit_login_required())
        if not findings:
            self.stdout.write(self.style.SUCCESS('No unprotected protected-looking routes found.'))
            return

        self.stdout.write(self.style.WARNING(f'Found {len(findings)} route(s) to review:'))
        for finding in findings:
            self.stdout.write(
                f'- {finding.pattern} name={finding.name} view={finding.view} reason={finding.reason}'
            )

        if options['fail']:
            raise SystemExit(1)


def audit_login_required() -> Iterable[RouteFinding]:
    for pattern in iter_urlpatterns(get_resolver().url_patterns):
        route = getattr(pattern, '_audit_route', str(pattern.pattern))
        name = pattern.name or ''
        callback = pattern.callback
        view_name = get_view_name(callback)

        if is_ignored_route(name, route, view_name):
            continue
        if is_public_route(name, route):
            continue
        if has_login_required(callback):
            continue
        if not looks_protected(name, route):
            continue

        yield RouteFinding(
            name=name or '<unnamed>',
            pattern=route,
            view=view_name,
            reason='api/settings/messages/dashboard/upload route without login_required marker',
        )


def iter_urlpatterns(patterns, prefix='') -> Iterable[URLPattern]:
    for pattern in patterns:
        current = f'{prefix}{pattern.pattern}'
        if isinstance(pattern, URLResolver):
            yield from iter_urlpatterns(pattern.url_patterns, current)
        elif isinstance(pattern, URLPattern):
            pattern._audit_route = current
            yield pattern


def is_ignored_route(name: str, route: str, view_name: str) -> bool:
    if route.startswith('admin/'):
        return True
    if view_name.startswith(('django.contrib.admin.', 'django_ckeditor_5.')):
        return True
    return False


def is_public_route(name: str, route: str) -> bool:
    if name in PUBLIC_NAMES:
        return True
    if any(name.startswith(prefix) for prefix in PUBLIC_NAME_PREFIXES):
        return True
    return any(route.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES)


def looks_protected(name: str, route: str) -> bool:
    if route.startswith(('api/', 'messages/', 'settings/', 'dashboard/', 'upload-avatar/', 'update-')):
        return True
    protected_tokens = (
        'ban',
        'block',
        'conversation',
        'dashboard',
        'delete',
        'email',
        'export',
        'favorite',
        'follow',
        'message',
        'note',
        'preference',
        'profile',
        'report',
        'security',
        'settings',
        'upload',
        'vault',
    )
    return any(token in name for token in protected_tokens)


def has_login_required(callback) -> bool:
    if getattr(callback, 'login_url', None) is not None:
        return True

    view_class = getattr(callback, 'view_class', None)
    if view_class is not None:
        dispatch = getattr(view_class, 'dispatch', None)
        if getattr(dispatch, 'login_url', None) is not None:
            return True
        if any(base.__name__ == 'LoginRequiredMixin' for base in view_class.mro()):
            return True

    wrapped = getattr(callback, '__wrapped__', None)
    while wrapped is not None:
        if getattr(wrapped, 'login_url', None) is not None:
            return True
        wrapped = getattr(wrapped, '__wrapped__', None)

    if source_has_login_required(callback):
        return True

    return False


def source_has_login_required(callback) -> bool:
    target = unwrap_to_original(callback)
    try:
        source_lines, start_line = inspect.getsourcelines(target)
        source_file = inspect.getsourcefile(target)
    except (OSError, TypeError):
        return False

    if not source_file:
        return False
    normalized_source = source_file.replace('\\', '/')
    if not any(f'/{dirname}/' in normalized_source for dirname in PROJECT_SOURCE_DIRS):
        return False

    decorator_lines = []
    for line in source_lines:
        stripped = line.strip()
        if stripped.startswith('@'):
            decorator_lines.append(stripped)
            continue
        if stripped.startswith('def ') or stripped.startswith('async def '):
            break
        if stripped:
            decorator_lines.clear()
    return any(line.startswith('@login_required') for line in decorator_lines)


def unwrap_to_original(callback):
    current = callback
    seen = set()
    while getattr(current, '__wrapped__', None) is not None and id(current) not in seen:
        seen.add(id(current))
        current = current.__wrapped__
    return current


def get_view_name(callback) -> str:
    view_class = getattr(callback, 'view_class', None)
    if view_class is not None:
        return f'{view_class.__module__}.{view_class.__name__}'
    module = getattr(callback, '__module__', '<unknown>')
    name = getattr(callback, '__name__', repr(callback))
    return f'{module}.{name}'
