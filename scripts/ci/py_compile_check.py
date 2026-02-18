#!/usr/bin/env python3
"""
Compile Python files in key Architect paths and emit a deterministic report.
"""
from __future__ import annotations

import argparse
import py_compile
from pathlib import Path
import sys


def _collect_python_files(roots: list[Path]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        files.extend(sorted(root.rglob("*.py")))
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile Python files for CI checks.")
    parser.add_argument(
        "--output-list",
        default="artifacts/ci/compiled_files.txt",
        help="Path to write the compiled file list.",
    )
    args = parser.parse_args()

    roots = [
        Path("apps/architect-studio"),
        Path("shared"),
        Path("tests"),
    ]
    files = _collect_python_files(roots)

    output_list = Path(args.output_list)
    output_list.parent.mkdir(parents=True, exist_ok=True)
    output_list.write_text("\n".join(str(path) for path in files) + "\n", encoding="utf-8")

    failures: list[str] = []
    for file_path in files:
        try:
            py_compile.compile(str(file_path), doraise=True)
        except Exception as exc:  # pragma: no cover - exercised in CI failure mode
            failures.append(f"{file_path}: {exc}")

    if failures:
        print("Python compile failures detected:")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print(f"Compiled {len(files)} files successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
