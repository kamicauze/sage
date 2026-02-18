"""
Qwen3-TTS Evaluation Tool

Generates comparison audio between base and fine-tuned models
for subjective evaluation of Sheng voice quality.

Usage:
    python brain/voice/training/eval_tts.py --size 0.6b
    python brain/voice/training/eval_tts.py --size 1.7b --phrases "Sasa niaje" "Mambo vipi"
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

from brain.voice.paths import get_project_root, get_training_artifacts_dir

logging.basicConfig(level=logging.INFO, format="[TTS-Eval] %(asctime)s - %(message)s")
logger = logging.getLogger("TTS-Eval")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = str(get_project_root(__file__))
TRAINING_ARTIFACTS_DIR = str(get_training_artifacts_dir(__file__))

# Add qwen_tts package to path
QWEN_TTS_DIR = os.path.join(SCRIPT_DIR, "qwen3-tts")
if QWEN_TTS_DIR not in sys.path:
    sys.path.insert(0, QWEN_TTS_DIR)

# Default evaluation phrases covering Sheng patterns
DEFAULT_PHRASES = [
    "Sasa, niaje? Mambo vipi?",
    "Bro the meeting was so boring, nilikuwa tu naskia usingizi.",
    "Sage, washa taa kwa sitting room.",
    "I think tunafaa plan this thing properly before we start.",
    "The temperature today is twenty six degrees Celsius.",
    "Maze I'm so happy bana, you have no idea.",
    "Nimekuwa thinking about starting a side hustle, you know.",
    "Habari yako? Mimi niko sawa tu.",
    "Turn on the lights hapa kwa bedroom.",
    "That's the funniest thing I've heard all week!",
]


def generate_with_model(
    model_path,
    phrases,
    output_dir,
    prefix,
    speaker_name=None,
    ref_audio=None,
    device="cuda",
    max_new_tokens=640,
):
    """Load a model, generate audio for all phrases, then free it."""
    import torch
    import soundfile as sf
    from qwen_tts.inference.qwen3_tts_model import Qwen3TTSModel

    logger.info(f"Loading model from {model_path}...")
    tts = Qwen3TTSModel.from_pretrained(
        model_path,
        torch_dtype=torch.bfloat16,
        attn_implementation="sdpa",
    )
    tts.model = tts.model.to(device)
    tts.device = torch.device(device)

    model_type = tts.model.tts_model_type
    logger.info(f"Model type: {model_type}, generating {len(phrases)} samples...")

    results = []
    for i, phrase in enumerate(phrases):
        logger.info(f"  [{i+1}/{len(phrases)}] '{phrase[:60]}'")
        try:
            # Cap generation length to avoid runaway decoding loops.
            phrase_max_tokens = max(128, min(max_new_tokens, 64 + len(phrase.split()) * 12))
            if model_type == "custom_voice":
                wavs, sr = tts.generate_custom_voice(
                    text=phrase,
                    speaker=speaker_name,
                    max_new_tokens=phrase_max_tokens,
                )
            elif model_type == "base":
                wavs, sr = tts.generate_voice_clone(
                    text=phrase,
                    ref_audio=ref_audio,
                    x_vector_only_mode=True,
                    max_new_tokens=phrase_max_tokens,
                )
            else:
                logger.warning(f"Unknown model type '{model_type}', skipping")
                continue

            out_path = os.path.join(output_dir, f"{i:03d}_{prefix}.wav")
            sf.write(out_path, wavs[0], sr)
            results.append({"phrase": phrase, f"{prefix}_audio": out_path})
        except Exception as e:
            logger.error(f"  Failed: {e}")
            results.append({"phrase": phrase, f"{prefix}_audio": None, "error": str(e)})

    # Free GPU memory
    del tts
    if device == "cuda":
        torch.cuda.empty_cache()

    return results


def evaluate(args):
    """Generate comparison audio samples."""
    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"
    epoch_tag = f"epoch{args.checkpoint}" if args.checkpoint is not None else "final"
    output_dir = os.path.join(TRAINING_ARTIFACTS_DIR, f"eval_output/{args.size}/{epoch_tag}")
    os.makedirs(output_dir, exist_ok=True)

    ref_audio = os.path.join(PROJECT_ROOT, "brain/voice/qwen_reference.wav")
    if not os.path.exists(ref_audio):
        logger.warning("No reference audio found at brain/voice/qwen_reference.wav")
        ref_audio = None

    phrases = args.phrases if args.phrases else DEFAULT_PHRASES

    base_model_path = os.path.join(TRAINING_ARTIFACTS_DIR, f"models/Qwen3-TTS-12Hz-{args.size.upper()}-Base")
    if args.checkpoint is not None:
        checkpoint_path = os.path.join(
            TRAINING_ARTIFACTS_DIR,
            f"checkpoints/qwen3-tts-sheng-{args.size}/checkpoint-epoch-{args.checkpoint}",
        )
    else:
        checkpoint_path = os.path.join(TRAINING_ARTIFACTS_DIR, f"checkpoints/qwen3-tts-sheng-{args.size}/final")

    if not os.path.exists(base_model_path):
        logger.error(f"Base model not found at {base_model_path}")
        sys.exit(1)

    has_finetuned = os.path.exists(checkpoint_path)
    if not has_finetuned:
        logger.warning(f"No fine-tuned checkpoint at {checkpoint_path}")
        logger.warning("Will only generate base model samples.")

    # Generate fine-tuned samples first (more important)
    ft_results = []
    if has_finetuned:
        ft_results = generate_with_model(
            model_path=checkpoint_path,
            phrases=phrases,
            output_dir=output_dir,
            prefix="finetuned",
            speaker_name=args.speaker_name,
            device=device,
            max_new_tokens=args.max_new_tokens,
        )

    # Generate base model samples
    base_results = []
    if ref_audio:
        base_results = generate_with_model(
            model_path=base_model_path,
            phrases=phrases,
            output_dir=output_dir,
            prefix="base",
            ref_audio=ref_audio,
            device=device,
            max_new_tokens=args.max_new_tokens,
        )
    else:
        logger.warning("Skipping base model (no reference audio for voice cloning)")

    # Merge results
    results = []
    for i, phrase in enumerate(phrases):
        entry = {"phrase": phrase}
        if i < len(ft_results) and ft_results[i].get("finetuned_audio"):
            entry["finetuned_audio"] = ft_results[i]["finetuned_audio"]
        if i < len(base_results) and base_results[i].get("base_audio"):
            entry["base_audio"] = base_results[i]["base_audio"]
        results.append(entry)

    # Write results summary
    summary_path = os.path.join(output_dir, "eval_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    generated = sum(1 for r in results if r.get("finetuned_audio") or r.get("base_audio"))

    # Print evaluation checklist
    print("\n" + "=" * 60)
    print("EVALUATION CHECKLIST (MOS - Mean Opinion Score)")
    print("=" * 60)
    print("\nRate each sample 1-5 on these criteria:")
    print("  1. Naturalness - Does it sound like natural speech?")
    print("  2. Sheng Prosody - Does the intonation feel Kenyan?")
    print("  3. Code-switching - Are English/Swahili transitions smooth?")
    print("  4. Speaker Similarity - Does it sound like your voice?")
    print("  5. Intelligibility - Can you understand every word?")
    print(f"\nSamples saved to: {output_dir}")
    print(f"Summary: {summary_path}")
    print(f"Total phrases evaluated: {generated}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Evaluate Qwen3-TTS fine-tuning quality")
    parser.add_argument("--size", choices=["0.6b", "1.7b"], default="0.6b", help="Model size")
    parser.add_argument("--phrases", nargs="+", default=None, help="Custom evaluation phrases")
    parser.add_argument("--checkpoint", type=int, default=None, help="Specific epoch checkpoint to eval (e.g. 1, 3)")
    parser.add_argument("--speaker-name", default="sage_sheng", help="Speaker name in fine-tuned model")
    parser.add_argument("--max-new-tokens", type=int, default=640, help="Generation cap to prevent runaway samples")
    args = parser.parse_args()
    evaluate(args)


if __name__ == "__main__":
    main()
