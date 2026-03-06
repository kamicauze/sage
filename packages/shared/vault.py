"""
Credential Vault
Encrypted at-rest storage for OAuth tokens, API keys, and other secrets.

Uses Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256).
Key can be provided via SAGE_VAULT_KEY env var or auto-generated on first use.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

try:
    from cryptography.fernet import Fernet
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False


def _resolve_path(raw: str) -> Path:
    base = Path(raw).expanduser()
    if not base.is_absolute():
        base = Path(os.getcwd()) / base
    return base.resolve()


class CredentialVault:
    """Encrypted at-rest credential storage using Fernet."""

    def __init__(
        self,
        vault_path: str = None,
        key_source: str = None,
    ):
        raw = vault_path or os.getenv("SAGE_VAULT_PATH", ".sage_memory/vault.enc")
        self._path = _resolve_path(raw)
        self._lock = Lock()
        self._fernet = self._init_fernet(key_source)

    def _init_fernet(self, key_source: str = None):
        """Initialize Fernet cipher from key source."""
        if not HAS_CRYPTOGRAPHY:
            raise ImportError(
                "cryptography package is required for the credential vault. "
                "Install with: pip install cryptography"
            )

        master = key_source or os.getenv("SAGE_VAULT_KEY", "")

        if not master:
            # Auto-generate and persist key on first use
            key_file = self._path.parent / ".vault_key"
            if key_file.exists():
                master = key_file.read_text(encoding="utf-8").strip()
            else:
                master = Fernet.generate_key().decode("ascii")
                key_file.parent.mkdir(parents=True, exist_ok=True)
                key_file.write_text(master, encoding="utf-8")
                try:
                    os.chmod(str(key_file), 0o600)
                except OSError:
                    pass  # Windows doesn't support chmod the same way
                print(f"[Vault] Generated new encryption key at {key_file}")
            return Fernet(master.encode("ascii") if isinstance(master, str) else master)

        # Derive key from user-provided master password via PBKDF2
        dk = hashlib.pbkdf2_hmac(
            "sha256",
            master.encode("utf-8"),
            b"sage-vault-salt-v1",
            100_000,
        )
        key = base64.urlsafe_b64encode(dk[:32])
        return Fernet(key)

    def store(self, name: str, value: str) -> None:
        """Store a credential."""
        with self._lock:
            data = self._load()
            data[name] = value
            self._save(data)

    def retrieve(self, name: str) -> Optional[str]:
        """Retrieve a credential by name. Returns None if not found."""
        with self._lock:
            data = self._load()
            return data.get(name)

    def delete(self, name: str) -> bool:
        """Delete a credential. Returns True if it existed."""
        with self._lock:
            data = self._load()
            if name in data:
                del data[name]
                self._save(data)
                return True
            return False

    def list_keys(self) -> List[str]:
        """List all stored credential names (not values)."""
        with self._lock:
            return list(self._load().keys())

    def _load(self) -> Dict[str, str]:
        """Load and decrypt vault contents."""
        if not self._path.exists():
            return {}
        try:
            encrypted = self._path.read_bytes()
            decrypted = self._fernet.decrypt(encrypted)
            data = json.loads(decrypted.decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception as e:
            print(f"[Vault] Error loading vault: {e}")
            return {}

    def _save(self, data: Dict[str, str]) -> None:
        """Encrypt and save vault contents (atomic write)."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        plaintext = json.dumps(data, sort_keys=True).encode("utf-8")
        encrypted = self._fernet.encrypt(plaintext)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_bytes(encrypted)
        tmp.rename(self._path)


# --- Singleton ---

_vault: Optional[CredentialVault] = None


def get_vault() -> CredentialVault:
    """Get the shared vault instance."""
    global _vault
    if _vault is None:
        _vault = CredentialVault()
    return _vault
