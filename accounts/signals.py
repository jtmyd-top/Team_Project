import logging
import secrets
import string

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.avatar import fetch_avatar_async
from accounts.models import Profile


logger = logging.getLogger(__name__)


def _assign_search_code(profile):
    if profile.search_code:
        return False

    alphabet = string.ascii_uppercase + string.digits
    for _ in range(5):
        code = ''.join(secrets.choice(alphabet) for _ in range(8))
        if not Profile.objects.filter(search_code=code).exists():
            profile.search_code = code
            return True
    return False


def _initialize_vault(profile, username):
    try:
        from vault.crypto import VaultEncryption

        dek = VaultEncryption.generate_dek()
        encrypted_dek_b64, iv_b64 = VaultEncryption.encrypt_dek(dek)

        profile.encrypted_vault_key = encrypted_dek_b64
        profile.vault_key_iv = iv_b64
        profile.vault_initialized = True
        profile.save(update_fields=['encrypted_vault_key', 'vault_key_iv', 'vault_initialized'])

        logger.info("[Vault] Auto-initialized vault for new user: %s", username)
    except Exception as exc:
        logger.error("[Vault] Failed to auto-initialize vault for user %s: %s", username, exc)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if not created:
        return

    profile = Profile.objects.create(user=instance)
    transaction.on_commit(lambda: fetch_avatar_async(instance.id))

    try:
        updated = _assign_search_code(profile)
        if updated:
            profile.save(update_fields=['search_code'])
    except Exception as exc:
        logger.error("[Profile] Failed to generate search_code: %s", exc)

    _initialize_vault(profile, instance.username)
