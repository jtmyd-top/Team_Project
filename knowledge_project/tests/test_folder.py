"""folder 模块测试

覆盖:
- folder_list_api: 列表 / 创建 / 跨用户隔离
- folder_detail_api: 详情 / 重命名 / 跨用户 404
- move_note_api: 移动 / inbox / 跨用户笔记或文件夹 404
- trash_note_api / restore_note_api: 移入/恢复回收站
- toggle_note_favorite_api: 切换收藏
- restore_folder_api / permanent_delete_folder_api: 仅对回收站项可用
"""

from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from notes.models import Folder, Note

from ._helpers import login, make_user, parse, post_json


@override_settings(SESSION_ENGINE='django.contrib.sessions.backends.db')
class _FolderTestBase(TestCase):
    def setUp(self):
        cache.clear()


# =========================================================================
# folder_list_api
# =========================================================================
class FolderListApiTests(_FolderTestBase):
    def test_list_returns_empty_for_new_user(self):
        user = make_user('fl01')
        login(self.client, user)
        body = parse(self.client.get(reverse('folder_list_api')))
        self.assertEqual(body['folders'], [])
        self.assertEqual(body['inbox_count'], 0)

    def test_list_counts_inbox_notes(self):
        user = make_user('fl02')
        # 3 个 inbox 笔记(folder=None),2 个保密,1 个回收站,1 个文件夹内
        folder = Folder.objects.create(name='F', owner=user)
        Note.objects.create(author=user, title='in1', content='')
        Note.objects.create(author=user, title='in2', content='')
        Note.objects.create(author=user, title='in3', content='')
        Note.objects.create(author=user, title='secret', content='', is_secret=True)  # 不计
        Note.objects.create(author=user, title='trash', content='', is_trashed=True)  # 不计
        Note.objects.create(author=user, title='fnote', content='', folder=folder)    # 不计
        login(self.client, user)
        body = parse(self.client.get(reverse('folder_list_api')))
        self.assertEqual(body['inbox_count'], 3)

    def test_create_folder(self):
        user = make_user('fl03')
        login(self.client, user)
        response = post_json(self.client, reverse('folder_list_api'), {'name': 'NewBox'})
        self.assertEqual(response.status_code, 201)
        body = parse(response)
        self.assertEqual(body['name'], 'NewBox')
        self.assertTrue(Folder.objects.filter(id=body['id'], owner=user).exists())

    def test_create_folder_rejects_empty_name(self):
        user = make_user('fl04')
        login(self.client, user)
        response = post_json(self.client, reverse('folder_list_api'), {'name': '   '})
        self.assertEqual(response.status_code, 400)

    def test_list_excludes_other_users_folders(self):
        user_a = make_user('fl05a')
        user_b = make_user('fl05b')
        Folder.objects.create(name='A', owner=user_a)
        Folder.objects.create(name='B1', owner=user_b)
        Folder.objects.create(name='B2', owner=user_b)
        login(self.client, user_a)
        body = parse(self.client.get(reverse('folder_list_api')))
        names = {f['name'] for f in body['folders']}
        self.assertEqual(names, {'A'})

    def test_create_nested_folder(self):
        user = make_user('fl06')
        parent = Folder.objects.create(name='Parent', owner=user)
        login(self.client, user)
        response = post_json(self.client, reverse('folder_list_api'), {
            'name': 'Child',
            'parent_id': parent.id,
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(parse(response)['parent_id'], parent.id)


# =========================================================================
# folder_detail_api
# =========================================================================
class FolderDetailApiTests(_FolderTestBase):
    def test_get_returns_404_for_other_user_folder(self):
        owner = make_user('fd01')
        intruder = make_user('fd01_intr')
        folder = Folder.objects.create(name='Mine', owner=owner)
        login(self.client, intruder)
        response = self.client.get(reverse('folder_detail_api', args=[folder.id]))
        self.assertEqual(response.status_code, 404)

    def test_rename_folder(self):
        user = make_user('fd02')
        folder = Folder.objects.create(name='Old', owner=user)
        login(self.client, user)
        response = self.client.put(
            reverse('folder_detail_api', args=[folder.id]),
            data='{"name": "Renamed"}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        folder.refresh_from_db()
        self.assertEqual(folder.name, 'Renamed')

    def test_delete_folder_moves_to_trash(self):
        user = make_user('fd03')
        folder = Folder.objects.create(name='ToDelete', owner=user)
        Note.objects.create(author=user, title='n1', content='', folder=folder)
        login(self.client, user)
        response = self.client.delete(reverse('folder_detail_api', args=[folder.id]))
        self.assertEqual(response.status_code, 200)
        folder.refresh_from_db()
        self.assertTrue(folder.is_trashed)
        # 文件夹内笔记同时被移入回收站
        note = Note.objects.get(title='n1')
        self.assertTrue(note.is_trashed)


# =========================================================================
# move_note_api
# =========================================================================
class MoveNoteApiTests(_FolderTestBase):
    def test_move_to_folder(self):
        user = make_user('mv01')
        folder = Folder.objects.create(name='Box', owner=user)
        note = Note.objects.create(author=user, title='roaming', content='')
        login(self.client, user)
        response = post_json(self.client, reverse('move_note_api', args=[note.id]),
                             {'folder_id': folder.id})
        self.assertEqual(response.status_code, 200)
        note.refresh_from_db()
        self.assertEqual(note.folder_id, folder.id)

    def test_move_to_inbox(self):
        user = make_user('mv02')
        folder = Folder.objects.create(name='Box', owner=user)
        note = Note.objects.create(author=user, title='n', content='', folder=folder)
        login(self.client, user)
        response = post_json(self.client, reverse('move_note_api', args=[note.id]),
                             {'folder_id': None})
        self.assertEqual(response.status_code, 200)
        note.refresh_from_db()
        self.assertIsNone(note.folder_id)

    def test_move_rejects_other_users_note(self):
        owner = make_user('mv03_o')
        intruder = make_user('mv03_i')
        folder = Folder.objects.create(name='Box', owner=intruder)
        note = Note.objects.create(author=owner, title='n', content='')
        login(self.client, intruder)
        response = post_json(self.client, reverse('move_note_api', args=[note.id]),
                             {'folder_id': folder.id})
        self.assertEqual(response.status_code, 404)

    def test_move_rejects_other_users_folder(self):
        user_a = make_user('mv04_a')
        user_b = make_user('mv04_b')
        foreign_folder = Folder.objects.create(name='B-box', owner=user_b)
        note = Note.objects.create(author=user_a, title='n', content='')
        login(self.client, user_a)
        response = post_json(self.client, reverse('move_note_api', args=[note.id]),
                             {'folder_id': foreign_folder.id})
        self.assertEqual(response.status_code, 404)
        note.refresh_from_db()
        self.assertIsNone(note.folder_id)


class CopyNoteApiTests(_FolderTestBase):
    def test_copy_to_folder_preserves_content_and_tags(self):
        user = make_user('cp01')
        folder = Folder.objects.create(name='Box', owner=user)
        source = Note.objects.create(
            author=user,
            title='source',
            content='<p>Hello</p>',
            is_public=True,
            views=12,
        )
        source.tags.create(name='copy-tag')
        login(self.client, user)

        response = post_json(self.client, reverse('copy_note_api', args=[source.id]), {
            'folder_id': folder.id,
        })

        self.assertEqual(response.status_code, 201)
        copied = Note.objects.get(id=parse(response)['note_id'])
        source.refresh_from_db()
        self.assertEqual(copied.author, user)
        self.assertEqual(copied.folder_id, folder.id)
        self.assertEqual(copied.title, source.title)
        self.assertEqual(copied.content, source.content)
        self.assertFalse(copied.is_public)
        self.assertEqual(copied.views, 0)
        self.assertEqual(list(copied.tags.values_list('name', flat=True)), ['copy-tag'])
        self.assertIsNone(source.folder_id)
        self.assertTrue(source.is_public)

    def test_copy_to_inbox(self):
        user = make_user('cp02')
        folder = Folder.objects.create(name='Box', owner=user)
        source = Note.objects.create(author=user, title='n', content='', folder=folder)
        login(self.client, user)
        response = post_json(self.client, reverse('copy_note_api', args=[source.id]), {
            'folder_id': None,
        })
        self.assertEqual(response.status_code, 201)
        copied = Note.objects.get(id=parse(response)['note_id'])
        self.assertIsNone(copied.folder_id)
        source.refresh_from_db()
        self.assertEqual(source.folder_id, folder.id)

    def test_copy_rejects_other_users_note(self):
        owner = make_user('cp03_o')
        intruder = make_user('cp03_i')
        source = Note.objects.create(author=owner, title='n', content='')
        login(self.client, intruder)
        response = post_json(self.client, reverse('copy_note_api', args=[source.id]), {
            'folder_id': None,
        })
        self.assertEqual(response.status_code, 404)

    def test_copy_rejects_other_users_folder(self):
        user_a = make_user('cp04_a')
        user_b = make_user('cp04_b')
        foreign_folder = Folder.objects.create(name='B-box', owner=user_b)
        source = Note.objects.create(author=user_a, title='n', content='')
        login(self.client, user_a)
        response = post_json(self.client, reverse('copy_note_api', args=[source.id]), {
            'folder_id': foreign_folder.id,
        })
        self.assertEqual(response.status_code, 404)


# =========================================================================
# trash_note_api / restore_note_api
# =========================================================================
class TrashAndRestoreNoteTests(_FolderTestBase):
    def test_trash_note(self):
        user = make_user('tr01')
        note = Note.objects.create(author=user, title='n', content='')
        login(self.client, user)
        response = post_json(self.client, reverse('trash_note_api', args=[note.id]))
        self.assertEqual(response.status_code, 200)
        note.refresh_from_db()
        self.assertTrue(note.is_trashed)

    def test_restore_note(self):
        user = make_user('tr02')
        note = Note.objects.create(author=user, title='n', content='', is_trashed=True)
        login(self.client, user)
        response = post_json(self.client, reverse('restore_note_api', args=[note.id]))
        self.assertEqual(response.status_code, 200)
        note.refresh_from_db()
        self.assertFalse(note.is_trashed)

    def test_trash_rejects_other_user(self):
        owner = make_user('tr03_o')
        intruder = make_user('tr03_i')
        note = Note.objects.create(author=owner, title='n', content='')
        login(self.client, intruder)
        response = post_json(self.client, reverse('trash_note_api', args=[note.id]))
        self.assertEqual(response.status_code, 404)


# =========================================================================
# toggle_note_favorite_api
# =========================================================================
class ToggleFavoriteTests(_FolderTestBase):
    def test_toggle_marks_favorited(self):
        user = make_user('fv01')
        note = Note.objects.create(author=user, title='n', content='', is_favorited=False)
        login(self.client, user)
        response = post_json(self.client, reverse('toggle_note_favorite_api', args=[note.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(parse(response)['is_favorited'])

    def test_toggle_unmarks_favorited(self):
        user = make_user('fv02')
        note = Note.objects.create(author=user, title='n', content='', is_favorited=True)
        login(self.client, user)
        response = post_json(self.client, reverse('toggle_note_favorite_api', args=[note.id]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(parse(response)['is_favorited'])

    def test_toggle_rejects_other_user(self):
        owner = make_user('fv03_o')
        intruder = make_user('fv03_i')
        note = Note.objects.create(author=owner, title='n', content='')
        login(self.client, intruder)
        response = post_json(self.client, reverse('toggle_note_favorite_api', args=[note.id]))
        self.assertEqual(response.status_code, 404)


# =========================================================================
# restore_folder_api / permanent_delete_folder_api
# =========================================================================
class FolderTrashLifecycleTests(_FolderTestBase):
    def test_restore_trashed_folder(self):
        user = make_user('frc01')
        folder = Folder.objects.create(name='F', owner=user, is_trashed=True)
        Note.objects.create(author=user, title='n', content='', folder=folder, is_trashed=True)
        login(self.client, user)
        response = post_json(self.client, reverse('restore_folder_api', args=[folder.id]))
        self.assertEqual(response.status_code, 200)
        folder.refresh_from_db()
        self.assertFalse(folder.is_trashed)
        note = Note.objects.get(title='n')
        self.assertFalse(note.is_trashed)

    def test_restore_non_trashed_returns_404(self):
        user = make_user('frc02')
        folder = Folder.objects.create(name='F', owner=user, is_trashed=False)
        login(self.client, user)
        response = post_json(self.client, reverse('restore_folder_api', args=[folder.id]))
        self.assertEqual(response.status_code, 404)

    def test_permanent_delete_trashed_folder(self):
        user = make_user('frc03')
        folder = Folder.objects.create(name='F', owner=user, is_trashed=True)
        login(self.client, user)
        response = self.client.delete(reverse('permanent_delete_folder_api', args=[folder.id]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Folder.objects.filter(id=folder.id).exists())

    def test_permanent_delete_non_trashed_returns_404(self):
        user = make_user('frc04')
        folder = Folder.objects.create(name='F', owner=user, is_trashed=False)
        login(self.client, user)
        response = self.client.delete(reverse('permanent_delete_folder_api', args=[folder.id]))
        self.assertEqual(response.status_code, 404)
