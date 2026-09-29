"""
Voice check: measure how well STT and TTS work, using only the MQTT topics the
services already publish. Run it on any machine that can reach the broker while
brain.voice.transcriber and/or brain.voice.speaker are running.

    ./sage voicecheck status          # are STT and TTS up, which model/engine
    ./sage voicecheck tts             # speak test phrases, report time-to-audio and gen time
    ./sage voicecheck stt             # you say each phrase; reports WER, latency, parser hit
    ./sage voicecheck wav a.wav b.wav # offline: transcribe files with the STT settings (needs faster-whisper)
    ./sage voicecheck all             # status + tts + stt

Phrases default to the switch commands (what the loop must understand); pass
--phrases FILE (one per line) to test your own.
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import re
import statistics
import sys
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

_probe = Path(__file__).resolve().parent
for _parent in [_probe, *_probe.parents]:
    if (_parent / "sage.py").exists():
        if str(_parent) not in sys.path:
            sys.path.insert(0, str(_parent))
        break

DEFAULT_PHRASES = [
    "turn on the desk lamp",
    "switch off the fan",
    "lights off",
    "turn on the main light",
    "is the fan on",
    "switch off everything",
    "toggle the desk lamp",
    "office lights off",
    "turn off the fan and the lamp",
    "hey sage what time is it",
]

TTS_PHRASES = [
    "Desk lamp on.",
    "Lights off.",
    "Fan is on.",
    "All off.",
    "I did not catch a switch command.",
    "The kitchen light and the desk lamp are on, the fan is off.",
]

TOPICS = {
    "transcript": "sage/voice/transcript",
    "stt_status": "sage/stt/status",
    "stt_metrics": "sage/stt/metrics",
    "stt_levels": "sage/stt/levels",
    "stt_control": "sage/stt/control",
    "tts_in": "sage/voice/response",
    "tts_status": "sage/tts/status",
    "tts_metrics": "sage/tts/metrics",
    "tts_clear": "sage/tts/clear",
}


# ---- pure helpers (unit tested) --------------------------------------------------

def norm_words(text: str) -> List[str]:
    text = (text or "").lower().replace("’", "'")
    text = re.sub(r"[^\w\s']+", " ", text)
    return text.split()


def word_error_rate(expected: str, heard: str) -> float:
    """Classic WER = edit distance over reference words. 0.0 is perfect, can exceed 1.0."""
    ref, hyp = norm_words(expected), norm_words(heard)
    if not ref:
        return 0.0 if not hyp else 1.0
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i]
        for j, h in enumerate(hyp, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (0 if r == h else 1)))
        prev = cur
    return prev[-1] / len(ref)


def parser_agrees(expected: str, heard: str) -> Optional[bool]:
    """Would the switch parser do the same thing with what STT heard as with the intended phrase?"""
    try:
        from brain.devices.switch_commands import SwitchRegistry, parse_switch_command
        registry = SwitchRegistry.load()
    except Exception:
        return None
    want = parse_switch_command(expected, registry)
    got = parse_switch_command(heard, registry)
    if want is None and got is None:
        return True
    if want is None or got is None:
        return False
    return want.action == got.action and [s.id for s in want.switches] == [s.id for s in got.switches]


def grade(wer: float) -> str:
    if wer == 0:
        return "perfect"
    if wer <= 0.2:
        return "good"
    if wer <= 0.5:
        return "rough"
    return "bad"


def summarize_stt(results: List[Dict]) -> Dict:
    heard = [r for r in results if r.get("heard") is not None]
    wers = [r["wer"] for r in heard]
    lat = [r["transcribe_ms"] for r in heard if r.get("transcribe_ms") is not None]
    agree = [r["parser_ok"] for r in heard if r.get("parser_ok") is not None]
    return {
        "phrases": len(results),
        "heard": len(heard),
        "missed": len(results) - len(heard),
        "mean_wer": round(statistics.mean(wers), 3) if wers else None,
        "perfect": sum(1 for w in wers if w == 0),
        "parser_ok": sum(1 for a in agree if a),
        "parser_total": len(agree),
        "median_transcribe_ms": int(statistics.median(lat)) if lat else None,
        "max_transcribe_ms": max(lat) if lat else None,
    }


def summarize_tts(results: List[Dict]) -> Dict:
    ok = [r for r in results if r.get("first_audio_ms") is not None]
    gen = [r["gen_ms"] for r in ok if r.get("gen_ms") is not None]
    tta = [r["first_audio_ms"] for r in ok]
    rtf = [r["gen_ms"] / 1000 / r["audio_s"] for r in ok if r.get("gen_ms") and r.get("audio_s")]
    return {
        "phrases": len(results),
        "spoken": len(ok),
        "failed": len(results) - len(ok),
        "median_first_audio_ms": int(statistics.median(tta)) if tta else None,
        "max_first_audio_ms": max(tta) if tta else None,
        "median_gen_ms": int(statistics.median(gen)) if gen else None,
        "mean_realtime_factor": round(statistics.mean(rtf), 2) if rtf else None,
        "engine": next((r.get("engine") for r in ok if r.get("engine")), None),
    }


# ---- MQTT plumbing -----------------------------------------------------------------

class Bus:
    """Thin subscriber that queues every message with its arrival time."""

    def __init__(self, host: str, port: int):
        from brain.devices.switch_controller import mqtt_client

        self.q: "queue.Queue[tuple[float, str, str]]" = queue.Queue()
        self.client = mqtt_client()
        self.client.on_message = lambda c, u, m: self.q.put((time.time(), m.topic, m.payload.decode("utf-8", "ignore")))
        self.client.connect(host, port, 60)
        for t in ("sage/voice/#", "sage/stt/#", "sage/tts/#"):
            self.client.subscribe(t)
        self.client.loop_start()

    def publish(self, topic: str, payload: str):
        self.client.publish(topic, payload)

    def drain(self):
        while True:
            try:
                self.q.get_nowait()
            except queue.Empty:
                return

    def wait_for(self, predicate, timeout: float):
        """Return (t, topic, payload) of the first message matching predicate, else None."""
        deadline = time.time() + timeout
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                return None
            try:
                item = self.q.get(timeout=min(remaining, 0.2))
            except queue.Empty:
                continue
            if predicate(*item):
                return item

    def collect_until(self, predicate, timeout: float):
        """Like wait_for, but returns every message consumed up to and including the match (or all, on timeout)."""
        seen = []
        deadline = time.time() + timeout
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                return seen, None
            try:
                item = self.q.get(timeout=min(remaining, 0.2))
            except queue.Empty:
                continue
            seen.append(item)
            if predicate(*item):
                return seen, item

    def close(self):
        self.client.loop_stop()
        self.client.disconnect()


def _json(payload: str) -> Dict:
    try:
        return json.loads(payload)
    except Exception:
        return {}


# ---- checks -------------------------------------------------------------------------

def check_status(bus: Bus, timeout: float = 4.0) -> Dict:
    print("\n== Service status ==")
    bus.drain()
    stt_seen = bus.wait_for(lambda t, topic, p: topic == TOPICS["stt_levels"], timeout)
    if stt_seen:
        print("✅ STT is running (audio levels flowing on sage/stt/levels)")
    else:
        print(f"❌ STT not seen in {timeout:.0f}s: brain.voice.transcriber is not running or not on this broker")

    bus.drain()
    bus.publish(TOPICS["tts_in"], json.dumps({"text": "Voice check.", "source": "voice_check"}))
    t0 = time.time()
    tts_seen = bus.wait_for(lambda t, topic, p: topic == TOPICS["tts_status"], timeout + 6)
    tts = {}
    if tts_seen:
        tts = _json(tts_seen[2])
        st = tts.get("status")
        if st == "disabled":
            print(f"⚠️  TTS is running but DISABLED (engine={tts.get('engine')}). Enable it: "
                  "mosquitto_pub -t sage/tts/control -m '{\"enabled\": true}'")
        else:
            print(f"✅ TTS is running (engine={tts.get('engine')}, status={st}, "
                  f"first reaction {int((tts_seen[0]-t0)*1000)}ms)")
            bus.wait_for(lambda t, topic, p: topic == TOPICS["tts_status"] and _json(p).get("status") in ("done", "idle"), 15)
    else:
        print(f"❌ TTS not seen: brain.voice.speaker is not running or not on this broker")
    return {"stt_up": bool(stt_seen), "tts_up": bool(tts_seen), "tts": tts}


def check_tts(bus: Bus, phrases: List[str], timeout: float = 30.0, interactive: bool = False) -> List[Dict]:
    print("\n== TTS ==  (listen: is every phrase audible and natural?)")
    bus.publish(TOPICS["tts_clear"], json.dumps({"reason": "voice_check"}))
    results = []
    is_status = lambda p, *states: _json(p).get("status") in states  # noqa: E731
    for i, phrase in enumerate(phrases):
        bus.drain()
        t0 = time.time()
        bus.publish(TOPICS["tts_in"], json.dumps({"text": phrase, "source": "voice_check"}))
        row: Dict = {"text": phrase, "first_audio_ms": None, "gen_ms": None, "audio_s": None, "engine": None}
        # First phrase may have to load the model: allow longer.
        seen, speaking = bus.collect_until(
            lambda t, topic, p: topic == TOPICS["tts_status"] and is_status(p, "speaking", "disabled"),
            timeout * (2 if i == 0 else 1))
        if speaking and is_status(speaking[2], "disabled"):
            print("  ⚠️  TTS is disabled; enable with: mosquitto_pub -t sage/tts/control -m '{\"enabled\": true}'")
            results.append(row)
            break
        if speaking:
            row["first_audio_ms"] = int((speaking[0] - t0) * 1000)
            row["engine"] = _json(speaking[2]).get("engine")
            more, done = bus.collect_until(
                lambda t, topic, p: topic == TOPICS["tts_status"] and is_status(p, "done", "idle"), timeout)
            seen += more
            row["playback_ms"] = int((done[0] - speaking[0]) * 1000) if done else None
        for _, topic, payload in seen:  # synth metrics are published just before "speaking"
            m = _json(payload)
            if topic == TOPICS["tts_metrics"] and m.get("event") == "synth":
                row["gen_ms"], row["audio_s"] = m.get("gen_ms"), m.get("audio_duration_s")
            if topic == TOPICS["tts_metrics"] and m.get("event") == "model_loaded":
                row["model_load_ms"] = m.get("load_ms")
        if row["first_audio_ms"] is None:
            status = "❌ no audio      "
        else:
            status = (f"first audio {row['first_audio_ms']:>5}ms  gen {row['gen_ms'] if row['gen_ms'] is not None else '?':>5}ms"
                      f"  audio {row['audio_s'] if row['audio_s'] is not None else '?'}s")
            if row.get("model_load_ms"):
                status += f"  (model load {row['model_load_ms']}ms)"
        print(f"  {status}   '{phrase}'")
        if interactive and row["first_audio_ms"] is not None:
            ans = input("     clear? [Y/n/notes] ").strip()
            row["rating"] = ans or "y"
        results.append(row)
    s = summarize_tts(results)
    print(f"\n  TTS summary: {s['spoken']}/{s['phrases']} spoken, engine={s['engine']}, "
          f"median first-audio {s['median_first_audio_ms']}ms (max {s['max_first_audio_ms']}), "
          f"median gen {s['median_gen_ms']}ms, realtime factor {s['mean_realtime_factor']}")
    if s["median_first_audio_ms"] and s["median_first_audio_ms"] > 1500:
        print("  ⚠️  slow first audio: set TTS_PREWARM=true, use TTS_ENGINE=kokoro, or check the GPU is used")
    return results


def check_stt(bus: Bus, phrases: List[str], timeout: float = 12.0) -> List[Dict]:
    print("\n== STT ==  say each phrase after the prompt, then pause. Keep TTS quiet meanwhile.")
    bus.publish(TOPICS["stt_control"], json.dumps({"enabled": True}))
    results = []
    for i, phrase in enumerate(phrases, 1):
        input(f"\n  [{i}/{len(phrases)}] press Enter, then say:  \"{phrase}\"  ")
        bus.drain()
        t0 = time.time()
        heard = bus.wait_for(lambda t, topic, p: topic == TOPICS["transcript"], timeout)
        row: Dict = {"expected": phrase, "heard": None, "wer": None, "transcribe_ms": None, "audio_s": None, "parser_ok": None}
        if heard is None:
            print(f"     ❌ nothing transcribed in {timeout:.0f}s (mic level? VAD threshold? STT disabled?)")
            results.append(row)
            continue
        text = heard[2]
        if text.startswith("{"):
            text = str(_json(text).get("text", text))
        metrics = bus.wait_for(lambda t, topic, p: topic == TOPICS["stt_metrics"] and "transcribe_ms" in _json(p), 2.0)
        m = _json(metrics[2]) if metrics else {}
        row.update({
            "heard": text,
            "wer": round(word_error_rate(phrase, text), 3),
            "transcribe_ms": m.get("transcribe_ms"),
            "audio_s": m.get("audio_duration_s"),
            "end_to_end_ms": int((heard[0] - t0) * 1000),
            "parser_ok": parser_agrees(phrase, text),
        })
        p_icon = {True: "parser ✅", False: "parser ❌", None: ""}[row["parser_ok"]]
        print(f"     heard: '{text}'")
        print(f"     WER {row['wer']:.2f} ({grade(row['wer'])})  transcribe {row['transcribe_ms']}ms  "
              f"audio {row['audio_s']}s  {p_icon}")
        results.append(row)
    s = summarize_stt(results)
    print(f"\n  STT summary: heard {s['heard']}/{s['phrases']}, perfect {s['perfect']}, mean WER {s['mean_wer']}, "
          f"parser would act correctly on {s['parser_ok']}/{s['parser_total']}, "
          f"median transcribe {s['median_transcribe_ms']}ms (max {s['max_transcribe_ms']})")
    bad = [r for r in results if r.get("parser_ok") is False]
    if bad:
        print("  💡 consistently misheard device names can be added as aliases in devices/switches.json:")
        for r in bad:
            print(f"     wanted '{r['expected']}'  got '{r['heard']}'")
    if s["missed"]:
        print("  💡 missed phrases: check `arecord -l` / input device, STT_VAD_THRESHOLD (lower = more sensitive), STT_MIN_SPEECH_MS")
    return results


def check_wav(files: List[str]) -> List[Dict]:
    """Offline transcription with the same settings the transcriber uses. Needs faster-whisper."""
    from faster_whisper import WhisperModel  # heavy; only here

    model_id = os.getenv("STT_MODEL_PATH", "").strip() or os.getenv("STT_MODEL_SIZE", "medium.en")
    device = os.getenv("STT_DEVICE", "cuda")
    compute = os.getenv("STT_COMPUTE_TYPE", "float16")
    print(f"\n== WAV ==  model={model_id} device={device} compute={compute}")
    t = time.time()
    model = WhisperModel(model_id, device=device, compute_type=compute)
    print(f"  model loaded in {int((time.time()-t)*1000)}ms")
    results = []
    for f in files:
        expected = None
        sidecar = Path(f).with_suffix(".txt")
        if sidecar.exists():
            expected = sidecar.read_text(encoding="utf-8").strip()
        t = time.time()
        segments, info = model.transcribe(f, beam_size=int(os.getenv("STT_BEAM_SIZE", "1")), vad_filter=True,
                                          language=os.getenv("STT_LANGUAGE") or None, temperature=0.0)
        text = "".join(s.text for s in segments).strip()
        ms = int((time.time() - t) * 1000)
        row = {"file": f, "heard": text, "transcribe_ms": ms, "expected": expected,
               "wer": round(word_error_rate(expected, text), 3) if expected else None}
        print(f"  {Path(f).name}: '{text}'  ({ms}ms" + (f", WER {row['wer']:.2f}" if expected else "") + ")")
        results.append(row)
    return results


def load_phrases(path: Optional[str], default: List[str]) -> List[str]:
    if not path:
        return default
    return [l.strip() for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Measure STT and TTS over MQTT")
    parser.add_argument("mode", choices=["status", "tts", "stt", "wav", "all"])
    parser.add_argument("files", nargs="*", help="WAV files for 'wav' mode")
    parser.add_argument("--host", default=os.getenv("MQTT_HOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", "1883")))
    parser.add_argument("--phrases", help="File with one phrase per line")
    parser.add_argument("--interactive", action="store_true", help="Ask you to rate each TTS phrase")
    parser.add_argument("--report", help="Write JSON results to this file")
    args = parser.parse_args(argv)
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass

    report: Dict = {"ts": int(time.time()), "mode": args.mode}
    if args.mode == "wav":
        if not args.files:
            print("give one or more .wav files (a sidecar .txt with the expected text enables WER)")
            return 2
        report["wav"] = check_wav(args.files)
    else:
        bus = Bus(args.host, args.port)
        try:
            if args.mode in ("status", "all"):
                report["status"] = check_status(bus)
            if args.mode in ("tts", "all"):
                report["tts"] = check_tts(bus, load_phrases(args.phrases, TTS_PHRASES), interactive=args.interactive)
                report["tts_summary"] = summarize_tts(report["tts"])
            if args.mode in ("stt", "all"):
                report["stt"] = check_stt(bus, load_phrases(args.phrases, DEFAULT_PHRASES))
                report["stt_summary"] = summarize_stt(report["stt"])
        finally:
            bus.close()
    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nreport written to {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
