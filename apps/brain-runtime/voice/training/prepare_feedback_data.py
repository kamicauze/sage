"""
Prepare retraining datasets from lab feedback annotations.

Current focus: STT feedback collected from Voice Lab.

Usage:
    python brain/voice/training/prepare_feedback_data.py --task stt
    python brain/voice/training/prepare_feedback_data.py --task stt --include-base
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple

# Ensure workspace root is importable when run via apps/... path.
_probe = Path(__file__).resolve().parent
for _parent in [_probe, *_probe.parents]:
    if (_parent / "sage.py").exists():
        if str(_parent) not in sys.path:
            sys.path.insert(0, str(_parent))
        break

from brain.voice.paths import get_training_artifacts_dir, get_training_data_dir

logging.basicConfig(level=logging.INFO, format="[Feedback-Prep] %(asctime)s - %(message)s")
logger = logging.getLogger("Feedback-Prep")

DEFAULT_FEEDBACK_JSONL = (
    Path(get_training_artifacts_dir(__file__)) / "feedback" / "stt_annotations.jsonl"
)
DEFAULT_OUTPUT_DIR = Path(get_training_data_dir(__file__)) / "stt_feedback_dataset"
DEFAULT_BASE_DATASET_DIR = Path(get_training_data_dir(__file__)) / "stt_dataset"


def _load_jsonl(path: Path) -> List[Dict]:
    if not path.exists():
        logger.error(f"Feedback file not found: {path}")
        logger.error("Save some STT annotations in `./sage lab` first.")
        sys.exit(1)

    entries: List[Dict] = []
    bad = 0
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            raw = line.strip()
            if not raw:
                continue
            try:
                entries.append(json.loads(raw))
            except Exception:
                bad += 1
                logger.warning(f"Skipping malformed JSON at line {line_no}")
    logger.info(f"Loaded {len(entries)} feedback entries from {path}")
    if bad:
        logger.info(f"Skipped {bad} malformed lines")
    return entries


def _read_dataset_jsonl(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    rows: List[Dict[str, str]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw:
                continue
            item = json.loads(raw)
            audio = str(item.get("audio", "")).strip()
            text = " ".join(str(item.get("text", "")).split()).strip()
            if not audio or not text or not os.path.exists(audio):
                continue
            rows.append({"audio": os.path.abspath(audio), "text": text})
    return rows


def _load_base_dataset(base_dir: Path) -> List[Dict[str, str]]:
    train_rows = _read_dataset_jsonl(base_dir / "train.jsonl")
    val_rows = _read_dataset_jsonl(base_dir / "val.jsonl")
    rows = train_rows + val_rows
    logger.info(f"Loaded {len(rows)} base STT rows from {base_dir}")
    return rows


def _to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _to_int(value, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _quality_repeat_factor(quality: int, max_repeats: int) -> int:
    if quality <= 2:
        return min(max_repeats, 3)
    if quality == 3:
        return min(max_repeats, 2)
    return 1


def _collect_feedback_rows(
    entries: List[Dict],
    only_marked: bool,
    min_quality: int,
    max_repeats: int,
) -> Tuple[List[Dict[str, str]], Dict[str, int]]:
    """
    Convert feedback entries into weighted rows of {"audio", "text"}.

    Lower quality entries are repeated more times to up-weight hard cases.
    """
    dropped = Counter()
    dedup: Dict[Tuple[str, str], Dict[str, object]] = {}

    for e in entries:
        use_for_training = _to_bool(e.get("use_for_training", False))
        if only_marked and not use_for_training:
            dropped["unmarked"] += 1
            continue

        quality = _to_int(e.get("quality", 3), 3)
        if quality < min_quality:
            dropped["below_min_quality"] += 1
            continue

        text = str(e.get("corrected_text", "")).strip() or str(e.get("transcript", "")).strip()
        text = " ".join(text.split())
        if not text:
            dropped["empty_text"] += 1
            continue

        audio = str(e.get("audio_path", "")).strip() or str(e.get("source_audio_path", "")).strip()
        if not audio:
            dropped["missing_audio_path"] += 1
            continue
        audio = os.path.abspath(audio)
        if not os.path.exists(audio):
            dropped["missing_audio_file"] += 1
            continue

        repeat = _quality_repeat_factor(quality, max_repeats)
        key = (audio, text)
        prev = dedup.get(key)
        if prev is None or int(prev["repeat"]) < repeat:
            dedup[key] = {"audio": audio, "text": text, "repeat": repeat}

    rows: List[Dict[str, str]] = []
    for item in dedup.values():
        repeat = int(item["repeat"])
        for _ in range(repeat):
            rows.append({"audio": item["audio"], "text": item["text"]})

    stats = dict(dropped)
    stats["unique_feedback_rows"] = len(dedup)
    stats["expanded_feedback_rows"] = len(rows)
    return rows, stats


def _split_rows(rows: List[Dict[str, str]], val_split: float, seed: int):
    random.seed(seed)
    random.shuffle(rows)

    if len(rows) <= 1 or val_split <= 0:
        return rows, []

    split_idx = int(len(rows) * (1 - val_split))
    split_idx = max(1, min(split_idx, len(rows) - 1))
    return rows[:split_idx], rows[split_idx:]


def _write_jsonl(path: Path, rows: List[Dict[str, str]]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def prepare_stt_feedback_dataset(args):
    feedback_path = Path(args.feedback_jsonl).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    base_dir = Path(args.base_dataset_dir).expanduser().resolve()

    entries = _load_jsonl(feedback_path)
    feedback_rows, feedback_stats = _collect_feedback_rows(
        entries=entries,
        only_marked=args.only_marked,
        min_quality=args.min_quality,
        max_repeats=args.max_repeats,
    )

    all_rows = list(feedback_rows)
    base_rows = []
    if args.include_base:
        base_rows = _load_base_dataset(base_dir)
        all_rows.extend(base_rows)

    if not all_rows:
        logger.error("No rows available after filtering feedback.")
        logger.error("Check annotation quality/use_for_training filters.")
        sys.exit(1)

    train_rows, val_rows = _split_rows(all_rows, args.val_split, args.seed)

    train_path = output_dir / "train.jsonl"
    val_path = output_dir / "val.jsonl"
    summary_path = output_dir / "summary.json"

    _write_jsonl(train_path, train_rows)
    _write_jsonl(val_path, val_rows)

    summary = {
        "task": "stt",
        "feedback_jsonl": str(feedback_path),
        "output_dir": str(output_dir),
        "include_base": bool(args.include_base),
        "base_dataset_dir": str(base_dir),
        "val_split": float(args.val_split),
        "seed": int(args.seed),
        "only_marked": bool(args.only_marked),
        "min_quality": int(args.min_quality),
        "max_repeats": int(args.max_repeats),
        "feedback_entries_total": len(entries),
        "feedback_stats": feedback_stats,
        "base_rows": len(base_rows),
        "train_rows": len(train_rows),
        "val_rows": len(val_rows),
    }
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    logger.info("Feedback dataset preparation complete.")
    logger.info(f"Train: {len(train_rows)} -> {train_path}")
    logger.info(f"Val: {len(val_rows)} -> {val_path}")
    logger.info(f"Summary: {summary_path}")
    logger.info(
        "Next: ./sage train stt --whisper-model whisper-small --data-dir "
        + str(output_dir)
    )


def main():
    parser = argparse.ArgumentParser(description="Prepare retraining datasets from lab feedback")
    parser.add_argument("--task", choices=["stt"], default="stt")
    parser.add_argument("--feedback-jsonl", default=str(DEFAULT_FEEDBACK_JSONL))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--val-split", type=float, default=0.1)
    parser.add_argument("--include-base", action="store_true", help="Merge with existing stt_dataset")
    parser.add_argument("--base-dataset-dir", default=str(DEFAULT_BASE_DATASET_DIR))
    parser.add_argument("--only-marked", dest="only_marked", action="store_true", help="Use only `use_for_training=true` rows")
    parser.add_argument("--include-unmarked", dest="only_marked", action="store_false", help="Include all rows regardless of flag")
    parser.add_argument("--min-quality", type=int, default=1, help="Minimum quality score to include (1-5)")
    parser.add_argument("--max-repeats", type=int, default=3, help="Max oversampling factor for low-quality rows")
    parser.add_argument("--seed", type=int, default=42)
    parser.set_defaults(only_marked=True)
    args = parser.parse_args()

    if args.task == "stt":
        prepare_stt_feedback_dataset(args)
    else:
        logger.error(f"Unsupported task: {args.task}")
        sys.exit(1)


if __name__ == "__main__":
    main()

