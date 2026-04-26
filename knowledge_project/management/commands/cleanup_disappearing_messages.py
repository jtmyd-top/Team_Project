"""定时清理阅后即焚过期消息

使用：
    python manage.py cleanup_disappearing_messages
建议通过 cron / 计划任务每 1~5 分钟执行一次。
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from knowledge_project.models import ConversationSettings, Message


class Command(BaseCommand):
    help = "扫描所有开启了阅后即焚的对话，销毁已读超过 TTL 的消息"

    def handle(self, *args, **options):
        now = timezone.now()
        total = 0
        processed_pairs = set()

        settings_qs = ConversationSettings.objects.filter(
            disappearing_enabled=True
        ).select_related('user', 'peer')

        for cs in settings_qs:
            pair = tuple(sorted([cs.user_id, cs.peer_id]))
            if pair in processed_pairs:
                continue
            processed_pairs.add(pair)

            ttls = [max(cs.disappearing_ttl_seconds or 0, 0)]
            reverse = ConversationSettings.objects.filter(
                user_id=cs.peer_id, peer_id=cs.user_id, disappearing_enabled=True
            ).first()
            if reverse:
                ttls.append(max(reverse.disappearing_ttl_seconds or 0, 0))
            ttl = min(ttls)

            base_qs = Message.objects.filter(
                (Q(sender_id=cs.user_id) & Q(recipient_id=cs.peer_id)) |
                (Q(sender_id=cs.peer_id) & Q(recipient_id=cs.user_id)),
                is_read=True,
                is_recalled=False,
                read_at__isnull=False,
            )
            if ttl > 0:
                base_qs = base_qs.filter(read_at__lt=now - timedelta(seconds=ttl))

            updated = base_qs.update(is_recalled=True, recalled_at=now)
            if updated:
                total += updated
                self.stdout.write(
                    f"{cs.user.username} <-> {cs.peer.username}: 销毁 {updated} 条 (ttl={ttl}s)"
                )

        self.stdout.write(self.style.SUCCESS(f"共销毁 {total} 条过期消息"))
