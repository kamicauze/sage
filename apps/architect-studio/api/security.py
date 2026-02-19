"""
Security helpers for Architect API.
"""
from __future__ import annotations

import hmac
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from fastapi import HTTPException, Request

from architect.paths import PROJECTS_DIR, REPO_ROOT

_PROJECT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_DEFAULT_CORS_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:19006",
    "http://127.0.0.1:19006",
)
_AUTH_EXEMPT_PREFIXES = ("/docs", "/redoc", "/openapi.json")


@dataclass(frozen=True)
class APISecurityConfig:
    token: str | None
    auth_required: bool
    cors_origins: list[str]
    auth_exempt_paths: tuple[str, ...] = ("/", "/stats/health")


def _parse_bool(raw: str | None, default: bool = False) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _normalized_allowed_roots(roots: Iterable[Path]) -> list[Path]:
    normalized: list[Path] = []
    for root in roots:
        normalized.append(root.resolve())
    return normalized


def parse_cors_origins(raw: str | None) -> list[str]:
    if not raw:
        return list(_DEFAULT_CORS_ORIGINS)

    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    if not origins:
        return list(_DEFAULT_CORS_ORIGINS)
    if "*" in origins and len(origins) > 1:
        raise ValueError("SAGE_ARCHITECT_API_CORS_ORIGINS cannot mix '*' with specific origins")
    return origins


def load_api_security_config() -> APISecurityConfig:
    token = (os.getenv("SAGE_ARCHITECT_API_TOKEN") or "").strip() or None
    auth_required = _parse_bool(
        os.getenv("SAGE_ARCHITECT_API_AUTH_REQUIRED"),
        default=token is not None,
    )
    if auth_required and not token:
        raise RuntimeError(
            "SAGE_ARCHITECT_API_AUTH_REQUIRED is true but SAGE_ARCHITECT_API_TOKEN is not configured"
        )

    return APISecurityConfig(
        token=token,
        auth_required=auth_required,
        cors_origins=parse_cors_origins(os.getenv("SAGE_ARCHITECT_API_CORS_ORIGINS")),
    )


def path_requires_auth(path: str, config: APISecurityConfig) -> bool:
    if not config.auth_required:
        return False
    if path in config.auth_exempt_paths:
        return False
    return not any(path.startswith(prefix) for prefix in _AUTH_EXEMPT_PREFIXES)


def extract_request_token(request: Request) -> str | None:
    auth_header = request.headers.get("authorization", "")
    if auth_header:
        parts = auth_header.split(None, 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1].strip()
            if token:
                return token

    for header in ("x-architect-token", "x-api-token"):
        value = request.headers.get(header, "").strip()
        if value:
            return value
    return None


def is_request_authorized(request: Request, config: APISecurityConfig) -> bool:
    if not config.auth_required:
        return True

    provided = extract_request_token(request)
    if not provided or not config.token:
        return False
    return hmac.compare_digest(provided, config.token)


def validate_project_id(project_id: str) -> str:
    if not _PROJECT_ID_RE.fullmatch(project_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid project_id: use letters, numbers, underscores, and hyphens only",
        )
    return project_id


def _resolve_path_in_roots(
    raw_path: str,
    *,
    allowed_roots: Sequence[Path],
    field_name: str,
    must_exist: bool,
    require_file: bool,
) -> Path:
    if not raw_path or not raw_path.strip():
        raise HTTPException(status_code=400, detail=f"{field_name} must not be empty")

    candidate = Path(raw_path.strip()).expanduser()
    if any(part == ".." for part in candidate.parts):
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}: path traversal is not allowed")

    roots = _normalized_allowed_roots(allowed_roots)

    if candidate.is_absolute():
        resolved_candidates = [candidate.resolve()]
    else:
        resolved_candidates = [(root / candidate).resolve() for root in roots]

    saw_in_scope = False
    missing_in_scope = False

    for resolved in resolved_candidates:
        if not any(_is_within(resolved, root) for root in roots):
            continue
        saw_in_scope = True

        if must_exist and not resolved.exists():
            missing_in_scope = True
            continue

        if require_file and resolved.exists() and not resolved.is_file():
            raise HTTPException(status_code=400, detail=f"{field_name} must point to a file: {raw_path}")

        return resolved

    if saw_in_scope and must_exist and missing_in_scope:
        raise HTTPException(status_code=404, detail=f"{field_name} not found: {raw_path}")

    raise HTTPException(
        status_code=400,
        detail=f"Invalid {field_name}: path is outside allowed roots",
    )


def resolve_manifest_path(manifest_path: str) -> Path:
    resolved = _resolve_path_in_roots(
        manifest_path,
        allowed_roots=(PROJECTS_DIR, REPO_ROOT),
        field_name="manifest_path",
        must_exist=True,
        require_file=True,
    )
    if resolved.suffix.lower() not in {".yaml", ".yml"}:
        raise HTTPException(status_code=400, detail="manifest_path must reference a .yaml/.yml file")
    return resolved


def resolve_repo_file_path(file_path: str, *, manifest_repo_path: str | None = None) -> Path:
    allowed_roots: list[Path] = [REPO_ROOT]

    if manifest_repo_path:
        manifest_repo = Path(manifest_repo_path)
        if not manifest_repo.is_absolute():
            manifest_repo = (REPO_ROOT / manifest_repo).resolve()
        else:
            manifest_repo = manifest_repo.resolve()
        if _is_within(manifest_repo, REPO_ROOT):
            allowed_roots.insert(0, manifest_repo)

    return _resolve_path_in_roots(
        file_path,
        allowed_roots=allowed_roots,
        field_name="file_path",
        must_exist=True,
        require_file=True,
    )
