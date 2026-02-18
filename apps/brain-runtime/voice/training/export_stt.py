"""
Export fine-tuned Whisper to CTranslate2 format for faster-whisper.

Merges LoRA weights back into the base model, then converts to
CTranslate2 INT8 quantized format for deployment on Jetson Orin Nano.

Usage:
    python brain/voice/training/export_stt.py
    python brain/voice/training/export_stt.py --model whisper-medium --quantize int8
"""

import os
import sys
import argparse
import logging
import shutil

# Ensure workspace root is importable when run via apps/... path.
from pathlib import Path

_probe = Path(__file__).resolve().parent
for _parent in [_probe, *_probe.parents]:
    if (_parent / "sage.py").exists():
        if str(_parent) not in sys.path:
            sys.path.insert(0, str(_parent))
        break

from brain.voice.paths import get_training_artifacts_dir

logging.basicConfig(level=logging.INFO, format="[STT-Export] %(asctime)s - %(message)s")
logger = logging.getLogger("STT-Export")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TRAINING_ARTIFACTS_DIR = str(get_training_artifacts_dir(__file__))


def merge_lora(base_model_name, adapter_path, merged_output_dir):
    """Merge LoRA adapter weights back into base Whisper model."""
    import torch
    from transformers import WhisperForConditionalGeneration, WhisperProcessor
    from peft import PeftModel

    logger.info(f"Loading base model: {base_model_name}")
    base_model = WhisperForConditionalGeneration.from_pretrained(
        f"openai/{base_model_name}",
        torch_dtype=torch.float16,
    )

    logger.info(f"Loading LoRA adapter: {adapter_path}")
    model = PeftModel.from_pretrained(base_model, adapter_path)

    logger.info("Merging LoRA weights into base model...")
    model = model.merge_and_unload()

    logger.info(f"Saving merged model: {merged_output_dir}")
    os.makedirs(merged_output_dir, exist_ok=True)
    model.save_pretrained(merged_output_dir)

    # Also save processor/tokenizer
    processor = WhisperProcessor.from_pretrained(f"openai/{base_model_name}")
    processor.save_pretrained(merged_output_dir)

    logger.info("Merge complete.")
    return merged_output_dir


def convert_to_ctranslate2(merged_model_dir, output_dir, quantization="int8"):
    """Convert merged HuggingFace model to CTranslate2 format."""
    import subprocess

    logger.info(f"Converting to CTranslate2 ({quantization})...")
    os.makedirs(output_dir, exist_ok=True)

    cmd = [
        sys.executable, "-m", "ctranslate2.converters.transformers",
        "--model", merged_model_dir,
        "--output_dir", output_dir,
        "--quantization", quantization,
        "--force",
    ]

    # Try ct2-transformers-converter first (may be installed as CLI)
    try:
        cmd_alt = [
            "ct2-transformers-converter",
            "--model", merged_model_dir,
            "--output_dir", output_dir,
            "--quantization", quantization,
            "--force",
        ]
        logger.info(f"Running: {' '.join(cmd_alt)}")
        result = subprocess.run(cmd_alt, capture_output=True, text=True)
        if result.returncode == 0:
            logger.info("CTranslate2 conversion complete.")
            return output_dir
        else:
            logger.warning(f"ct2 CLI failed: {result.stderr}")
            logger.info("Trying Python module approach...")
    except FileNotFoundError:
        pass

    # Fallback to Python module
    try:
        logger.info(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            logger.info("CTranslate2 conversion complete.")
            return output_dir
        else:
            logger.error(f"Conversion failed: {result.stderr}")
            sys.exit(1)
    except Exception as e:
        logger.error(f"CTranslate2 conversion error: {e}")
        logger.error("Install ctranslate2: pip install ctranslate2")
        sys.exit(1)


def verify_model(ct2_model_dir):
    """Quick verification that the exported model loads in faster-whisper."""
    try:
        from faster_whisper import WhisperModel

        logger.info("Verifying model loads in faster-whisper...")
        model = WhisperModel(ct2_model_dir, device="cpu", compute_type="int8")

        # Generate a tiny test
        import numpy as np
        dummy_audio = np.zeros(16000, dtype=np.float32)  # 1 second silence
        segments, info = model.transcribe(dummy_audio, beam_size=1)
        # Just need it to not crash
        for _ in segments:
            pass

        logger.info("Verification passed! Model loads correctly in faster-whisper.")
        del model
        return True

    except Exception as e:
        logger.error(f"Verification failed: {e}")
        return False


def export(args):
    """Full export pipeline: merge LoRA -> CTranslate2 -> verify."""
    adapter_path = os.path.join(TRAINING_ARTIFACTS_DIR, "checkpoints/whisper-sheng/final_adapter")
    if not os.path.exists(adapter_path):
        logger.error(f"No fine-tuned adapter found at {adapter_path}")
        logger.error("Run finetune_stt.py first.")
        sys.exit(1)

    # Step 1: Merge LoRA
    merged_dir = os.path.join(TRAINING_ARTIFACTS_DIR, "checkpoints/whisper-sheng/merged")
    merge_lora(args.model, adapter_path, merged_dir)

    # Step 2: Convert to CTranslate2
    ct2_dir = os.path.join(os.path.dirname(SCRIPT_DIR), "models/whisper-sheng-ct2")
    convert_to_ctranslate2(merged_dir, ct2_dir, args.quantize)

    # Step 3: Verify
    if verify_model(ct2_dir):
        logger.info("=" * 60)
        logger.info("EXPORT SUCCESSFUL")
        logger.info(f"Model: {ct2_dir}")
        logger.info(f"Quantization: {args.quantize}")
        logger.info("")
        logger.info("To use in Sage, set in .env:")
        logger.info(f"  STT_MODEL_PATH={ct2_dir}")
        logger.info("  STT_LANGUAGE=sw")
        logger.info("")
        logger.info("For Jetson: scp -r the directory to your Jetson")
        logger.info("=" * 60)
    else:
        logger.error("Export verification failed. Check the model manually.")

    # Cleanup merged model (large, no longer needed)
    if args.cleanup:
        logger.info(f"Cleaning up merged model at {merged_dir}...")
        shutil.rmtree(merged_dir)


def main():
    parser = argparse.ArgumentParser(description="Export fine-tuned Whisper to CTranslate2")
    parser.add_argument("--model", default="whisper-small", help="Base Whisper model name")
    parser.add_argument("--quantize", default="int8", choices=["int8", "float16", "float32"],
                        help="CTranslate2 quantization")
    parser.add_argument("--no-cleanup", dest="cleanup", action="store_false",
                        help="Keep merged model after conversion")
    args = parser.parse_args()
    export(args)


if __name__ == "__main__":
    main()
