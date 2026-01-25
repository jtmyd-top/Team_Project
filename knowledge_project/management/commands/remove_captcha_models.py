from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = 'Remove captcha-related database tables (CaptchaSession)'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            # 删除 CaptchaSession 表
            try:
                cursor.execute("DROP TABLE IF EXISTS knowledge_project_captchasession CASCADE;")
                self.stdout.write(
                    self.style.SUCCESS('Successfully dropped CaptchaSession table')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error dropping CaptchaSession table: {e}')
                )