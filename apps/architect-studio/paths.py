"""
Central path/config definitions for Sage Architect.

Use this module instead of hardcoded "architect/..." strings so repo layout
changes are isolated to one place.
"""
from pathlib import Path
from typing import Union


# Repo layout roots
REPO_ROOT = Path(__file__).resolve().parents[2]
APPS_DIR = REPO_ROOT / "apps"
PACKAGES_DIR = REPO_ROOT / "packages"
GENERATED_DIR = REPO_ROOT / "generated"

# App/package directories
ARCHITECT_DIR = APPS_DIR / "architect-studio"
ARCHITECT_COMPAT_DIR = REPO_ROOT / "architect"
BRAIN_DIR = APPS_DIR / "brain-runtime"
BRAIN_COMPAT_DIR = REPO_ROOT / "brain"
SHARED_DIR = PACKAGES_DIR / "shared"
SHARED_COMPAT_DIR = REPO_ROOT / "shared"

# Architect runtime data/config directories
ARCHITECT_GENERATED_DIR = GENERATED_DIR / "architect"
WORKSPACES_DIR = ARCHITECT_GENERATED_DIR / "workspaces"
PROJECTS_DIR = ARCHITECT_DIR / "projects"
PROMPTS_DIR = ARCHITECT_DIR / "prompts"
CACHE_DIR = ARCHITECT_DIR / ".cache"
UI_DIR = ARCHITECT_DIR / "ui"

# Common files
USAGE_FILE = ARCHITECT_DIR / "usage.json"
USAGE_LOG_FILE = CACHE_DIR / "usage_log.jsonl"
LLM_REGISTRY_FILE = CACHE_DIR / "llm_registry.json"
BRAIN_ENV_FILE = BRAIN_DIR / ".env"


def root_relative(path: Union[Path, str]) -> str:
    """Return a stable, root-relative POSIX path string."""
    path = Path(path)
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except Exception:
        try:
            return path.relative_to(REPO_ROOT).as_posix()
        except Exception:
            return path.as_posix()


def project_manifest_path(project_name: str = "sage") -> Path:
    return PROJECTS_DIR / f"{project_name}.yaml"


def workspace_dir(project_id: str) -> Path:
    return WORKSPACES_DIR / project_id


def workspace_plan_path(project_id: str) -> Path:
    return workspace_dir(project_id) / "plan.md"


def workspace_sandbox_path(project_id: str) -> Path:
    return workspace_dir(project_id) / "sandbox"


def prompt_path(filename: str) -> Path:
    return PROMPTS_DIR / filename
