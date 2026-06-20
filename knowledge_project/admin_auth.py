"""Compatibility exports for the migrated admin auth module."""

from ops.admin_auth import SecureAdminSite, secure_admin_site

__all__ = ['SecureAdminSite', 'secure_admin_site']
