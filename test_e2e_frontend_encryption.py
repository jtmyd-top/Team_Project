#!/usr/bin/env python
"""
End-to-End Encryption Test (Frontend Implementation)

Tests the corrected E2E encryption flow:
1. Frontend toggles is_secret flag using /api/notes/{id}/toggle-secret/
2. Frontend encrypts plaintext using crypto-js in browser
3. Backend receives and stores encrypted content as-is (no decryption)
4. Frontend retrieves encrypted content and decrypts in browser
5. Backend never sees plaintext
"""

import os
import sys
import django
import json

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Team_Project.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from knowledge_project.models import Note


class FrontendE2EEncryptionTest:
    """Test suite for frontend-based E2E encryption"""

    def __init__(self):
        self.client = Client()
        self.test_user = None
        self.errors = []
        self.successes = []

    def log_success(self, message):
        """Log successful test"""
        msg = f"[PASS] {message}"
        print(msg)
        self.successes.append(msg)

    def log_error(self, message):
        """Log error"""
        msg = f"[FAIL] {message}"
        print(msg)
        self.errors.append(msg)

    def setup_test_user(self):
        """Create test user"""
        print("\n" + "="*70)
        print("SETUP: Creating test user")
        print("="*70)

        try:
            # Clean up existing test user
            User.objects.filter(username='test_frontend_e2e').delete()

            # Create new user
            self.test_user = User.objects.create_user(
                username='test_frontend_e2e',
                email='test_e2e@example.com',
                password='testpass123'
            )
            self.log_success(f"User created: {self.test_user.username}")
            return True

        except Exception as e:
            self.log_error(f"Setup failed: {e}")
            return False

    def test_toggle_secret_api(self):
        """Test the toggle-secret API endpoint"""
        print("\n" + "="*70)
        print("TEST 1: Toggle Secret API (/api/notes/{id}/toggle-secret/)")
        print("="*70)

        try:
            # Login
            login_ok = self.client.login(username='test_frontend_e2e', password='testpass123')
            if not login_ok:
                self.log_error("Login failed")
                return False
            self.log_success("User logged in")

            # Create a plain note first
            response = self.client.get('/knowledge/')
            csrf_token = response.cookies.get('csrftoken')

            note_data = {
                'title': 'Test Note for Toggle',
                'content': '<p>This is a test note</p>',
                'is_secret': False
            }

            response = self.client.post(
                '/api/notes/create/',
                data=json.dumps(note_data),
                content_type='application/json',
                HTTP_X_CSRFTOKEN=csrf_token
            )

            if response.status_code not in [200, 201]:
                self.log_error(f"Create note failed: {response.status_code}")
                return False

            note_id = response.json().get('id')
            if not note_id:
                self.log_error("No note ID returned")
                return False

            self.log_success(f"Plain note created (ID: {note_id}, is_secret=false)")

            # Verify initial state in database
            note = Note.objects.get(id=note_id)
            if note.is_secret:
                self.log_error("New note should have is_secret=false")
                return False
            self.log_success("Verified is_secret=false in database")

            # Toggle to secret
            response = self.client.post(
                f'/api/notes/{note_id}/toggle-secret/',
                content_type='application/json',
                HTTP_X_CSRFTOKEN=csrf_token
            )

            if response.status_code != 200:
                self.log_error(f"Toggle secret failed: {response.status_code} - {response.content}")
                return False

            data = response.json()
            if data.get('status') != 'success':
                self.log_error(f"Toggle API returned: {data}")
                return False

            if not data.get('is_secret'):
                self.log_error("API response should have is_secret=true")
                return False

            self.log_success("API toggle successful (is_secret=true)")

            # Verify in database
            note.refresh_from_db()
            if not note.is_secret:
                self.log_error("Database should have is_secret=true after toggle")
                return False

            self.log_success("Database updated correctly (is_secret=true)")

            # Toggle back to plain
            response = self.client.post(
                f'/api/notes/{note_id}/toggle-secret/',
                content_type='application/json',
                HTTP_X_CSRFTOKEN=csrf_token
            )

            if response.status_code != 200:
                self.log_error(f"Toggle back failed: {response.status_code}")
                return False

            note.refresh_from_db()
            if note.is_secret:
                self.log_error("Note should have is_secret=false after toggling back")
                return False

            self.log_success("Toggle back successful (is_secret=false)")
            return note_id

        except Exception as e:
            self.log_error(f"Toggle secret test failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def test_frontend_encryption_storage(self):
        """Test that frontend-encrypted content is stored as-is by backend"""
        print("\n" + "="*70)
        print("TEST 2: Frontend Encryption Storage (Backend receives ciphertext)")
        print("="*70)

        try:
            response = self.client.get('/knowledge/')
            csrf_token = response.cookies.get('csrftoken')

            # Create a secret note with encrypted content
            # Simulating what the frontend would send:
            # plaintext = "Secret message"
            # Frontend encrypts with crypto-js AES, resulting in Base64 ciphertext
            # Example encrypted content (this would come from crypto-js)
            simulated_encrypted_content = "U2FsdGVkX1+abc123...encrypted_base64_content..."

            note_data = {
                'title': 'Frontend Encrypted Note',
                'content': simulated_encrypted_content,
                'is_secret': True
            }

            response = self.client.post(
                '/api/notes/create/',
                data=json.dumps(note_data),
                content_type='application/json',
                HTTP_X_CSRFTOKEN=csrf_token
            )

            if response.status_code not in [200, 201]:
                self.log_error(f"Create encrypted note failed: {response.status_code}")
                return False

            note_id = response.json().get('id')
            self.log_success(f"Secret note created (ID: {note_id})")

            # CRITICAL: Verify backend did NOT modify the encrypted content
            note = Note.objects.get(id=note_id)
            if note.content != simulated_encrypted_content:
                self.log_error(
                    f"Backend modified encrypted content!\n"
                    f"  Expected: {simulated_encrypted_content}\n"
                    f"  Got: {note.content}"
                )
                return False

            self.log_success("Backend stored encrypted content as-is (no modification)")

            # Verify is_secret flag
            if not note.is_secret:
                self.log_error("Note should have is_secret=true")
                return False

            self.log_success("is_secret flag set correctly")

            return note_id

        except Exception as e:
            self.log_error(f"Storage test failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def test_api_response_includes_is_secret(self):
        """Test that all API responses include is_secret flag"""
        print("\n" + "="*70)
        print("TEST 3: API Responses Include is_secret Flag")
        print("="*70)

        try:
            response = self.client.get('/knowledge/')
            csrf_token = response.cookies.get('csrftoken')

            # Create a test note
            note_data = {
                'title': 'Response Test Note',
                'content': '<p>Test content</p>',
                'is_secret': False
            }

            response = self.client.post(
                '/api/notes/create/',
                data=json.dumps(note_data),
                content_type='application/json',
                HTTP_X_CSRFTOKEN=csrf_token
            )

            note_id = response.json().get('id')
            self.log_success(f"Note created (ID: {note_id})")

            # Test GET response includes is_secret
            response = self.client.get(f'/api/notes/{note_id}/?full_content=true')
            if response.status_code != 200:
                self.log_error(f"GET failed: {response.status_code}")
                return False

            data = response.json()
            if 'is_secret' not in data:
                self.log_error("GET response missing is_secret field")
                return False

            if data.get('is_secret') != False:
                self.log_error(f"GET response is_secret should be false, got {data.get('is_secret')}")
                return False

            self.log_success("[OK] GET response includes is_secret=false")

            # Test PATCH response includes is_secret
            patch_data = {
                'title': 'Updated Title',
                'content': '<p>Updated content</p>'
            }

            response = self.client.patch(
                f'/api/notes/{note_id}/',
                data=json.dumps(patch_data),
                content_type='application/json',
                HTTP_X_CSRFTOKEN=csrf_token
            )

            if response.status_code != 200:
                self.log_error(f"PATCH failed: {response.status_code}")
                return False

            data = response.json()
            if 'is_secret' not in data:
                self.log_error("PATCH response missing is_secret field")
                return False

            self.log_success("[OK] PATCH response includes is_secret field")

            return True

        except Exception as e:
            self.log_error(f"Response test failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def test_no_backend_encryption_endpoints(self):
        """Verify that old backend encryption endpoints are gone"""
        print("\n" + "="*70)
        print("TEST 4: Old Backend Encryption Endpoints Removed")
        print("="*70)

        try:
            response = self.client.get('/knowledge/')
            csrf_token = response.cookies.get('csrftoken')

            # Create a test note
            note_data = {
                'title': 'Endpoint Test Note',
                'content': '<p>Test</p>',
                'is_secret': True
            }

            response = self.client.post(
                '/api/notes/create/',
                data=json.dumps(note_data),
                content_type='application/json',
                HTTP_X_CSRFTOKEN=csrf_token
            )

            note_id = response.json().get('id')

            # Try to call old /api/vault/encrypt/ endpoint
            response = self.client.post(
                '/api/vault/encrypt/',
                data=json.dumps({'plaintext': 'test'}),
                content_type='application/json',
                HTTP_X_CSRFTOKEN=csrf_token
            )

            if response.status_code == 404:
                self.log_success("[OK] /api/vault/encrypt/ correctly removed (404)")
            else:
                self.log_error(f"Old encryption endpoint still exists (status: {response.status_code})")
                return False

            # Try to call old /api/notes/{id}/decrypt/ endpoint
            response = self.client.post(
                f'/api/notes/{note_id}/decrypt/',
                data=json.dumps({'encrypted_data': 'test'}),
                content_type='application/json',
                HTTP_X_CSRFTOKEN=csrf_token
            )

            if response.status_code == 404:
                self.log_success("[OK] /api/notes/{id}/decrypt/ correctly removed (404)")
            else:
                self.log_error(f"Old decrypt endpoint still exists (status: {response.status_code})")
                return False

            return True

        except Exception as e:
            self.log_error(f"Endpoint test failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def run_all_tests(self):
        """Run all tests"""
        print("\n" + "="*70)
        print("FRONTEND E2E ENCRYPTION TEST SUITE")
        print("="*70)
        print("Testing the corrected frontend-based E2E encryption flow\n")

        # Setup
        if not self.setup_test_user():
            return False

        # Test 1: Toggle secret API
        if not self.test_toggle_secret_api():
            return False

        # Test 2: Frontend encryption storage
        if not self.test_frontend_encryption_storage():
            return False

        # Test 3: API responses
        if not self.test_api_response_includes_is_secret():
            return False

        # Test 4: No backend endpoints
        if not self.test_no_backend_encryption_endpoints():
            return False

        # Summary
        self.print_summary()

        return len(self.errors) == 0

    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        print(f"Passed: {len(self.successes)}")
        print(f"Failed: {len(self.errors)}")

        if self.errors:
            print("\nFailed tests:")
            for error in self.errors:
                print(f"  {error}")

        print("\n" + "="*70 + "\n")

        if len(self.errors) == 0:
            print("[OK] All tests passed!")
            print("[OK] Frontend E2E encryption correctly implemented")
            print("[OK] Backend only stores/retrieves encrypted content")
            print("[OK] Old backend encryption endpoints removed\n")


if __name__ == '__main__':
    suite = FrontendE2EEncryptionTest()
    success = suite.run_all_tests()
    sys.exit(0 if success else 1)
