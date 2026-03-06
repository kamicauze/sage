from __future__ import annotations

import json
import os
import platform
import shlex
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

PROJECT_REGISTRY_PATH = Path(
    os.getenv("SAGE_PROJECT_GIT_STORE_PATH", ".sage_memory/projects/git_registry.json")
).expanduser()
CONTROL_CONFIG_PATH = Path(
    os.getenv("SAGE_PROJECT_CONTROL_CONFIG_PATH", ".sage_memory/projects/control_plane.json")
).expanduser()
MIRROR_QUEUE_PATH = Path(
    os.getenv("SAGE_PROJECT_MIRROR_QUEUE_PATH", ".sage_memory/projects/mirror_queue.json")
).expanduser()

DEFAULT_PROVIDER_TIMEOUT_SEC = float(os.getenv("SAGE_PROJECT_PROVIDER_TIMEOUT_SEC", "900"))
DEFAULT_COMMAND_TIMEOUT_SEC = float(os.getenv("SAGE_PROJECT_COMMAND_TIMEOUT_SEC", "45"))
PROJECT_DOC_INLINE_COUNT = int(os.getenv("SAGE_PROJECT_DOC_INLINE_COUNT", "2"))
PROJECT_DOC_INLINE_CHARS = int(os.getenv("SAGE_PROJECT_DOC_INLINE_CHARS", "2200"))
PROJECT_DOC_INLINE_TIMEOUT_SEC = float(os.getenv("SAGE_PROJECT_DOC_INLINE_TIMEOUT_SEC", "6"))


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def current_node_id() -> str:
    return (
        (os.getenv("SAGE_NODE_ID") or "").strip()
        or (platform.node() or "").strip()
        or "unknown-node"
    )


def _architect_api_base_url() -> str:
    return (os.getenv("SAGE_ARCHITECT_API_URL") or "http://127.0.0.1:8000").strip().rstrip("/")


def _read_json(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    try:
        if not path.exists():
            return dict(default)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass
    return dict(default)


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temp_path.replace(path)


def load_project_registry() -> Dict[str, Any]:
    payload = _read_json(PROJECT_REGISTRY_PATH, {"version": 1, "projects": {}})
    payload.setdefault("version", 1)
    payload.setdefault("projects", {})
    if not isinstance(payload["projects"], dict):
        payload["projects"] = {}
    return payload


def load_control_config() -> Dict[str, Any]:
    payload = _read_json(
        CONTROL_CONFIG_PATH,
        {
            "version": 1,
            "default_executor": "codex_cli",
            "default_target_node": current_node_id(),
            "nodes": {},
        },
    )
    payload.setdefault("version", 1)
    payload.setdefault("nodes", {})
    payload.setdefault("default_executor", "codex_cli")
    payload.setdefault("default_target_node", current_node_id())
    if not isinstance(payload["nodes"], dict):
        payload["nodes"] = {}
    return payload


def save_control_config(payload: Dict[str, Any]) -> None:
    payload = dict(payload)
    payload["updated_at"] = utc_now_iso()
    _write_json(CONTROL_CONFIG_PATH, payload)


def load_mirror_queue() -> Dict[str, Any]:
    payload = _read_json(MIRROR_QUEUE_PATH, {"version": 1, "items": []})
    payload.setdefault("version", 1)
    payload.setdefault("items", [])
    if not isinstance(payload["items"], list):
        payload["items"] = []
    return payload


def save_mirror_queue(payload: Dict[str, Any]) -> None:
    payload = dict(payload)
    payload["updated_at"] = utc_now_iso()
    _write_json(MIRROR_QUEUE_PATH, payload)


def upsert_node(node_id: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    clean_node_id = str(node_id or "").strip()
    if not clean_node_id:
        raise RuntimeError("Missing node_id.")
    config = load_control_config()
    existing = dict(config["nodes"].get(clean_node_id) or {})
    merged = {**existing, **spec}
    merged["id"] = clean_node_id
    config["nodes"][clean_node_id] = merged
    save_control_config(config)
    return merged


def list_nodes() -> List[Dict[str, Any]]:
    config = load_control_config()
    return [dict(value, id=key) for key, value in sorted(config.get("nodes", {}).items())]


def _collect_git_snapshot(repo_path: str, node_id: Optional[str] = None) -> Dict[str, Any]:
    resolved = str(Path(repo_path).expanduser().resolve())
    if not Path(resolved).exists():
        raise RuntimeError(f"Repo path does not exist: {resolved}")

    def run_git(args: List[str]) -> str:
        result = subprocess.run(
            ["git"] + args,
            cwd=resolved,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "git command failed").strip())
        return (result.stdout or "").strip()

    run_git(["rev-parse", "--is-inside-work-tree"])
    status_lines = run_git(["status", "--porcelain"])
    try:
        remote_url = run_git(["remote", "get-url", "origin"])
    except Exception:
        remote_url = ""

    dirty_files = [line for line in status_lines.splitlines() if line.strip()]
    return {
        "node_id": node_id or current_node_id(),
        "path": resolved,
        "branch": run_git(["rev-parse", "--abbrev-ref", "HEAD"]),
        "head_sha": run_git(["rev-parse", "--short", "HEAD"]),
        "head_subject": run_git(["log", "-1", "--pretty=%s"]),
        "head_author": run_git(["log", "-1", "--pretty=%an"]),
        "head_time": run_git(["log", "-1", "--date=iso-strict", "--pretty=%cI"]),
        "dirty": bool(dirty_files),
        "dirty_count": len(dirty_files),
        "remote_url": remote_url,
        "last_seen": utc_now_iso(),
    }


def register_or_update_project(
    project_id: str,
    repo_path: str,
    *,
    aliases: Optional[List[str]] = None,
    node_id: Optional[str] = None,
) -> Dict[str, Any]:
    snapshot = _collect_git_snapshot(repo_path, node_id=node_id)
    return _save_project_snapshot(project_id, snapshot, aliases=aliases)


def _node_spec_for_snapshot(node_id: str) -> Dict[str, Any]:
    config = load_control_config()
    spec = dict(config.get("nodes", {}).get(node_id) or {})
    if spec:
        return spec
    if node_id == current_node_id():
        return {"id": node_id, "transport": "local"}
    raise RuntimeError(f"Unknown node '{node_id}'.")


def _save_project_snapshot(
    project_id: str,
    snapshot: Dict[str, Any],
    *,
    aliases: Optional[List[str]] = None,
) -> Dict[str, Any]:
    registry = load_project_registry()
    project = dict(registry["projects"].get(project_id) or {})
    merged_aliases = list(project.get("aliases") or [])
    for alias in aliases or []:
        clean = str(alias or "").strip()
        if clean and clean not in merged_aliases:
            merged_aliases.append(clean)

    project.update(
        {
            "project_id": project_id,
            "aliases": merged_aliases,
            "remote_url": snapshot.get("remote_url") or project.get("remote_url", ""),
            "google_assets": list(project.get("google_assets") or []),
            "nodes": dict(project.get("nodes") or {}),
        }
    )
    project["nodes"][str(snapshot["node_id"])] = dict(snapshot)
    registry["projects"][project_id] = project
    registry["updated_at"] = utc_now_iso()
    _write_json(PROJECT_REGISTRY_PATH, registry)
    return project


def get_project(project_id: str) -> Optional[Dict[str, Any]]:
    return load_project_registry().get("projects", {}).get(project_id)


def get_project_snapshot(project_id: str, node_id: str) -> Optional[Dict[str, Any]]:
    project = get_project(project_id)
    if not project:
        return None
    return dict((project.get("nodes") or {}).get(node_id) or {}) or None


def list_project_google_assets(project_id: str) -> List[Dict[str, Any]]:
    project = get_project(project_id)
    if not project:
        raise RuntimeError(f"Unknown project '{project_id}'.")
    assets = project.get("google_assets") or []
    if not isinstance(assets, list):
        return []
    return [dict(asset) for asset in assets if isinstance(asset, dict)]


def upsert_project_google_asset(project_id: str, asset: Dict[str, Any]) -> Dict[str, Any]:
    clean_project_id = str(project_id or "").strip()
    if not clean_project_id:
        raise RuntimeError("Missing project_id.")
    project = get_project(clean_project_id)
    if not project:
        raise RuntimeError(f"Unknown project '{clean_project_id}'.")

    clean_asset = {
        "asset_id": str(asset.get("asset_id") or "").strip(),
        "kind": str(asset.get("kind") or "").strip() or "file",
        "title": str(asset.get("title") or "").strip() or "Untitled",
        "url": str(asset.get("url") or "").strip(),
        "mime_type": str(asset.get("mime_type") or "").strip(),
        "role": str(asset.get("role") or "").strip(),
        "source": str(asset.get("source") or "google_drive").strip(),
        "updated_at": utc_now_iso(),
    }
    if not clean_asset["asset_id"] and not clean_asset["url"]:
        raise RuntimeError("Google asset requires asset_id or url.")

    registry = load_project_registry()
    project_record = dict(registry["projects"].get(clean_project_id) or {})
    assets = [dict(item) for item in (project_record.get("google_assets") or []) if isinstance(item, dict)]

    def is_same(existing: Dict[str, Any]) -> bool:
        existing_id = str(existing.get("asset_id") or "").strip()
        existing_url = str(existing.get("url") or "").strip()
        return bool(
            (clean_asset["asset_id"] and existing_id == clean_asset["asset_id"]) or
            (clean_asset["url"] and existing_url == clean_asset["url"])
        )

    replaced = False
    next_assets: List[Dict[str, Any]] = []
    for existing in assets:
        if is_same(existing):
            merged = dict(existing)
            merged.update({key: value for key, value in clean_asset.items() if value})
            next_assets.append(merged)
            replaced = True
        else:
            next_assets.append(existing)
    if not replaced:
        next_assets.append(clean_asset)

    project_record["google_assets"] = next_assets
    registry["projects"][clean_project_id] = project_record
    registry["updated_at"] = utc_now_iso()
    _write_json(PROJECT_REGISTRY_PATH, registry)
    return {
        "project_id": clean_project_id,
        "google_assets": [dict(item) for item in next_assets],
    }


def _build_ssh_target(spec: Dict[str, Any]) -> str:
    host = str(spec.get("ssh_host") or spec.get("host") or "").strip()
    if not host:
        raise RuntimeError("SSH node missing host/ssh_host.")
    user = str(spec.get("ssh_user") or spec.get("user") or "").strip()
    if user:
        return f"{user}@{host}"
    return host


def _runner_prefix(spec: Dict[str, Any]) -> List[str]:
    ssh_command = str(spec.get("ssh_command") or "ssh").strip()
    prefix = shlex.split(ssh_command)
    if not prefix:
        prefix = ["ssh"]
    prefix.append(_build_ssh_target(spec))
    return prefix


def run_command_on_node(
    node_id: str,
    spec: Dict[str, Any],
    *,
    argv: List[str],
    repo_path: Optional[str] = None,
    stdin_text: Optional[str] = None,
    timeout_sec: float = DEFAULT_COMMAND_TIMEOUT_SEC,
) -> Dict[str, Any]:
    clean_argv = [str(part) for part in argv if str(part)]
    if not clean_argv:
        raise RuntimeError("Empty command.")

    transport = str(spec.get("transport") or "local").strip().lower()
    if transport == "local":
        try:
            result = subprocess.run(
                clean_argv,
                cwd=repo_path or None,
                input=stdin_text,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
            )
        except subprocess.TimeoutExpired as exc:
            return {
                "node_id": node_id,
                "transport": transport,
                "argv": clean_argv,
                "returncode": 124,
                "stdout": (exc.stdout or "").strip() if isinstance(exc.stdout, str) else "",
                "stderr": f"Command timed out after {timeout_sec:.1f}s",
                "success": False,
                "timeout": True,
            }
        return {
            "node_id": node_id,
            "transport": transport,
            "argv": clean_argv,
            "returncode": result.returncode,
            "stdout": (result.stdout or "").strip(),
            "stderr": (result.stderr or "").strip(),
            "success": result.returncode == 0,
        }

    if transport == "ssh":
        repo_clause = f"cd {shlex.quote(repo_path)} && " if repo_path else ""
        command_str = repo_clause + shlex.join(clean_argv)
        remote_cmd = _runner_prefix(spec) + ["bash", "-lc", shlex.quote(command_str)]
        try:
            result = subprocess.run(
                remote_cmd,
                input=stdin_text,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
            )
        except subprocess.TimeoutExpired as exc:
            return {
                "node_id": node_id,
                "transport": transport,
                "argv": clean_argv,
                "returncode": 124,
                "stdout": (exc.stdout or "").strip() if isinstance(exc.stdout, str) else "",
                "stderr": f"Command timed out after {timeout_sec:.1f}s",
                "success": False,
                "timeout": True,
                "remote_command": command_str,
            }
        return {
            "node_id": node_id,
            "transport": transport,
            "argv": clean_argv,
            "returncode": result.returncode,
            "stdout": (result.stdout or "").strip(),
            "stderr": (result.stderr or "").strip(),
            "success": result.returncode == 0,
            "remote_command": command_str,
        }

    raise RuntimeError(f"Unsupported transport '{transport}' for node '{node_id}'.")


def _dirty_probe(
    node_id: str,
    spec: Dict[str, Any],
    repo_path: str,
    *,
    fallback_count: int = 0,
    timeout_sec: float = 5.0,
) -> Dict[str, Any]:
    result = run_command_on_node(
        node_id,
        spec,
        argv=["git", "status", "--short", "--untracked-files=no"],
        repo_path=repo_path,
        timeout_sec=timeout_sec,
    )
    if result.get("success"):
        dirty_files = [line for line in str(result.get("stdout") or "").splitlines() if line.strip()]
        return {
            "dirty_files": dirty_files,
            "dirty": bool(dirty_files),
            "dirty_count": len(dirty_files),
            "dirty_probe_error": "",
        }
    return {
        "dirty_files": [],
        "dirty": None,
        "dirty_count": fallback_count,
        "dirty_probe_error": str(result.get("stderr") or result.get("stdout") or "dirty probe failed").strip(),
    }


def collect_project_snapshot(
    repo_path: str,
    *,
    node_id: Optional[str] = None,
) -> Dict[str, Any]:
    effective_node_id = str(node_id or current_node_id()).strip() or current_node_id()
    spec = _node_spec_for_snapshot(effective_node_id)
    transport = str(spec.get("transport") or "local").strip().lower()
    if transport == "local":
        return _collect_git_snapshot(repo_path, node_id=effective_node_id)

    probe = run_command_on_node(
        effective_node_id,
        spec,
        argv=["git", "rev-parse", "--is-inside-work-tree"],
        repo_path=repo_path,
    )
    if not probe.get("success"):
        raise RuntimeError((probe.get("stderr") or probe.get("stdout") or "git probe failed").strip())

    resolved = run_command_on_node(
        effective_node_id,
        spec,
        argv=["pwd", "-P"],
        repo_path=repo_path,
    )
    if not resolved.get("success"):
        raise RuntimeError((resolved.get("stderr") or resolved.get("stdout") or "pwd failed").strip())

    def require_git(args: List[str]) -> str:
        result = run_command_on_node(effective_node_id, spec, argv=["git"] + args, repo_path=repo_path)
        if not result.get("success"):
            raise RuntimeError((result.get("stderr") or result.get("stdout") or "git command failed").strip())
        return str(result.get("stdout") or "").strip()

    def optional_git(args: List[str]) -> str:
        result = run_command_on_node(effective_node_id, spec, argv=["git"] + args, repo_path=repo_path)
        if not result.get("success"):
            return ""
        return str(result.get("stdout") or "").strip()

    dirty = _dirty_probe(effective_node_id, spec, repo_path, timeout_sec=5.0)
    return {
        "node_id": effective_node_id,
        "path": str(resolved.get("stdout") or "").strip(),
        "branch": require_git(["rev-parse", "--abbrev-ref", "HEAD"]),
        "head_sha": require_git(["rev-parse", "--short", "HEAD"]),
        "head_subject": require_git(["log", "-1", "--pretty=%s"]),
        "head_author": require_git(["log", "-1", "--pretty=%an"]),
        "head_time": require_git(["log", "-1", "--date=iso-strict", "--pretty=%cI"]),
        "dirty": dirty["dirty"],
        "dirty_count": dirty["dirty_count"],
        "dirty_probe_error": dirty["dirty_probe_error"],
        "remote_url": optional_git(["remote", "get-url", "origin"]),
        "last_seen": utc_now_iso(),
    }


def sync_project_snapshot(
    project_id: str,
    repo_path: str,
    *,
    aliases: Optional[List[str]] = None,
    node_id: Optional[str] = None,
) -> Dict[str, Any]:
    snapshot = collect_project_snapshot(repo_path, node_id=node_id)
    return _save_project_snapshot(project_id, snapshot, aliases=aliases)


def check_node_online(node_id: str, spec: Dict[str, Any], timeout_sec: float = 5.0) -> bool:
    if str(spec.get("transport") or "local").lower() == "local":
        return True
    result = run_command_on_node(
        node_id,
        spec,
        argv=["/usr/bin/env", "true"],
        timeout_sec=timeout_sec,
    )
    return bool(result.get("success"))


def resolve_execution_target(
    project_id: str,
    preferred_node: Optional[str] = None,
) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
    config = load_control_config()
    project = get_project(project_id)
    if not project:
        raise RuntimeError(f"Unknown project '{project_id}'.")

    project_nodes = dict(project.get("nodes") or {})
    if not project_nodes:
        raise RuntimeError(f"Project '{project_id}' has no known node snapshots.")

    candidate_ids: List[str] = []
    if preferred_node:
        candidate_ids.append(preferred_node)

    default_target = str(config.get("default_target_node") or "").strip()
    if default_target and default_target not in candidate_ids:
        candidate_ids.append(default_target)

    for node_id in project_nodes.keys():
        if node_id not in candidate_ids:
            candidate_ids.append(node_id)

    fallback = None
    for node_id in candidate_ids:
        snapshot = dict(project_nodes.get(node_id) or {})
        if not snapshot:
            continue
        spec = dict(config.get("nodes", {}).get(node_id) or {})
        if not spec:
            if node_id == current_node_id():
                spec = {"id": node_id, "transport": "local"}
            else:
                fallback = fallback or (node_id, {"id": node_id, "transport": "ssh"}, snapshot)
                continue
        if fallback is None:
            fallback = (node_id, spec, snapshot)
        if check_node_online(node_id, spec):
            return node_id, spec, snapshot

    if fallback:
        return fallback
    raise RuntimeError(f"No execution target available for project '{project_id}'.")


def project_status(project_id: str, preferred_node: Optional[str] = None) -> Dict[str, Any]:
    project = get_project(project_id)
    if not project:
        raise RuntimeError(f"Unknown project '{project_id}'.")
    node_id, spec, snapshot = resolve_execution_target(project_id, preferred_node)
    repo_path = str(snapshot.get("path") or "").strip()
    if not repo_path:
        raise RuntimeError(f"Project '{project_id}' has no path for node '{node_id}'.")

    branch = run_command_on_node(node_id, spec, argv=["git", "branch", "--show-current"], repo_path=repo_path)
    head = run_command_on_node(node_id, spec, argv=["git", "log", "-1", "--pretty=%H%x09%s%x09%cI"], repo_path=repo_path)
    dirty = _dirty_probe(
        node_id,
        spec,
        repo_path,
        fallback_count=int(snapshot.get("dirty_count") or 0),
        timeout_sec=5.0,
    )
    return {
        "project_id": project_id,
        "node_id": node_id,
        "repo_path": repo_path,
        "transport": spec.get("transport", "local"),
        "online": check_node_online(node_id, spec),
        "branch": (branch.get("stdout") or snapshot.get("branch") or "").strip(),
        "head": (head.get("stdout") or "").strip(),
        "dirty": dirty["dirty"],
        "dirty_count": dirty["dirty_count"],
        "dirty_files": dirty["dirty_files"],
        "dirty_probe_error": dirty["dirty_probe_error"],
        "google_assets": [dict(item) for item in (project.get("google_assets") or []) if isinstance(item, dict)],
        "snapshot": snapshot,
    }


def _provider_env_var(provider: str) -> str:
    mapping = {
        "codex_cli": "SAGE_CODEX_CLI_CMD",
        "claude_cli": "SAGE_CLAUDE_CLI_CMD",
    }
    env_var = mapping.get(provider)
    if not env_var:
        raise RuntimeError(f"Unsupported executor '{provider}'.")
    return env_var


def _provider_command(provider: str) -> str:
    env_var = _provider_env_var(provider)
    command = str(os.getenv(env_var) or "").strip()
    if not command:
        raise RuntimeError(f"{env_var} is not configured.")
    return command


def _fetch_linked_doc_context(google_assets: List[Dict[str, Any]]) -> List[str]:
    snippets: List[str] = []
    base_url = _architect_api_base_url()
    for asset in google_assets[: max(0, PROJECT_DOC_INLINE_COUNT)]:
        source = str(asset.get("source") or "").strip()
        asset_id = str(asset.get("asset_id") or "").strip()
        title = str(asset.get("title") or "Untitled").strip()
        role = str(asset.get("role") or "").strip()
        if source != "google_drive" or not asset_id:
            continue
        try:
            response = requests.get(
                f"{base_url}/google/drive/files/{asset_id}/content",
                params={"max_chars": PROJECT_DOC_INLINE_CHARS},
                timeout=PROJECT_DOC_INLINE_TIMEOUT_SEC,
            )
            if not response.ok:
                continue
            payload = response.json()
            if not isinstance(payload, dict) or not payload.get("content_available"):
                continue
            content = str(payload.get("content") or "").strip()
            if not content:
                continue
            header = f"{title}"
            if role:
                header = f"{header} role={role}"
            snippets.append(f"[DOC CONTENT] {header}\n{content}")
        except Exception:
            continue
    return snippets


def build_chat_prompt(message: str, history: Optional[List[Dict[str, str]]] = None, status: Optional[Dict[str, Any]] = None) -> str:
    blocks: List[str] = []
    if status:
        project_lines = [
            f"[PROJECT] {status.get('project_id')} on {status.get('node_id')}",
            f"[REPO] {status.get('repo_path')}",
            f"[BRANCH] {status.get('branch')}",
            f"[HEAD] {status.get('head')}",
            f"[DIRTY] {len(status.get('dirty_files') or [])} file(s)",
        ]
        google_assets = [dict(item) for item in (status.get("google_assets") or []) if isinstance(item, dict)]
        if google_assets:
            project_lines.append("[DOCS]")
            for asset in google_assets[:6]:
                title = str(asset.get("title") or "Untitled")
                kind = str(asset.get("kind") or "file").strip()
                role = str(asset.get("role") or "").strip()
                url = str(asset.get("url") or "").strip()
                line = f"{title} [{kind}]"
                if role:
                    line = f"{line} role={role}"
                if url:
                    line = f"{line} {url}"
                project_lines.append(line)
        blocks.append("\n".join(project_lines))
        blocks.extend(_fetch_linked_doc_context(google_assets))
    for item in (history or [])[-12:]:
        role = str(item.get("role") or "user").upper()
        content = str(item.get("content") or "").strip()
        if content:
            blocks.append(f"[{role}]\n{content}")
    blocks.append(f"[USER]\n{str(message or '').strip()}")
    return "\n\n".join(blocks).strip()


def run_project_chat(
    *,
    project_id: str,
    preferred_node: Optional[str],
    provider: str,
    message: str,
    history: Optional[List[Dict[str, str]]] = None,
    timeout_sec: float = DEFAULT_PROVIDER_TIMEOUT_SEC,
) -> Dict[str, Any]:
    status = project_status(project_id, preferred_node)
    node_id = str(status["node_id"])
    config = load_control_config()
    spec = dict(config.get("nodes", {}).get(node_id) or {})
    if not spec and node_id == current_node_id():
        spec = {"transport": "local"}
    repo_path = str(status["repo_path"])
    prompt = build_chat_prompt(message, history=history, status=status)
    command = _provider_command(provider)
    argv = shlex.split(command)
    started = time.monotonic()
    result = run_command_on_node(
        node_id,
        spec,
        argv=argv,
        repo_path=repo_path,
        stdin_text=prompt,
        timeout_sec=timeout_sec,
    )
    latency_ms = int((time.monotonic() - started) * 1000)
    if not result.get("success"):
        error_text = result.get("stderr") or result.get("stdout") or f"exit {result.get('returncode')}"
        raise RuntimeError(f"{provider} execution failed on {node_id}: {error_text}")
    return {
        "project_id": project_id,
        "node_id": node_id,
        "provider": provider,
        "model": provider,
        "reply": result.get("stdout", ""),
        "latency_ms": latency_ms,
        "status": status,
    }


def _ensure_backup_repo(target_node_id: str, target_spec: Dict[str, Any], project_id: str) -> str:
    backup_root = str(target_spec.get("backup_repo_root") or "").strip()
    if not backup_root:
        raise RuntimeError(f"Target node '{target_node_id}' missing backup_repo_root.")
    bare_repo_path = str((Path(backup_root).expanduser() / f"{project_id}.git").resolve())
    mkdir_cmd = (
        f"mkdir -p {shlex.quote(str(Path(backup_root).expanduser()))} && "
        f"if [ ! -d {shlex.quote(bare_repo_path)} ]; then git init --bare {shlex.quote(bare_repo_path)}; fi"
    )
    if str(target_spec.get("transport") or "local").lower() == "local":
        result = subprocess.run(
            ["bash", "-lc", mkdir_cmd],
            capture_output=True,
            text=True,
            timeout=DEFAULT_COMMAND_TIMEOUT_SEC,
        )
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "failed to create backup repo").strip())
    else:
        remote_cmd = _runner_prefix(target_spec) + ["bash", "-lc", mkdir_cmd]
        result = subprocess.run(
            remote_cmd,
            capture_output=True,
            text=True,
            timeout=DEFAULT_COMMAND_TIMEOUT_SEC,
        )
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "failed to create backup repo").strip())
    return bare_repo_path


def _backup_git_url(target_node_id: str, target_spec: Dict[str, Any], project_id: str) -> str:
    host = str(target_spec.get("git_host") or target_spec.get("ssh_host") or target_spec.get("host") or "").strip()
    if not host:
        raise RuntimeError(f"Target node '{target_node_id}' missing host for backup URL.")
    user = str(target_spec.get("git_user") or target_spec.get("ssh_user") or target_spec.get("user") or "").strip()
    bare_repo_path = _ensure_backup_repo(target_node_id, target_spec, project_id)
    if user:
        return f"ssh://{user}@{host}{bare_repo_path}"
    return f"ssh://{host}{bare_repo_path}"


def handoff_project(
    project_id: str,
    *,
    source_node: Optional[str] = None,
    target_node: Optional[str] = None,
) -> Dict[str, Any]:
    config = load_control_config()
    project = get_project(project_id)
    if not project:
        raise RuntimeError(f"Unknown project '{project_id}'.")

    effective_source = source_node or current_node_id()
    source_snapshot = dict((project.get("nodes") or {}).get(effective_source) or {})
    if not source_snapshot:
        raise RuntimeError(f"No snapshot for project '{project_id}' on node '{effective_source}'.")
    source_spec = dict(config.get("nodes", {}).get(effective_source) or {})
    if not source_spec and effective_source == current_node_id():
        source_spec = {"transport": "local"}

    effective_target = target_node or str(config.get("default_target_node") or current_node_id())
    target_spec = dict(config.get("nodes", {}).get(effective_target) or {})
    if not target_spec:
        raise RuntimeError(f"Unknown target node '{effective_target}'.")

    repo_path = str(source_snapshot.get("path") or "").strip()
    branch = str(source_snapshot.get("branch") or "main")
    backup_ref = f"refs/heads/backup/{effective_source}/{branch}"
    backup_url = _backup_git_url(effective_target, target_spec, project_id)
    result = run_command_on_node(
        effective_source,
        source_spec,
        argv=["git", "push", backup_url, f"HEAD:{backup_ref}"],
        repo_path=repo_path,
        timeout_sec=DEFAULT_PROVIDER_TIMEOUT_SEC,
    )
    if not result.get("success"):
        raise RuntimeError(result.get("stderr") or result.get("stdout") or "handoff failed")
    return {
        "project_id": project_id,
        "source_node": effective_source,
        "target_node": effective_target,
        "backup_ref": backup_ref,
        "backup_url": backup_url,
        "stdout": result.get("stdout", ""),
    }


def enqueue_mirror_task(
    *,
    project_id: str,
    source_node: str,
    target_node: str,
) -> Dict[str, Any]:
    queue = load_mirror_queue()
    item = {
        "id": f"mirror_{int(time.time() * 1000)}_{project_id}_{source_node}",
        "project_id": project_id,
        "source_node": source_node,
        "target_node": target_node,
        "created_at": utc_now_iso(),
        "attempts": 0,
        "last_error": None,
    }
    queue["items"].append(item)
    save_mirror_queue(queue)
    return item


def process_mirror_queue(limit: int = 20) -> Dict[str, Any]:
    queue = load_mirror_queue()
    processed: List[Dict[str, Any]] = []
    remaining: List[Dict[str, Any]] = []
    for item in queue.get("items", [])[:]:
        if len(processed) >= limit:
            remaining.append(item)
            continue
        try:
            result = handoff_project(
                item["project_id"],
                source_node=item["source_node"],
                target_node=item["target_node"],
            )
            processed.append({"id": item["id"], "status": "ok", "result": result})
        except Exception as exc:
            next_item = dict(item)
            next_item["attempts"] = int(next_item.get("attempts") or 0) + 1
            next_item["last_error"] = str(exc)
            remaining.append(next_item)
            processed.append({"id": item["id"], "status": "error", "error": str(exc)})
    if len(queue.get("items", [])) > limit:
        remaining.extend(queue["items"][limit:])
    queue["items"] = remaining
    save_mirror_queue(queue)
    return {"processed": processed, "remaining": remaining}


def summarize_catalog() -> Dict[str, Any]:
    config = load_control_config()
    registry = load_project_registry()
    projects_out: List[Dict[str, Any]] = []
    for project_id, project in sorted((registry.get("projects") or {}).items()):
        snapshots = []
        for node_id, snapshot in sorted((project.get("nodes") or {}).items()):
            spec = dict(config.get("nodes", {}).get(node_id) or {})
            snapshots.append(
                {
                    **snapshot,
                    "node_id": node_id,
                    "transport": spec.get("transport", "unknown"),
                    "online": check_node_online(node_id, spec) if spec else node_id == current_node_id(),
                }
            )
        projects_out.append(
            {
                "project_id": project_id,
                "aliases": list(project.get("aliases") or []),
                "remote_url": project.get("remote_url", ""),
                "google_assets": [dict(item) for item in (project.get("google_assets") or []) if isinstance(item, dict)],
                "nodes": snapshots,
            }
        )
    nodes_out = []
    for node in list_nodes():
        node_id = str(node.get("id") or "")
        nodes_out.append({**node, "online": check_node_online(node_id, node)})
    return {
        "success": True,
        "current_node_id": current_node_id(),
        "default_executor": config.get("default_executor", "codex_cli"),
        "default_target_node": config.get("default_target_node", current_node_id()),
        "nodes": nodes_out,
        "projects": projects_out,
    }
