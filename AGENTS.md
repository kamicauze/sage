# Sage Agent Indexing Guide

This repo contains large training artifacts and generated sandboxes. Index only the product code by default.

## Index First
- `apps/brain-runtime/`
- `apps/architect-studio/` (exclude `apps/architect-studio/workspaces/*/sandbox`)
- `packages/shared/`
- `tests/`
- `sage.py`

## Skip By Default
- `artifacts/` (voice checkpoints, base models, datasets, eval output)
- `generated/` (architect workspaces/sandboxes)
- `.venv/`, `.venv-vision/`
- `apps/architect-studio/ui/node_modules/`, `apps/architect-studio/ui/.next/`
- `.sage_memory/`, `.sage_memory_bench/`
- `yolov8n.pt`
- legacy symlink paths at repo root: `brain/`, `architect/`, `shared/`

## Voice Layout
- Runtime voice code is in `brain/voice/`.
- Large voice training artifacts are in `artifacts/voice/`.
- Backward-compatible symlinks remain in:
  - `brain/voice/training_data`
  - `brain/voice/training/checkpoints`
  - `brain/voice/training/models`
  - `brain/voice/training/eval_output`

## Compatibility Paths
- Root `brain` -> `apps/brain-runtime`
- Root `architect` -> `apps/architect-studio`
- Root `shared` -> `packages/shared`
- `apps/architect-studio/workspaces` -> `generated/architect/workspaces`
