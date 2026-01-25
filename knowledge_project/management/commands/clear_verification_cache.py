from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.db import connection


class Command(BaseCommand):
    help = '清理验证码相关的缓存数据'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            choices=['all', 'hourly', 'daily', 'login'],
            default='all',
            help='指定要清理的缓存类型'
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='仅清理特定用户的验证码缓存'
        )

    def handle(self, *args, **options):
        cache_type = options['type']
        user_id = options.get('user_id')

        self.stdout.write(f"开始清理验证码缓存 (类型: {cache_type})...")

        try:
            if cache_type in ['all', 'hourly']:
                self.clear_hourly_limits(user_id)
            if cache_type in ['all', 'daily']:
                self.clear_daily_limits(user_id)
            if cache_type in ['all', 'login']:
                self.clear_login_codes(user_id)

            self.stdout.write(
                self.style.SUCCESS('验证码缓存清理完成')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'清理缓存时出错: {e}')
            )

    def clear_hourly_limits(self, user_id=None):
        """清理小时限制缓存"""
        self.stdout.write("正在清理小时限制缓存...")

        # 使用Redis的keys命令（如果使用Redis作为cache backend）
        try:
            if hasattr(cache, 'client'):
                # Redis backend
                pattern = "email_attempts_hourly_*"
                if user_id:
                    pattern += f"*user_{user_id}*"

                keys = cache.client.keys(pattern)
                if keys:
                    cache.client.delete(*keys)
                    self.stdout.write(f"  删除了 {len(keys)} 个小时限制缓存项")
        except:
            # 对于其他backend，无法批量删除
            self.stdout.write("  警告: 当前缓存后端不支持批量删除")

    def clear_daily_limits(self, user_id=None):
        """清理天限制缓存"""
        self.stdout.write("正在清理天限制缓存...")

        try:
            if hasattr(cache, 'client'):
                # Redis backend
                patterns = [
                    "email_attempts_daily_*",
                    "email_code_daily_*"
                ]

                for pattern in patterns:
                    if user_id:
                        pattern += f"*user_{user_id}*"

                    keys = cache.client.keys(pattern)
                    if keys:
                        cache.client.delete(*keys)
                        self.stdout.write(f"  删除了 {len(keys)} 个天限制缓存项")
        except:
            self.stdout.write("  警告: 当前缓存后端不支持批量删除")

    def clear_login_codes(self, user_id=None):
        """清理登录验证码session"""
        self.stdout.write("正在清理登录验证码...")

        # 这个需要根据session backend的实现来清理
        # 由于session通常存储在不同的后端，这里提供通用建议
        self.stdout.write("  提示: 请清理Django session表或重启应用服务器来清理session数据")