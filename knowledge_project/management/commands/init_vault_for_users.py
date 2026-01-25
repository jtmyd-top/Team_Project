"""
Management command to initialize vault for all existing users
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from knowledge_project.models import Profile, User
from knowledge_project.utils.vault_crypto import VaultEncryption
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Initialize vault for all existing users who have not yet initialized it'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without actually saving to database',
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='Only initialize vault for specific user ID',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force re-initialize vault even if already initialized',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        user_id = options.get('user_id')
        force = options.get('force', False)

        self.stdout.write(self.style.SUCCESS('Starting Vault Initialization for Existing Users...'))

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be saved'))

        # 获取需要初始化的用户
        if force:
            # 强制重新初始化所有用户
            query = User.objects.filter(is_active=True)
            filter_text = 'all users'
        else:
            # 只初始化未初始化的用户
            query = User.objects.filter(
                is_active=True,
                profile__vault_initialized=False
            )
            filter_text = 'users with uninitialized vault'

        if user_id:
            query = query.filter(id=user_id)
            filter_text = f'user {user_id}'

        total_users = query.count()
        self.stdout.write(f'Found {total_users} {filter_text}')

        if total_users == 0:
            self.stdout.write(self.style.WARNING('No users to initialize'))
            return

        initialized_count = 0
        error_count = 0

        with transaction.atomic():
            for idx, user in enumerate(query, 1):
                try:
                    self.stdout.write(
                        f'[{idx}/{total_users}] Initializing vault for user: {user.username}... ',
                        ending=''
                    )

                    profile = user.profile

                    # 生成随机 DEK
                    dek = VaultEncryption.generate_dek()

                    # 用 KEK 加密 DEK
                    encrypted_dek_b64, iv_b64 = VaultEncryption.encrypt_dek(dek)

                    # 保存到数据库（如果不是 dry run）
                    if not dry_run:
                        profile.encrypted_vault_key = encrypted_dek_b64
                        profile.vault_key_iv = iv_b64
                        profile.vault_initialized = True
                        profile.save(update_fields=[
                            'encrypted_vault_key',
                            'vault_key_iv',
                            'vault_initialized'
                        ])

                    self.stdout.write(self.style.SUCCESS('[OK]'))
                    initialized_count += 1

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'[FAILED] {e}'))
                    logger.error(f"Failed to initialize vault for user {user.username}: {e}")
                    error_count += 1

        # 显示总结
        self.stdout.write('\n' + '='*70)
        self.stdout.write(self.style.SUCCESS('Vault Initialization Summary:'))
        self.stdout.write(f'  Total processed: {total_users}')
        self.stdout.write(self.style.SUCCESS(f'  Initialized: {initialized_count}'))
        self.stdout.write(self.style.ERROR(f'  Errors: {error_count}'))

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes were saved'))
        else:
            self.stdout.write(self.style.SUCCESS('Initialization completed successfully!'))

        self.stdout.write('='*70)
