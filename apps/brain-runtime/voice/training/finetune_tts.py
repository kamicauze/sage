"""
Qwen3-TTS Fine-tuning for Sheng Voice

Wraps the official Qwen3-TTS sft_12hz.py fine-tuning script.

Designed for NVIDIA 4070 Ti (12GB VRAM).
  - 0.6B: full fine-tuning, ~4GB VRAM (comfortable)
  - 1.7B: LoRA fine-tuning (auto-enabled), ~5-6GB VRAM

Usage:
    python brain/voice/training/finetune_tts.py --size 0.6b
    python brain/voice/training/finetune_tts.py --size 1.7b --epochs 5
    python brain/voice/training/finetune_tts.py --size 1.7b --no-lora  # force full (needs >16GB)
"""

import os
import sys
import argparse
import logging
import subprocess
import json
from collections import Counter

# Ensure workspace root is importable when run via apps/... path.
from pathlib import Path

_probe = Path(__file__).resolve().parent
for _parent in [_probe, *_probe.parents]:
    if (_parent / "sage.py").exists():
        if str(_parent) not in sys.path:
            sys.path.insert(0, str(_parent))
        break

from brain.voice.paths import get_training_artifacts_dir, get_training_data_dir

logging.basicConfig(level=logging.INFO, format="[TTS-Train] %(asctime)s - %(message)s")
logger = logging.getLogger("TTS-Train")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TRAINING_ARTIFACTS_DIR = str(get_training_artifacts_dir(__file__))
TRAINING_DATA_DIR = str(get_training_data_dir(__file__))


def get_model_path(size):
    """Get base model path for given size."""
    size_map = {
        "0.6b": os.path.join(TRAINING_ARTIFACTS_DIR, "models/Qwen3-TTS-12Hz-0.6B-Base"),
        "1.7b": os.path.join(TRAINING_ARTIFACTS_DIR, "models/Qwen3-TTS-12Hz-1.7B-Base"),
    }
    path = size_map.get(size)
    if not path or not os.path.exists(path):
        logger.error(f"Model not found for size '{size}' at {path}")
        logger.error("Run './sage train setup' first to download models.")
        sys.exit(1)
    return path


def get_checkpoint_dir(size):
    """Get checkpoint directory for given size."""
    return os.path.join(TRAINING_ARTIFACTS_DIR, f"checkpoints/qwen3-tts-sheng-{size}")


def validate_tokenized_dataset(data_path, max_duplicate_texts=3):
    """
    Block obvious dataset corruption before expensive training.

    Validates:
    - required fields exist
    - audio/ref paths exist
    - audio_codes has shape [T, 16]
    - identical transcript repeats do not exceed cap
    """
    required = {"audio", "text", "ref_audio", "audio_codes"}
    errors = []
    text_counts = Counter()
    sample_count = 0

    with open(data_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            sample_count += 1
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"Line {idx}: invalid JSON ({exc})")
                continue

            missing = required - item.keys()
            if missing:
                errors.append(f"Line {idx}: missing required fields {sorted(missing)}")
                continue

            text = (item.get("text") or "").strip()
            if not text:
                errors.append(f"Line {idx}: empty text")
            else:
                text_counts[text.lower()] += 1

            audio_path = item.get("audio", "")
            if not os.path.exists(audio_path):
                errors.append(f"Line {idx}: missing audio file {audio_path}")

            ref_audio_path = item.get("ref_audio", "")
            if not os.path.exists(ref_audio_path):
                errors.append(f"Line {idx}: missing ref_audio file {ref_audio_path}")

            codes = item.get("audio_codes")
            if not isinstance(codes, list) or not codes:
                errors.append(f"Line {idx}: audio_codes missing/empty")
            elif not isinstance(codes[0], list) or len(codes[0]) != 16:
                errors.append(f"Line {idx}: audio_codes must be shaped [T,16]")

    duplicate_over_cap = {txt: c for txt, c in text_counts.items() if c > max_duplicate_texts}
    if duplicate_over_cap:
        examples = sorted(duplicate_over_cap.items(), key=lambda x: x[1], reverse=True)[:5]
        errors.append(
            f"Found transcript duplicates beyond cap ({max_duplicate_texts}): {examples}"
        )

    if sample_count < 40:
        errors.append(
            f"Only {sample_count} samples found. This is likely too small for stable fine-tuning."
        )

    if errors:
        logger.error("Dataset sanity check failed:")
        for err in errors[:20]:
            logger.error(f"  - {err}")
        if len(errors) > 20:
            logger.error(f"  ... and {len(errors) - 20} more issues.")
        logger.error(
            "Fix dataset issues first (re-run `./sage collect --export` and "
            "`./sage train prepare-tts`). Training aborted."
        )
        sys.exit(1)

    logger.info(
        f"Dataset sanity check passed: {sample_count} samples, "
        f"{len(text_counts)} unique transcripts."
    )


def train(args):
    """Run fine-tuning via the official sft_12hz.py script."""
    import torch

    model_path = get_model_path(args.size)
    checkpoint_dir = get_checkpoint_dir(args.size)
    os.makedirs(checkpoint_dir, exist_ok=True)

    # Check training data
    data_path = args.data
    if not os.path.exists(data_path):
        logger.error(f"Training data not found at {data_path}")
        logger.error("Run './sage train prepare-tts' first.")
        sys.exit(1)
    validate_tokenized_dataset(data_path, max_duplicate_texts=args.max_duplicate_texts)

    # Count samples
    with open(data_path, "r", encoding="utf-8") as f:
        sample_count = sum(1 for line in f if line.strip())
    logger.info(f"Training data: {sample_count} samples from {data_path}")

    # GPU info
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        vram_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
        logger.info(f"GPU: {gpu_name} ({vram_gb:.1f}GB)")
    else:
        logger.warning("No GPU detected! Training will be very slow on CPU.")

    # Locate official sft_12hz.py
    official_script = os.path.join(SCRIPT_DIR, "qwen3-tts/finetuning/sft_12hz.py")
    if not os.path.exists(official_script):
        logger.error(f"Official fine-tuning script not found at {official_script}")
        logger.error("Run './sage train setup' to clone the Qwen3-TTS repo.")
        sys.exit(1)

    # Auto-enable LoRA for 1.7B on GPUs with <=16GB VRAM
    use_lora = args.lora
    if use_lora is None:
        if torch.cuda.is_available():
            vram_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
            use_lora = args.size == "1.7b" and vram_gb <= 16
        else:
            use_lora = args.size == "1.7b"

    logger.info(f"Model: Qwen3-TTS-12Hz-{args.size.upper()}-Base")
    logger.info(f"Mode: {'LoRA' if use_lora else 'Full'} fine-tuning")
    logger.info(f"Epochs: {args.epochs}, Batch size: {args.batch_size}, LR: {args.lr}")
    logger.info(f"Speaker name: {args.speaker_name}")
    logger.info(f"Output: {checkpoint_dir}")

    cmd = [
        sys.executable, "-m", "accelerate.commands.launch",
        "--num_processes", "1",
        "--mixed_precision", "bf16",
        official_script,
        "--init_model_path", model_path,
        "--output_model_path", checkpoint_dir,
        "--train_jsonl", data_path,
        "--batch_size", str(args.batch_size),
        "--lr", str(args.lr),
        "--num_epochs", str(args.epochs),
        "--speaker_name", args.speaker_name,
    ]

    if use_lora:
        cmd.extend([
            "--use_lora",
            "--lora_rank", str(args.lora_rank),
            "--lora_alpha", str(args.lora_alpha),
        ])

    # Run from the finetuning directory so relative imports (dataset.py) work
    cwd = os.path.dirname(official_script)
    logger.info(f"Running: {' '.join(cmd)}")
    logger.info(f"Working directory: {cwd}")

    # Use home disk for temp files (root partition may be full)
    env = os.environ.copy()
    home_tmp = os.path.join(os.path.expanduser("~"), "tmp")
    os.makedirs(home_tmp, exist_ok=True)
    env["TMPDIR"] = home_tmp
    env["TEMP"] = home_tmp
    env["TMP"] = home_tmp
    env["TORCH_EXTENSIONS_DIR"] = os.path.join(home_tmp, "torch_extensions")
    env["PYTHONUNBUFFERED"] = "1"

    # Single-GPU DeepSpeed distributed setup (avoids MPI dependency)
    env["MASTER_ADDR"] = "localhost"
    env["MASTER_PORT"] = "29500"
    env["RANK"] = "0"
    env["LOCAL_RANK"] = "0"
    env["WORLD_SIZE"] = "1"

    result = subprocess.run(cmd, cwd=cwd, env=env)

    if result.returncode == 0:
        logger.info(f"Fine-tuning complete!")
        logger.info(f"Checkpoints saved to: {checkpoint_dir}")

        # List checkpoints
        for item in sorted(os.listdir(checkpoint_dir)):
            item_path = os.path.join(checkpoint_dir, item)
            if os.path.isdir(item_path):
                logger.info(f"  {item}")

        # Point to final checkpoint for deployment
        final_epoch = f"checkpoint-epoch-{args.epochs - 1}"
        final_path = os.path.join(checkpoint_dir, final_epoch)
        if os.path.exists(final_path):
            # Create a 'final' symlink for convenience
            final_link = os.path.join(checkpoint_dir, "final")
            if os.path.lexists(final_link):
                os.remove(final_link)
            os.symlink(final_path, final_link)
            logger.info(f"Final model: {final_link} -> {final_epoch}")
            logger.info(f"To deploy: set QWEN_TTS_MODEL={final_link}")
    else:
        logger.error(f"Fine-tuning failed with return code {result.returncode}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Fine-tune Qwen3-TTS on Sheng voice data")
    parser.add_argument("--size", choices=["0.6b", "1.7b"], default="0.6b",
                        help="Model size (0.6b for Jetson, 1.7b for desktop)")
    parser.add_argument("--data", default=None, help="Path to tokenized training JSONL")
    parser.add_argument("--epochs", type=int, default=3, help="Number of training epochs")
    parser.add_argument("--batch-size", type=int, default=2, help="Training batch size")
    parser.add_argument("--lr", type=float, default=2e-5, help="Learning rate")
    parser.add_argument("--speaker-name", default="sage_sheng",
                        help="Speaker name (stored in model config)")
    parser.add_argument("--lora", default=None, action="store_true",
                        help="Force LoRA fine-tuning (auto-enabled for 1.7b on <=16GB VRAM)")
    parser.add_argument("--no-lora", dest="lora", action="store_false",
                        help="Force full fine-tuning (needs >16GB VRAM for 1.7b)")
    parser.add_argument("--lora-rank", type=int, default=16, help="LoRA rank")
    parser.add_argument("--lora-alpha", type=int, default=32, help="LoRA alpha")
    parser.add_argument(
        "--max-duplicate-texts",
        type=int,
        default=3,
        help="Abort if an identical transcript appears more than this many times",
    )
    args = parser.parse_args()

    if args.data is None:
        args.data = os.path.join(TRAINING_DATA_DIR, "tts_tokenized.jsonl")

    train(args)


if __name__ == "__main__":
    main()
