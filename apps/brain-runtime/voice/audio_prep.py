"""
Audio Preprocessing Utilities for Sage Sheng Training Pipeline.

Handles silence trimming, normalization, sample rate conversion,
quality validation, and reference audio extraction for both
Qwen3-TTS and Whisper fine-tuning data preparation.
"""

import os
import logging
import numpy as np
import soundfile as sf
import librosa

logger = logging.getLogger("AudioPrep")

# Target sample rates
TTS_SAMPLE_RATE = 24000   # Qwen3-TTS expects 24kHz
STT_SAMPLE_RATE = 16000   # Whisper expects 16kHz


def load_audio(path, target_sr=None):
    """Load audio file, optionally resample."""
    audio, sr = sf.read(path, dtype="float32")
    # Convert stereo to mono
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if target_sr and sr != target_sr:
        audio = librosa.resample(audio, orig_sr=sr, target_sr=target_sr)
        sr = target_sr
    return audio, sr


def trim_silence(audio, sr, top_db=25, margin_ms=50):
    """Trim leading/trailing silence. Keep a small margin for naturalness."""
    trimmed, index = librosa.effects.trim(audio, top_db=top_db)
    # Add margin around the detected speech region
    margin_samples = int(sr * margin_ms / 1000)
    start = max(0, index[0] - margin_samples)
    end = min(len(audio), index[1] + margin_samples)
    return audio[start:end]


def normalize_peak(audio, target_db=-1.0):
    """Peak-normalize audio to target dB."""
    peak = np.max(np.abs(audio))
    if peak == 0:
        return audio
    target_amplitude = 10 ** (target_db / 20)
    return audio * (target_amplitude / peak)


def compute_snr(audio, sr, silence_duration=0.1):
    """Estimate SNR by comparing signal energy to noise floor."""
    # Use first/last silence_duration seconds as noise estimate
    noise_samples = int(sr * silence_duration)
    if len(audio) < noise_samples * 4:
        return 0.0  # Too short to estimate

    noise = np.concatenate([audio[:noise_samples], audio[-noise_samples:]])
    noise_power = np.mean(noise ** 2) + 1e-10
    signal_power = np.mean(audio ** 2) + 1e-10
    snr = 10 * np.log10(signal_power / noise_power)
    return float(snr)


def check_clipping(audio, threshold=0.99):
    """Check for clipping (samples at or near max amplitude)."""
    clipped_samples = np.sum(np.abs(audio) >= threshold)
    clipping_ratio = clipped_samples / len(audio)
    return {
        "clipped_samples": int(clipped_samples),
        "clipping_ratio": float(clipping_ratio),
        "is_clipped": clipping_ratio > 0.001  # More than 0.1% clipped
    }


def validate_audio(audio, sr, min_duration=0.3, max_duration=60.0, min_snr=0.0):
    """Validate audio quality for training. SNR check is lenient for home recordings."""
    duration = len(audio) / sr
    issues = []

    if duration < min_duration:
        issues.append(f"Too short: {duration:.1f}s (min {min_duration}s)")
    if duration > max_duration:
        issues.append(f"Too long: {duration:.1f}s (max {max_duration}s)")

    snr = compute_snr(audio, sr)
    if snr < min_snr:
        issues.append(f"Low SNR: {snr:.1f}dB (min {min_snr}dB)")

    clip_info = check_clipping(audio)
    if clip_info["is_clipped"]:
        issues.append(f"Clipping detected: {clip_info['clipped_samples']} samples")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "duration": duration,
        "snr": snr,
        "clipping": clip_info,
    }


def process_for_training(input_path, output_dir, file_id):
    """
    Process a raw recording into training-ready formats.
    Creates both TTS (24kHz) and STT (16kHz) versions.

    Returns dict with paths and metadata, or None if invalid.
    """
    os.makedirs(output_dir, exist_ok=True)

    # Load at native sample rate
    audio, sr = load_audio(input_path)

    # Trim silence
    audio = trim_silence(audio, sr)

    # Normalize
    audio = normalize_peak(audio, target_db=-1.0)

    # Validate
    validation = validate_audio(audio, sr)
    if not validation["valid"]:
        logger.warning(f"Audio {file_id} failed validation: {validation['issues']}")
        return None

    # Save TTS version (24kHz)
    tts_audio = librosa.resample(audio, orig_sr=sr, target_sr=TTS_SAMPLE_RATE) if sr != TTS_SAMPLE_RATE else audio
    tts_path = os.path.join(output_dir, f"{file_id}_24k.wav")
    sf.write(tts_path, tts_audio, TTS_SAMPLE_RATE)

    # Save STT version (16kHz)
    stt_audio = librosa.resample(audio, orig_sr=sr, target_sr=STT_SAMPLE_RATE) if sr != STT_SAMPLE_RATE else audio
    stt_path = os.path.join(output_dir, f"{file_id}_16k.wav")
    sf.write(stt_path, stt_audio, STT_SAMPLE_RATE)

    return {
        "file_id": file_id,
        "tts_path": tts_path,
        "stt_path": stt_path,
        "duration": validation["duration"],
        "snr": validation["snr"],
    }


def extract_reference_audio(audio_dir, output_path, target_duration=3.0):
    """
    Find the best 3-second clip from recorded data for Qwen3-TTS reference.
    Selects the clip with highest SNR and clearest speech.
    """
    best_clip = None
    best_snr = -float("inf")

    for fname in os.listdir(audio_dir):
        if not fname.endswith("_24k.wav"):
            continue

        path = os.path.join(audio_dir, fname)
        audio, sr = sf.read(path, dtype="float32")
        duration = len(audio) / sr

        if duration < target_duration:
            continue

        # Try multiple windows and pick highest SNR
        target_samples = int(sr * target_duration)
        step = sr  # 1-second steps
        for start in range(0, len(audio) - target_samples, step):
            clip = audio[start:start + target_samples]
            snr = compute_snr(clip, sr)
            clip_info = check_clipping(clip)

            if snr > best_snr and not clip_info["is_clipped"]:
                best_snr = snr
                best_clip = clip

    if best_clip is not None:
        sf.write(output_path, best_clip, TTS_SAMPLE_RATE)
        logger.info(f"Reference audio saved: {output_path} (SNR: {best_snr:.1f}dB)")
        return output_path
    else:
        logger.error("No suitable clip found for reference audio")
        return None


def batch_process(raw_dir, output_dir, texts_map=None):
    """
    Process all recordings in a directory.

    Args:
        raw_dir: Directory with raw WAV recordings
        output_dir: Output directory for processed files
        texts_map: Optional dict mapping filename -> transcript text

    Returns:
        List of processed file metadata dicts
    """
    results = []

    for fname in sorted(os.listdir(raw_dir)):
        if not fname.endswith(".wav"):
            continue

        file_id = os.path.splitext(fname)[0]
        input_path = os.path.join(raw_dir, fname)

        result = process_for_training(input_path, output_dir, file_id)
        if result:
            # Attach transcript if available
            if texts_map and file_id in texts_map:
                result["text"] = texts_map[file_id]
            else:
                txt_path = os.path.join(raw_dir, f"{file_id}.txt")
                if os.path.exists(txt_path):
                    with open(txt_path, "r", encoding="utf-8") as f:
                        result["text"] = f.read().strip()

            results.append(result)

    logger.info(f"Processed {len(results)} files from {raw_dir}")
    return results
