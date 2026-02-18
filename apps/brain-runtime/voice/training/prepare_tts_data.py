"""
Prepare training data for Qwen3-TTS fine-tuning.

Reads exported TTS JSONL, performs sanity filtering, runs audio through
Qwen3-TTS-Tokenizer-12Hz to generate audio_codes, and writes the JSONL
expected by sft_12hz.py.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import wave
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List

# Ensure workspace root is importable when run via apps/... path.
_probe = Path(__file__).resolve().parent
for _parent in [_probe, *_probe.parents]:
    if (_parent / "sage.py").exists():
        if str(_parent) not in sys.path:
            sys.path.insert(0, str(_parent))
        break

from brain.voice.paths import get_project_root, get_training_artifacts_dir, get_training_data_dir

logging.basicConfig(level=logging.INFO, format="[TTS-Prep] %(asctime)s - %(message)s")
logger = logging.getLogger("TTS-Prep")

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = get_project_root(__file__)
DEFAULT_DATA_DIR = str(get_training_data_dir(__file__))
DEFAULT_TOKENIZER = str(get_training_artifacts_dir(__file__) / "models" / "Qwen3-TTS-Tokenizer-12Hz")
DEFAULT_REF_AUDIO = str((PROJECT_ROOT / "brain" / "voice" / "qwen_reference.wav").resolve())
BATCH_SIZE = 32


def _norm_text(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _duration_seconds(path: str) -> float:
    with wave.open(path, "rb") as wf:
        return wf.getnframes() / float(wf.getframerate())


def _resolve_data_path(raw_path: str, data_dir: str) -> str:
    """Resolve historical/broken absolute paths into current training_data root."""
    candidates: List[Path] = []
    raw = (raw_path or "").strip()
    data_root = Path(data_dir).resolve()

    if raw:
        p = Path(raw).expanduser()
        candidates.append(p)

        # Map old absolute prefixes to current artifacts root.
        marker = "artifacts/voice/training_data/"
        if marker in raw:
            rel = raw.split(marker, 1)[1]
            candidates.append(data_root / rel)
        marker = "brain/voice/training_data/"
        if marker in raw:
            rel = raw.split(marker, 1)[1]
            candidates.append(data_root / rel)

        # Fallback by basename into processed/.
        candidates.append(data_root / "processed" / p.name)

    for c in candidates:
        if c.exists():
            return str(c.resolve())

    # Keep a deterministic output path even when missing.
    if candidates:
        return str(candidates[0])
    return ""


def _resolve_ref_path(raw_ref: str) -> str:
    candidates = [
        Path((raw_ref or "").strip()).expanduser(),
        Path(DEFAULT_REF_AUDIO),
        SCRIPT_DIR.parent / "qwen_reference.wav",
    ]
    for c in candidates:
        if str(c).strip() and c.exists():
            return str(c.resolve())
    return str(Path(DEFAULT_REF_AUDIO))


def load_training_data(data_dir: str) -> List[Dict[str, str]]:
    """Load exported TTS JSONL (or build entries from manifest fallback)."""
    tts_jsonl = os.path.join(data_dir, "tts_training.jsonl")

    if not os.path.exists(tts_jsonl):
        manifest_path = os.path.join(data_dir, "manifest.jsonl")
        if not os.path.exists(manifest_path):
            logger.error(f"No training data found in {data_dir}")
            logger.error("Run './sage collect' first, then './sage collect --export'.")
            sys.exit(1)

        ref_audio = _resolve_ref_path(DEFAULT_REF_AUDIO)
        if not os.path.exists(ref_audio):
            logger.error(f"Reference audio not found at {ref_audio}")
            logger.error("Run './sage collect --export' to generate reference audio.")
            sys.exit(1)

        logger.info("Building from manifest (no tts_training.jsonl found)...")
        entries: List[Dict[str, str]] = []
        with open(manifest_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                item = json.loads(line)
                entries.append(
                    {
                        "audio": _resolve_data_path(item.get("tts_path", ""), data_dir),
                        "text": item.get("text", ""),
                        "ref_audio": ref_audio,
                    }
                )
        logger.info(f"Built {len(entries)} entries from manifest")
        return entries

    entries: List[Dict[str, str]] = []
    with open(tts_jsonl, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            entries.append(
                {
                    "audio": _resolve_data_path(item.get("audio", item.get("audio_path", "")), data_dir),
                    "text": item.get("text", ""),
                    "ref_audio": _resolve_ref_path(item.get("ref_audio", DEFAULT_REF_AUDIO)),
                }
            )

    logger.info(f"Loaded {len(entries)} entries from {tts_jsonl}")
    return entries


def basic_sanity_filter(
    entries: List[Dict[str, str]],
    min_duration: float,
    max_duration: float,
    max_duplicates: int,
) -> List[Dict[str, str]]:
    """
    Apply deterministic sanity checks before tokenization.

    This blocks obvious corruption:
    - missing audio
    - empty text
    - very short/long clips
    - excessive duplicate transcripts
    """
    text_counts: Counter[str] = Counter()
    kept: List[Dict[str, str]] = []
    dropped = Counter()

    for entry in entries:
        audio = entry.get("audio", "")
        text = (entry.get("text", "") or "").strip()
        ref = entry.get("ref_audio", "")

        if not text:
            dropped["empty_text"] += 1
            continue
        if not audio or not os.path.exists(audio):
            dropped["missing_audio"] += 1
            continue
        if not ref or not os.path.exists(ref):
            dropped["missing_ref_audio"] += 1
            continue

        try:
            dur = _duration_seconds(audio)
        except Exception:
            dropped["unreadable_audio"] += 1
            continue

        if dur < min_duration:
            dropped["too_short"] += 1
            continue
        if dur > max_duration:
            dropped["too_long"] += 1
            continue

        key = _norm_text(text)
        text_counts[key] += 1
        if text_counts[key] > max_duplicates:
            dropped["duplicate_text_cap"] += 1
            continue

        kept.append(entry)

    logger.info(f"Sanity filter kept {len(kept)}/{len(entries)} samples")
    for reason, count in sorted(dropped.items()):
        logger.info(f"  Dropped {count} for {reason}")
    return kept


def asr_sanity_filter(
    entries: List[Dict[str, str]],
    threshold: float,
    asr_model: str,
    asr_device: str,
) -> List[Dict[str, str]]:
    """
    Use quick ASR alignment to catch transcript/audio mismatches.

    Clips with <=3 words are skipped to avoid over-filtering short utterances.
    """
    try:
        from faster_whisper import WhisperModel
    except Exception as exc:
        logger.error(f"ASR sanity check requested but faster-whisper is unavailable: {exc}")
        sys.exit(1)

    compute_type = "float16" if asr_device.startswith("cuda") else "int8"
    logger.info(
        f"Running ASR sanity filter on {len(entries)} samples "
        f"(model={asr_model}, device={asr_device}, threshold={threshold})..."
    )
    model = WhisperModel(asr_model, device=asr_device, compute_type=compute_type)

    kept: List[Dict[str, str]] = []
    dropped = 0
    checked = 0
    skipped_short = 0

    for idx, entry in enumerate(entries, 1):
        ref_text = (entry.get("text", "") or "").strip()
        if len(ref_text.split()) <= 3:
            kept.append(entry)
            skipped_short += 1
            continue

        try:
            segments, _ = model.transcribe(
                entry["audio"],
                beam_size=1,
                best_of=1,
                language="en",
                condition_on_previous_text=False,
                temperature=0.0,
            )
            hyp = " ".join(seg.text.strip() for seg in segments).strip()
        except Exception:
            dropped += 1
            continue

        checked += 1
        score = SequenceMatcher(None, _norm_text(ref_text), _norm_text(hyp)).ratio()
        if score >= threshold:
            kept.append(entry)
        else:
            dropped += 1

        if idx % 25 == 0:
            logger.info(f"  ASR sanity progress: {idx}/{len(entries)}")

    logger.info(
        f"ASR sanity kept {len(kept)}/{len(entries)} samples "
        f"(checked={checked}, short_skipped={skipped_short}, dropped={dropped})"
    )
    return kept


def tokenize_batched(entries: List[Dict[str, str]], tokenizer_path: str, device: str = "cuda"):
    """Run audio through Qwen3-TTS-Tokenizer-12Hz to get audio_codes."""
    from qwen_tts import Qwen3TTSTokenizer

    logger.info(f"Loading Qwen3-TTS Tokenizer from {tokenizer_path}...")
    tokenizer = Qwen3TTSTokenizer.from_pretrained(
        tokenizer_path,
        device_map=device,
    )
    logger.info("Tokenizer loaded.")

    if not entries:
        logger.error("No valid entries left after sanity filtering.")
        sys.exit(1)

    logger.info(f"Tokenizing {len(entries)} audio files in batches of {BATCH_SIZE}...")

    output_entries = []
    batch_entries = []
    batch_audios = []

    for entry in entries:
        batch_entries.append(entry)
        batch_audios.append(entry["audio"])

        if len(batch_entries) >= BATCH_SIZE:
            enc_res = tokenizer.encode(batch_audios)
            for code, e in zip(enc_res.audio_codes, batch_entries):
                e["audio_codes"] = code.cpu().tolist()
                output_entries.append(e)
            logger.info(f"  Tokenized {len(output_entries)}/{len(entries)}")
            batch_entries.clear()
            batch_audios.clear()

    if batch_audios:
        enc_res = tokenizer.encode(batch_audios)
        for code, e in zip(enc_res.audio_codes, batch_entries):
            e["audio_codes"] = code.cpu().tolist()
            output_entries.append(e)

    logger.info(f"Tokenized {len(output_entries)} audio files successfully")
    return output_entries


def prepare(
    data_dir: str,
    tokenizer_path: str,
    output_path: str,
    device: str = "cuda",
    min_duration: float = 0.6,
    max_duration: float = 20.0,
    max_duplicates: int = 3,
    sanity_asr: bool = True,
    asr_threshold: float = 0.55,
    asr_model: str = "tiny.en",
    asr_device: str = "cpu",
):
    """Main preparation pipeline."""
    entries = load_training_data(data_dir)
    entries = basic_sanity_filter(
        entries,
        min_duration=min_duration,
        max_duration=max_duration,
        max_duplicates=max_duplicates,
    )

    if sanity_asr:
        entries = asr_sanity_filter(
            entries,
            threshold=asr_threshold,
            asr_model=asr_model,
            asr_device=asr_device,
        )

    output_entries = tokenize_batched(entries, tokenizer_path, device)

    with open(output_path, "w", encoding="utf-8") as f:
        for entry in output_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    logger.info(f"Prepared {len(output_entries)} samples -> {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Prepare data for Qwen3-TTS fine-tuning")
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR, help="Training data directory")
    parser.add_argument("--tokenizer", default=DEFAULT_TOKENIZER, help="Qwen3-TTS tokenizer path")
    parser.add_argument("--output", default=None, help="Output JSONL path")
    parser.add_argument("--device", default="cuda", help="Tokenizer device map (cuda/cpu)")
    parser.add_argument("--min-duration", type=float, default=0.6, help="Minimum clip duration in seconds")
    parser.add_argument("--max-duration", type=float, default=20.0, help="Maximum clip duration in seconds")
    parser.add_argument("--max-duplicates", type=int, default=3, help="Maximum identical transcript repeats")
    parser.add_argument("--sanity-asr", dest="sanity_asr", action="store_true", help="Enable ASR mismatch filtering")
    parser.add_argument("--no-sanity-asr", dest="sanity_asr", action="store_false", help="Disable ASR mismatch filtering")
    parser.add_argument("--asr-threshold", type=float, default=0.55, help="ASR text similarity threshold")
    parser.add_argument("--asr-model", default="tiny.en", help="faster-whisper model for sanity checks")
    parser.add_argument("--asr-device", default="cpu", help="ASR device (cpu/cuda)")
    parser.set_defaults(sanity_asr=True)
    args = parser.parse_args()

    if args.output is None:
        args.output = os.path.join(args.data_dir, "tts_tokenized.jsonl")

    prepare(
        data_dir=args.data_dir,
        tokenizer_path=args.tokenizer,
        output_path=args.output,
        device=args.device,
        min_duration=args.min_duration,
        max_duration=args.max_duration,
        max_duplicates=args.max_duplicates,
        sanity_asr=args.sanity_asr,
        asr_threshold=args.asr_threshold,
        asr_model=args.asr_model,
        asr_device=args.asr_device,
    )


if __name__ == "__main__":
    main()
