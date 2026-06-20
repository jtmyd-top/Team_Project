"""Compatibility exports for legacy signal helpers."""

from vault.services import on_password_reset, reset_vault_fail_count_for_user

__all__ = ['on_password_reset', 'reset_vault_fail_count_for_user']
