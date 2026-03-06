from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_STORE_PATH = Path(
    os.getenv("SAGE_PROJECT_GIT_STORE_PATH", ".sage_memory/projects/git_registry.json")
).expanduser()

_HELP_TEXT = (
    "Project git commands:\n"
    "- /git register <project_id> | <repo_path> | <aliases csv> | <node_id>\n"
    "- /git sync <project_id> | <repo_path> | <node_id>\n"
    "- /git sync-all | <node_id>\n"
    "- /git last <project_id> | <node_id>\n"
    "- /git projects"
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_node_id() -> str:
    return (
        (os.getenv("SAGE_NODE_ID") or "").strip()
        or (platform.node() or "").strip()
        or "unknown-node"
    )


def _empty_store() -> Dict[str, Any]:
    return {
        "version": 1,
        "updated_at": _now_iso(),
        "projects": {},
    }


def _load_store() -> Dict[str, Any]:
    try:
        if not _STORE_PATH.exists():
            return _empty_store()
        payload = json.loads(_STORE_PATH.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return _empty_store()
        payload.setdefault("version", 1)
        payload.setdefault("projects", {})
        if not isinstance(payload["projects"], dict):
            payload["projects"] = {}
        return payload
    except Exception:
        return _empty_store()


def _save_store(store: Dict[str, Any]) -> None:
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    store["updated_at"] = _now_iso()
    temp_path = _STORE_PATH.with_suffix(".tmp")
    temp_path.write_text(json.dumps(store, indent=2, sort_keys=True), encoding="utf-8")
    temp_path.replace(_STORE_PATH)


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _normalize_aliases(value: Optional[str]) -> List[str]:
    if not value:
        return []
    aliases = []
    for chunk in re.split(r"[,|]", value):
        cleaned = chunk.strip()
        if cleaned:
            aliases.append(cleaned)
    return aliases


def _run_git(repo_path: str, args: List[str]) -> str:
    result = subprocess.run(
        ["git"] + args,
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=15,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "git command failed").strip())
    return (result.stdout or "").strip()


def _collect_snapshot(repo_path: str, node_id: Optional[str] = None) -> Dict[str, Any]:
    resolved_path = str(Path(repo_path).expanduser().resolve())
    if not Path(resolved_path).exists():
        raise RuntimeError(f"Repo path does not exist: {resolved_path}")

    _run_git(resolved_path, ["rev-parse", "--is-inside-work-tree"])
    head_sha = _run_git(resolved_path, ["rev-parse", "--short", "HEAD"])
    branch = _run_git(resolved_path, ["rev-parse", "--abbrev-ref", "HEAD"])
    head_subject = _run_git(resolved_path, ["log", "-1", "--pretty=%s"])
    head_author = _run_git(resolved_path, ["log", "-1", "--pretty=%an"])
    head_time = _run_git(resolved_path, ["log", "-1", "--date=iso-strict", "--pretty=%cI"])
    status_lines = _run_git(resolved_path, ["status", "--porcelain"])
    try:
        remote_url = _run_git(resolved_path, ["remote", "get-url", "origin"])
    except Exception:
        remote_url = ""

    dirty_files = [line for line in status_lines.splitlines() if line.strip()]
    return {
        "node_id": node_id or _default_node_id(),
        "path": resolved_path,
        "branch": branch,
        "head_sha": head_sha,
        "head_subject": head_subject,
        "head_author": head_author,
        "head_time": head_time,
        "dirty": bool(dirty_files),
        "dirty_count": len(dirty_files),
        "remote_url": remote_url,
        "last_seen": _now_iso(),
    }


def register_project(
    project_id: str,
    repo_path: str,
    aliases: Optional[List[str]] = None,
    node_id: Optional[str] = None,
) -> Dict[str, Any]:
    clean_project_id = (project_id or "").strip()
    if not clean_project_id:
        raise RuntimeError("Missing project_id.")
    snapshot = _collect_snapshot(repo_path, node_id=node_id)

    store = _load_store()
    project = store["projects"].get(clean_project_id, {})
    merged_aliases = list(project.get("aliases", []))
    for alias in aliases or []:
        if alias not in merged_aliases:
            merged_aliases.append(alias)

    project.update(
        {
            "project_id": clean_project_id,
            "aliases": merged_aliases,
            "remote_url": snapshot.get("remote_url") or project.get("remote_url", ""),
            "nodes": dict(project.get("nodes") or {}),
        }
    )
    project["nodes"][snapshot["node_id"]] = snapshot
    store["projects"][clean_project_id] = project
    _save_store(store)
    return {
        "project_id": clean_project_id,
        "node_id": snapshot["node_id"],
        "snapshot": snapshot,
    }


def sync_project(
    project_id: str,
    repo_path: Optional[str] = None,
    node_id: Optional[str] = None,
) -> Dict[str, Any]:
    clean_project_id = (project_id or "").strip()
    if not clean_project_id:
        raise RuntimeError("Missing project_id.")

    effective_node = (node_id or _default_node_id()).strip()
    store = _load_store()
    project = store["projects"].get(clean_project_id)
    if not project:
        raise RuntimeError(f"Unknown project '{clean_project_id}'. Register it first.")

    known_snapshot = dict((project.get("nodes") or {}).get(effective_node) or {})
    effective_path = str(repo_path or known_snapshot.get("path") or "").strip()
    if not effective_path:
        raise RuntimeError(
            f"No repo path known for project '{clean_project_id}' on node '{effective_node}'."
        )

    snapshot = _collect_snapshot(effective_path, node_id=effective_node)
    project.setdefault("nodes", {})
    project["nodes"][effective_node] = snapshot
    if snapshot.get("remote_url"):
        project["remote_url"] = snapshot["remote_url"]
    store["projects"][clean_project_id] = project
    _save_store(store)
    return {
        "project_id": clean_project_id,
        "node_id": effective_node,
        "snapshot": snapshot,
    }


def sync_all_projects(node_id: Optional[str] = None) -> Dict[str, Any]:
    effective_node = (node_id or _default_node_id()).strip()
    store = _load_store()
    updated = []
    skipped = []

    for project_id, project in sorted(store.get("projects", {}).items()):
        snapshot = dict((project.get("nodes") or {}).get(effective_node) or {})
        repo_path = str(snapshot.get("path") or "").strip()
        if not repo_path:
            skipped.append(project_id)
            continue
        try:
            result = sync_project(project_id, repo_path=repo_path, node_id=effective_node)
            updated.append(
                {
                    "project_id": project_id,
                    "head_sha": result["snapshot"]["head_sha"],
                    "head_subject": result["snapshot"]["head_subject"],
                }
            )
        except Exception as exc:
            skipped.append(f"{project_id}: {exc}")

    return {
        "node_id": effective_node,
        "updated": updated,
        "skipped": skipped,
    }


def _iter_project_names(project_id: str, project: Dict[str, Any]) -> List[str]:
    names = [project_id]
    for alias in project.get("aliases", []) or []:
        if isinstance(alias, str) and alias.strip():
            names.append(alias.strip())
    return names


def _resolve_project_id(store: Dict[str, Any], text: str) -> Optional[str]:
    lowered = str(text or "").lower()
    best: Optional[Tuple[int, str]] = None

    for project_id, project in (store.get("projects") or {}).items():
        for name in _iter_project_names(project_id, project):
            candidate = name.lower().strip()
            if not candidate:
                continue
            if candidate in lowered:
                score = len(candidate.replace(" ", ""))
                if best is None or score > best[0]:
                    best = (score, project_id)
            elif _slugify(candidate) and _slugify(candidate) in _slugify(lowered):
                score = len(_slugify(candidate))
                if best is None or score > best[0]:
                    best = (score, project_id)

    return best[1] if best else None


def _resolve_node_id(store: Dict[str, Any], project_id: Optional[str], text: str) -> Optional[str]:
    lowered = str(text or "").lower()
    known_nodes: List[str] = []
    if project_id:
        project = (store.get("projects") or {}).get(project_id, {})
        known_nodes.extend(list((project.get("nodes") or {}).keys()))
    else:
        for project in (store.get("projects") or {}).values():
            known_nodes.extend(list((project.get("nodes") or {}).keys()))

    if "this machine" in lowered or "this node" in lowered or "here" in lowered:
        return _default_node_id()

    best: Optional[Tuple[int, str]] = None
    for node_id in sorted(set(known_nodes)):
        lowered_node = node_id.lower()
        if lowered_node and lowered_node in lowered:
            score = len(lowered_node)
            if best is None or score > best[0]:
                best = (score, node_id)
    return best[1] if best else None


def _iso_sort_key(value: str) -> str:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
    except Exception:
        return ""


def _format_snapshot(project_id: str, node_id: str, snapshot: Dict[str, Any]) -> str:
    dirty_text = "dirty" if snapshot.get("dirty") else "clean"
    branch = snapshot.get("branch") or "unknown-branch"
    seen = snapshot.get("last_seen") or "unknown"
    commit_time = snapshot.get("head_time") or "unknown time"
    return (
        f"Last known commit for {project_id} on {node_id}: "
        f"{snapshot.get('head_sha', '?')} {snapshot.get('head_subject', '(no subject)')} "
        f"(branch {branch}, {dirty_text}, commit {commit_time}, seen {seen})."
    )


def _answer_last_commit(project_id: str, node_id: Optional[str], refresh_local: bool = True) -> str:
    store = _load_store()
    project = (store.get("projects") or {}).get(project_id)
    if not project:
        return f"I do not know project '{project_id}' yet. Register it first with /git register."

    current_node = _default_node_id()
    if refresh_local:
        local_snapshot = dict((project.get("nodes") or {}).get(current_node) or {})
        local_path = str(local_snapshot.get("path") or "").strip()
        if local_path and Path(local_path).exists():
            try:
                sync_project(project_id, repo_path=local_path, node_id=current_node)
                store = _load_store()
                project = store["projects"][project_id]
            except Exception:
                pass

    nodes = dict(project.get("nodes") or {})
    if not nodes:
        return f"Project '{project_id}' is registered, but I do not have any node snapshots yet."

    if node_id:
        snapshot = nodes.get(node_id)
        if not snapshot:
            return f"I do not have a snapshot for {project_id} on {node_id}."
        return _format_snapshot(project_id, node_id, snapshot)

    latest_node, latest_snapshot = max(
        nodes.items(),
        key=lambda item: (
            _iso_sort_key(str(item[1].get("last_seen") or "")),
            str(item[1].get("head_time") or ""),
            str(item[1].get("head_sha") or ""),
        ),
    )
    other_nodes = [name for name in nodes.keys() if name != latest_node]
    response = _format_snapshot(project_id, latest_node, latest_snapshot)
    if other_nodes:
        response += f" Other known nodes: {', '.join(sorted(other_nodes))}."
    return response


def _list_projects_text() -> str:
    store = _load_store()
    projects = store.get("projects") or {}
    if not projects:
        return "No projects registered yet. Use /git register <project_id> | <repo_path>."

    lines = ["Registered git projects:"]
    for project_id, project in sorted(projects.items()):
        aliases = ", ".join(project.get("aliases") or []) or "none"
        nodes = ", ".join(sorted((project.get("nodes") or {}).keys())) or "none"
        lines.append(f"- {project_id} (aliases: {aliases}; nodes: {nodes})")
    return "\n".join(lines)


def _parse_pipe_parts(text: str) -> List[str]:
    return [part.strip() for part in str(text or "").split("|") if part.strip()]


def _handle_command(text: str) -> Dict[str, Any]:
    lowered = text.lower().strip()
    if lowered in {"/git", "/git help", "/project", "/repo"}:
        return {"handled": True, "action": "help", "response_text": _HELP_TEXT}

    if lowered.startswith("/git projects"):
        return {"handled": True, "action": "projects", "response_text": _list_projects_text()}

    if lowered.startswith("/git register "):
        parts = _parse_pipe_parts(text[len("/git register "):])
        if len(parts) < 2:
            return {"handled": True, "action": "register", "response_text": _HELP_TEXT}
        project_id = parts[0]
        repo_path = parts[1]
        aliases = _normalize_aliases(parts[2]) if len(parts) >= 3 else []
        node_id = parts[3] if len(parts) >= 4 else None
        result = register_project(project_id, repo_path, aliases=aliases, node_id=node_id)
        snapshot = result["snapshot"]
        return {
            "handled": True,
            "action": "register",
            "response_text": (
                f"Registered {project_id} on {snapshot['node_id']}: "
                f"{snapshot['head_sha']} {snapshot['head_subject']}."
            ),
        }

    if lowered.startswith("/git sync-all"):
        parts = _parse_pipe_parts(text[len("/git sync-all"):])
        node_id = parts[0] if parts else None
        result = sync_all_projects(node_id=node_id)
        updated = result["updated"]
        skipped = result["skipped"]
        response = f"Synced {len(updated)} project(s) for {result['node_id']}."
        if updated:
            preview = ", ".join(
                f"{item['project_id']}={item['head_sha']}" for item in updated[:5]
            )
            response += f" Updated: {preview}."
        if skipped:
            response += f" Skipped: {', '.join(skipped[:5])}."
        return {"handled": True, "action": "sync_all", "response_text": response}

    if lowered.startswith("/git sync "):
        parts = _parse_pipe_parts(text[len("/git sync "):])
        if not parts:
            return {"handled": True, "action": "sync", "response_text": _HELP_TEXT}
        project_id = parts[0]
        repo_path = parts[1] if len(parts) >= 2 else None
        node_id = parts[2] if len(parts) >= 3 else None
        result = sync_project(project_id, repo_path=repo_path, node_id=node_id)
        snapshot = result["snapshot"]
        return {
            "handled": True,
            "action": "sync",
            "response_text": (
                f"Synced {project_id} on {snapshot['node_id']}: "
                f"{snapshot['head_sha']} {snapshot['head_subject']}."
            ),
        }

    if lowered.startswith("/git last "):
        parts = _parse_pipe_parts(text[len("/git last "):])
        if not parts:
            return {"handled": True, "action": "last_commit", "response_text": _HELP_TEXT}
        project_id = parts[0]
        node_id = parts[1] if len(parts) >= 2 else None
        return {
            "handled": True,
            "action": "last_commit",
            "response_text": _answer_last_commit(project_id, node_id=node_id),
        }

    return {"handled": True, "action": "help", "response_text": _HELP_TEXT}


def handle_project_git_text(
    *,
    user_text: str,
    conversation_id: Optional[str] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    del conversation_id, request_id

    text = str(user_text or "").strip()
    lowered = text.lower()
    if not text:
        return {"handled": False}

    if lowered.startswith(("/git", "/project", "/repo")):
        try:
            return _handle_command(text)
        except Exception as exc:
            return {
                "handled": True,
                "action": "error",
                "error": str(exc),
                "response_text": f"Project git request failed: {exc}",
            }

    commit_candidate = "commit" in lowered and any(
        marker in lowered for marker in ("last", "latest", "recent", "newest")
    )
    if not commit_candidate:
        return {"handled": False}

    store = _load_store()
    project_id = _resolve_project_id(store, lowered)
    node_id = _resolve_node_id(store, project_id, lowered)
    if not project_id:
        return {
            "handled": True,
            "action": "last_commit",
            "response_text": (
                "I can answer that once the project is registered. "
                "Use /git register <project_id> | <repo_path> | <aliases csv>."
            ),
        }

    try:
        return {
            "handled": True,
            "action": "last_commit",
            "response_text": _answer_last_commit(project_id, node_id=node_id),
        }
    except Exception as exc:
        return {
            "handled": True,
            "action": "error",
            "error": str(exc),
            "response_text": f"Project git request failed: {exc}",
        }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Register and sync project git snapshots for Sage.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    register = subparsers.add_parser("register")
    register.add_argument("--project-id", required=True)
    register.add_argument("--path", required=True)
    register.add_argument("--aliases", default="")
    register.add_argument("--node-id", default="")

    sync = subparsers.add_parser("sync")
    sync.add_argument("--project-id", required=True)
    sync.add_argument("--path", default="")
    sync.add_argument("--node-id", default="")

    sync_all = subparsers.add_parser("sync-all")
    sync_all.add_argument("--node-id", default="")

    last_commit = subparsers.add_parser("last-commit")
    last_commit.add_argument("--project-id", required=True)
    last_commit.add_argument("--node-id", default="")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    if args.command == "register":
        result = register_project(
            args.project_id,
            args.path,
            aliases=_normalize_aliases(args.aliases),
            node_id=args.node_id or None,
        )
        print(
            _format_snapshot(
                result["project_id"],
                result["node_id"],
                result["snapshot"],
            )
        )
        return 0

    if args.command == "sync":
        result = sync_project(
            args.project_id,
            repo_path=args.path or None,
            node_id=args.node_id or None,
        )
        print(
            _format_snapshot(
                result["project_id"],
                result["node_id"],
                result["snapshot"],
            )
        )
        return 0

    if args.command == "sync-all":
        result = sync_all_projects(node_id=args.node_id or None)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    if args.command == "last-commit":
        print(_answer_last_commit(args.project_id, node_id=args.node_id or None))
        return 0

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
