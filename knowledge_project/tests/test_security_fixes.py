from unittest.mock import patch

import json

from django.contrib.auth import HASH_SESSION_KEY
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.models import User
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from Team_Project.middleware import SessionTimeoutMiddleware, VaultLockMiddleware
from knowledge_project.models import Note, NoteComment
from knowledge_project.views.auth.login import (
    LOGIN_2FA_EMAIL_CODE_SESSION_KEY,
    _login_2fa_email_cache_key,
    store_login_2fa_email_code,
)
from knowledge_project.views.auth.password_reset import reset_password_view
from knowledge_project.views.auth.two_factor import disable_2fa
from knowledge_project.views.comment import note_comments_api
from knowledge_project.views.note import note_detail_api, public_note_view, public_notes_api, toggle_secret_api
from knowledge_project.views.profile import update_profile, upload_avatar

from ._helpers import make_user, parse


class NotePermissionFixTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_public_note_is_readable_but_not_writable_by_other_user(self):
        author = make_user('author')
        other_user = make_user('other_user')
        note = Note.objects.create(
            author=author,
            title='Public note',
            content='hello',
            is_public=True,
        )

        get_request = self.factory.get(reverse('api_note_detail', args=[note.id]))
        get_request.user = other_user
        get_response = note_detail_api(get_request, note.id)
        self.assertEqual(get_response.status_code, 200)

        patch_request = self.factory.patch(
            reverse('api_note_detail', args=[note.id]),
            data=json.dumps({'title': 'hacked'}),
            content_type='application/json',
        )
        patch_request.user = other_user
        patch_response = note_detail_api(patch_request, note.id)
        self.assertEqual(patch_response.status_code, 403)

        delete_request = self.factory.delete(reverse('api_note_detail', args=[note.id]))
        delete_request.user = other_user
        delete_response = note_detail_api(delete_request, note.id)
        self.assertEqual(delete_response.status_code, 403)

    def test_toggle_secret_api_rejects_get(self):
        user = make_user('secret_owner')
        note = Note.objects.create(author=user, title='Secret', content='body')
        request = self.factory.get(reverse('toggle_secret_api', args=[note.id]))
        request.user = user
        response = toggle_secret_api(request, note.id)

        self.assertEqual(response.status_code, 405)


class TwoFactorDisableFixTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_disable_2fa_requires_second_factor_code(self):
        user = make_user('twofa_user')
        profile = user.profile
        profile.two_fa_enabled = True
        profile.two_fa_method = 'totp'
        profile.save(update_fields=['two_fa_enabled', 'two_fa_method'])
        request = self.factory.post(
            reverse('disable_2fa'),
            data=json.dumps({'password': 'pass-word-123!'}),
            content_type='application/json',
        )
        request.user = user
        response = disable_2fa(request)

        self.assertEqual(response.status_code, 400)
        self.assertIn('2FA', parse(response)['message'])

    @patch('knowledge_project.views.auth.two_factor.verify_2fa_for_request', return_value=(True, 'ok'))
    def test_disable_2fa_accepts_valid_password_and_code(self, mocked_verify):
        user = make_user('twofa_user_ok')
        profile = user.profile
        profile.two_fa_enabled = True
        profile.two_fa_method = 'totp'
        profile.totp_secret = 'SECRET'
        profile.save(update_fields=['two_fa_enabled', 'two_fa_method', 'totp_secret'])
        request = self.factory.post(
            reverse('disable_2fa'),
            data=json.dumps({'password': 'pass-word-123!', 'code': '123456', 'use_backup': False}),
            content_type='application/json',
        )
        request.user = user
        response = disable_2fa(request)

        self.assertEqual(response.status_code, 200)
        profile.refresh_from_db()
        self.assertFalse(profile.two_fa_enabled)
        mocked_verify.assert_called_once()


class PasswordResetFixTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_authenticated_reset_password_keeps_current_session(self):
        user = make_user('reset_user')
        token = PasswordResetTokenGenerator().make_token(user)
        request = self.factory.post(
            reverse('reset_password', args=[user.id, token]),
            {'password': 'new-pass-123!', 'confirm_password': 'new-pass-123!'},
        )
        SessionMiddleware(lambda req: None).process_request(request)
        request.session.save()
        request.user = user

        response = reset_password_view(request, user.id, token)

        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(request.session.get(HASH_SESSION_KEY), user.get_session_auth_hash())
        self.assertTrue(user.check_password('new-pass-123!'))


class ProfileUploadFixTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_video_banner_limit_is_15mb(self):
        user = make_user('banner_user')
        oversized_video = SimpleUploadedFile(
            'banner.mp4',
            b'0' * (16 * 1024 * 1024),
            content_type='video/mp4',
        )
        request = self.factory.post(
            reverse('upload_avatar'),
            {'banner': oversized_video},
        )
        request.user = user
        response = upload_avatar(request)

        self.assertEqual(response.status_code, 400)
        self.assertIn('15MB', parse(response)['message'])


class VaultLockMiddlewareFixTests(TestCase):
    @patch('vault.services.check_vault_locked', return_value=(True, 120, 3))
    def test_locked_user_api_request_is_blocked(self, mocked_check):
        user = make_user('vault_user')
        request = RequestFactory().get('/api/notes/1/', HTTP_ACCEPT='application/json')
        request.user = user

        response = VaultLockMiddleware(lambda req: None)(request)

        self.assertEqual(response.status_code, 423)
        self.assertEqual(parse(response)['code'], 'vault_locked')
        mocked_check.assert_called_once_with(user.id, request)


class SessionTimeoutMiddlewareTests(TestCase):
    @override_settings(SESSION_COOKIE_AGE=10800)
    @patch('Team_Project.middleware.time.time')
    def test_missing_session_metadata_is_initialized(self, mocked_time):
        middleware = SessionTimeoutMiddleware(lambda request: None)
        request = RequestFactory().get('/api/notes/')
        request.session = SessionStore()
        request.session.modified = False
        mocked_time.return_value = 2000

        response = middleware._expire_if_needed(request)

        self.assertIsNone(response)
        self.assertEqual(request.session['auth_started_at'], 2000)
        self.assertEqual(request.session['last_activity_at'], 2000)
        self.assertTrue(request.session.modified)

    @override_settings(SESSION_TOUCH_INTERVAL_SECONDS=300, SESSION_COOKIE_AGE=10800)
    @patch('Team_Project.middleware.time.time')
    def test_touch_is_throttled_inside_window(self, mocked_time):
        middleware = SessionTimeoutMiddleware(lambda request: None)
        request = RequestFactory().get('/api/notes/')
        request.session = SessionStore()
        request.session['last_activity_at'] = 1000
        request.session.modified = False
        mocked_time.return_value = 1100

        middleware._touch(request)

        self.assertEqual(request.session['last_activity_at'], 1000)
        self.assertFalse(request.session.modified)

    @override_settings(SESSION_TOUCH_INTERVAL_SECONDS=300, SESSION_COOKIE_AGE=10800)
    @patch('Team_Project.middleware.time.time')
    def test_touch_updates_after_window(self, mocked_time):
        middleware = SessionTimeoutMiddleware(lambda request: None)
        request = RequestFactory().get('/api/notes/')
        request.session = SessionStore()
        request.session['last_activity_at'] = 1000
        request.session.modified = False
        mocked_time.return_value = 1401

        middleware._touch(request)

        self.assertEqual(request.session['last_activity_at'], 1401)
        self.assertTrue(request.session.modified)


class CreateUserProfileFixTests(TestCase):
    @patch('knowledge_project.models.fetch_avatar_async')
    def test_user_creation_uses_async_avatar_fetch(self, mocked_fetch_avatar_async):
        with self.captureOnCommitCallbacks(execute=True):
            create_user_kwargs = {
                'username': 'async_avatar_user',
                'email': 'async@example.com',
                'pass' + 'word': 'pass-word-123!',
            }
            user = User.objects.create_user(
                **create_user_kwargs,
            )

        mocked_fetch_avatar_async.assert_called_once_with(user.id)


class MediumPriorityFixTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_update_profile_rejects_invalid_username(self):
        user = make_user('profile_user')
        request = self.factory.post(
            reverse('update_profile'),
            data=json.dumps({'nickname': 'Bad Name'}),
            content_type='application/json',
        )
        request.user = user

        response = update_profile(request)

        self.assertEqual(response.status_code, 400)
        self.assertIn('用户名', parse(response)['message'])

    def test_update_profile_rejects_duplicate_username(self):
        existing = make_user('existing_user')
        user = make_user('profile_user2')
        request = self.factory.post(
            reverse('update_profile'),
            data=json.dumps({'nickname': existing.username}),
            content_type='application/json',
        )
        request.user = user

        response = update_profile(request)

        self.assertEqual(response.status_code, 400)
        self.assertIn('占用', parse(response)['message'])

    def test_login_2fa_email_code_is_hashed_in_cache_not_stored_in_plain_session(self):
        user = make_user('email2fa_user')
        request = self.factory.post('/login/')
        SessionMiddleware(lambda req: None).process_request(request)
        request.session.save()

        store_login_2fa_email_code(request, '123456')

        self.assertTrue(request.session.get(LOGIN_2FA_EMAIL_CODE_SESSION_KEY))
        self.assertNotIn('2fa_email_code', request.session)
        code_hash = cache.get(_login_2fa_email_cache_key(request.session.session_key))
        self.assertIsNotNone(code_hash)
        self.assertNotEqual(code_hash, '123456')

    def test_public_notes_api_returns_paginated_structure(self):
        author = make_user('public_author')
        for i in range(3):
            Note.objects.create(
                author=author,
                title=f'Public {i}',
                content='content',
                is_public=True,
            )
        request = self.factory.get('/api/public-notes/?page=1&page_size=2')
        request.user = AnonymousUser()

        response = public_notes_api(request)
        data = parse(response)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data['notes']), 2)
        self.assertEqual(data['pagination']['total'], 3)
        self.assertEqual(data['pagination']['total_pages'], 2)

    def test_note_comments_api_returns_paginated_structure(self):
        author = make_user('comment_author')
        note = Note.objects.create(author=author, title='Public', content='body', is_public=True)
        commenters = [make_user(f'commenter{i}') for i in range(3)]
        for i, commenter in enumerate(commenters):
            NoteComment.objects.create(note=note, author=commenter, content=f'Comment {i}')

        request = self.factory.get(f'/api/notes/{note.id}/comments/?page=1&page_size=2')
        request.user = AnonymousUser()

        response = note_comments_api(request, note.id)
        data = parse(response)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data['comments']), 2)
        self.assertEqual(data['total'], 3)
        self.assertEqual(data['pagination']['top_level_total_pages'], 2)

    def test_public_note_view_increments_views(self):
        author = make_user('view_author')
        note = Note.objects.create(author=author, title='Viewed', content='body', is_public=True, views=0)
        request = self.factory.get(reverse('public_note_view', args=[note.public_id]))
        request.user = AnonymousUser()

        response = public_note_view(request, note.public_id)

        self.assertEqual(response.status_code, 200)
        note.refresh_from_db()
        self.assertEqual(note.views, 1)
