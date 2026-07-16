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
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from notes.models import Asset, Folder, Note, NoteAsset, NoteCollaborator, NoteHistory, NoteRevision

from ._helpers import login, make_user, parse, post_json


@override_settings(
    SESSION_ENGINE='django.contrib.sessions.backends.db',
    # API tests bypass the HTTPS reverse proxy used in production.
    SECURE_SSL_REDIRECT=False,
)
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

    def test_create_note_rejects_secret_public_combination(self):
        user = make_user('secret_public_owner')
        login(self.client, user)
        response = post_json(self.client, reverse('create_note_api'), {
            'title': 'do not publish',
            'is_secret': True,
            'is_public': True,
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Note.objects.filter(author=user, title='do not publish').exists())


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


class NoteRevisionApiTests(_NoteTestBase):
    def test_create_and_update_generate_immutable_revisions(self):
        user = make_user('revision_owner')
        login(self.client, user)
        created = post_json(self.client, reverse('create_note_api'), {
            'title': 'first',
            'content': '<p>one</p>',
        })
        self.assertEqual(created.status_code, 200)
        note = Note.objects.get(id=parse(created)['id'])
        self.assertEqual(NoteRevision.objects.filter(note=note).count(), 1)

        updated = self.client.patch(
            reverse('api_note_detail', args=[note.id]),
            data=json.dumps({'title': 'second', 'content': '<p>two</p>'}),
            content_type='application/json',
        )
        self.assertEqual(updated.status_code, 200, updated.content)
        revisions = list(NoteRevision.objects.filter(note=note).order_by('version_number'))
        self.assertEqual([(item.version_number, item.title) for item in revisions], [(1, 'first'), (2, 'second')])

    def test_editor_can_compare_but_only_manager_can_restore(self):
        owner = make_user('revision_owner2')
        editor = make_user('revision_editor')
        note = Note.objects.create(author=owner, title='one', content='<p>one</p>')
        first = NoteRevision.objects.create(note=note, version_number=1, title='one', content='<p>one</p>', created_by=owner)
        second = NoteRevision.objects.create(note=note, version_number=2, title='two', content='<p>two</p>', created_by=owner)
        NoteCollaborator.objects.create(note=note, user=editor, role=NoteCollaborator.ROLE_EDITOR, added_by=owner)

        login(self.client, editor)
        listing = self.client.get(reverse('note_revisions_api', args=[note.id]))
        self.assertEqual(listing.status_code, 200)
        self.assertFalse(parse(listing)['can_restore'])
        compare = self.client.get(reverse('note_revision_compare_api', args=[note.id]), {'from': first.id, 'to': second.id})
        self.assertEqual(compare.status_code, 200)
        self.assertIn('one', parse(compare)['diff'])
        blocked = post_json(self.client, reverse('restore_note_revision_api', args=[note.id, first.id]))
        self.assertEqual(blocked.status_code, 403)

    def test_manager_restore_creates_a_new_revision(self):
        owner = make_user('revision_owner3')
        note = Note.objects.create(author=owner, title='current', content='<p>current</p>')
        original = NoteRevision.objects.create(note=note, version_number=1, title='original', content='<p>original</p>', created_by=owner)
        NoteRevision.objects.create(note=note, version_number=2, title='current', content='<p>current</p>', created_by=owner)
        login(self.client, owner)
        response = post_json(self.client, reverse('restore_note_revision_api', args=[note.id, original.id]))
        self.assertEqual(response.status_code, 200, response.content)
        note.refresh_from_db()
        self.assertEqual(note.title, 'original')
        self.assertEqual(NoteRevision.objects.filter(note=note).count(), 3)
        self.assertEqual(NoteRevision.objects.get(note=note, version_number=3).action, NoteRevision.ACTION_RESTORED)


class NoteAnnotationAndCleanupApiTests(_NoteTestBase):
    def test_comment_can_include_a_text_anchor(self):
        owner = make_user('annotation_owner')
        note = Note.objects.create(author=owner, title='note', content='<p>selected text</p>')
        login(self.client, owner)
        response = post_json(self.client, reverse('note_comment_create_api', args=[note.id]), {
            'content': 'Please refine this section.',
            'anchor_text': 'selected text',
            'anchor_start': 0,
            'anchor_end': 13,
            'anchor_context': 'selected text',
        })
        self.assertEqual(response.status_code, 201, response.content)
        body = parse(response)
        self.assertEqual(body['anchor_text'], 'selected text')
        comments = self.client.get(reverse('note_comments_api', args=[note.id]))
        self.assertEqual(parse(comments)['comments'][0]['anchor_start'], 0)

    def test_orphan_cleanup_only_lists_and_deletes_the_current_users_unlinked_assets(self):
        owner = make_user('cleanup_owner')
        other = make_user('cleanup_other')
        orphan = Asset.objects.create(
            uploader=owner,
            name='orphan.txt',
            file=SimpleUploadedFile('orphan.txt', b'orphan'),
        )
        linked = Asset.objects.create(
            uploader=owner,
            name='linked.txt',
            file=SimpleUploadedFile('linked.txt', b'linked'),
        )
        other_asset = Asset.objects.create(
            uploader=other,
            name='other.txt',
            file=SimpleUploadedFile('other.txt', b'other'),
        )
        note = Note.objects.create(author=owner, title='linked', content='')
        NoteAsset.objects.create(note=note, asset=linked)

        login(self.client, owner)
        listed = self.client.get(reverse('orphan_note_assets_api'))
        self.assertEqual(listed.status_code, 200)
        self.assertEqual([item['id'] for item in parse(listed)['assets']], [orphan.id])

        deleted = post_json(self.client, reverse('delete_orphan_note_assets_api'), {
            'asset_ids': [orphan.id, linked.id, other_asset.id],
        })
        self.assertEqual(deleted.status_code, 200, deleted.content)
        self.assertEqual(parse(deleted)['deleted_ids'], [orphan.id])
        self.assertFalse(Asset.objects.filter(id=orphan.id).exists())
        self.assertTrue(Asset.objects.filter(id=linked.id).exists())
        self.assertTrue(Asset.objects.filter(id=other_asset.id).exists())


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
        self.assertIn('revision_token', body)

    def test_stale_revision_token_rejects_content_overwrite(self):
        user = make_user('detail05')
        note = Note.objects.create(author=user, title='t', content='<p>first</p>')
        login(self.client, user)
        detail_url = reverse('api_note_detail', args=[note.id])

        initial = parse(self.client.get(detail_url + '?full_content=true'))
        note.content = '<p>changed elsewhere</p>'
        note.save()

        response = self.client.patch(
            detail_url,
            data=json.dumps({
                'content': '<p>stale write</p>',
                'base_revision_token': initial['revision_token'],
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(parse(response)['code'], 'note_edit_conflict')
        note.refresh_from_db()
        self.assertEqual(note.content, '<p>changed elsewhere</p>')


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

    def test_toggle_secret_revokes_existing_collaborators(self):
        owner = make_user('toggler04')
        collaborator = make_user('toggler05')
        note = Note.objects.create(author=owner, title='t', content='')
        NoteCollaborator.objects.create(note=note, user=collaborator, added_by=owner)
        login(self.client, owner)

        response = post_json(self.client, reverse('toggle_secret_api', args=[note.id]))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(NoteCollaborator.objects.filter(note=note).exists())


class NoteCollaborationApiTests(_NoteTestBase):
    def test_secret_note_rejects_collaborator_listing(self):
        owner = make_user('collab_secret_owner')
        collaborator = make_user('collab_secret_user')
        note = Note.objects.create(author=owner, title='secret', content='', is_secret=True)
        login(self.client, owner)

        response = self.client.get(reverse('note_collaborators_api', args=[note.id]))

        self.assertEqual(response.status_code, 400)
        self.assertIn('保密笔记', parse(response)['error'])

    def test_secret_note_rejects_adding_collaborator(self):
        owner = make_user('collab_post_owner')
        collaborator = make_user('collab_post_user')
        note = Note.objects.create(author=owner, title='secret', content='', is_secret=True)
        login(self.client, owner)

        response = post_json(
            self.client,
            reverse('note_collaborators_api', args=[note.id]),
            {'user_id': collaborator.id, 'role': 'reader'},
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(NoteCollaborator.objects.filter(note=note, user=collaborator).exists())

    def test_editor_presence_requires_write_permission_and_reports_other_editor(self):
        owner = make_user('presence_owner')
        editor = make_user('presence_editor')
        reader = make_user('presence_reader')
        note = Note.objects.create(author=owner, title='shared', content='')
        NoteCollaborator.objects.create(
            note=note,
            user=editor,
            role=NoteCollaborator.ROLE_EDITOR,
            added_by=owner,
        )
        NoteCollaborator.objects.create(
            note=note,
            user=reader,
            role=NoteCollaborator.ROLE_READER,
            added_by=owner,
        )

        login(self.client, editor)
        response = post_json(
            self.client,
            reverse('note_editing_session_api', args=[note.id]),
            {'action': 'enter'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(parse(response)['editing_by_others'])

        login(self.client, owner)
        response = self.client.get(reverse('note_editing_session_api', args=[note.id]))
        self.assertEqual(response.status_code, 200)
        body = parse(response)
        self.assertTrue(body['editing_by_others'])
        self.assertEqual(body['editing_by'], editor.username)

        login(self.client, reader)
        response = post_json(
            self.client,
            reverse('note_editing_session_api', args=[note.id]),
            {'action': 'enter'},
        )
        self.assertEqual(response.status_code, 403)

    def test_editor_presence_leave_removes_current_user(self):
        owner = make_user('presence_leave_owner')
        note = Note.objects.create(author=owner, title='shared', content='')
        login(self.client, owner)
        url = reverse('note_editing_session_api', args=[note.id])

        self.assertEqual(post_json(self.client, url, {'action': 'enter'}).status_code, 200)
        response = post_json(self.client, url, {'action': 'leave'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(parse(response)['active_editors'], [])


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

    def test_public_note_view_rejects_secret_public_note(self):
        user = make_user('pubview_secret')
        note = Note.objects.create(
            author=user,
            title='secret public',
            content='<p>x</p>',
            is_public=True,
            is_secret=True,
        )
        response = self.client.get(reverse('public_note_view', args=[note.public_id]))
        self.assertEqual(response.status_code, 200)
        self.assertIn('error_message', response.context)

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

    def test_history_api_excludes_notes_no_longer_public(self):
        author = make_user('histauth07')
        viewer = make_user('histview07')
        visible = Note.objects.create(author=author, title='visible', content='ok', is_public=True)
        private = Note.objects.create(author=author, title='private-now', content='secret text', is_public=False)
        secret = Note.objects.create(author=author, title='secret-now', content='vault text', is_public=True, is_secret=True)
        trashed = Note.objects.create(author=author, title='trashed-now', content='trash text', is_public=True, is_trashed=True)
        for note in (visible, private, secret, trashed):
            NoteHistory.objects.create(user=viewer, note=note)

        login(self.client, viewer)
        response = self.client.get(reverse('note_history_api'))

        self.assertEqual(response.status_code, 200)
        titles = {item['title'] for item in parse(response)}
        self.assertEqual(titles, {'visible'})

    def test_record_history_invalidates_cached_history(self):
        author = make_user('histauth08')
        viewer = make_user('histview08')
        first_note = Note.objects.create(author=author, title='first', content='', is_public=True)
        second_note = Note.objects.create(author=author, title='second', content='', is_public=True)
        NoteHistory.objects.create(user=viewer, note=first_note)
        login(self.client, viewer)
        first = self.client.get(reverse('note_history_api'))
        self.assertEqual(first.status_code, 200)
        self.assertEqual({item['title'] for item in parse(first)}, {'first'})

        response = post_json(self.client, reverse('record_note_history_api'), {'note_id': second_note.id})
        self.assertEqual(response.status_code, 200)
        second = self.client.get(reverse('note_history_api'))

        titles = {item['title'] for item in parse(second)}
        self.assertEqual(titles, {'first', 'second'})


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

    def test_does_not_include_secret_public_notes(self):
        author = make_user('pubapi_secret')
        Note.objects.create(author=author, title='public', content='', is_public=True)
        Note.objects.create(author=author, title='secret', content='', is_public=True, is_secret=True)

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
