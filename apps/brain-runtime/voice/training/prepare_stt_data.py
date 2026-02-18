"""
Prepare training data for Whisper STT fine-tuning.

Converts collected audio + transcripts into a HuggingFace Dataset
for LoRA fine-tuning. Focuses on phonetic accuracy for Kenyan
speech patterns — the syllable-level output is cross-referenced
against a Sheng lexicon post-transcription.

Usage:
    python brain/voice/training/prepare_stt_data.py
    python brain/voice/training/prepare_stt_data.py --augment-swahili
"""

import os
import sys
import json
import argparse
import logging

# Ensure workspace root is importable when run via apps/... path.
from pathlib import Path

_probe = Path(__file__).resolve().parent
for _parent in [_probe, *_probe.parents]:
    if (_parent / "sage.py").exists():
        if str(_parent) not in sys.path:
            sys.path.insert(0, str(_parent))
        break

from brain.voice.paths import get_training_data_dir

logging.basicConfig(level=logging.INFO, format="[STT-Prep] %(asctime)s - %(message)s")
logger = logging.getLogger("STT-Prep")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA_DIR = str(get_training_data_dir(__file__))


def _resolve_data_path(raw_path, data_dir):
    raw = (raw_path or "").strip()
    if not raw:
        return ""
    candidates = []
    candidates.append(raw)
    marker = "artifacts/voice/training_data/"
    if marker in raw:
        rel = raw.split(marker, 1)[1]
        candidates.append(os.path.join(data_dir, rel))
    marker = "brain/voice/training_data/"
    if marker in raw:
        rel = raw.split(marker, 1)[1]
        candidates.append(os.path.join(data_dir, rel))
    candidates.append(os.path.join(data_dir, "processed", os.path.basename(raw)))

    for c in candidates:
        if os.path.exists(c):
            return os.path.abspath(c)
    return os.path.abspath(candidates[0])


def load_manifest(data_dir):
    """Load collected recording manifest."""
    manifest_path = os.path.join(data_dir, "manifest.jsonl")
    if not os.path.exists(manifest_path):
        logger.error(f"No manifest found at {manifest_path}")
        logger.error("Run './sage collect' first to record training data.")
        sys.exit(1)

    entries = []
    with open(manifest_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))

    logger.info(f"Loaded {len(entries)} entries from manifest")
    return entries


def prepare_hf_dataset(entries, output_dir, data_dir, val_split=0.1):
    """
    Convert entries to HuggingFace Dataset format.

    Creates train/validation JSONL files with:
    - audio: path to 16kHz WAV
    - text: transcript (as-is, mixed language)
    """
    import random

    os.makedirs(output_dir, exist_ok=True)

    # Filter for valid entries with STT audio
    valid = []
    for entry in entries:
        stt_path = _resolve_data_path(entry.get("stt_path", ""), data_dir)
        text = entry.get("text", "").strip()
        if stt_path and os.path.exists(stt_path) and text:
            valid.append({
                "audio": os.path.abspath(stt_path),
                "text": text,
            })

    if not valid:
        logger.error("No valid entries found with STT audio paths.")
        sys.exit(1)

    # Shuffle and split
    random.seed(42)
    random.shuffle(valid)
    split_idx = max(1, int(len(valid) * (1 - val_split)))
    train_set = valid[:split_idx]
    val_set = valid[split_idx:]

    # Write JSONL files
    train_path = os.path.join(output_dir, "train.jsonl")
    val_path = os.path.join(output_dir, "val.jsonl")

    for path, dataset in [(train_path, train_set), (val_path, val_set)]:
        with open(path, "w", encoding="utf-8") as f:
            for entry in dataset:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    logger.info(f"Train: {len(train_set)} samples -> {train_path}")
    logger.info(f"Val: {len(val_set)} samples -> {val_path}")

    return train_path, val_path


def augment_with_common_voice(output_dir, language="sw", max_samples=500):
    """
    Optionally download and append Common Voice Swahili data
    to improve base Swahili phonetic recognition.
    """
    try:
        from datasets import load_dataset
    except ImportError:
        logger.error("Install 'datasets' package: pip install datasets")
        sys.exit(1)

    logger.info(f"Downloading Common Voice {language} (max {max_samples} samples)...")

    try:
        ds = load_dataset(
            "mozilla-foundation/common_voice_16_1",
            language,
            split=f"train[:{max_samples}]",
            trust_remote_code=True,
        )
    except Exception as e:
        logger.warning(f"Could not download Common Voice {language}: {e}")
        logger.warning("Continuing without augmentation.")
        return

    # Append to training JSONL
    train_path = os.path.join(output_dir, "train.jsonl")
    augment_dir = os.path.join(output_dir, "common_voice_augment")
    os.makedirs(augment_dir, exist_ok=True)

    import soundfile as sf
    added = 0

    with open(train_path, "a", encoding="utf-8") as f:
        for i, sample in enumerate(ds):
            try:
                # Save audio to local file (16kHz mono)
                audio = sample["audio"]
                audio_path = os.path.join(augment_dir, f"cv_{language}_{i:05d}.wav")
                sf.write(audio_path, audio["array"], audio["sampling_rate"])

                entry = {
                    "audio": os.path.abspath(audio_path),
                    "text": sample["sentence"],
                }
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                added += 1

            except Exception as e:
                logger.debug(f"Skipping sample {i}: {e}")
                continue

    logger.info(f"Augmented with {added} Common Voice {language} samples")


def main():
    parser = argparse.ArgumentParser(description="Prepare data for Whisper STT fine-tuning")
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR, help="Training data directory")
    parser.add_argument("--output-dir", default=None, help="Output directory for HF dataset")
    parser.add_argument("--val-split", type=float, default=0.1, help="Validation split ratio")
    parser.add_argument("--augment-swahili", action="store_true", help="Add Common Voice Swahili data")
    parser.add_argument("--augment-max", type=int, default=500, help="Max augmentation samples")
    args = parser.parse_args()

    if args.output_dir is None:
        args.output_dir = os.path.join(args.data_dir, "stt_dataset")

    entries = load_manifest(args.data_dir)
    train_path, val_path = prepare_hf_dataset(entries, args.output_dir, args.data_dir, args.val_split)

    if args.augment_swahili:
        augment_with_common_voice(args.output_dir, "sw", args.augment_max)

    logger.info("STT data preparation complete.")
    logger.info(f"Next: python brain/voice/training/finetune_stt.py --data-dir {args.output_dir}")


if __name__ == "__main__":
    main()
