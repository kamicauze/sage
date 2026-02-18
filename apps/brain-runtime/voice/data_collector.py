"""
Sage Sheng Data Collection UI

Gradio-based recording tool for capturing paired audio + text training data.
Feeds both Qwen3-TTS and Whisper fine-tuning pipelines.

Usage:
    python -m brain.voice.data_collector
    # or: ./sage collect
"""

import os
import sys
import json
import time
import uuid
import logging
import urllib.error
import urllib.request
import gradio as gr
import numpy as np
import soundfile as sf

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from brain.voice.sheng_prompts import get_prompts, CATEGORIES
from brain.voice.audio_prep import process_for_training, extract_reference_audio
from brain.voice.paths import get_training_data_dir

logging.basicConfig(level=logging.INFO, format="[Collector] %(asctime)s - %(message)s")
logger = logging.getLogger("Collector")

try:
    from dotenv import load_dotenv

    APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    REPO_ROOT = os.path.abspath(os.path.join(APP_ROOT, "..", ".."))
    load_dotenv(os.path.join(APP_ROOT, ".env"))
    load_dotenv(os.path.join(REPO_ROOT, ".env"))
except Exception:
    pass

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = str(get_training_data_dir(__file__))
RAW_DIR = os.path.join(DATA_DIR, "raw")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
MANIFEST_PATH = os.path.join(DATA_DIR, "manifest.jsonl")
REF_AUDIO_PATH = os.path.join(SCRIPT_DIR, "qwen_reference.wav")

os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

# State
_prompt_queue = []
_current_prompt_idx = 0

SCRIPT_STYLE_GUIDES = {
    "Sheng Casual": "casual Sheng and Kenyan English code-switching for everyday life",
    "Kenyan English": "clean Kenyan English with natural local phrasing",
    "Smart Home Command": "home automation command phrasing that still sounds conversational",
    "Technical": "developer and AI workflow language with natural pacing",
    "Narrative": "short story-like script with expressive but clear delivery",
}


def _load_manifest():
    """Load existing manifest entries."""
    entries = []
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
    return entries


def _save_manifest_entry(entry):
    """Append a single entry to the manifest."""
    with open(MANIFEST_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _get_progress():
    """Get recording progress stats."""
    entries = _load_manifest()
    total_duration = sum(e.get("duration", 0) for e in entries)
    total_prompts = len(get_prompts())

    # Count per category
    cat_counts = {}
    for e in entries:
        cat = e.get("category", "unknown")
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    return {
        "recorded": len(entries),
        "total_prompts": total_prompts,
        "total_duration_min": round(total_duration / 60, 1),
        "categories": cat_counts,
    }


def get_progress_text():
    """Format progress as readable text."""
    p = _get_progress()
    lines = [
        f"Recorded: {p['recorded']} / {p['total_prompts']} prompts",
        f"Total audio: {p['total_duration_min']} minutes",
        f"Target: ~60-120 minutes",
        "",
        "Per category:",
    ]
    for cat_name in CATEGORIES:
        count = p["categories"].get(cat_name, 0)
        total = len(CATEGORIES[cat_name])
        lines.append(f"  {cat_name}: {count}/{total}")
    return "\n".join(lines)


def init_prompts(category, shuffle):
    """Initialize the prompt queue."""
    global _prompt_queue, _current_prompt_idx
    cat = None if category == "all" else category
    _prompt_queue = get_prompts(category=cat, shuffle=shuffle)
    _current_prompt_idx = 0

    # Skip already recorded prompts
    recorded_texts = set()
    for entry in _load_manifest():
        recorded_texts.add(entry.get("text", ""))

    _prompt_queue = [p for p in _prompt_queue if p["text"] not in recorded_texts]

    if not _prompt_queue:
        return "All prompts in this category have been recorded!", "", get_progress_text()

    prompt = _prompt_queue[0]
    return (
        f"[{prompt['category']}] Prompt 1/{len(_prompt_queue)}",
        prompt["text"],
        get_progress_text(),
    )


def _resolve_cloud_llm_config():
    """Resolve cloud LLM settings from environment variables."""
    provider_raw = (os.getenv("SAGE_COLLECT_LLM_PROVIDER", "") or "").strip().lower()
    base_url = os.getenv("SAGE_COLLECT_LLM_BASE_URL", "").strip().rstrip("/")
    model = os.getenv("SAGE_COLLECT_LLM_MODEL", "").strip()
    api_key_override = os.getenv("SAGE_COLLECT_LLM_API_KEY", "").strip()
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

    timeout_raw = os.getenv("SAGE_COLLECT_LLM_TIMEOUT_SEC", "25")
    try:
        timeout_sec = float(timeout_raw)
    except ValueError:
        timeout_sec = 25.0

    return {
        "provider": provider,
        "base_url": base_url,
        "model": model,
        "api_key": api_key,
        "timeout_sec": timeout_sec,
    }


def _extract_response_text(choice):
    """Extract text from OpenAI-compatible chat completion responses."""
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


def _normalize_script_text(text):
    """Keep generated scripts easy to read aloud."""
    clean = " ".join((text or "").replace("\r", " ").replace("\n", " ").split()).strip()
    if clean.startswith('"') and clean.endswith('"') and len(clean) >= 2:
        clean = clean[1:-1].strip()
    if clean.startswith("'") and clean.endswith("'") and len(clean) >= 2:
        clean = clean[1:-1].strip()
    if len(clean) > 800:
        clean = clean[:800].rsplit(" ", 1)[0].strip() + "..."
    return clean


def generate_cloud_script(topic, style, target_seconds, include_numbers, current_header, current_prompt, current_custom):
    """Generate a read-aloud script via cloud LLM."""
    try:
        config = _resolve_cloud_llm_config()
        if not config["api_key"]:
            raise RuntimeError(
                f"Missing API key for provider '{config['provider']}'. "
                "Set SAGE_COLLECT_LLM_API_KEY, or set SAGE_COLLECT_LLM_PROVIDER=xai with XAI_API_KEY."
            )

        style_guide = SCRIPT_STYLE_GUIDES.get(style, SCRIPT_STYLE_GUIDES["Sheng Casual"])
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
                    "You write short scripts for voice recording datasets. "
                    "Return plain text only with no markdown, no title, and no quotes."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Create one read-aloud script.\n"
                    f"Style: {style_guide}\n"
                    f"Topic: {clean_topic}\n"
                    f"Target length: about {words_target} words.\n"
                    "Language: Kenyan English with optional Sheng code-switching when natural.\n"
                    "Format: one paragraph only, easy to read out loud.\n"
                    f"{numbers_line}"
                ),
            },
        ]

        payload = {
            "model": config["model"],
            "messages": messages,
            "temperature": 0.9,
        }
        request_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{config['base_url']}/chat/completions",
            data=request_data,
            headers={
                "Authorization": f"Bearer {config['api_key']}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "sage-data-collector/1.0",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=config["timeout_sec"]) as resp:
            body = resp.read().decode("utf-8")
            response_json = json.loads(body)

        choices = response_json.get("choices") or []
        if not choices:
            raise RuntimeError("Cloud LLM returned no choices.")

        generated = _normalize_script_text(_extract_response_text(choices[0]))
        if not generated:
            raise RuntimeError("Cloud LLM response was empty.")

        header = f"[generated/{style.lower().replace(' ', '_')}] On-the-fly script"
        status = f"Generated {len(generated.split())} words via {config['provider']}:{config['model']}"
        return header, generated, generated, status

    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="ignore")
        error_body = " ".join(error_body.split())[:200]
        message = f"Generator error: HTTP {exc.code} {error_body}"
        logger.warning(message)
        return current_header, current_prompt, current_custom, message
    except Exception as exc:
        message = f"Generator error: {exc}"
        logger.warning(message)
        return current_header, current_prompt, current_custom, message


def save_recording(audio, prompt_text, custom_text):
    """Save a recording and its transcript, process for training."""
    if audio is None:
        return "No audio recorded!", "", get_progress_text(), ""

    # Use custom text if provided, otherwise use the prompt text
    text = custom_text.strip() if custom_text.strip() else prompt_text.strip()
    if not text:
        return "No text provided!", "", get_progress_text(), ""

    # Generate file ID
    file_id = f"{int(time.time())}_{uuid.uuid4().hex[:6]}"

    # Gradio audio comes as (sample_rate, numpy_array)
    sr, audio_data = audio
    audio_data = audio_data.astype(np.float32)

    # Normalize if int format
    if audio_data.dtype == np.int16 or np.max(np.abs(audio_data)) > 1.0:
        audio_data = audio_data / np.max(np.abs(audio_data))

    # Convert stereo to mono
    if audio_data.ndim > 1:
        audio_data = audio_data.mean(axis=1)

    # Save raw audio
    raw_path = os.path.join(RAW_DIR, f"{file_id}.wav")
    sf.write(raw_path, audio_data, sr)

    # Save raw transcript
    txt_path = os.path.join(RAW_DIR, f"{file_id}.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(text)

    # Process for training (creates 24kHz + 16kHz versions)
    result = process_for_training(raw_path, PROCESSED_DIR, file_id)

    if result is None:
        return "Audio failed quality check. Try recording again (less noise, speak clearly).", "", get_progress_text(), ""

    # Determine category
    category = "freeform"
    for p in _prompt_queue:
        if p["text"] == text:
            category = p["category"]
            break

    # Save manifest entry
    entry = {
        "file_id": file_id,
        "text": text,
        "category": category,
        "tts_path": result["tts_path"],
        "stt_path": result["stt_path"],
        "duration": result["duration"],
        "snr": result["snr"],
        "timestamp": time.time(),
    }
    _save_manifest_entry(entry)

    logger.info(f"Saved: {file_id} ({result['duration']:.1f}s, SNR:{result['snr']:.1f}dB) - '{text[:50]}'")

    # Advance to next prompt
    header, prompt, progress = next_prompt_internal()
    return header, prompt, progress, ""


def next_prompt_internal():
    """Move to next prompt and return updated UI state."""
    global _current_prompt_idx

    _current_prompt_idx += 1
    if _current_prompt_idx >= len(_prompt_queue):
        return "All prompts done! Switch category or record freeform.", "", get_progress_text()

    prompt = _prompt_queue[_current_prompt_idx]
    return (
        f"[{prompt['category']}] Prompt {_current_prompt_idx + 1}/{len(_prompt_queue)}",
        prompt["text"],
        get_progress_text(),
    )


def skip_prompt():
    """Skip current prompt without recording."""
    return next_prompt_internal()


def export_training_data():
    """Export manifest to Qwen3-TTS fine-tuning JSONL format."""
    entries = _load_manifest()
    if not entries:
        return "No recordings found. Record some data first."

    # Generate reference audio from best clips
    ref_path = extract_reference_audio(PROCESSED_DIR, REF_AUDIO_PATH)
    if not ref_path:
        return "Could not extract reference audio. Need more recordings."

    # Write TTS JSONL
    tts_jsonl_path = os.path.join(DATA_DIR, "tts_training.jsonl")
    with open(tts_jsonl_path, "w", encoding="utf-8") as f:
        for entry in entries:
            tts_entry = {
                "audio_path": os.path.abspath(entry["tts_path"]),
                "text": entry["text"],
                "ref_audio": os.path.abspath(ref_path),
            }
            f.write(json.dumps(tts_entry, ensure_ascii=False) + "\n")

    # Write STT JSONL
    stt_jsonl_path = os.path.join(DATA_DIR, "stt_training.jsonl")
    with open(stt_jsonl_path, "w", encoding="utf-8") as f:
        for entry in entries:
            stt_entry = {
                "audio_path": os.path.abspath(entry["stt_path"]),
                "text": entry["text"],
            }
            f.write(json.dumps(stt_entry, ensure_ascii=False) + "\n")

    return (
        f"Exported {len(entries)} samples:\n"
        f"  TTS: {tts_jsonl_path}\n"
        f"  STT: {stt_jsonl_path}\n"
        f"  Ref: {ref_path}\n"
        f"\nReady for fine-tuning!"
    )


# --- Gradio UI ---
def build_ui():
    with gr.Blocks(title="Sage Sheng Data Collector", theme=gr.themes.Soft()) as demo:
        gr.Markdown("# Sage Sheng Data Collector")
        gr.Markdown("Record your voice reading prompts to train Sage on Kenyan/Sheng speech patterns.")

        with gr.Row():
            # Left: Controls
            with gr.Column(scale=1):
                gr.Markdown("### Session Setup")
                category_select = gr.Dropdown(
                    choices=["all"] + list(CATEGORIES.keys()),
                    value="all",
                    label="Category",
                )
                shuffle_check = gr.Checkbox(value=True, label="Shuffle prompts")
                start_btn = gr.Button("Start Session", variant="primary")

                gr.Markdown("---")
                gr.Markdown("### Progress")
                progress_text = gr.Textbox(
                    value=get_progress_text(),
                    label="Recording Stats",
                    lines=15,
                    interactive=False,
                )

                gr.Markdown("---")
                export_btn = gr.Button("Export Training Data", variant="secondary")
                export_status = gr.Textbox(label="Export Status", interactive=False, lines=4)

            # Right: Recording
            with gr.Column(scale=2):
                gr.Markdown("### Current Prompt")
                prompt_header = gr.Textbox(
                    value="Press 'Start Session' to begin",
                    label="Info",
                    interactive=False,
                )
                prompt_display = gr.Textbox(
                    value="",
                    label="Read this aloud:",
                    lines=3,
                    interactive=False,
                    elem_id="prompt-text",
                )

                gr.Markdown("### Record")
                audio_input = gr.Audio(
                    sources=["microphone"],
                    type="numpy",
                    label="Record your voice",
                )

                gr.Markdown("### Custom Text (optional)")
                custom_text = gr.Textbox(
                    value="",
                    label="Override prompt text (for freeform recording)",
                    lines=2,
                    placeholder="Leave empty to use the prompt text above",
                )

                gr.Markdown("### On-the-fly Script Generator")
                gr.Markdown(
                    "Uses OpenAI-compatible chat completions. "
                    "Configure with `OPENAI_API_KEY` or `SAGE_COLLECT_LLM_*` env vars."
                )
                script_topic = gr.Textbox(
                    value="",
                    label="Topic",
                    lines=1,
                    placeholder="e.g. rainy Nairobi commute, coding sprint, smart home evening routine",
                )
                with gr.Row():
                    script_style = gr.Dropdown(
                        choices=list(SCRIPT_STYLE_GUIDES.keys()),
                        value="Sheng Casual",
                        label="Style",
                    )
                    script_length = gr.Slider(
                        minimum=8,
                        maximum=60,
                        step=1,
                        value=18,
                        label="Approx length (seconds)",
                    )
                include_numbers = gr.Checkbox(
                    value=False,
                    label="Include natural numbers/dates/times",
                )
                generate_btn = gr.Button("Generate Script", variant="secondary")

                with gr.Row():
                    save_btn = gr.Button("Save & Next", variant="primary", size="lg")
                    skip_btn = gr.Button("Skip", variant="secondary")

                save_status = gr.Textbox(label="Status", interactive=False)

        # Event handlers
        start_btn.click(
            fn=init_prompts,
            inputs=[category_select, shuffle_check],
            outputs=[prompt_header, prompt_display, progress_text],
        )

        save_btn.click(
            fn=save_recording,
            inputs=[audio_input, prompt_display, custom_text],
            outputs=[prompt_header, prompt_display, progress_text, custom_text],
        )

        generate_btn.click(
            fn=generate_cloud_script,
            inputs=[
                script_topic,
                script_style,
                script_length,
                include_numbers,
                prompt_header,
                prompt_display,
                custom_text,
            ],
            outputs=[prompt_header, prompt_display, custom_text, save_status],
        )

        skip_btn.click(
            fn=skip_prompt,
            outputs=[prompt_header, prompt_display, progress_text],
        )

        export_btn.click(
            fn=export_training_data,
            outputs=[export_status],
        )

    return demo


if __name__ == "__main__":
    demo = build_ui()
    demo.launch(server_name="0.0.0.0", server_port=7861)
