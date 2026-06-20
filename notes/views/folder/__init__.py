"""Folder view exports split by responsibility."""
from .common import build_folder_tree
from .favorite import favorited_notes_api, toggle_note_favorite_api
from .listing import (
    all_notes_flat_api,
    folder_breadcrumb_api,
    folder_detail_api,
    folder_list_api,
    folder_notes_api,
    inbox_notes_api,
)
from .move import copy_note_api, move_note_api
from .trash import (
    permanent_delete_folder_api,
    permanent_delete_note_api,
    restore_folder_api,
    restore_note_api,
    trash_note_api,
    trashed_folder_contents_api,
    trashed_items_api,
    trashed_notes_api,
)

__all__ = [
    'build_folder_tree',
    'folder_list_api',
    'folder_detail_api',
    'folder_notes_api',
    'inbox_notes_api',
    'folder_breadcrumb_api',
    'all_notes_flat_api',
    'move_note_api',
    'copy_note_api',
    'favorited_notes_api',
    'toggle_note_favorite_api',
    'trashed_items_api',
    'trashed_folder_contents_api',
    'restore_folder_api',
    'permanent_delete_folder_api',
    'trashed_notes_api',
    'trash_note_api',
    'restore_note_api',
    'permanent_delete_note_api',
]
