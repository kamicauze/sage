import json
import os
import shutil
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import List

import gradio as gr
import numpy as np
import paho.mqtt.client as mqtt

# Ensure workspace root is importable when run via brain/... path.
_probe = Path(__file__).resolve().parent
for _parent in [_probe, *_probe.parents]:
    if (_parent / "sage.py").exists():
        if str(_parent) not in sys.path:
            sys.path.insert(0, str(_parent))
        break

from brain.voice.paths import get_training_artifacts_dir

# MQTT controls for live mouth service.
MQTT_HOST = "localhost"
MQTT_PORT = 1883

VOICE_DIR = Path(__file__).resolve().parent
TRAINING_ARTIFACTS_DIR = Path(get_training_artifacts_dir(__file__))
REFERENCE_WAV = VOICE_DIR / "reference.wav"
QWEN_REFERENCE_WAV = VOICE_DIR / "qwen_reference.wav"
FEEDBACK_DIR = TRAINING_ARTIFACTS_DIR / "feedback"
STT_FEEDBACK_JSONL = FEEDBACK_DIR / "stt_annotations.jsonl"
STT_FEEDBACK_AUDIO_DIR = FEEDBACK_DIR / "stt_audio"

PHONEME_SETS = {
    "J vs Y": [
        "Juma just joined the project yesterday.",
        "Sasa niaje, Jide? Tuko jobsite leo?",
        "The jacket in that shop is genuine leather.",
        "Jana niliona John akiwa na yellow jersey mpya.",
        "Please adjust the generator before we start the journey.",
        "Niaje bro, hiyo joke ilikuwa aje?",
    ],
    "CH vs SH": [
        "Check the charger in the kitchen shelf.",
        "She chose fresh chips and chai for lunch.",
        "The church choir shared a short chorus.",
        "Nishow chance ya schedule ya chama meeting.",
        "Chef alisema fish ni fresh, si chewy.",
    ],
    "Final Consonants": [
        "I packed the laptop, mask, and notebook.",
        "Please switch the light and lock the desk.",
        "Stop at the next point and check the map.",
        "Text me back before you sleep tonight.",
        "Niko strict na budget, lazima nipick right amount.",
    ],
    "Code-switch Cadence": [
        "Maze I need this done leo, no stress.",
        "Nimekuwa planning this project all week, sasa twende.",
        "Bro,akikisha lights zimezimwa before ulale.",
        "We can meet kwa parking lot then tuchat kidogo.",
        "I am calm but harakisha tu, time inaenda.",
    ],
}

QWEN_STYLE_PRESETS = {
    "Default (Balanced)": {
        "instruction": "",
        "temperature": 0.9,
        "top_p": 1.0,
        "top_k": 50,
        "repetition_penalty": 1.08,
        "do_sample": True,
        "subtalker_dosample": True,
        "subtalker_top_k": 50,
        "subtalker_top_p": 1.0,
        "subtalker_temperature": 0.9,
        "non_streaming_mode": True,
    },
    "Reflective Analytical (Calm)": {
        "instruction": (
            "Speak in a thoughtful, analytical style, as if thinking while speaking. "
            "Use moderate-to-slow pace with longer natural pauses between ideas and occasional micro-hesitations. "
            "Tone must stay calm, grounded, and precise; avoid dramatic or announcer energy. "
            "Qualify thoughts gently instead of strong assertions. "
            "Use slight falling intonation at sentence endings. "
            "Keep emotion restrained and internal. "
            "Allow some sentence fragments to trail off softly before resolving. "
            "Keep articulation slightly loose and less polished, while remaining sincere and honest. "
            "Sound like a private reflective voice note, not a performance."
        ),
        "temperature": 0.72,
        "top_p": 0.9,
        "top_k": 24,
        "repetition_penalty": 1.06,
        "do_sample": True,
        "subtalker_dosample": True,
        "subtalker_top_k": 24,
        "subtalker_top_p": 0.9,
        "subtalker_temperature": 0.78,
        "non_streaming_mode": True,
    },
}

DEFAULT_QWEN_STYLE_PRESET = "Reflective Analytical (Calm)"

_QWEN_LOCK = threading.Lock()
_QWEN_MODEL = None
_QWEN_MODEL_PATH = None
_QWEN_DEVICE = None
_QWEN_MODEL_LAST_LOAD_TS = None

_STT_LOCK = threading.Lock()
_STT_MODEL = None
_STT_MODEL_ID = None
_STT_DEVICE = None
_STT_COMPUTE_TYPE = None
_STT_MODEL_LAST_LOAD_TS = None

QWEN_LANGUAGE_ALIASES = {
    "auto": "Auto",
    "en": "English",
    "english": "English",
    "zh": "Chinese",
    "chinese": "Chinese",
    "fr": "French",
    "french": "French",
    "de": "German",
    "german": "German",
    "it": "Italian",
    "italian": "Italian",
    "ja": "Japanese",
    "japanese": "Japanese",
    "ko": "Korean",
    "korean": "Korean",
    "pt": "Portuguese",
    "portuguese": "Portuguese",
    "ru": "Russian",
    "russian": "Russian",
    "es": "Spanish",
    "spanish": "Spanish",
}

QWEN_LANGUAGE_DROPDOWN_CHOICES = [
    "Auto",
    "English",
    "sw (fallback to Auto)",
    "Chinese",
    "French",
    "German",
    "Italian",
    "Japanese",
    "Korean",
    "Portuguese",
    "Russian",
    "Spanish",
]

STT_SCRIPT_STYLE_GUIDES = {
    "Sheng Casual": "casual Sheng and Kenyan English code-switching for everyday conversation",
    "Kenyan English": "clean Kenyan English with natural local phrasing",
    "Smart Home Command": "home automation command style while sounding natural",
    "Technical": "developer and AI workflow language with clear pacing",
    "Narrative": "short story-like narration with expressive but clear delivery",
}

try:
    from dotenv import load_dotenv

    APP_ROOT = VOICE_DIR.parent
    REPO_ROOT = APP_ROOT.parent.parent
    load_dotenv(APP_ROOT / ".env")
    load_dotenv(REPO_ROOT / ".env")
except Exception:
    pass


def send_config(engine, speed, voice, qwen_instruction):
    client = mqtt.Client()
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    instruction = (qwen_instruction or "").strip()
    config = {
        "engine": engine.lower(),
        "speed": speed,
        "voice": voice,  # For Kokoro
        "qwen_instruction": instruction,
    }
    client.publish("sage/voice/config", json.dumps(config))
    client.disconnect()
    if instruction:
        return f"Config sent: {engine} ({speed}x), qwen_instruction applied."
    return f"Config sent: {engine} ({speed}x), qwen_instruction cleared."


def send_speech(text):
    client = mqtt.Client()
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.publish("sage/voice/response", json.dumps({"text": text}))
    client.disconnect()
    return "Sent to speaker queue."


def _copy_reference(audio_path, target_path: Path, success_msg: str):
    if not audio_path:
        return "No audio provided."
    src = Path(audio_path)
    if not src.exists():
        return f"Audio path not found: {src}"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, target_path)
    return success_msg


def update_reference(audio_path):
    return _copy_reference(audio_path, REFERENCE_WAV, "Reference audio updated for F5.")


def update_qwen_reference(audio_path):
    return _copy_reference(audio_path, QWEN_REFERENCE_WAV, "Qwen reference audio updated.")


def _qwen_repo_path() -> Path:
    return VOICE_DIR / "training" / "qwen3-tts"


def _ensure_qwen_importable():
    local_repo = _qwen_repo_path()
    if local_repo.exists() and str(local_repo) not in sys.path:
        sys.path.insert(0, str(local_repo))
    try:
        from qwen_tts import Qwen3TTSModel
    except Exception as exc:
        raise RuntimeError(
            "Failed to import qwen_tts. Run './sage train setup' and ensure qwen-tts is installed."
        ) from exc
    return Qwen3TTSModel


def _checkpoint_root(model_size: str) -> Path:
    return TRAINING_ARTIFACTS_DIR / "checkpoints" / f"qwen3-tts-sheng-{model_size}"


def _base_model_path(model_size: str) -> Path:
    return TRAINING_ARTIFACTS_DIR / "models" / f"Qwen3-TTS-12Hz-{model_size.upper()}-Base"


def _stt_local_model_path() -> Path:
    return VOICE_DIR / "models" / "whisper-sheng-ct2"


def _default_stt_model_id() -> str:
    local_path = _stt_local_model_path()
    if local_path.exists() and local_path.is_dir() and any(local_path.iterdir()):
        return str(local_path)
    return "medium.en"


def _append_jsonl(path: Path, record: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _format_stt_cache_status():
    with _STT_LOCK:
        if _STT_MODEL is None:
            return "STT Cache: COLD (no model loaded)"
        age = (
            time.time() - _STT_MODEL_LAST_LOAD_TS
            if _STT_MODEL_LAST_LOAD_TS is not None
            else 0.0
        )
        return (
            f"STT Cache: WARM | device={_STT_DEVICE} | compute={_STT_COMPUTE_TYPE} | "
            f"model={_STT_MODEL_ID} | loaded {age:.1f}s ago"
        )


def refresh_stt_cache_status():
    return _format_stt_cache_status()


def _resolve_stt_device(device_choice: str) -> str:
    preferred = (device_choice or "auto").strip().lower()
    if preferred not in {"auto", "cuda", "cpu"}:
        preferred = "auto"
    if preferred == "auto":
        try:
            import torch
        except Exception:
            return "cpu"
        return "cuda" if torch.cuda.is_available() else "cpu"
    return preferred


def _unload_stt_model():
    global _STT_MODEL, _STT_MODEL_ID, _STT_DEVICE, _STT_COMPUTE_TYPE, _STT_MODEL_LAST_LOAD_TS
    message = "No STT model is currently cached."
    with _STT_LOCK:
        if _STT_MODEL is not None:
            del _STT_MODEL
            _STT_MODEL = None
            _STT_MODEL_ID = None
            _STT_DEVICE = None
            _STT_COMPUTE_TYPE = None
            _STT_MODEL_LAST_LOAD_TS = None
            message = "Unloaded STT model cache."
            try:
                import torch

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass
    return message, _format_stt_cache_status()


def _load_stt_model(model_id: str, device_choice: str, compute_type: str):
    global _STT_MODEL, _STT_MODEL_ID, _STT_DEVICE, _STT_COMPUTE_TYPE, _STT_MODEL_LAST_LOAD_TS
    resolved_model_id = (model_id or "").strip() or _default_stt_model_id()
    resolved_device = _resolve_stt_device(device_choice)
    resolved_compute = (compute_type or "float16").strip()

    with _STT_LOCK:
        if (
            _STT_MODEL is not None
            and _STT_MODEL_ID == resolved_model_id
            and _STT_DEVICE == resolved_device
            and _STT_COMPUTE_TYPE == resolved_compute
        ):
            return _STT_MODEL, resolved_model_id, resolved_device, resolved_compute, False

        if _STT_MODEL is not None:
            del _STT_MODEL
            _STT_MODEL = None
            try:
                import torch

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass

        try:
            from faster_whisper import WhisperModel
        except Exception as exc:
            raise RuntimeError(
                "faster-whisper is not available. Install training dependencies first."
            ) from exc

        model = WhisperModel(
            resolved_model_id,
            device=resolved_device,
            compute_type=resolved_compute,
        )
        _STT_MODEL = model
        _STT_MODEL_ID = resolved_model_id
        _STT_DEVICE = resolved_device
        _STT_COMPUTE_TYPE = resolved_compute
        _STT_MODEL_LAST_LOAD_TS = time.time()
        return model, resolved_model_id, resolved_device, resolved_compute, True


def prewarm_stt_model(model_id: str, device_choice: str, compute_type: str):
    try:
        t0 = time.perf_counter()
        _model, resolved_model_id, resolved_device, resolved_compute, was_cold = _load_stt_model(
            model_id, device_choice, compute_type
        )
        elapsed = time.perf_counter() - t0
        state = "COLD load" if was_cold else "WARM cache"
        return (
            f"STT prewarm done: {state} on {resolved_device}/{resolved_compute} in {elapsed:.2f}s for {resolved_model_id}",
            _format_stt_cache_status(),
        )
    except Exception as exc:
        return f"STT prewarm failed: {exc}", _format_stt_cache_status()


def run_stt_probe(
    audio_path: str,
    model_id: str,
    device_choice: str,
    compute_type: str,
    beam_size: int,
    language_hint: str,
    initial_prompt: str,
    vad_filter: bool,
    condition_on_previous_text: bool,
    temperature: float,
):
    if not audio_path:
        return "", "", "No audio provided.", _format_stt_cache_status()

    path = Path(audio_path)
    if not path.exists():
        return "", "", f"Audio path not found: {path}", _format_stt_cache_status()

    status_lines = [f"Audio: {path}"]
    transcript = ""
    segments_json = "[]"
    started_total = time.perf_counter()

    def _safe_float(value, default=0.0):
        try:
            if value is None:
                return float(default)
            return float(value)
        except Exception:
            return float(default)

    try:
        t0 = time.perf_counter()
        model, resolved_model_id, resolved_device, resolved_compute, was_cold = _load_stt_model(
            model_id, device_choice, compute_type
        )
        load_elapsed = time.perf_counter() - t0
        load_state = "COLD load" if was_cold else "WARM cache"
        status_lines.append(
            f"Model: {resolved_model_id} on {resolved_device}/{resolved_compute} ({load_state}, load={load_elapsed:.2f}s)"
        )

        transcribe_kwargs = {
            "beam_size": int(beam_size),
            "best_of": 1,
            "temperature": float(temperature),
            "condition_on_previous_text": bool(condition_on_previous_text),
        }
        lang = (language_hint or "").strip()
        if lang and lang.lower() != "auto":
            transcribe_kwargs["language"] = lang
        prompt = (initial_prompt or "").strip()
        if prompt:
            transcribe_kwargs["initial_prompt"] = prompt
        if bool(vad_filter):
            transcribe_kwargs["vad_filter"] = True
            transcribe_kwargs["vad_parameters"] = {
                "min_silence_duration_ms": 200,
                "speech_pad_ms": 100,
            }

        t1 = time.perf_counter()
        segments_iter, info = model.transcribe(str(path), **transcribe_kwargs)
        segments = list(segments_iter)
        infer_elapsed = time.perf_counter() - t1

        text_parts = []
        segment_rows = []
        for segment in segments:
            text = (segment.text or "").strip()
            if text:
                text_parts.append(text)
            segment_rows.append(
                {
                    "id": int(segment.id),
                    "start": round(float(segment.start), 3),
                    "end": round(float(segment.end), 3),
                    "text": text,
                    "avg_logprob": round(_safe_float(segment.avg_logprob, 0.0), 4),
                    "no_speech_prob": round(_safe_float(segment.no_speech_prob, 0.0), 4),
                }
            )

        transcript = " ".join(text_parts).strip()
        segments_json = json.dumps(segment_rows, ensure_ascii=False, indent=2)

        audio_duration = _safe_float(getattr(info, "duration", 0.0), 0.0)
        if audio_duration <= 0 and segment_rows:
            audio_duration = max(0.0, segment_rows[-1]["end"] - segment_rows[0]["start"])
        rtf = infer_elapsed / max(audio_duration, 1e-3)

        status_lines.append(f"Detected language: {getattr(info, 'language', 'unknown')}")
        status_lines.append(
            f"Language probability: {_safe_float(getattr(info, 'language_probability', 0.0), 0.0):.3f}"
        )
        status_lines.append(
            f"Transcription: infer={infer_elapsed:.2f}s audio={audio_duration:.2f}s rtf={rtf:.2f}x"
        )
        status_lines.append(f"Segments: {len(segment_rows)}")
        if not transcript:
            status_lines.append("Transcript is empty (no speech detected or filtered).")
    except Exception as exc:
        status_lines.append(f"Transcription failed: {exc}")

    total_elapsed = time.perf_counter() - started_total
    status_lines.append(f"Total wall time: {total_elapsed:.2f}s")
    return transcript, segments_json, "\n".join(status_lines), _format_stt_cache_status()


def _resolve_script_llm_config():
    provider_raw = (
        os.getenv("SAGE_SCRIPT_LLM_PROVIDER")
        or os.getenv("SAGE_COLLECT_LLM_PROVIDER")
        or ""
    ).strip().lower()
    base_url = (
        os.getenv("SAGE_SCRIPT_LLM_BASE_URL")
        or os.getenv("SAGE_COLLECT_LLM_BASE_URL")
        or ""
    ).strip().rstrip("/")
    model = (
        os.getenv("SAGE_SCRIPT_LLM_MODEL")
        or os.getenv("SAGE_COLLECT_LLM_MODEL")
        or ""
    ).strip()
    api_key_override = (
        os.getenv("SAGE_SCRIPT_LLM_API_KEY")
        or os.getenv("SAGE_COLLECT_LLM_API_KEY")
        or ""
    ).strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    xai_key = os.getenv("XAI_API_KEY", "").strip() or os.getenv("GROK_API_KEY", "").strip()

    if provider_raw:
        provider = provider_raw
    elif api_key_override and "x.ai" in base_url:
        provider = "xai"
    elif openai_key:
        provider = "openai"
    elif xai_key:
        provider = "xai"
    else:
        provider = "openai"

    if provider in {"grok", "xai"}:
        provider = "xai"
        base_url = base_url or "https://api.x.ai/v1"
        model = model or "grok-3-mini"
        api_key = api_key_override or xai_key
    elif provider == "openai":
        base_url = base_url or "https://api.openai.com/v1"
        model = model or "gpt-4o-mini"
        api_key = api_key_override or openai_key
    else:
        provider = "openai-compatible"
        base_url = base_url or "https://api.openai.com/v1"
        model = model or "gpt-4o-mini"
        api_key = api_key_override or openai_key or xai_key

    timeout_raw = (
        os.getenv("SAGE_SCRIPT_LLM_TIMEOUT_SEC")
        or os.getenv("SAGE_COLLECT_LLM_TIMEOUT_SEC")
        or "25"
    )
    try:
        timeout_sec = float(timeout_raw)
    except Exception:
        timeout_sec = 25.0

    return {
        "provider": provider,
        "base_url": base_url,
        "model": model,
        "api_key": api_key,
        "timeout_sec": timeout_sec,
    }


def _extract_chat_text(choice):
    message = choice.get("message", {})
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text", "")
                if text:
                    parts.append(text)
        return " ".join(parts)
    return str(content or "")


def _normalize_script_text(text: str) -> str:
    clean = " ".join((text or "").replace("\r", " ").replace("\n", " ").split()).strip()
    if clean.startswith('"') and clean.endswith('"') and len(clean) >= 2:
        clean = clean[1:-1].strip()
    if clean.startswith("'") and clean.endswith("'") and len(clean) >= 2:
        clean = clean[1:-1].strip()
    if len(clean) > 800:
        clean = clean[:800].rsplit(" ", 1)[0].strip() + "..."
    return clean


def generate_stt_script(
    topic: str,
    style: str,
    target_seconds: int,
    include_numbers: bool,
    current_corrected: str,
):
    try:
        config = _resolve_script_llm_config()
        if not config["api_key"]:
            raise RuntimeError(
                f"Missing API key for provider '{config['provider']}'. "
                "Set SAGE_SCRIPT_LLM_API_KEY, or set SAGE_SCRIPT_LLM_PROVIDER=xai with XAI_API_KEY."
            )

        style_guide = STT_SCRIPT_STYLE_GUIDES.get(style, STT_SCRIPT_STYLE_GUIDES["Sheng Casual"])
        clean_topic = (topic or "").strip() or "daily life in Nairobi"
        words_target = max(12, min(140, int(float(target_seconds) * 2.6)))
        numbers_line = (
            "Include one natural number, date, time, or amount."
            if include_numbers
            else "Do not force numbers or dates unless they occur naturally."
        )

        messages = [
            {
                "role": "system",
                "content": (
                    "You write one short transcript script for speech data collection. "
                    "Return plain text only, no markdown, no title, no quotes."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Create one script that can be read out loud and used as a corrected transcript.\n"
                    f"Style: {style_guide}\n"
                    f"Topic: {clean_topic}\n"
                    f"Target length: about {words_target} words.\n"
                    "Language: Kenyan English with optional natural Sheng code-switching.\n"
                    "Format: one paragraph only.\n"
                    f"{numbers_line}"
                ),
            },
        ]
        payload = {
            "model": config["model"],
            "messages": messages,
            "temperature": 0.9,
        }
        req = urllib.request.Request(
            f"{config['base_url']}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {config['api_key']}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "sage-voice-lab/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=config["timeout_sec"]) as resp:
            response_json = json.loads(resp.read().decode("utf-8"))

        choices = response_json.get("choices") or []
        if not choices:
            raise RuntimeError("Cloud LLM returned no choices.")
        generated = _normalize_script_text(_extract_chat_text(choices[0]))
        if not generated:
            raise RuntimeError("Cloud LLM response was empty.")
        status = f"Generated corrected transcript ({len(generated.split())} words) via {config['provider']}:{config['model']}"
        return generated, status
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="ignore")
        error_body = " ".join(error_body.split())[:200]
        return current_corrected, f"Script generator error: HTTP {exc.code} {error_body}"
    except Exception as exc:
        return current_corrected, f"Script generator error: {exc}"


def save_stt_annotation(
    audio_path: str,
    transcript: str,
    corrected_text: str,
    quality: int,
    issue_tags: str,
    use_for_training: bool,
    notes: str,
    model_id: str,
    language_hint: str,
    beam_size: int,
    segments_json: str,
):
    if not audio_path:
        return "No audio selected. Transcribe or upload audio first."
    src = Path(audio_path)
    if not src.exists():
        return f"Audio path not found: {src}"

    ts = time.time()
    uid = uuid.uuid4().hex[:8]
    dst_name = f"{int(ts)}_{uid}_{src.name}"
    copied_path = STT_FEEDBACK_AUDIO_DIR / dst_name
    copied_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, copied_path)

    transcript_raw = (transcript or "").strip()
    corrected_raw = (corrected_text or "").strip()
    if use_for_training and not (corrected_raw or transcript_raw):
        return (
            "Cannot mark for training without text. Provide corrected text "
            "or generate a transcript first."
        )

    record = {
        "timestamp": ts,
        "audio_path": str(copied_path.resolve()),
        "source_audio_path": str(src.resolve()),
        "transcript": transcript_raw,
        "corrected_text": corrected_raw,
        "quality": int(quality),
        "issue_tags": (issue_tags or "").strip(),
        "use_for_training": bool(use_for_training),
        "notes": (notes or "").strip(),
        "model_id": (model_id or "").strip(),
        "language_hint": (language_hint or "").strip(),
        "beam_size": int(beam_size),
        "segments_json": (segments_json or "").strip(),
    }
    _append_jsonl(STT_FEEDBACK_JSONL, record)

    train_text = corrected_raw or transcript_raw
    action = "included for retraining" if use_for_training else "saved as analysis only"
    return (
        f"Saved annotation ({action}). Feedback file: {STT_FEEDBACK_JSONL}\n"
        f"Training text: {train_text[:140]}"
    )


def _list_checkpoint_labels(model_size: str) -> List[str]:
    root = _checkpoint_root(model_size)
    labels: List[str] = []
    if (root / "final").exists():
        labels.append("final")

    def _epoch_num(path: Path) -> int:
        try:
            return int(path.name.rsplit("-", 1)[1])
        except Exception:
            return -1

    epoch_dirs = sorted(
        [p for p in root.glob("checkpoint-epoch-*") if p.is_dir()],
        key=_epoch_num,
    )
    labels.extend([p.name for p in epoch_dirs])
    return labels


def refresh_checkpoint_choices(model_size: str):
    labels = _list_checkpoint_labels(model_size)
    if not labels:
        root = _checkpoint_root(model_size)
        return (
            gr.update(choices=[], value=None),
            f"No checkpoints found for {model_size} at {root}. Run './sage train tts --size {model_size}'.",
        )
    return gr.update(choices=labels, value=labels[0]), f"Loaded {len(labels)} checkpoints for {model_size}."


def phrase_set_to_options(set_name: str):
    phrases = PHONEME_SETS.get(set_name, PHONEME_SETS["J vs Y"])
    first = phrases[0] if phrases else ""
    return gr.update(choices=phrases, value=first), first


def phrase_to_text(phrase: str):
    return phrase or ""


def apply_qwen_style_preset(preset_name: str):
    preset = QWEN_STYLE_PRESETS.get(
        preset_name, QWEN_STYLE_PRESETS[DEFAULT_QWEN_STYLE_PRESET]
    )
    label = preset_name if preset_name in QWEN_STYLE_PRESETS else DEFAULT_QWEN_STYLE_PRESET
    return (
        preset["instruction"],
        float(preset["temperature"]),
        float(preset["top_p"]),
        int(preset["top_k"]),
        float(preset["repetition_penalty"]),
        bool(preset["do_sample"]),
        bool(preset["subtalker_dosample"]),
        int(preset["subtalker_top_k"]),
        float(preset["subtalker_top_p"]),
        float(preset["subtalker_temperature"]),
        bool(preset["non_streaming_mode"]),
        f"Applied style preset: {label}",
    )


def _format_cache_status():
    with _QWEN_LOCK:
        if _QWEN_MODEL is None:
            return "Cache: COLD (no model loaded)"
        age = (
            time.time() - _QWEN_MODEL_LAST_LOAD_TS
            if _QWEN_MODEL_LAST_LOAD_TS is not None
            else 0.0
        )
        path = _QWEN_MODEL_PATH or "unknown"
        return (
            f"Cache: WARM | device={_QWEN_DEVICE} | model={path} | "
            f"loaded {age:.1f}s ago"
        )


def refresh_cache_status():
    return _format_cache_status()


def _normalize_qwen_language(language: str):
    raw = (language or "Auto").strip()
    key = raw.lower()

    if key in ("sw", "swahili", "sw (fallback to auto)"):
        return "Auto", (
            "Swahili is not explicitly supported by this Qwen language list; "
            "falling back to Auto detection."
        )

    mapped = QWEN_LANGUAGE_ALIASES.get(key)
    if mapped:
        return mapped, None

    return "Auto", f"Language '{raw}' not recognized; falling back to Auto."


def _unload_qwen_model():
    global _QWEN_MODEL, _QWEN_MODEL_PATH, _QWEN_DEVICE, _QWEN_MODEL_LAST_LOAD_TS
    message = "No lab model is currently cached."
    with _QWEN_LOCK:
        if _QWEN_MODEL is not None:
            del _QWEN_MODEL
            _QWEN_MODEL = None
            _QWEN_MODEL_PATH = None
            _QWEN_DEVICE = None
            _QWEN_MODEL_LAST_LOAD_TS = None
            message = "Unloaded Qwen model cache."
            try:
                import torch

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass
    return message, _format_cache_status()


def _load_qwen_model(model_path: Path):
    global _QWEN_MODEL, _QWEN_MODEL_PATH, _QWEN_DEVICE, _QWEN_MODEL_LAST_LOAD_TS
    resolved_path = str(model_path.resolve())
    with _QWEN_LOCK:
        try:
            import torch
        except Exception as exc:
            raise RuntimeError("PyTorch is not available in this environment.") from exc

        device = "cuda" if torch.cuda.is_available() else "cpu"
        if (
            _QWEN_MODEL is not None
            and _QWEN_MODEL_PATH == resolved_path
            and _QWEN_DEVICE == device
        ):
            return _QWEN_MODEL, device, False

        if _QWEN_MODEL is not None:
            del _QWEN_MODEL
            _QWEN_MODEL = None
            if device == "cuda":
                torch.cuda.empty_cache()

        Qwen3TTSModel = _ensure_qwen_importable()
        dtype = torch.bfloat16 if device == "cuda" else torch.float32
        model = Qwen3TTSModel.from_pretrained(
            resolved_path,
            torch_dtype=dtype,
            attn_implementation="sdpa",
        )
        model.model = model.model.to(device)
        model.device = torch.device(device)

        _QWEN_MODEL = model
        _QWEN_MODEL_PATH = resolved_path
        _QWEN_DEVICE = device
        _QWEN_MODEL_LAST_LOAD_TS = time.time()
        return model, device, True


def prewarm_selected_model(model_size: str, checkpoint_label: str, target: str):
    try:
        if target == "Base model":
            model_path = _base_model_path(model_size)
        else:
            if not checkpoint_label:
                return "Select a fine-tuned checkpoint first.", _format_cache_status()
            model_path = _checkpoint_root(model_size) / checkpoint_label

        if not model_path.exists():
            return f"Model path not found: {model_path}", _format_cache_status()

        t0 = time.perf_counter()
        _model, device, was_cold = _load_qwen_model(model_path)
        elapsed = time.perf_counter() - t0
        state = "COLD load" if was_cold else "WARM cache"
        return (
            f"Prewarm done: {state} on {device} in {elapsed:.2f}s for {model_path}",
            _format_cache_status(),
        )
    except Exception as exc:
        return f"Prewarm failed: {exc}", _format_cache_status()


def _resolve_probe_text(selected_phrase: str, custom_text: str) -> str:
    text = (custom_text or "").strip()
    if text:
        return text
    return (selected_phrase or "").strip()


def _parse_extra_kwargs(raw_json: str):
    raw = (raw_json or "").strip()
    if not raw:
        return {}, None
    try:
        parsed = json.loads(raw)
    except Exception as exc:
        return None, f"Invalid JSON in extra kwargs: {exc}"
    if not isinstance(parsed, dict):
        return None, "Extra kwargs must be a JSON object (dictionary)."

    blocked = {
        "text",
        "language",
        "speaker",
        "instruct",
        "ref_audio",
        "ref_text",
        "x_vector_only_mode",
        "non_streaming_mode",
    }
    collision = sorted([k for k in parsed.keys() if k in blocked])
    if collision:
        return None, (
            "Extra kwargs contains reserved keys managed by the lab UI: "
            + ", ".join(collision)
        )
    return parsed, None


def _encode_audio_for_gradio(wav, sr: int):
    audio = np.asarray(wav, dtype=np.float32)
    if audio.ndim > 1:
        audio = np.mean(audio, axis=1).astype(np.float32)
    return int(sr), audio


def run_phoneme_probe(
    model_size: str,
    checkpoint_label: str,
    selected_phrase: str,
    custom_text: str,
    mode: str,
    speaker_name: str,
    language: str,
    instruction: str,
    temperature: float,
    top_p: float,
    top_k: int,
    repetition_penalty: float,
    max_new_tokens: int,
    do_sample: bool,
    subtalker_dosample: bool,
    subtalker_top_k: int,
    subtalker_top_p: float,
    subtalker_temperature: float,
    non_streaming_mode: bool,
    x_vector_only_mode: bool,
    base_ref_text: str,
    extra_kwargs_json: str,
):
    phrase = _resolve_probe_text(selected_phrase, custom_text)
    if not phrase:
        return None, None, "No probe text provided.", _format_cache_status()
    if not checkpoint_label and mode in ("Finetuned only", "Both"):
        return None, None, "No fine-tuned checkpoint selected.", _format_cache_status()

    resolved_language, lang_note = _normalize_qwen_language(language)
    extra_kwargs, extra_kwargs_err = _parse_extra_kwargs(extra_kwargs_json)
    if extra_kwargs_err:
        return None, None, extra_kwargs_err, _format_cache_status()

    gen_kwargs = {
        "max_new_tokens": int(max_new_tokens),
        "temperature": float(temperature),
        "top_p": float(top_p),
        "top_k": int(top_k),
        "repetition_penalty": float(repetition_penalty),
        "do_sample": bool(do_sample),
        "subtalker_dosample": bool(subtalker_dosample),
        "subtalker_top_k": int(subtalker_top_k),
        "subtalker_top_p": float(subtalker_top_p),
        "subtalker_temperature": float(subtalker_temperature),
    }
    gen_kwargs.update(extra_kwargs)

    status_lines = [f"Probe text: {phrase}", f"Language: {resolved_language}"]
    if lang_note:
        status_lines.append(lang_note)
    if extra_kwargs:
        status_lines.append(
            "Extra kwargs: " + ", ".join(sorted(str(key) for key in extra_kwargs.keys()))
        )
    finetuned_audio = None
    base_audio = None
    started_total = time.perf_counter()

    try:
        if mode in ("Finetuned only", "Both"):
            ckpt_path = _checkpoint_root(model_size) / checkpoint_label
            if not ckpt_path.exists():
                raise FileNotFoundError(f"Checkpoint not found: {ckpt_path}")

            t0 = time.perf_counter()
            model, device, was_cold = _load_qwen_model(ckpt_path)
            load_elapsed = time.perf_counter() - t0
            load_state = "COLD load" if was_cold else "WARM cache"
            model_type = getattr(model.model, "tts_model_type", "unknown")
            if model_type != "custom_voice":
                raise RuntimeError(
                    f"Selected checkpoint is type '{model_type}', expected 'custom_voice'."
                )

            t1 = time.perf_counter()
            wavs, sr = model.generate_custom_voice(
                text=phrase,
                speaker=(speaker_name or "sage_sheng").strip(),
                language=resolved_language,
                instruct=(instruction.strip() or None),
                non_streaming_mode=bool(non_streaming_mode),
                **gen_kwargs,
            )
            infer_elapsed = time.perf_counter() - t1
            if not wavs:
                raise RuntimeError("Fine-tuned generation returned no audio.")

            finetuned_audio = _encode_audio_for_gradio(wavs[0], sr)
            duration = len(finetuned_audio[1]) / float(sr)
            rtf = infer_elapsed / max(duration, 1e-3)
            status_lines.append(
                f"Fine-tuned [{checkpoint_label}] on {device} ({load_state}): "
                f"load={load_elapsed:.2f}s infer={infer_elapsed:.2f}s dur={duration:.2f}s rtf={rtf:.2f}x"
            )

        if mode in ("Base only", "Both"):
            base_path = _base_model_path(model_size)
            if not base_path.exists():
                raise FileNotFoundError(f"Base model not found: {base_path}")
            if not QWEN_REFERENCE_WAV.exists():
                raise FileNotFoundError(
                    f"Missing Qwen reference audio at {QWEN_REFERENCE_WAV}. Upload one in Live Control."
                )
            ref_text = (base_ref_text or "").strip() or None
            if not bool(x_vector_only_mode) and not ref_text:
                raise ValueError(
                    "Base ref_text is required when x_vector_only_mode is disabled (ICL mode)."
                )

            t0 = time.perf_counter()
            model, device, was_cold = _load_qwen_model(base_path)
            load_elapsed = time.perf_counter() - t0
            load_state = "COLD load" if was_cold else "WARM cache"
            model_type = getattr(model.model, "tts_model_type", "unknown")
            if model_type != "base":
                raise RuntimeError(f"Base model loaded as type '{model_type}', expected 'base'.")

            t1 = time.perf_counter()
            wavs, sr = model.generate_voice_clone(
                text=phrase,
                language=resolved_language,
                ref_audio=str(QWEN_REFERENCE_WAV),
                ref_text=ref_text,
                x_vector_only_mode=bool(x_vector_only_mode),
                non_streaming_mode=bool(non_streaming_mode),
                **gen_kwargs,
            )
            infer_elapsed = time.perf_counter() - t1
            if not wavs:
                raise RuntimeError("Base generation returned no audio.")

            base_audio = _encode_audio_for_gradio(wavs[0], sr)
            duration = len(base_audio[1]) / float(sr)
            rtf = infer_elapsed / max(duration, 1e-3)
            status_lines.append(
                f"Base on {device} ({load_state}): load={load_elapsed:.2f}s infer={infer_elapsed:.2f}s "
                f"dur={duration:.2f}s rtf={rtf:.2f}x"
            )

        total_elapsed = time.perf_counter() - started_total
        status_lines.append(f"Total wall time: {total_elapsed:.2f}s")
        if mode == "Both":
            status_lines.append("Both mode swaps models on one GPU, so response time is slower.")
    except Exception as exc:
        status_lines.append(f"Generation failed: {exc}")

    return finetuned_audio, base_audio, "\n".join(status_lines), _format_cache_status()


INITIAL_PHONEME_SET = "J vs Y"
INITIAL_PHRASES = PHONEME_SETS[INITIAL_PHONEME_SET]
INITIAL_CHECKPOINTS_17B = _list_checkpoint_labels("1.7b")
INITIAL_CHECKPOINT_17B = INITIAL_CHECKPOINTS_17B[0] if INITIAL_CHECKPOINTS_17B else None


with gr.Blocks(title="Sage Voice Lab") as demo:
    gr.Markdown("# Sage Voice Lab")
    gr.Markdown(
        "Live TTS control plus a phoneme/prosody probe tab for comparing base vs fine-tuned Qwen checkpoints."
    )

    with gr.Tabs():
        with gr.Tab("Live Control"):
            with gr.Row():
                with gr.Column():
                    engine_radio = gr.Radio(["F5", "Kokoro", "Qwen"], label="Engine", value="F5")

                    with gr.Group(visible=True) as f5_group:
                        gr.Markdown("### F5-TTS (Cloning)")
                        gr.Markdown("Uses `brain/voice/reference.wav`.")
                        ref_input = gr.Audio(
                            label="Update Reference Voice (Upload/Record)",
                            sources=["upload", "microphone"],
                            type="filepath",
                        )
                        save_ref_btn = gr.Button("Update Reference", size="sm")

                    with gr.Group(visible=False) as kokoro_group:
                        gr.Markdown("### Kokoro")
                        voice_dropdown = gr.Dropdown(
                            [
                                "af_bella",
                                "af_sarah",
                                "am_michael",
                                "am_adam",
                                "bf_emma",
                                "bf_isabella",
                                "bm_george",
                                "bm_lewis",
                            ],
                            label="Voice",
                            value="af_bella",
                        )

                    with gr.Group(visible=False) as qwen_group:
                        gr.Markdown("### Qwen3-TTS")
                        gr.Markdown("Update reference used for base voice cloning.")
                        qwen_ref_input = gr.Audio(
                            label="Update Qwen Reference Voice",
                            sources=["upload", "microphone"],
                            type="filepath",
                        )
                        save_qwen_ref_btn = gr.Button("Update Qwen Reference", size="sm")
                        live_qwen_instruction_tb = gr.Textbox(
                            value=QWEN_STYLE_PRESETS[DEFAULT_QWEN_STYLE_PRESET]["instruction"],
                            lines=5,
                            label="Runtime Qwen Instruction (custom_voice)",
                            placeholder="Optional style instruction pushed to speaker service.",
                        )

                    speed_slider = gr.Slider(
                        minimum=0.5,
                        maximum=2.0,
                        value=0.85,
                        step=0.05,
                        label="Speed",
                    )
                    apply_btn = gr.Button("Apply Config", variant="secondary")

                with gr.Column():
                    text_input = gr.Textbox(
                        label="Text to Speak",
                        value="Hello. I am Sage.",
                        lines=3,
                    )
                    speak_btn = gr.Button("Speak (Send to Mouth)", variant="primary")
                    live_status_msg = gr.Textbox(label="Status", interactive=False)

        with gr.Tab("Phoneme Lab"):
            gr.Markdown(
                "Probe consonants/prosody with base vs fine-tuned checkpoints. "
                "On one GPU, `Both` mode is slower because models are swapped."
            )
            with gr.Row():
                with gr.Column(scale=1):
                    model_size_dd = gr.Dropdown(
                        choices=["1.7b", "0.6b"],
                        value="1.7b",
                        label="Model Size",
                    )
                    checkpoint_dd = gr.Dropdown(
                        choices=INITIAL_CHECKPOINTS_17B,
                        value=INITIAL_CHECKPOINT_17B,
                        label="Fine-tuned Checkpoint",
                    )
                    refresh_btn = gr.Button("Refresh Checkpoints", size="sm")
                    prewarm_target_dd = gr.Dropdown(
                        choices=["Fine-tuned checkpoint", "Base model"],
                        value="Fine-tuned checkpoint",
                        label="Prewarm Target",
                    )
                    with gr.Row():
                        prewarm_btn = gr.Button("Prewarm Target", variant="secondary")
                        refresh_cache_btn = gr.Button("Refresh Cache", size="sm")
                    cache_status_msg = gr.Textbox(
                        label="Model Cache",
                        value=_format_cache_status(),
                        lines=3,
                        interactive=False,
                    )

                    mode_radio = gr.Radio(
                        choices=["Both", "Finetuned only", "Base only"],
                        value="Both",
                        label="Output Mode",
                    )
                    speaker_name_tb = gr.Textbox(
                        value="sage_sheng",
                        label="Speaker Name (custom_voice)",
                    )
                    language_dd = gr.Dropdown(
                        choices=QWEN_LANGUAGE_DROPDOWN_CHOICES,
                        value="Auto",
                        label="Language",
                    )
                    instruction_tb = gr.Textbox(
                        value="",
                        lines=2,
                        label="Instruction (optional)",
                        placeholder="Example: Kenyan Sheng cadence, crisp J consonants, medium pace.",
                    )
                    style_preset_dd = gr.Dropdown(
                        choices=list(QWEN_STYLE_PRESETS.keys()),
                        value=DEFAULT_QWEN_STYLE_PRESET,
                        label="Style Preset",
                    )
                    apply_style_btn = gr.Button("Apply Style Preset", size="sm")

                    temperature_sl = gr.Slider(0.2, 1.3, value=0.9, step=0.05, label="Temperature")
                    top_p_sl = gr.Slider(0.1, 1.0, value=1.0, step=0.05, label="Top-p")
                    top_k_sl = gr.Slider(1, 100, value=50, step=1, label="Top-k")
                    repetition_sl = gr.Slider(1.0, 1.3, value=1.08, step=0.01, label="Repetition Penalty")
                    max_tokens_sl = gr.Slider(128, 2048, value=640, step=16, label="Max New Tokens")

                    with gr.Accordion("Advanced Generation Controls", open=False):
                        do_sample_cb = gr.Checkbox(value=True, label="do_sample")
                        subtalker_dosample_cb = gr.Checkbox(value=True, label="subtalker_dosample")
                        subtalker_top_k_sl = gr.Slider(1, 100, value=50, step=1, label="Subtalker Top-k")
                        subtalker_top_p_sl = gr.Slider(0.1, 1.0, value=1.0, step=0.05, label="Subtalker Top-p")
                        subtalker_temp_sl = gr.Slider(0.2, 1.3, value=0.9, step=0.05, label="Subtalker Temperature")
                        non_streaming_cb = gr.Checkbox(
                            value=True,
                            label="non_streaming_mode",
                        )
                        x_vector_only_cb = gr.Checkbox(
                            value=True,
                            label="Base: x_vector_only_mode",
                        )
                        base_ref_text_tb = gr.Textbox(
                            value="",
                            lines=2,
                            label="Base: ref_text (required if x_vector_only_mode is off)",
                            placeholder="Transcript for your qwen_reference.wav when using ICL mode.",
                        )
                        extra_kwargs_tb = gr.Textbox(
                            value="",
                            lines=3,
                            label="Extra Generate Kwargs (JSON)",
                            placeholder='Example: {"num_beams": 1}',
                        )

                    generate_btn = gr.Button("Generate Probe", variant="primary")
                    unload_btn = gr.Button("Unload Model Cache", variant="secondary")

                with gr.Column(scale=2):
                    phoneme_set_dd = gr.Dropdown(
                        choices=list(PHONEME_SETS.keys()),
                        value=INITIAL_PHONEME_SET,
                        label="Phoneme Focus",
                    )
                    phrase_dd = gr.Dropdown(
                        choices=INITIAL_PHRASES,
                        value=INITIAL_PHRASES[0],
                        label="Preset Phrase",
                    )
                    custom_phrase_tb = gr.Textbox(
                        value=INITIAL_PHRASES[0],
                        lines=3,
                        label="Probe Text (editable)",
                    )

                    with gr.Row():
                        finetuned_audio_out = gr.Audio(label="Fine-tuned Output", type="numpy")
                        base_audio_out = gr.Audio(label="Base Output", type="numpy")
                    lab_status_msg = gr.Textbox(label="Probe Status", lines=10, interactive=False)

        with gr.Tab("STT Lab"):
            gr.Markdown(
                "Transcribe uploaded/recorded audio with your fine-tuned Whisper CTranslate2 model "
                "or a base faster-whisper model."
            )
            with gr.Row():
                with gr.Column(scale=1):
                    stt_model_id_tb = gr.Textbox(
                        value=_default_stt_model_id(),
                        label="STT Model ID or Path",
                        placeholder="Examples: medium.en or /abs/path/to/whisper-sheng-ct2",
                    )
                    stt_device_dd = gr.Dropdown(
                        choices=["auto", "cuda", "cpu"],
                        value="auto",
                        label="Device",
                    )
                    stt_compute_dd = gr.Dropdown(
                        choices=["float16", "int8", "float32", "int8_float16"],
                        value="float16",
                        label="Compute Type",
                    )
                    stt_beam_sl = gr.Slider(1, 8, value=1, step=1, label="Beam Size")
                    stt_language_tb = gr.Textbox(
                        value="sw",
                        label="Language Hint (or 'auto')",
                    )
                    stt_prompt_tb = gr.Textbox(
                        value="Sage assistant, home automation, coding help.",
                        lines=2,
                        label="Initial Prompt (optional)",
                    )
                    stt_vad_cb = gr.Checkbox(value=True, label="VAD Filter")
                    stt_condition_prev_cb = gr.Checkbox(
                        value=False,
                        label="condition_on_previous_text",
                    )
                    stt_temp_sl = gr.Slider(
                        0.0,
                        1.0,
                        value=0.0,
                        step=0.05,
                        label="Temperature",
                    )
                    with gr.Row():
                        stt_prewarm_btn = gr.Button("Prewarm STT Model", variant="secondary")
                        stt_refresh_cache_btn = gr.Button("Refresh STT Cache", size="sm")
                    stt_unload_btn = gr.Button("Unload STT Cache", variant="secondary")
                    stt_cache_status_msg = gr.Textbox(
                        label="STT Cache",
                        value=_format_stt_cache_status(),
                        lines=3,
                        interactive=False,
                    )

                with gr.Column(scale=2):
                    stt_audio_in = gr.Audio(
                        label="Audio to Transcribe",
                        sources=["upload", "microphone"],
                        type="filepath",
                    )
                    stt_transcribe_btn = gr.Button("Transcribe Audio", variant="primary")
                    stt_transcript_out = gr.Textbox(
                        label="Transcript",
                        lines=4,
                    )
                    stt_segments_out = gr.Code(
                        label="Segments (JSON)",
                        language="json",
                        value="[]",
                    )
                    stt_status_msg = gr.Textbox(
                        label="STT Status",
                        lines=10,
                        interactive=False,
                    )
                    gr.Markdown("### STT Annotation")
                    stt_corrected_tb = gr.Textbox(
                        label="Corrected Transcript (optional)",
                        lines=3,
                        placeholder="Fix words here. If empty, current transcript can still be used.",
                    )
                    with gr.Accordion("Script Generator", open=False):
                        gr.Markdown(
                            "Generate a transcript draft via cloud LLM and map it into "
                            "`Corrected Transcript`."
                        )
                        stt_script_topic_tb = gr.Textbox(
                            value="",
                            label="Topic",
                            lines=1,
                            placeholder="e.g. school run in Nairobi, late-night coding session",
                        )
                        with gr.Row():
                            stt_script_style_dd = gr.Dropdown(
                                choices=list(STT_SCRIPT_STYLE_GUIDES.keys()),
                                value="Sheng Casual",
                                label="Style",
                            )
                            stt_script_length_sl = gr.Slider(
                                minimum=8,
                                maximum=60,
                                step=1,
                                value=16,
                                label="Approx length (seconds)",
                            )
                        stt_script_numbers_cb = gr.Checkbox(
                            value=False,
                            label="Include natural numbers/dates/times",
                        )
                        stt_generate_script_btn = gr.Button(
                            "Generate into Corrected Transcript",
                            variant="secondary",
                        )
                    stt_quality_sl = gr.Slider(1, 5, value=3, step=1, label="Quality (1=poor, 5=excellent)")
                    stt_issue_tags_tb = gr.Textbox(
                        label="Issue Tags (comma separated)",
                        placeholder="consonants,sh->ch,accent,code-switching,noise",
                    )
                    stt_use_training_cb = gr.Checkbox(
                        value=True,
                        label="Use this sample for retraining",
                    )
                    stt_notes_tb = gr.Textbox(
                        label="Notes",
                        lines=2,
                    )
                    stt_save_annotation_btn = gr.Button("Save STT Annotation", variant="secondary")
                    stt_annotation_status_msg = gr.Textbox(
                        label="Annotation Status",
                        lines=3,
                        interactive=False,
                    )
                    gr.Markdown(
                        "Build retraining data with: `./sage train prepare-feedback --task stt --include-base`"
                    )

    def toggle_groups(engine):
        return {
            f5_group: gr.update(visible=(engine == "F5")),
            kokoro_group: gr.update(visible=(engine == "Kokoro")),
            qwen_group: gr.update(visible=(engine == "Qwen")),
        }

    engine_radio.change(
        fn=toggle_groups,
        inputs=[engine_radio],
        outputs=[f5_group, kokoro_group, qwen_group],
    )

    apply_btn.click(
        fn=send_config,
        inputs=[engine_radio, speed_slider, voice_dropdown, live_qwen_instruction_tb],
        outputs=[live_status_msg],
    )
    save_ref_btn.click(
        fn=update_reference,
        inputs=[ref_input],
        outputs=[live_status_msg],
    )
    save_qwen_ref_btn.click(
        fn=update_qwen_reference,
        inputs=[qwen_ref_input],
        outputs=[live_status_msg],
    )
    speak_btn.click(
        fn=send_speech,
        inputs=[text_input],
        outputs=[live_status_msg],
    )

    model_size_dd.change(
        fn=refresh_checkpoint_choices,
        inputs=[model_size_dd],
        outputs=[checkpoint_dd, lab_status_msg],
    )
    refresh_btn.click(
        fn=refresh_checkpoint_choices,
        inputs=[model_size_dd],
        outputs=[checkpoint_dd, lab_status_msg],
    )
    refresh_cache_btn.click(
        fn=refresh_cache_status,
        outputs=[cache_status_msg],
    )
    prewarm_btn.click(
        fn=prewarm_selected_model,
        inputs=[model_size_dd, checkpoint_dd, prewarm_target_dd],
        outputs=[lab_status_msg, cache_status_msg],
    )
    phoneme_set_dd.change(
        fn=phrase_set_to_options,
        inputs=[phoneme_set_dd],
        outputs=[phrase_dd, custom_phrase_tb],
    )
    phrase_dd.change(
        fn=phrase_to_text,
        inputs=[phrase_dd],
        outputs=[custom_phrase_tb],
    )
    apply_style_btn.click(
        fn=apply_qwen_style_preset,
        inputs=[style_preset_dd],
        outputs=[
            instruction_tb,
            temperature_sl,
            top_p_sl,
            top_k_sl,
            repetition_sl,
            do_sample_cb,
            subtalker_dosample_cb,
            subtalker_top_k_sl,
            subtalker_top_p_sl,
            subtalker_temp_sl,
            non_streaming_cb,
            lab_status_msg,
        ],
    )
    unload_btn.click(
        fn=_unload_qwen_model,
        outputs=[lab_status_msg, cache_status_msg],
    )
    generate_btn.click(
        fn=run_phoneme_probe,
        inputs=[
            model_size_dd,
            checkpoint_dd,
            phrase_dd,
            custom_phrase_tb,
            mode_radio,
            speaker_name_tb,
            language_dd,
            instruction_tb,
            temperature_sl,
            top_p_sl,
            top_k_sl,
            repetition_sl,
            max_tokens_sl,
            do_sample_cb,
            subtalker_dosample_cb,
            subtalker_top_k_sl,
            subtalker_top_p_sl,
            subtalker_temp_sl,
            non_streaming_cb,
            x_vector_only_cb,
            base_ref_text_tb,
            extra_kwargs_tb,
        ],
        outputs=[finetuned_audio_out, base_audio_out, lab_status_msg, cache_status_msg],
    )
    stt_refresh_cache_btn.click(
        fn=refresh_stt_cache_status,
        outputs=[stt_cache_status_msg],
    )
    stt_prewarm_btn.click(
        fn=prewarm_stt_model,
        inputs=[stt_model_id_tb, stt_device_dd, stt_compute_dd],
        outputs=[stt_status_msg, stt_cache_status_msg],
    )
    stt_unload_btn.click(
        fn=_unload_stt_model,
        outputs=[stt_status_msg, stt_cache_status_msg],
    )
    stt_transcribe_btn.click(
        fn=run_stt_probe,
        inputs=[
            stt_audio_in,
            stt_model_id_tb,
            stt_device_dd,
            stt_compute_dd,
            stt_beam_sl,
            stt_language_tb,
            stt_prompt_tb,
            stt_vad_cb,
            stt_condition_prev_cb,
            stt_temp_sl,
        ],
        outputs=[stt_transcript_out, stt_segments_out, stt_status_msg, stt_cache_status_msg],
    )
    stt_generate_script_btn.click(
        fn=generate_stt_script,
        inputs=[
            stt_script_topic_tb,
            stt_script_style_dd,
            stt_script_length_sl,
            stt_script_numbers_cb,
            stt_corrected_tb,
        ],
        outputs=[stt_corrected_tb, stt_annotation_status_msg],
    )
    stt_save_annotation_btn.click(
        fn=save_stt_annotation,
        inputs=[
            stt_audio_in,
            stt_transcript_out,
            stt_corrected_tb,
            stt_quality_sl,
            stt_issue_tags_tb,
            stt_use_training_cb,
            stt_notes_tb,
            stt_model_id_tb,
            stt_language_tb,
            stt_beam_sl,
            stt_segments_out,
        ],
        outputs=[stt_annotation_status_msg],
    )


if __name__ == "__main__":
    def _env_bool(name: str, default: bool = False) -> bool:
        raw = os.getenv(name)
        if raw is None:
            return default
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    host = os.getenv("SAGE_LAB_HOST", "127.0.0.1").strip() or "127.0.0.1"
    try:
        port = int(os.getenv("SAGE_LAB_PORT", "7860"))
    except Exception:
        port = 7860
    share = _env_bool("SAGE_LAB_SHARE", False)
    demo.launch(server_name=host, server_port=port, share=share)
