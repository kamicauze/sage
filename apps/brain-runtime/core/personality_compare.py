"""
Compare personality responses for the same user message.

Usage:
  python brain/core/personality_compare.py "your message here"
"""

import argparse
import asyncio
import json
import os
import sys
import urllib.request
from datetime import datetime

_BRAIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BRAIN_DIR not in sys.path:
    sys.path.insert(0, _BRAIN_DIR)

try:
    from ai.advisor import advise
    from ai.conversation import ConversationHistory
    from ai.personality_engine import reset_personality_engine
    _ADVISE_AVAILABLE = True
    _ADVISE_IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover - fallback if dependencies missing
    _ADVISE_AVAILABLE = False
    _ADVISE_IMPORT_ERROR = exc
    from ai.model_policy import choose_model
    from ai.personalities import (
        build_core_identity_prompt,
        build_mode_prompt,
        build_tone_hint,
        classify_tone,
        is_grief_disclosure,
        select_mode,
    )
    from ai.personality_engine import PersonalityEngine, reset_personality_engine


DEFAULT_PERSONALITIES = ["sage", "kenyan_babe", "martin"]


def build_context(message: str, personality: str) -> dict:
    return {
        "trigger": {"type": "voice_transcript", "text": message},
        "personality": personality,
        "local_hour": datetime.now().hour,
        "state": {"rooms": {}},
        "summary": {},
    }


async def run_once(message: str, personality: str) -> dict:
    reset_personality_engine()
    context = build_context(message, personality)
    meta = {"reason": "user_intent"}

    if _ADVISE_AVAILABLE:
        conversation = ConversationHistory()
        return await advise(context, meta=meta, conversation=conversation)

    # Minimal fallback if aiohttp/advise is unavailable.
    engine = PersonalityEngine()
    engine.process_user_message(message)
    personality_guidance = engine.get_prompt_injection()
    if personality_guidance:
        context["personality_guidance"] = personality_guidance

    mode = select_mode(meta["reason"], context)
    prompt_variant = "full" if mode in ("supportive", "reflective") else "light"
    tone = classify_tone(message)
    is_emotional = tone in ("tender", "frustrated") or is_grief_disclosure(message)
    is_conversational = meta["reason"] in ("smalltalk", "user_intent") and mode == "supportive"
    skip_json = is_emotional or is_conversational

    core_prompt = build_core_identity_prompt(
        personality=personality,
        include_examples=True,
        prompt_variant=prompt_variant,
    )
    mode_prompt = build_mode_prompt(mode, skip_json_schema=skip_json)
    tone_hint = build_tone_hint(message)

    system_messages = [
        {"role": "system", "content": core_prompt},
        {"role": "system", "content": f"{mode_prompt}\n\n{tone_hint}".strip()},
    ]
    if is_grief_disclosure(message):
        system_messages.append({
            "role": "system",
            "content": "He's sharing something painful. Be with him. Ask about what he's shared, let him lead."
        })

    policy = choose_model(meta, context)
    response_text = _call_ollama(
        messages=system_messages + [{"role": "user", "content": json.dumps(context)}],
        model=policy["model"],
        options=policy["options"],
    )
    text = _extract_text(response_text)
    enriched = engine.enrich_response(text)
    return {"type": "suggestion", "text": enriched}


def _call_ollama(messages: list, model: str, options: dict) -> str:
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": options,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{host}/api/chat",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = resp.read().decode("utf-8")
    parsed = json.loads(body)
    return parsed.get("message", {}).get("content", "")


def _extract_text(response_text: str) -> str:
    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict) and isinstance(parsed.get("text"), str):
            return parsed["text"].strip()
    except json.JSONDecodeError:
        pass
    return cleaned


async def main() -> int:
    parser = argparse.ArgumentParser(description="Compare personality responses.")
    parser.add_argument("message", help="User message to test")
    parser.add_argument(
        "--personalities",
        default=",".join(DEFAULT_PERSONALITIES),
        help="Comma-separated list of personalities",
    )
    args = parser.parse_args()

    personalities = [p.strip() for p in args.personalities.split(",") if p.strip()]
    if not personalities:
        print("No personalities provided.")
        return 2

    for personality in personalities:
        print("\n" + "=" * 72)
        print(f"Personality: {personality}")
        print("=" * 72)
        if not _ADVISE_AVAILABLE:
            print(f"(Fallback mode: {_ADVISE_IMPORT_ERROR})")
        try:
            response = await run_once(args.message, personality)
        except Exception as exc:
            print(f"Error: {exc}")
            continue

        text = response.get("text") or ""
        if text:
            print(text)
        else:
            print(f"No text response. Raw: {response}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
