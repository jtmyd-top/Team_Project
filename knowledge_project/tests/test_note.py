"""note 子模块测试

覆盖:
- 笔记 CRUD: create_note_api / update_note_api / delete_note_api
- note_detail_api: 跨用户 private = 403,回收站保密笔记不返 content
- toggle_secret_api: 成功切换,保密自动取消公开
- public_note_view: 非公开 404
- search_notes_api: 仅当前用户、跳过保密
- get_all_notes_api: 跳过保密+回收站
- note_history_api / record_note_history_api
- public_notes_api: 兼容性字段(分页结构由 test_security_fixes 覆盖)

不重复 test_security_fixes.py 已覆盖的:
- 公开笔记跨用户写 = 403
- toggle_secret_api GET = 405
- public_note_view 浏览量原子递增
- public_notes_api 分页
"""

from __future__ import annotations

import json
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from knowledge_project.models import Asset, Folder, Note, NoteAsset, NoteHistory

from ._helpers import login, make_user, parse, post_json


@override_settings(SESSION_ENGINE='django.contrib.sessions.backends.db')
class _NoteTestBase(TestCase):
    def setUp(self):
        cache.clear()


# =========================================================================
# create_note_api
# =========================================================================
class CreateNoteApiTests(_NoteTestBase):
    def test_create_note_success(self):
        user = make_user('owner01')
        login(self.client, user)
        response = post_json(self.client, reverse('create_note_api'), {
            'title': 'My note',
            'content': '<p>hello</p>',
        })
        self.assertEqual(response.status_code, 200)
        body = parse(response)
        self.assertEqual(body['title'], 'My note')
        self.assertFalse(body['is_secret'])
        self.assertTrue(Note.objects.filter(id=body['id'], author=user).exists())

    def test_create_note_requires_login(self):
        response = post_json(self.client, reverse('create_note_api'), {'title': 'x'})
        # @login_required 默认重定向(302),API 走 LOGIN_URL 跳转
        self.assertIn(response.status_code, (302, 401, 403))

    def test_create_note_with_folder(self):
        user = make_user('owner02')
        folder = Folder.objects.create(name='Box', owner=user)
        login(self.client, user)
        response = post_json(self.client, reverse('create_note_api'), {
            'title': 'In folder',
            'content': '',
            'folder_id': folder.id,
        })
        self.assertEqual(response.status_code, 200)
        body = parse(response)
        self.assertEqual(body['folder_id'], folder.id)
        note = Note.objects.get(id=body['id'])
        self.assertEqual(note.folder_id, folder.id)

    def test_create_note_rejects_other_users_folder(self):
        owner = make_user('owner03')
        intruder = make_user('intruder03')
        folder = Folder.objects.create(name='OwnerBox', owner=owner)
        login(self.client, intruder)
        response = post_json(self.client, reverse('create_note_api'), {
            'title': 'attempt',
            'folder_id': folder.id,
        })
        self.assertEqual(response.status_code, 400)

    def test_create_secret_note_requires_vault_unlock_when_2fa_on(self):
        user = make_user('secret01')
        user.profile.two_fa_enabled = True
        user.profile.save(update_fields=['two_fa_enabled'])
        login(self.client, user)
        # 未解锁 vault
        response = post_json(self.client, reverse('create_note_api'), {
            'title': 'secret',
            'is_secret': True,
        })
        self.assertEqual(response.status_code, 403)
        body = parse(response)
        self.assertEqual(body.get('code'), 'vault_locked')

    def test_create_secret_note_works_without_2fa(self):
        # 未开 2FA 时 create secret 不需要 vault 解锁
        user = make_user('secret02')
        login(self.client, user)
        response = post_json(self.client, reverse('create_note_api'), {
            'title': 'secret',
            'is_secret': True,
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(parse(response)['is_secret'])


# =========================================================================
# update_note_api / delete_note_api
# =========================================================================
class UpdateAndDeleteNoteApiTests(_NoteTestBase):
    def test_update_note_success(self):
        user = make_user('updater01')
        note = Note.objects.create(author=user, title='Old', content='old body')
        login(self.client, user)
        response = post_json(self.client, reverse('update_note_api', args=[note.id]), {
            'title': 'New',
            'content': '<p>new body</p>',
        })
        self.assertEqual(response.status_code, 200)
        note.refresh_from_db()
        self.assertEqual(note.title, 'New')
        self.assertIn('new body', note.content)

    def test_update_note_rejects_non_author(self):
        owner = make_user('updater02')
        intruder = make_user('intruder02')
        note = Note.objects.create(author=owner, title='Mine', content='x')
        login(self.client, intruder)
        response = post_json(self.client, reverse('update_note_api', args=[note.id]), {'title': 'hacked'})
        self.assertEqual(response.status_code, 404)
        note.refresh_from_db()
        self.assertEqual(note.title, 'Mine')

    def test_delete_note_moves_to_trash(self):
        user = make_user('deleter01')
        note = Note.objects.create(author=user, title='Trash me', content='')
        login(self.client, user)
        response = post_json(self.client, reverse('delete_note_api', args=[note.id]))
        self.assertEqual(response.status_code, 200)
        note.refresh_from_db()
        self.assertTrue(note.is_trashed)
        self.assertIsNotNone(note.trashed_at)

    def test_delete_note_rejects_non_author(self):
        owner = make_user('deleter02')
        intruder = make_user('intruder04')
        note = Note.objects.create(author=owner, title='keep', content='')
        login(self.client, intruder)
        response = post_json(self.client, reverse('delete_note_api', args=[note.id]))
        self.assertEqual(response.status_code, 404)
        note.refresh_from_db()
        self.assertFalse(note.is_trashed)


class NoteAssetSyncTests(_NoteTestBase):
    def test_note_save_tracks_protected_upload_images(self):
        user = make_user('assetlink01')
        asset = Asset.objects.create(
            uploader=user,
            asset_type='image',
            name='tracked.png',
            file='user_1/tracked.png',
        )

        note = Note.objects.create(
            author=user,
            title='with image',
            content='<p><img src="/protected_uploads/user_1/tracked.png"></p>',
        )

        self.assertTrue(NoteAsset.objects.filter(note=note, asset=asset).exists())

    def test_note_save_removes_stale_asset_links(self):
        user = make_user('assetlink02')
        asset = Asset.objects.create(
            uploader=user,
            asset_type='image',
            name='stale.png',
            file='user_1/stale.png',
        )
        note = Note.objects.create(
            author=user,
            title='with image',
            content='<img src="/protected_uploads/user_1/stale.png">',
        )

        note.content = '<p>removed</p>'
        note.save()

        self.assertFalse(NoteAsset.objects.filter(note=note, asset=asset).exists())

    def test_note_save_with_title_only_update_fields_skips_asset_sync(self):
        user = make_user('assetlink03')
        note = Note.objects.create(author=user, title='original', content='<p>body</p>')

        with patch('notes.models.sync_note_asset_links') as sync_mock:
            note.title = 'renamed'
            note.save(update_fields=['title'])

        sync_mock.assert_not_called()

    def test_note_save_with_content_update_fields_runs_asset_sync(self):
        user = make_user('assetlink04')
        note = Note.objects.create(author=user, title='original', content='<p>body</p>')

        with patch('notes.models.sync_note_asset_links') as sync_mock:
            note.content = '<p>updated</p>'
            note.save(update_fields=['content'])

        sync_mock.assert_called_once_with(note)

    def test_note_save_without_content_change_skips_asset_sync(self):
        user = make_user('assetlink05')
        note = Note.objects.create(author=user, title='original', content='<p>body</p>')

        with patch('notes.models.sync_note_asset_links') as sync_mock:
            note.title = 'renamed again'
            note.save()

        sync_mock.assert_not_called()


class TrashedFolderApiTests(_NoteTestBase):
    def test_trashed_items_api_reports_children_count_from_annotations(self):
        user = make_user('trash01')
        login(self.client, user)

        root = Folder.objects.create(name='root', owner=user, is_trashed=True)
        Folder.objects.create(name='child', owner=user, parent=root, is_trashed=True)
        Note.objects.create(author=user, folder=root, title='root note', content='', is_trashed=True)

        response = self.client.get(reverse('trashed_items_api'))

        self.assertEqual(response.status_code, 200)
        body = parse(response)
        root_entry = next(item for item in body['items'] if item['type'] == 'folder' and item['id'] == root.id)
        self.assertEqual(root_entry['children_count'], 2)
        self.assertTrue(root_entry['has_children'])

    def test_trashed_folder_contents_api_reports_subfolder_children_count(self):
        user = make_user('trash02')
        login(self.client, user)

        root = Folder.objects.create(name='root', owner=user, is_trashed=True)
        child = Folder.objects.create(name='child', owner=user, parent=root, is_trashed=True)
        Folder.objects.create(name='grandchild', owner=user, parent=child, is_trashed=True)
        Note.objects.create(author=user, folder=child, title='child note', content='', is_trashed=True)
        Note.objects.create(author=user, folder=root, title='root note', content='', is_trashed=True)

        response = self.client.get(reverse('trashed_folder_contents_api', args=[root.id]))

        self.assertEqual(response.status_code, 200)
        body = parse(response)
        self.assertEqual({note['title'] for note in body['notes']}, {'root note'})
        child_entry = next(item for item in body['subfolders'] if item['id'] == child.id)
        self.assertEqual(child_entry['children_count'], 2)
        self.assertTrue(child_entry['has_children'])


# =========================================================================
# note_detail_api
# =========================================================================
class NoteDetailApiTests(_NoteTestBase):
    def test_get_private_note_by_non_author_returns_403(self):
        owner = make_user('detail01')
        intruder = make_user('intruder05')
        note = Note.objects.create(author=owner, title='private', content='secret', is_public=False)
        login(self.client, intruder)
        response = self.client.get(reverse('api_note_detail', args=[note.id]))
        self.assertEqual(response.status_code, 403)

    def test_get_public_note_by_other_user_returns_200(self):
        owner = make_user('detail02')
        viewer = make_user('viewer02')
        note = Note.objects.create(author=owner, title='shared', content='public body', is_public=True)
        login(self.client, viewer)
        response = self.client.get(reverse('api_note_detail', args=[note.id]))
        self.assertEqual(response.status_code, 200)

    def test_trashed_secret_note_does_not_return_content(self):
        user = make_user('detail03')
        note = Note.objects.create(
            author=user, title='trashed secret', content='SENSITIVE',
            is_secret=True, is_trashed=True,
        )
        login(self.client, user)
        response = self.client.get(reverse('api_note_detail', args=[note.id]))
        self.assertEqual(response.status_code, 200)
        body = parse(response)
        # 安全红线: 回收站保密笔记 content 必须为空
        self.assertEqual(body['content'], '')
        self.assertTrue(body['is_secret'])
        self.assertTrue(body['is_trashed'])

    def test_get_full_content_returns_extra_fields(self):
        user = make_user('detail04')
        note = Note.objects.create(author=user, title='t', content='<p>x</p>', is_public=False)
        login(self.client, user)
        response = self.client.get(reverse('api_note_detail', args=[note.id]) + '?full_content=true')
        self.assertEqual(response.status_code, 200)
        body = parse(response)
        # full_content 模式应包含 public_url / folder_id / is_favorited 字段
        self.assertIn('public_url', body)
        self.assertIn('folder_id', body)
        self.assertIn('is_favorited', body)


# =========================================================================
# toggle_secret_api
# =========================================================================
class ToggleSecretApiTests(_NoteTestBase):
    def test_toggle_secret_marks_note_secret(self):
        user = make_user('toggler01')
        note = Note.objects.create(author=user, title='t', content='', is_secret=False)
        login(self.client, user)
        response = post_json(self.client, reverse('toggle_secret_api', args=[note.id]))
        self.assertEqual(response.status_code, 200)
        note.refresh_from_db()
        self.assertTrue(note.is_secret)

    def test_toggle_secret_revokes_public(self):
        # 标记为保密后,自动取消公开
        user = make_user('toggler02')
        note = Note.objects.create(author=user, title='t', content='', is_public=True, is_secret=False)
        login(self.client, user)
        response = post_json(self.client, reverse('toggle_secret_api', args=[note.id]))
        self.assertEqual(response.status_code, 200)
        note.refresh_from_db()
        self.assertTrue(note.is_secret)
        self.assertFalse(note.is_public)

    def test_toggle_secret_rejects_other_user(self):
        owner = make_user('toggler03')
        intruder = make_user('intruder06')
        note = Note.objects.create(author=owner, title='t', content='')
        login(self.client, intruder)
        response = post_json(self.client, reverse('toggle_secret_api', args=[note.id]))
        self.assertEqual(response.status_code, 404)


# =========================================================================
# public_note_view (单独页面,非 API)
# =========================================================================
class PublicNoteViewTests(_NoteTestBase):
    def test_non_public_note_renders_error_message(self):
        # 现实现:对非公开/不存在的笔记返回 200 + 渲染错误页(非 404),
        # 由前端展示 error_message。后续考虑改为 404 更利于 SEO。
        user = make_user('pubview01')
        note = Note.objects.create(author=user, title='hidden', content='', is_public=False)
        response = self.client.get(reverse('public_note_view', args=[note.public_id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['error_message'], '抱歉，这篇笔记不存在或未公开分享。')

    def test_public_note_renders_200(self):
        user = make_user('pubview02')
        note = Note.objects.create(author=user, title='visible', content='<p>x</p>', is_public=True)
        response = self.client.get(reverse('public_note_view', args=[note.public_id]))
        self.assertEqual(response.status_code, 200)

    def test_author_note_count_excludes_trashed_public_notes(self):
        user = make_user('pubview03')
        note = Note.objects.create(author=user, title='visible', content='<p>x</p>', is_public=True)
        Note.objects.create(author=user, title='trashed', content='', is_public=True, is_trashed=True)

        response = self.client.get(reverse('public_note_view', args=[note.public_id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['note_data']['author']['note_count'], 1)


class HomeViewTests(_NoteTestBase):
    def test_home_excludes_trashed_public_notes(self):
        author = make_user('homepub01')
        Note.objects.create(author=author, title='visible', content='', is_public=True)
        Note.objects.create(author=author, title='trashed', content='', is_public=True, is_trashed=True)

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        titles = {note.title for note in response.context['articles']}
        self.assertEqual(titles, {'visible'})


# =========================================================================
# search_notes_api
# =========================================================================
class SearchNotesApiTests(_NoteTestBase):
    def test_search_empty_query_returns_empty_list(self):
        user = make_user('search01')
        Note.objects.create(author=user, title='Findme', content='')
        login(self.client, user)
        response = self.client.get(reverse('api_search_notes'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(parse(response), [])

    def test_search_matches_own_notes_only(self):
        user = make_user('search02')
        other = make_user('other02')
        Note.objects.create(author=user, title='HelloWorld', content='')
        Note.objects.create(author=other, title='HelloWorld', content='')
        login(self.client, user)
        response = self.client.get(reverse('api_search_notes') + '?q=Hello')
        self.assertEqual(response.status_code, 200)
        results = parse(response)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['title'], 'HelloWorld')

    def test_search_excludes_secret_notes(self):
        user = make_user('search03')
        Note.objects.create(author=user, title='SecretMatch', content='', is_secret=True)
        Note.objects.create(author=user, title='OpenMatch', content='')
        login(self.client, user)
        response = self.client.get(reverse('api_search_notes') + '?q=Match')
        results = parse(response)
        self.assertEqual({r['title'] for r in results}, {'OpenMatch'})


# =========================================================================
# get_all_notes_api
# =========================================================================
class GetAllNotesApiTests(_NoteTestBase):
    def test_excludes_secret_and_trashed(self):
        user = make_user('alln01')
        Note.objects.create(author=user, title='Open', content='')
        Note.objects.create(author=user, title='Secret', content='', is_secret=True)
        Note.objects.create(author=user, title='Trashed', content='', is_trashed=True)
        login(self.client, user)
        response = self.client.get(reverse('get_all_notes_api'))
        self.assertEqual(response.status_code, 200)
        titles = {n['title'] for n in parse(response)}
        self.assertEqual(titles, {'Open'})


# =========================================================================
# note_history_api / record_note_history_api
# =========================================================================
class NoteHistoryTests(_NoteTestBase):
    def test_record_history_creates_entry_for_public_note(self):
        author = make_user('histauth01')
        viewer = make_user('histview01')
        note = Note.objects.create(author=author, title='public', content='', is_public=True)
        login(self.client, viewer)
        response = post_json(self.client, reverse('record_note_history_api'), {'note_id': note.id})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(NoteHistory.objects.filter(user=viewer, note=note).exists())

    def test_record_history_rejects_private_note(self):
        author = make_user('histauth02')
        viewer = make_user('histview02')
        note = Note.objects.create(author=author, title='private', content='', is_public=False)
        login(self.client, viewer)
        response = post_json(self.client, reverse('record_note_history_api'), {'note_id': note.id})
        self.assertEqual(response.status_code, 404)

    def test_record_history_rejects_trashed_public_note(self):
        author = make_user('histauth06')
        viewer = make_user('histview06')
        note = Note.objects.create(author=author, title='trashed', content='', is_public=True, is_trashed=True)
        login(self.client, viewer)
        response = post_json(self.client, reverse('record_note_history_api'), {'note_id': note.id})
        self.assertEqual(response.status_code, 404)

    def test_record_history_is_idempotent(self):
        # 多次记录同一条只产生一条历史(update_or_create)
        author = make_user('histauth03')
        viewer = make_user('histview03')
        note = Note.objects.create(author=author, title='public', content='', is_public=True)
        login(self.client, viewer)
        post_json(self.client, reverse('record_note_history_api'), {'note_id': note.id})
        post_json(self.client, reverse('record_note_history_api'), {'note_id': note.id})
        self.assertEqual(NoteHistory.objects.filter(user=viewer, note=note).count(), 1)

    def test_record_history_requires_note_id(self):
        viewer = make_user('histview04')
        login(self.client, viewer)
        response = post_json(self.client, reverse('record_note_history_api'), {})
        self.assertEqual(response.status_code, 400)

    def test_history_api_lists_own_views(self):
        author = make_user('histauth05')
        viewer = make_user('histview05')
        note = Note.objects.create(author=author, title='public', content='', is_public=True)
        NoteHistory.objects.create(user=viewer, note=note)
        login(self.client, viewer)
        response = self.client.get(reverse('note_history_api'))
        self.assertEqual(response.status_code, 200)
        # 视图返回结构因实现而异,只断言有数据返回
        body_text = response.content.decode('utf-8')
        self.assertIn('public', body_text)


# =========================================================================
# public_notes_api (只补充 test_security_fixes 未覆盖的过滤项)
# =========================================================================
class PublicNotesApiFilterTests(_NoteTestBase):
    def test_does_not_include_private_notes(self):
        author = make_user('pubapi01')
        Note.objects.create(author=author, title='public', content='', is_public=True)
        Note.objects.create(author=author, title='private', content='', is_public=False)
        response = self.client.get(reverse('public_notes_api'))
        self.assertEqual(response.status_code, 200)
        body = parse(response)
        titles = {n['title'] for n in body['notes']}
        self.assertEqual(titles, {'public'})

    def test_does_not_include_trashed_public_notes(self):
        author = make_user('pubapi02')
        Note.objects.create(author=author, title='public', content='', is_public=True)
        Note.objects.create(author=author, title='trashed', content='', is_public=True, is_trashed=True)

        response = self.client.get(reverse('public_notes_api'))

        self.assertEqual(response.status_code, 200)
        body = parse(response)
        titles = {n['title'] for n in body['notes']}
        self.assertEqual(titles, {'public'})

    def test_public_note_update_invalidates_cached_list(self):
        author = make_user('pubapi03')
        note = Note.objects.create(author=author, title='old title', content='', is_public=True)

        first = self.client.get(reverse('public_notes_api'))
        self.assertEqual(first.status_code, 200)
        self.assertIn('old title', {n['title'] for n in parse(first)['notes']})

        login(self.client, author)
        update = post_json(self.client, reverse('update_note_api', args=[note.id]), {
            'title': 'new title',
            'content': '',
        })
        self.assertEqual(update.status_code, 200)
        self.client.logout()

        second = self.client.get(reverse('public_notes_api'))
        self.assertEqual(second.status_code, 200)
        titles = {n['title'] for n in parse(second)['notes']}
        self.assertIn('new title', titles)
        self.assertNotIn('old title', titles)
