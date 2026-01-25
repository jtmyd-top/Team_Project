"""
Phase 3 Data Migration - Encrypt Existing Secret Notes
Management command to encrypt all existing is_secret=True notes
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from knowledge_project.models import Note, Profile
from knowledge_project.utils.vault_crypto import VaultEncryption
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Encrypt all existing secret notes (is_secret=True)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without actually saving to database',
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='Only encrypt notes for specific user ID',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        user_id = options.get('user_id')

        self.stdout.write(self.style.SUCCESS('Starting Phase 3 Data Migration...'))

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be saved'))

        # Get all secret notes
        query = Note.objects.filter(is_secret=True, is_trashed=False)
        if user_id:
            query = query.filter(author_id=user_id)

        total_notes = query.count()
        self.stdout.write(f'Found {total_notes} secret notes to encrypt')

        if total_notes == 0:
            self.stdout.write(self.style.WARNING('No notes to encrypt'))
            return

        encrypted_count = 0
        skipped_count = 0
        error_count = 0

        with transaction.atomic():
            for idx, note in enumerate(query, 1):
                try:
                    self.stdout.write(f'[{idx}/{total_notes}] Processing: {note.title[:50]}... ', ending='')

                    # Check if note is already encrypted
                    # Encrypted content is Base64 and doesn't contain common HTML tags
                    if '<' not in note.content and '>' not in note.content:
                        self.stdout.write(self.style.WARNING('ALREADY ENCRYPTED'))
                        skipped_count += 1
                        continue

                    # Get user's vault (DEK)
                    try:
                        profile = note.author.profile
                        if not profile.vault_initialized:
                            self.stdout.write(self.style.ERROR('VAULT NOT INITIALIZED'))
                            error_count += 1
                            continue

                        # Decrypt user's DEK
                        dek = VaultEncryption.decrypt_dek(
                            profile.encrypted_vault_key,
                            profile.vault_key_iv
                        )
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'VAULT DECRYPT FAILED: {e}'))
                        error_count += 1
                        continue

                    # Encrypt note content
                    try:
                        encrypted_content = VaultEncryption.encrypt_data(note.content, dek)
                        encrypted_title = VaultEncryption.encrypt_data(note.title, dek)

                        if not dry_run:
                            note.content = encrypted_content
                            note.title = encrypted_title
                            note.save(update_fields=['content', 'title'])

                        self.stdout.write(self.style.SUCCESS('ENCRYPTED'))
                        encrypted_count += 1

                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'ENCRYPTION FAILED: {e}'))
                        error_count += 1

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'ERROR: {e}'))
                    error_count += 1

        # Summary
        self.stdout.write('\n' + '='*70)
        self.stdout.write(self.style.SUCCESS('Migration Summary:'))
        self.stdout.write(f'  Total processed: {total_notes}')
        self.stdout.write(self.style.SUCCESS(f'  Encrypted: {encrypted_count}'))
        self.stdout.write(f'  Skipped (already encrypted): {skipped_count}')
        self.stdout.write(self.style.ERROR(f'  Errors: {error_count}'))

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes were saved'))
        else:
            self.stdout.write(self.style.SUCCESS('Migration completed successfully!'))

        self.stdout.write('='*70)
