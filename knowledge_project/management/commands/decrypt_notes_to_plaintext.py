"""
Decrypt Secret Notes Back to Plaintext
Management command to decrypt all is_secret=True notes back to plaintext format
so they can be re-encrypted with the new frontend E2E method
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from knowledge_project.models import Note, Profile
from knowledge_project.utils.vault_crypto import VaultEncryption
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Decrypt all secret notes back to plaintext for re-encryption with new frontend E2E method'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without actually saving to database',
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='Only decrypt notes for specific user ID',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        user_id = options.get('user_id')

        self.stdout.write(self.style.SUCCESS('Starting Decryption to Plaintext...'))

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be saved'))

        # Get all secret notes
        query = Note.objects.filter(is_secret=True, is_trashed=False)
        if user_id:
            query = query.filter(author_id=user_id)

        total_notes = query.count()
        self.stdout.write(f'Found {total_notes} secret notes to decrypt')

        if total_notes == 0:
            self.stdout.write(self.style.WARNING('No notes to decrypt'))
            return

        decrypted_count = 0
        already_plaintext_count = 0
        error_count = 0

        with transaction.atomic():
            for idx, note in enumerate(query, 1):
                try:
                    self.stdout.write(f'[{idx}/{total_notes}] Processing: {note.title[:50]}... ', ending='')

                    # Check if note is already plaintext
                    # Plaintext should contain common HTML tags
                    if '<' in note.content and '>' in note.content:
                        self.stdout.write(self.style.WARNING('ALREADY PLAINTEXT'))
                        already_plaintext_count += 1
                        continue

                    # Get user's vault (DEK)
                    try:
                        profile = note.author.profile
                        if not profile.vault_initialized:
                            self.stdout.write(self.style.ERROR('VAULT NOT INITIALIZED'))
                            error_count += 1
                            continue

                        # Decrypt user's DEK using KEK
                        dek = VaultEncryption.decrypt_dek(
                            profile.encrypted_vault_key,
                            profile.vault_key_iv
                        )
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'VAULT DECRYPT FAILED: {e}'))
                        error_count += 1
                        continue

                    # Decrypt note content and title
                    try:
                        plaintext_content = VaultEncryption.decrypt_data(note.content, dek)
                        plaintext_title = VaultEncryption.decrypt_data(note.title, dek)

                        if not dry_run:
                            note.content = plaintext_content
                            note.title = plaintext_title
                            # Keep is_secret=true, but content is now plaintext
                            # User will re-encrypt with frontend E2E when they save
                            note.save(update_fields=['content', 'title'])

                        self.stdout.write(self.style.SUCCESS('DECRYPTED'))
                        decrypted_count += 1

                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'DECRYPTION FAILED: {e}'))
                        error_count += 1

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'ERROR: {e}'))
                    error_count += 1

        # Summary
        self.stdout.write('\n' + '='*70)
        self.stdout.write(self.style.SUCCESS('Decryption Summary:'))
        self.stdout.write(f'  Total processed: {total_notes}')
        self.stdout.write(self.style.SUCCESS(f'  Decrypted: {decrypted_count}'))
        self.stdout.write(f'  Already plaintext: {already_plaintext_count}')
        self.stdout.write(self.style.ERROR(f'  Errors: {error_count}'))

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes were saved'))
        else:
            self.stdout.write(self.style.SUCCESS('Decryption completed successfully!'))
            self.stdout.write(self.style.WARNING('\nNext steps:'))
            self.stdout.write('  1. Clear browser cache and hard-refresh (Ctrl+F5)')
            self.stdout.write('  2. Complete 2FA verification to unlock vault')
            self.stdout.write('  3. Open each decrypted note and save it again')
            self.stdout.write('  4. Content will be automatically re-encrypted with new E2E format')

        self.stdout.write('='*70)
