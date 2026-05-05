from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from knowledge_project.models import Message


class Command(BaseCommand):
    help = '物理清理已满足条件且超过延迟窗口的私信与附件。曾被举报的消息/附件不会被清理。'

    def handle(self, *args, **options):
        now = timezone.now()
        queryset = (
            Message.objects.filter(
                pending_purge_at__isnull=False,
                pending_purge_at__lte=now,
                purged_at__isnull=True,
                deleted_for_sender=True,
                deleted_for_recipient=True,
                is_recalled=False,
                was_reported=False,
            )
            .prefetch_related('attachments__reports', 'reports')
            .order_by('pending_purge_at')
        )

        purged_count = 0
        skipped_count = 0

        for message in queryset.iterator():
            if message.reports.exists():
                skipped_count += 1
                continue

            attachments = list(message.attachments.all())
            if any(attachment.was_reported or attachment.reports.exists() for attachment in attachments):
                skipped_count += 1
                continue

            with transaction.atomic():
                for attachment in attachments:
                    if attachment.file:
                        attachment.file.delete(save=False)
                    attachment.delete()

                message.purged_at = now
                message.save(update_fields=['purged_at'])
                message.delete()
                purged_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'私信清理完成：purged={purged_count}, skipped={skipped_count}'
            )
        )
