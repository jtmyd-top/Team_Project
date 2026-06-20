"""Compatibility model exports for the asset domain.

The database models still live in ``notes.models`` for now. This gives new
asset code a domain-specific import path without changing app_label, content
types, permissions, or database tables.
"""
from notes.models import (
    Asset,
    NoteAsset,
    extract_protected_upload_paths,
    sync_note_asset_links,
    user_directory_path,
)

__all__ = [
    'Asset',
    'NoteAsset',
    'extract_protected_upload_paths',
    'sync_note_asset_links',
    'user_directory_path',
]
