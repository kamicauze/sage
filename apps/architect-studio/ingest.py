"""
Architect Ingestion Tool
Scans the current workspace and ingests files into the Architect's memory.

Usage:
    python3 architect/ingest.py [project_id] [root_dir]
"""
import sys
import os
# Add project root to path so we can import architect.memory
sys.path.append(os.getcwd())

from architect.memory import ArchitectMemory

IGNORE_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    ".venv-vision",
    ".sage_memory",
    ".sage_memory_bench",
    "node_modules",
    ".next",
    "artifacts",
    "generated",
}

IGNORE_EXTS = {
    ".pyc",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".db",
    ".sqlite",
    ".pt",
    ".onnx",
    ".safetensors",
    ".bin",
    ".wav",
    ".mp3",
    ".mp4",
    ".zip",
    ".tar",
    ".gz",
    ".pdf",
}

MAX_FILE_SIZE_BYTES = 1_000_000  # 1 MB


def _normalize_rel(path: str) -> str:
    return os.path.normpath(path).replace("\\", "/")


def ingest_manifest(manifest):
    print(f"--- Architect Ingestion: {manifest.name} ({manifest.id}) ---")
    memory = ArchitectMemory()
    
    # Use repo path from manifest
    root_dir = manifest.repo_path
    
    file_count = 0
    skipped_out_of_zone = 0
    skipped_too_large = 0
    
    for root, dirs, files in os.walk(root_dir):
        # Filter directories in place
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        for file in files:
            _, ext = os.path.splitext(file)
            if ext in IGNORE_EXTS:
                continue
                
            full_path = os.path.join(root, file)
            rel_path = _normalize_rel(os.path.relpath(full_path, start=root_dir))

            # Skip files not included by configured zones.
            if manifest.get_zone_for_file(rel_path) is None:
                skipped_out_of_zone += 1
                continue

            try:
                if os.path.getsize(full_path) > MAX_FILE_SIZE_BYTES:
                    skipped_too_large += 1
                    continue
            except OSError:
                continue

            memory.ingest(manifest, full_path)
            file_count += 1

    print(
        f"--- Ingestion Complete. Processed {file_count} files "
        f"(skipped: out_of_zone={skipped_out_of_zone}, too_large={skipped_too_large}). ---"
    )

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, help="Path to project manifest (.yaml)")
    args = parser.parse_args()
    
    if not os.path.exists(args.manifest):
        print(f"Error: Manifest not found at {args.manifest}")
        sys.exit(1)
        
    try:
        from architect.manifest import ProjectManifest
        manifest = ProjectManifest.load(args.manifest)
        
        # Resolve repo path relative to manifest if needed, or assume manual guidance
        # For now, we use the manifest's repo_path
        ingest_manifest(manifest)
    except Exception as e:
        print(f"Failed to load manifest: {e}")
        sys.exit(1)
