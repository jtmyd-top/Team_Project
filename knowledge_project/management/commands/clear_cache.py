from django.core.management.base import BaseCommand
from django.core.cache import cache


class Command(BaseCommand):
    help = 'Clear all Django cache'

    def handle(self, *args, **options):
        try:
            cache.clear()
            self.stdout.write(self.style.SUCCESS('Successfully cleared all cache.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error clearing cache: {e}'))