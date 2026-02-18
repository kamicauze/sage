"""
Voice path utilities resilient to repository layout changes.

This resolves the real workspace root (containing `sage.py`) even when
`brain/` is a symlink (e.g. `brain -> apps/brain-runtime`), then builds
stable paths for voice artifacts.
"""

from __future__ import annotations

from pathlib import Path


def get_project_root(start: str | Path | None = None) -> Path:
    """Find workspace root by walking parents until `sage.py` is found."""
    probe = Path(start or __file__).resolve()
    cursor = probe if probe.is_dir() else probe.parent

    for parent in [cursor, *cursor.parents]:
        if (parent / "sage.py").exists():
            return parent

    # Fallback for unexpected layouts.
    return Path(__file__).resolve().parents[3]


def get_voice_artifacts_root(start: str | Path | None = None) -> Path:
    return get_project_root(start) / "artifacts" / "voice"


def get_training_data_dir(start: str | Path | None = None) -> Path:
    return get_voice_artifacts_root(start) / "training_data"


def get_training_artifacts_dir(start: str | Path | None = None) -> Path:
    return get_voice_artifacts_root(start) / "training"

