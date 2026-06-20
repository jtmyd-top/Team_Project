"""Folder view shared helpers."""
import json
from django.db import models
from django.db.models import Count, Q, Exists, OuterRef
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from notes.models import Folder, Note
from core.utils.misc import get_sidebar_cache_key, log_action
# 【新增】導入安全檢查函數
from notes.views.note import check_note_secret_operation_permission



def build_folder_tree(folders, parent_id=None):
    """递归构建文件夹树（使用预加载的 notes_count）"""
    tree = []
    for folder in folders:
        if folder.parent_id == parent_id:
            children = build_folder_tree(folders, folder.id)
            tree.append({
                'id': folder.id,
                'name': folder.name,
                'parent_id': folder.parent_id,
                'order': folder.order,
                'children': children,
                # 使用预加载的 annotated 字段，避免 N+1 查询
                'notes_count': getattr(folder, 'notes_count', 0)
            })
    return tree

