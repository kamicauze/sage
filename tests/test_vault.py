"""
Tests for Credential Vault (Phase 5).

Covers:
- Encrypt/decrypt roundtrip
- Store, retrieve, delete, list operations
- Auto-generated encryption key
- Master password key derivation
- Atomic write safety
"""

import os
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Check if cryptography is available
try:
    from cryptography.fernet import Fernet
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


@unittest.skipUnless(HAS_CRYPTO, "cryptography package not installed")
class TestVaultBasicOperations(unittest.TestCase):
    """Test basic vault CRUD."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.vault_path = os.path.join(self.tmpdir, "test_vault.enc")
        from shared.vault import CredentialVault
        self.vault = CredentialVault(vault_path=self.vault_path)

    def test_store_and_retrieve(self):
        self.vault.store("api_key", "sk-test-12345")
        result = self.vault.retrieve("api_key")
        self.assertEqual(result, "sk-test-12345")

    def test_retrieve_nonexistent(self):
        result = self.vault.retrieve("does_not_exist")
        self.assertIsNone(result)

    def test_overwrite_existing(self):
        self.vault.store("key", "value1")
        self.vault.store("key", "value2")
        self.assertEqual(self.vault.retrieve("key"), "value2")

    def test_delete_existing(self):
        self.vault.store("key", "value")
        deleted = self.vault.delete("key")
        self.assertTrue(deleted)
        self.assertIsNone(self.vault.retrieve("key"))

    def test_delete_nonexistent(self):
        deleted = self.vault.delete("nope")
        self.assertFalse(deleted)

    def test_list_keys(self):
        self.vault.store("key_a", "val_a")
        self.vault.store("key_b", "val_b")
        self.vault.store("key_c", "val_c")
        keys = self.vault.list_keys()
        self.assertEqual(sorted(keys), ["key_a", "key_b", "key_c"])

    def test_list_keys_empty(self):
        keys = self.vault.list_keys()
        self.assertEqual(keys, [])


@unittest.skipUnless(HAS_CRYPTO, "cryptography package not installed")
class TestVaultEncryption(unittest.TestCase):
    """Test that data is actually encrypted on disk."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.vault_path = os.path.join(self.tmpdir, "encrypted.enc")

    def test_file_is_encrypted(self):
        from shared.vault import CredentialVault
        vault = CredentialVault(vault_path=self.vault_path)
        vault.store("secret", "super-secret-value-123")

        # Read raw file — should NOT contain plaintext
        raw = open(self.vault_path, "rb").read()
        self.assertNotIn(b"super-secret-value-123", raw)
        self.assertNotIn(b"secret", raw)
        self.assertTrue(len(raw) > 0)

    def test_different_vaults_independent(self):
        from shared.vault import CredentialVault
        v1 = CredentialVault(vault_path=os.path.join(self.tmpdir, "v1.enc"))
        v2 = CredentialVault(vault_path=os.path.join(self.tmpdir, "v2.enc"))

        v1.store("key", "value_from_v1")
        v2.store("key", "value_from_v2")

        self.assertEqual(v1.retrieve("key"), "value_from_v1")
        self.assertEqual(v2.retrieve("key"), "value_from_v2")


@unittest.skipUnless(HAS_CRYPTO, "cryptography package not installed")
class TestVaultKeyManagement(unittest.TestCase):
    """Test key generation and derivation."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_auto_generated_key_persists(self):
        from shared.vault import CredentialVault
        vault_path = os.path.join(self.tmpdir, "auto.enc")

        # First vault creates key
        v1 = CredentialVault(vault_path=vault_path)
        v1.store("test", "hello")

        # Key file should exist
        key_file = os.path.join(self.tmpdir, ".vault_key")
        self.assertTrue(os.path.exists(key_file))

        # Second vault reads same key
        v2 = CredentialVault(vault_path=vault_path)
        self.assertEqual(v2.retrieve("test"), "hello")

    def test_master_password_derivation(self):
        from shared.vault import CredentialVault
        vault_path = os.path.join(self.tmpdir, "password.enc")

        # Create with master password
        v1 = CredentialVault(vault_path=vault_path, key_source="my-master-password")
        v1.store("key", "encrypted-value")

        # Reopen with same password
        v2 = CredentialVault(vault_path=vault_path, key_source="my-master-password")
        self.assertEqual(v2.retrieve("key"), "encrypted-value")

    def test_wrong_password_fails(self):
        from shared.vault import CredentialVault
        vault_path = os.path.join(self.tmpdir, "wrong.enc")

        v1 = CredentialVault(vault_path=vault_path, key_source="correct-password")
        v1.store("key", "secret")

        # Wrong password should fail to decrypt (returns empty dict on error)
        v2 = CredentialVault(vault_path=vault_path, key_source="wrong-password")
        result = v2.retrieve("key")
        self.assertIsNone(result)  # Decrypt failed → empty dict


@unittest.skipUnless(HAS_CRYPTO, "cryptography package not installed")
class TestVaultAtomicWrite(unittest.TestCase):
    """Test that writes are atomic (tmp file + rename)."""

    def test_no_partial_writes(self):
        from shared.vault import CredentialVault
        tmpdir = tempfile.mkdtemp()
        vault_path = os.path.join(tmpdir, "atomic.enc")

        vault = CredentialVault(vault_path=vault_path)
        vault.store("key1", "val1")
        vault.store("key2", "val2")
        vault.store("key3", "val3")

        # No .tmp files should remain
        files = os.listdir(tmpdir)
        tmp_files = [f for f in files if f.endswith(".tmp")]
        self.assertEqual(len(tmp_files), 0)


class TestVaultWithoutCryptography(unittest.TestCase):
    """Test behavior when cryptography is not installed."""

    def test_has_cryptography_flag(self):
        from shared.vault import HAS_CRYPTOGRAPHY
        # This just verifies the flag exists and is boolean
        self.assertIsInstance(HAS_CRYPTOGRAPHY, bool)


if __name__ == "__main__":
    unittest.main()
