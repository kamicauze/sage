"""
Credential Vault API for Sage.

Provides REST endpoints for storing, retrieving, and managing
encrypted credentials. All values are encrypted at rest using Fernet.
"""
from __future__ import annotations

import sys
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# Ensure shared packages are importable
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

router = APIRouter(prefix="/vault", tags=["vault"])

_vault_instance = None
_VAULT_AVAILABLE = True


def _get_vault():
    global _vault_instance, _VAULT_AVAILABLE
    if not _VAULT_AVAILABLE:
        raise HTTPException(
            status_code=501,
            detail="Credential vault unavailable. Install: pip install cryptography",
        )
    if _vault_instance is None:
        try:
            from shared.vault import CredentialVault
            _vault_instance = CredentialVault()
        except ImportError:
            _VAULT_AVAILABLE = False
            raise HTTPException(
                status_code=501,
                detail="Credential vault unavailable. Install: pip install cryptography",
            )
    return _vault_instance


class VaultStoreRequest(BaseModel):
    name: str = Field(..., min_length=1, description="Credential name/key")
    value: str = Field(..., min_length=1, description="Credential value (will be encrypted)")


@router.get("/keys")
def list_vault_keys() -> Dict[str, Any]:
    """List all stored credential names (values are NOT returned)."""
    vault = _get_vault()
    keys = vault.list_keys()
    return {"success": True, "count": len(keys), "keys": keys}


@router.post("/store")
def store_credential(request: VaultStoreRequest) -> Dict[str, Any]:
    """Store or update an encrypted credential."""
    vault = _get_vault()
    vault.store(request.name, request.value)
    return {"success": True, "name": request.name}


@router.get("/retrieve/{name}")
def retrieve_credential(name: str) -> Dict[str, Any]:
    """Retrieve a credential by name."""
    vault = _get_vault()
    value = vault.retrieve(name)
    if value is None:
        raise HTTPException(status_code=404, detail=f"Credential '{name}' not found.")
    return {"success": True, "name": name, "value": value}


@router.delete("/{name}")
def delete_credential(name: str) -> Dict[str, Any]:
    """Delete a credential."""
    vault = _get_vault()
    deleted = vault.delete(name)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Credential '{name}' not found.")
    return {"success": True, "deleted": name}
