"""Compatibility exports for migrated note TOC helpers."""

from notes.toc import build_nested_toc, extract_toc_from_html, inject_heading_ids

__all__ = [
    'build_nested_toc',
    'extract_toc_from_html',
    'inject_heading_ids',
]
