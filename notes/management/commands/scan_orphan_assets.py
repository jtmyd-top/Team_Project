from django.core.management.base import BaseCommand

from notes.models import Asset


class Command(BaseCommand):
    help = 'List detached note assets; use --delete --yes for an explicit global cleanup.'

    def add_arguments(self, parser):
        parser.add_argument('--delete', action='store_true', help='Delete assets with no note references.')
        parser.add_argument('--yes', action='store_true', help='Confirm destructive deletion.')

    def handle(self, *args, **options):
        assets = Asset.objects.exclude(file='').filter(note_links__isnull=True).order_by('id')
        count = assets.count()
        total_bytes = 0
        for asset in assets.iterator():
            try:
                total_bytes += int(asset.file.size or 0)
            except (OSError, ValueError):
                pass
        self.stdout.write(f'Found {count} detached note assets ({total_bytes} bytes).')

        if not options['delete']:
            return
        if not options['yes']:
            self.stderr.write('Refusing deletion without --yes.')
            return

        deleted = 0
        for asset in assets.iterator():
            if asset.file:
                asset.file.delete(save=False)
            asset.delete()
            deleted += 1
        self.stdout.write(self.style.SUCCESS(f'Deleted {deleted} detached note assets.'))
