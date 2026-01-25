#!/usr/bin/env python
"""
End-to-End Encryption Integration Test

Tests the complete frontend-to-backend encryption flow:
1. Frontend encrypts plaintext using vault API
2. Backend stores ciphertext in database
3. Frontend decrypts ciphertext when retrieving notes
"""

import os
import sys
import django
import json
import requests
from io import StringIO

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Team_Project.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.test import Client, TestCase
from django.contrib.auth.models import User
from knowledge_project.models import Note, Profile
from knowledge_project.utils.vault_crypto import VaultEncryption

class E2EEncryptionTestSuite:
    """End-to-end encryption test suite"""

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
        """Create test user and initialize vault"""
        print("\n" + "="*60)
        print("SETUP: Creating test user and initializing vault")
        print("="*60)

        try:
            # Clean up existing test user
            User.objects.filter(username='test_e2e_user').delete()

            # Create new user
            self.test_user = User.objects.create_user(
                username='test_e2e_user',
                email='test@example.com',
                password='testpass123'
            )
            self.log_success(f"User created: {self.test_user.username}")

            # Initialize vault
            profile = self.test_user.profile
            profile.vault_initialized = True

            # Generate DEK
            dek = VaultEncryption.generate_dek()

            # Encrypt DEK with KEK (internally uses KEK)
            encrypted_dek, iv = VaultEncryption.encrypt_dek(dek)

            profile.encrypted_vault_key = encrypted_dek
            profile.vault_key_iv = iv
            profile.save()

            self.log_success("Vault initialized successfully")
            return True

        except Exception as e:
            self.log_error(f"Setup failed: {e}")
            return False

    def test_vault_encrypt_api(self):
        """Test the /api/vault/encrypt/ endpoint"""
        print("\n" + "="*60)
        print("TEST 1: Frontend Encryption API (/api/vault/encrypt/)")
        print("="*60)

        try:
            # Login first
            login_success = self.client.login(
                username='test_e2e_user',
                password='testpass123'
            )
            if not login_success:
                self.log_error("Failed to login")
                return False

            self.log_success("User logged in")

            # Get CSRF token
            response = self.client.get('/knowledge/')
            csrf_token = response.cookies.get('csrftoken')

            # Test encryption API
            plaintext = "This is a secret note content 秘密笔记"
            response = self.client.post(
                '/api/vault/encrypt/',
                data=json.dumps({'plaintext': plaintext}),
                content_type='application/json',
                HTTP_X_CSRFTOKEN=csrf_token
            )

            if response.status_code != 200:
                self.log_error(f"API returned status {response.status_code}: {response.content}")
                return False

            data = json.loads(response.content)

            if 'encrypted_data' not in data:
                self.log_error("Response missing 'encrypted_data' field")
                return False

            encrypted_data = data['encrypted_data']

            # Verify it's actually encrypted (not plaintext)
            if plaintext in encrypted_data:
                self.log_error("Encrypted data contains plaintext!")
                return False

            # Verify it's Base64 (no special chars except +, /, =)
            import re
            if not re.match(r'^[A-Za-z0-9+/]*={0,2}$', encrypted_data):
                self.log_error(f"Encrypted data is not valid Base64: {encrypted_data[:50]}")
                return False

            self.log_success(f"Encryption API works correctly")
            self.log_success(f"Plaintext length: {len(plaintext)}, Ciphertext length: {len(encrypted_data)}")

            return encrypted_data

        except Exception as e:
            self.log_error(f"Encryption API test failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def test_create_secret_note(self, encrypted_content):
        """Test creating and storing a secret note"""
        print("\n" + "="*60)
        print("TEST 2: Create Secret Note (Frontend → Backend)")
        print("="*60)

        try:
            # Get CSRF token
            response = self.client.get('/knowledge/')
            csrf_token = response.cookies.get('csrftoken')

            # Create note with encrypted content
            note_data = {
                'title': 'Secret Note Test',
                'content': encrypted_content,
                'is_secret': True
            }

            response = self.client.post(
                '/api/notes/create/',
                data=json.dumps(note_data),
                content_type='application/json',
                HTTP_X_CSRFTOKEN=csrf_token
            )

            if response.status_code != 200 and response.status_code != 201:
                self.log_error(f"Create note API returned {response.status_code}: {response.content}")
                return False

            data = json.loads(response.content)
            note_id = data.get('id')

            if not note_id:
                self.log_error("Response missing note ID")
                return False

            self.log_success(f"Secret note created with ID: {note_id}")

            # Verify in database that content is stored as ciphertext
            note = Note.objects.get(id=note_id)

            if note.content != encrypted_content:
                self.log_error(
                    f"Backend modified content!\n"
                    f"  Expected: {encrypted_content[:50]}...\n"
                    f"  Got: {note.content[:50]}..."
                )
                return False

            self.log_success("Database stores ciphertext correctly (no backend encryption)")

            # Verify is_secret flag
            if not note.is_secret:
                self.log_error("is_secret flag not set!")
                return False

            self.log_success("Note marked as secret correctly")

            return note_id

        except Exception as e:
            self.log_error(f"Create secret note test failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def test_decrypt_api(self, note_id):
        """Test the decryption API"""
        print("\n" + "="*60)
        print("TEST 3: Decryption API (/api/notes/{id}/decrypt/)")
        print("="*60)

        try:
            # Get note
            note = Note.objects.get(id=note_id)
            encrypted_content = note.content

            # Get CSRF token
            response = self.client.get('/knowledge/')
            csrf_token = response.cookies.get('csrftoken')

            # Call decrypt API
            response = self.client.post(
                f'/api/notes/{note_id}/decrypt/',
                data=json.dumps({'encrypted_data': encrypted_content}),
                content_type='application/json',
                HTTP_X_CSRFTOKEN=csrf_token
            )

            if response.status_code != 200:
                self.log_error(f"Decrypt API returned {response.status_code}: {response.content}")
                return False

            data = json.loads(response.content)
            plaintext = data.get('plaintext')

            if not plaintext:
                self.log_error("Decrypt response missing plaintext")
                return False

            expected_plaintext = "This is a secret note content 秘密笔记"
            if plaintext != expected_plaintext:
                self.log_error(
                    f"Decrypted content mismatch!\n"
                    f"  Expected: {expected_plaintext}\n"
                    f"  Got: {plaintext}"
                )
                return False

            self.log_success(f"Decryption successful: {plaintext}")
            return True

        except Exception as e:
            self.log_error(f"Decryption API test failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def test_plain_note_no_encryption(self):
        """Test that plain notes are NOT encrypted"""
        print("\n" + "="*60)
        print("TEST 4: Plain Notes Should NOT Be Encrypted")
        print("="*60)

        try:
            # Get CSRF token
            response = self.client.get('/knowledge/')
            csrf_token = response.cookies.get('csrftoken')

            plaintext = "<p>This is a plain note in HTML</p>"

            # Create plain note (is_secret=false)
            note_data = {
                'title': 'Plain Note Test',
                'content': plaintext,
                'is_secret': False
            }

            response = self.client.post(
                '/api/notes/create/',
                data=json.dumps(note_data),
                content_type='application/json',
                HTTP_X_CSRFTOKEN=csrf_token
            )

            if response.status_code not in [200, 201]:
                self.log_error(f"Create note API returned {response.status_code}")
                return False

            data = json.loads(response.content)
            note_id = data.get('id')

            # Check database
            note = Note.objects.get(id=note_id)

            if note.content != plaintext:
                self.log_error(
                    f"Plain note content was modified!\n"
                    f"  Expected: {plaintext}\n"
                    f"  Got: {note.content}"
                )
                return False

            self.log_success("Plain note stored as plaintext (correct)")

            if note.is_secret:
                self.log_error("Plain note should not have is_secret=true")
                return False

            self.log_success("Plain note is_secret flag is false (correct)")
            return True

        except Exception as e:
            self.log_error(f"Plain note test failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def run_all_tests(self):
        """Run all tests"""
        print("\n" + "="*60)
        print("END-TO-END ENCRYPTION TEST SUITE")
        print("="*60)

        # Setup
        if not self.setup_test_user():
            return False

        # Test 1: Encryption API
        encrypted_content = self.test_vault_encrypt_api()
        if not encrypted_content:
            return False

        # Test 2: Create secret note
        note_id = self.test_create_secret_note(encrypted_content)
        if not note_id:
            return False

        # Test 3: Decrypt API
        if not self.test_decrypt_api(note_id):
            return False

        # Test 4: Plain notes
        if not self.test_plain_note_no_encryption():
            return False

        # Summary
        self.print_summary()

        return len(self.errors) == 0

    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        print(f"[PASS] Tests passed: {len(self.successes)}")
        print(f"[FAIL] Tests failed: {len(self.errors)}")

        if self.errors:
            print("\nErrors:")
            for error in self.errors:
                print(f"  {error}")

        print("\n" + "="*60)


if __name__ == '__main__':
    suite = E2EEncryptionTestSuite()
    success = suite.run_all_tests()
    sys.exit(0 if success else 1)
