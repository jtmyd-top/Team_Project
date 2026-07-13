"""Create an application-level database and media snapshot."""
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from django.conf import settings
from django.core.management import BaseCommand, call_command
from django.utils import timezone

from ops.models import BackupRecord


class Command(BaseCommand):
    help = 'Create a portable JSON database snapshot, optionally with uploaded media.'

    def add_arguments(self, parser):
        parser.add_argument('--include-media', action='store_true')
        parser.add_argument('--output-dir', default='')
        parser.add_argument(
            '--retention-days',
            type=int,
            default=30,
            help='Delete successful snapshot archives older than this many days. Use 0 to disable pruning.',
        )

    def _prune_expired_backups(self, output_dir, retention_days):
        if retention_days <= 0:
            return 0

        cutoff = timezone.now() - timedelta(days=retention_days)
        resolved_output_dir = output_dir.resolve()
        expired_records = BackupRecord.objects.filter(
            kind=BackupRecord.KIND_SNAPSHOT,
            status=BackupRecord.STATUS_SUCCEEDED,
            completed_at__lt=cutoff,
        )
        deleted_count = 0
        for expired_record in expired_records.iterator():
            archive_path = Path(expired_record.storage_path)
            try:
                resolved_archive_path = archive_path.resolve()
            except OSError:
                self.stderr.write(
                    self.style.WARNING(
                        f'Skipped invalid backup path in record {expired_record.id}: {archive_path}'
                    )
                )
                continue

            if (
                resolved_archive_path.parent != resolved_output_dir
                or not resolved_archive_path.name.startswith('team-project-backup-')
                or resolved_archive_path.suffix != '.zip'
            ):
                self.stderr.write(
                    self.style.WARNING(
                        f'Skipped backup path outside the configured backup directory: {archive_path}'
                    )
                )
                continue

            try:
                resolved_archive_path.unlink(missing_ok=True)
            except OSError as exc:
                self.stderr.write(
                    self.style.WARNING(f'Could not remove expired backup {archive_path}: {exc}')
                )
                continue

            expired_record.delete()
            deleted_count += 1
        return deleted_count

    def handle(self, *args, **options):
        output_dir = Path(
            options['output_dir']
            or getattr(settings, 'BACKUP_DIR', Path(settings.BASE_DIR) / 'backups')
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        retention_days = max(0, int(options['retention_days']))
        timestamp = timezone.now().strftime('%Y%m%d-%H%M%S')
        archive_path = output_dir / f'team-project-backup-{timestamp}.zip'
        record = BackupRecord.objects.create(
            kind=BackupRecord.KIND_SNAPSHOT,
            status=BackupRecord.STATUS_RUNNING,
            storage_path=str(archive_path),
            metadata={'include_media': bool(options['include_media'])},
        )
        try:
            with TemporaryDirectory(prefix='team-project-backup-') as temp_dir:
                fixture_path = Path(temp_dir) / 'database.json'
                with fixture_path.open('w', encoding='utf-8') as fixture:
                    call_command(
                        'dumpdata',
                        '--natural-foreign',
                        '--natural-primary',
                        '--exclude', 'contenttypes',
                        '--exclude', 'auth.permission',
                        stdout=fixture,
                    )

                file_count = 0
                with ZipFile(archive_path, 'w', ZIP_DEFLATED) as archive:
                    archive.write(fixture_path, 'database.json')
                    if options['include_media']:
                        media_root = Path(settings.MEDIA_ROOT)
                        if media_root.exists():
                            for path in media_root.rglob('*'):
                                if path.is_file():
                                    archive.write(path, Path('media') / path.relative_to(media_root))
                                    file_count += 1

            record.status = BackupRecord.STATUS_SUCCEEDED
            record.completed_at = timezone.now()
            record.size_bytes = archive_path.stat().st_size
            record.metadata = {
                **record.metadata,
                'media_file_count': file_count,
                'restore_command': 'python manage.py loaddata database.json',
            }
            record.save(update_fields=['status', 'completed_at', 'size_bytes', 'metadata'])
            self.stdout.write(self.style.SUCCESS(f'Backup created: {archive_path}'))
            deleted_count = self._prune_expired_backups(output_dir, retention_days)
            if deleted_count:
                self.stdout.write(f'Pruned {deleted_count} expired backup archive(s).')
        except Exception as exc:
            record.status = BackupRecord.STATUS_FAILED
            record.completed_at = timezone.now()
            record.error_message = str(exc)[:4000]
            record.save(update_fields=['status', 'completed_at', 'error_message'])
            raise
