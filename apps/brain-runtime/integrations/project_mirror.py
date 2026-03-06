from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.project_control import (  # noqa: E402
    current_node_id,
    enqueue_mirror_task,
    handoff_project,
    process_mirror_queue,
    register_or_update_project,
)


def _runtime_root(script_path: Path) -> Path:
    return script_path.resolve().parents[3]


def _runtime_env(script_path: Path, source_node: str) -> dict[str, str]:
    root = _runtime_root(script_path)
    return {
        "SAGE_NODE_ID": source_node,
        "SAGE_PROJECT_GIT_STORE_PATH": str(root / ".sage_memory" / "projects" / "git_registry.json"),
        "SAGE_PROJECT_CONTROL_CONFIG_PATH": str(root / ".sage_memory" / "projects" / "control_plane.json"),
        "SAGE_PROJECT_MIRROR_QUEUE_PATH": str(root / ".sage_memory" / "projects" / "mirror_queue.json"),
    }


def _hook_body(
    *,
    script_path: Path,
    project_id: str,
    repo_path: Path,
    source_node: str,
    target_node: str,
) -> str:
    env = _runtime_env(script_path, source_node)
    return f"""#!/bin/zsh
set -euo pipefail

export SAGE_NODE_ID={env["SAGE_NODE_ID"]}
export SAGE_PROJECT_GIT_STORE_PATH={env["SAGE_PROJECT_GIT_STORE_PATH"]}
export SAGE_PROJECT_CONTROL_CONFIG_PATH={env["SAGE_PROJECT_CONTROL_CONFIG_PATH"]}
export SAGE_PROJECT_MIRROR_QUEUE_PATH={env["SAGE_PROJECT_MIRROR_QUEUE_PATH"]}

/usr/bin/env python3 {script_path} post-commit \\
  --project-id {project_id} \\
  --repo-path {repo_path} \\
  --source-node {source_node} \\
  --target-node {target_node}
"""


def install_post_commit_hook(
    *,
    project_id: str,
    repo_path: str,
    source_node: str,
    target_node: str,
) -> Path:
    repo = Path(repo_path).expanduser().resolve()
    hook_path = repo / ".git" / "hooks" / "post-commit"
    if not (repo / ".git").exists():
        raise RuntimeError(f"{repo} is not a git repository.")
    hook_path.parent.mkdir(parents=True, exist_ok=True)
    body = _hook_body(
        script_path=Path(__file__).resolve(),
        project_id=project_id,
        repo_path=repo,
        source_node=source_node,
        target_node=target_node,
    )
    hook_path.write_text(body, encoding="utf-8")
    hook_path.chmod(0o755)
    return hook_path


def post_commit_mirror(
    *,
    project_id: str,
    repo_path: str,
    source_node: str,
    target_node: str,
) -> dict:
    register_or_update_project(project_id, repo_path, node_id=source_node)
    try:
        return {
            "status": "mirrored",
            "result": handoff_project(
                project_id,
                source_node=source_node,
                target_node=target_node,
            ),
        }
    except Exception as exc:
        queued = enqueue_mirror_task(
            project_id=project_id,
            source_node=source_node,
            target_node=target_node,
        )
        return {
            "status": "queued",
            "error": str(exc),
            "queue_item": queued,
        }


def build_launchd_plist(
    *,
    label: str,
    interval_seconds: int,
    source_node: Optional[str] = None,
) -> str:
    node_id = source_node or current_node_id()
    script_path = Path(__file__).resolve()
    env = _runtime_env(script_path, node_id)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{label}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>SAGE_NODE_ID</key>
    <string>{env["SAGE_NODE_ID"]}</string>
    <key>SAGE_PROJECT_GIT_STORE_PATH</key>
    <string>{env["SAGE_PROJECT_GIT_STORE_PATH"]}</string>
    <key>SAGE_PROJECT_CONTROL_CONFIG_PATH</key>
    <string>{env["SAGE_PROJECT_CONTROL_CONFIG_PATH"]}</string>
    <key>SAGE_PROJECT_MIRROR_QUEUE_PATH</key>
    <string>{env["SAGE_PROJECT_MIRROR_QUEUE_PATH"]}</string>
  </dict>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/env</string>
    <string>python3</string>
    <string>{script_path}</string>
    <string>process-queue</string>
    <string>--source-node</string>
    <string>{node_id}</string>
  </array>
  <key>StartInterval</key>
  <integer>{interval_seconds}</integer>
  <key>RunAtLoad</key>
  <true/>
</dict>
</plist>
"""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Mirror project commits to the mini control plane.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    install = subparsers.add_parser("install-hook")
    install.add_argument("--project-id", required=True)
    install.add_argument("--repo-path", required=True)
    install.add_argument("--source-node", default=current_node_id())
    install.add_argument("--target-node", default="mini")

    post_commit = subparsers.add_parser("post-commit")
    post_commit.add_argument("--project-id", required=True)
    post_commit.add_argument("--repo-path", required=True)
    post_commit.add_argument("--source-node", default=current_node_id())
    post_commit.add_argument("--target-node", default="mini")

    process = subparsers.add_parser("process-queue")
    process.add_argument("--limit", type=int, default=20)
    process.add_argument("--source-node", default=current_node_id())

    plist = subparsers.add_parser("print-launchd")
    plist.add_argument("--label", default="com.sage.project-mirror")
    plist.add_argument("--interval-seconds", type=int, default=300)
    plist.add_argument("--source-node", default=current_node_id())

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)

    if args.command == "install-hook":
        hook_path = install_post_commit_hook(
            project_id=args.project_id,
            repo_path=args.repo_path,
            source_node=args.source_node,
            target_node=args.target_node,
        )
        print(hook_path)
        return 0

    if args.command == "post-commit":
        result = post_commit_mirror(
            project_id=args.project_id,
            repo_path=args.repo_path,
            source_node=args.source_node,
            target_node=args.target_node,
        )
        print(result)
        return 0

    if args.command == "process-queue":
        print(process_mirror_queue(limit=args.limit))
        return 0

    if args.command == "print-launchd":
        print(
            build_launchd_plist(
                label=args.label,
                interval_seconds=args.interval_seconds,
                source_node=args.source_node,
            )
        )
        return 0

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
