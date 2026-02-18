import glob
import json
import logging
import os
import queue
import sys
import threading
import time
import uuid

import numpy as np
import paho.mqtt.client as mqtt
import sounddevice as sd
import soundfile as sf
import torch
from dotenv import load_dotenv
from f5_tts.api import F5TTS
from kokoro_onnx import Kokoro

# Ensure workspace root is importable when run via apps/... path.
from pathlib import Path

PROJECT_ROOT = None
_probe = Path(__file__).resolve().parent
for _parent in [_probe, *_probe.parents]:
    if (_parent / "sage.py").exists():
        PROJECT_ROOT = _parent
        if str(_parent) not in sys.path:
            sys.path.insert(0, str(_parent))
        break

from brain.voice.paths import get_training_artifacts_dir

logging.basicConfig(level=logging.INFO, format="[Speaker] %(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("Speaker")

# Load runtime env from brain runtime first (matches brain/main.py behavior).
env_candidates = []
if PROJECT_ROOT:
    env_candidates.extend([
        PROJECT_ROOT / "apps" / "brain-runtime" / ".env",
        PROJECT_ROOT / "brain" / ".env",
        PROJECT_ROOT / ".env",
    ])
_loaded_env_path = None
for _env_path in env_candidates:
    if _env_path.exists():
        load_dotenv(_env_path)
        _loaded_env_path = str(_env_path)
        break
if not _loaded_env_path:
    load_dotenv()

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

PREWARM_TTS = os.getenv("TTS_PREWARM", "false").lower() == "true"
SAVE_DATASET = os.getenv("TTS_SAVE_DATASET", "false").lower() == "true"
IDLE_TIMEOUT = int(os.getenv("TTS_IDLE_TIMEOUT", "300"))
TTS_ENABLED_DEFAULT = os.getenv("TTS_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}

VOICE_DIR = os.path.dirname(__file__)
TRAINING_ARTIFACTS_DIR = str(get_training_artifacts_dir(__file__))

REFERENCE_WAV = os.path.join(VOICE_DIR, "reference.wav")
KOKORO_MODEL = os.path.join(VOICE_DIR, "models/kokoro-v0_19.onnx")
KOKORO_VOICES = os.path.join(VOICE_DIR, "models/voices.bin")
QWEN_REF_AUDIO = os.path.join(VOICE_DIR, "qwen_reference.wav")

QWEN_MODEL_ENV = os.getenv("QWEN_TTS_MODEL", "").strip()
QWEN_SPEAKER = os.getenv("QWEN_TTS_SPEAKER", "sage_sheng")
QWEN_LANGUAGE = os.getenv("QWEN_TTS_LANGUAGE", "Auto")
QWEN_MAX_NEW_TOKENS = int(os.getenv("QWEN_TTS_MAX_NEW_TOKENS", "640"))
QWEN_REPETITION_PENALTY = float(os.getenv("QWEN_TTS_REPETITION_PENALTY", "1.08"))
QWEN_TEMPERATURE = float(os.getenv("QWEN_TTS_TEMPERATURE", "0.9"))
QWEN_INSTRUCTION = os.getenv("QWEN_TTS_INSTRUCTION", os.getenv("QWEN_TTS_INSTRUCT", "")).strip()
TTS_AUTO_FALLBACK = os.getenv("TTS_AUTO_FALLBACK", "true").lower() == "true"
TTS_FALLBACK_ENGINE = os.getenv("TTS_FALLBACK_ENGINE", "kokoro").lower()
TTS_OUTPUT_DEVICE = os.getenv("TTS_OUTPUT_DEVICE", "").strip()
TTS_OUTPUT_DEVICE_INDEX = os.getenv("TTS_OUTPUT_DEVICE_INDEX", "").strip()
if _loaded_env_path:
    logger.info(f"Loaded env from {_loaded_env_path}")


class SpeakerService:
    def __init__(self):
        self.running = False
        self.mqtt_client = mqtt.Client()
        self.speech_queue = queue.Queue()

        self.engine_type = os.getenv("TTS_ENGINE", "kokoro").lower()
        self.tts_f5 = None
        self.tts_kokoro = None
        self.tts_qwen = None
        self.qwen_model_path = None
        self.auto_fallback = TTS_AUTO_FALLBACK
        self.fallback_engine = TTS_FALLBACK_ENGINE if TTS_FALLBACK_ENGINE in {"kokoro", "f5"} else "kokoro"

        self.speed = 0.85
        self.voice = "af_bella"
        self.qwen_instruction = QWEN_INSTRUCTION
        self.tts_enabled = TTS_ENABLED_DEFAULT
        self.last_model_load_ms = 0
        self.last_gen_ms = 0
        self.last_audio_duration_s = 0.0
        self.last_engine_event_ts = 0
        self._configure_output_device()

    def _publish_status(self, status: str, **extra):
        payload = {"status": status}
        payload.update({k: v for k, v in extra.items() if v is not None})
        try:
            self.mqtt_client.publish("sage/tts/status", json.dumps(payload))
        except Exception as exc:
            logger.debug(f"Failed to publish tts/status: {exc}")

    def _publish_metrics(self, **payload):
        safe_payload = {k: v for k, v in payload.items() if v is not None}
        safe_payload["ts"] = int(time.time() * 1000)
        try:
            self.mqtt_client.publish("sage/tts/metrics", json.dumps(safe_payload))
        except Exception as exc:
            logger.debug(f"Failed to publish tts/metrics: {exc}")

    def _engine_loaded(self, engine_name: str | None = None) -> bool:
        engine = (engine_name or self.engine_type).lower()
        if engine == "qwen":
            return self.tts_qwen is not None
        if engine == "kokoro":
            return self.tts_kokoro is not None
        if engine == "f5":
            return self.tts_f5 is not None
        return False

    def _configure_output_device(self):
        """
        Optionally pin playback to a specific output device.
        This avoids 'no audible sound' when system default routes to the wrong sink.
        """
        try:
            current_input, current_output = sd.default.device
            devices = sd.query_devices()

            # Highest priority: explicit output index
            if TTS_OUTPUT_DEVICE_INDEX:
                try:
                    out_idx = int(TTS_OUTPUT_DEVICE_INDEX)
                    if out_idx < 0 or out_idx >= len(devices):
                        raise ValueError(f"index {out_idx} out of range")
                    if devices[out_idx].get("max_output_channels", 0) <= 0:
                        raise ValueError(f"device {out_idx} has no output channels")
                    sd.default.device = [current_input, out_idx]
                    logger.info(
                        f"Audio output pinned by index: {out_idx} ({devices[out_idx]['name']})"
                    )
                    return
                except Exception as exc:
                    logger.warning(f"Invalid TTS_OUTPUT_DEVICE_INDEX='{TTS_OUTPUT_DEVICE_INDEX}': {exc}")

            # Next: name substring match (case-insensitive)
            if TTS_OUTPUT_DEVICE:
                needle = TTS_OUTPUT_DEVICE.lower()
                for idx, dev in enumerate(devices):
                    if dev.get("max_output_channels", 0) <= 0:
                        continue
                    if needle in str(dev.get("name", "")).lower():
                        sd.default.device = [current_input, idx]
                        logger.info(f"Audio output pinned by name: {idx} ({dev['name']})")
                        return
                logger.warning(f"No output device matched TTS_OUTPUT_DEVICE='{TTS_OUTPUT_DEVICE}'")

            # Log current default for debugging.
            out_name = "unknown"
            try:
                if isinstance(current_output, int) and 0 <= current_output < len(devices):
                    out_name = devices[current_output].get("name", "unknown")
            except Exception:
                pass
            logger.info(f"Audio output default: {current_output} ({out_name})")
        except Exception as exc:
            logger.warning(f"Could not configure audio output device: {exc}")

    def _fallback_from_qwen(self, reason: str):
        if not self.auto_fallback:
            return
        if self.engine_type != "qwen":
            return
        if self.fallback_engine == "qwen":
            return
        logger.warning(
            f"Qwen TTS unavailable ({reason}). Falling back to {self.fallback_engine}."
        )
        self._publish_metrics(
            event="fallback",
            from_engine="qwen",
            to_engine=self.fallback_engine,
            reason=reason[:240],
        )
        self.engine_type = self.fallback_engine
        self.load_model()

    def _latest_checkpoint_dir(self, model_size: str):
        base = os.path.join(TRAINING_ARTIFACTS_DIR, f"checkpoints/qwen3-tts-sheng-{model_size}")
        final = os.path.join(base, "final")
        if os.path.exists(final):
            return final

        candidates = []
        for path in glob.glob(os.path.join(base, "checkpoint-epoch-*")):
            try:
                epoch = int(path.rsplit("-", 1)[1])
                candidates.append((epoch, path))
            except ValueError:
                continue
        if candidates:
            return max(candidates, key=lambda x: x[0])[1]
        return None

    def _resolve_qwen_model_path(self):
        candidates = []
        if QWEN_MODEL_ENV:
            candidates.append(QWEN_MODEL_ENV)
        for size in ("1.7b", "0.6b"):
            latest = self._latest_checkpoint_dir(size)
            if latest:
                candidates.append(latest)

        for candidate in candidates:
            if candidate and os.path.exists(candidate):
                return os.path.abspath(candidate)
        return None

    def _qwen_generation_kwargs(self, text: str):
        words = max(1, len(text.split()))
        phrase_cap = max(128, min(QWEN_MAX_NEW_TOKENS, 64 + words * 12))
        return {
            "max_new_tokens": phrase_cap,
            "repetition_penalty": QWEN_REPETITION_PENALTY,
            "temperature": QWEN_TEMPERATURE,
        }

    def _synthesize_qwen(self, text: str):
        if not self.tts_qwen:
            return None, None

        model_type = getattr(self.tts_qwen.model, "tts_model_type", "base")
        kwargs = self._qwen_generation_kwargs(text)

        if model_type == "custom_voice":
            wavs, sr = self.tts_qwen.generate_custom_voice(
                text=text,
                speaker=QWEN_SPEAKER,
                language=QWEN_LANGUAGE,
                instruct=self.qwen_instruction or None,
                **kwargs,
            )
        elif model_type == "base":
            if not os.path.exists(QWEN_REF_AUDIO):
                raise FileNotFoundError(
                    f"Qwen base mode requires reference audio; missing {QWEN_REF_AUDIO}"
                )
            wavs, sr = self.tts_qwen.generate_voice_clone(
                text=text,
                language=QWEN_LANGUAGE,
                ref_audio=QWEN_REF_AUDIO,
                x_vector_only_mode=True,
                **kwargs,
            )
        else:
            raise RuntimeError(f"Unsupported qwen tts_model_type: {model_type}")

        if not wavs:
            return None, None
        return wavs[0], sr

    def connect_mqtt(self):
        try:
            self.mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
            self.mqtt_client.on_message = self.on_message
            self.mqtt_client.subscribe("sage/voice/response")
            self.mqtt_client.subscribe("sage/voice/config")
            self.mqtt_client.subscribe("sage/tts/clear")
            self.mqtt_client.subscribe("sage/tts/control")
            self.mqtt_client.loop_start()
            logger.info(f"Connected to MQTT broker at {MQTT_HOST}:{MQTT_PORT}")
            self._publish_status("idle" if self.tts_enabled else "disabled", engine=self.engine_type)
        except Exception as exc:
            logger.error(f"Failed to connect to MQTT: {exc}")
            sys.exit(1)

    def on_message(self, client, userdata, msg):
        topic = msg.topic
        payload_str = msg.payload.decode()

        try:
            payload = json.loads(payload_str, strict=False)
        except json.JSONDecodeError:
            if topic == "sage/voice/response":
                payload = {"text": payload_str}
            else:
                return

        if topic == "sage/tts/clear":
            queue_size = self.speech_queue.qsize()
            if queue_size > 0:
                logger.info(f"🗑️ Clearing speech queue ({queue_size} items)")
                with self.speech_queue.mutex:
                    self.speech_queue.queue.clear()
            return

        if topic == "sage/tts/control":
            enabled = bool(payload.get("enabled", True))
            self.tts_enabled = enabled
            if not enabled:
                queue_size = self.speech_queue.qsize()
                if queue_size > 0:
                    with self.speech_queue.mutex:
                        self.speech_queue.queue.clear()
                logger.info("💤 TTS disabled via control topic")
                self._publish_status("disabled", engine=self.engine_type)
            else:
                logger.info("🔊 TTS enabled via control topic")
                self._publish_status("idle", engine=self.engine_type)
            return

        if topic == "sage/voice/response":
            if not self.tts_enabled:
                logger.debug("Skipping voice/response because TTS is disabled")
                return
            if payload.get("no_tts") or payload.get("tts") is False:
                logger.debug("Skipping voice/response payload marked no_tts")
                return
            text = payload.get("text")
            if text:
                logger.info(f"Received text: '{text[:50]}...'")
                self.speech_queue.put(text)

        elif topic == "sage/voice/config":
            if "engine" in payload:
                self.switch_engine(payload["engine"])
            if "speed" in payload:
                self.speed = float(payload["speed"])
                logger.info(f"Speed set to {self.speed}")
            if "voice" in payload:
                self.voice = payload["voice"]
                logger.info(f"Voice set to {self.voice}")
            if "qwen_instruction" in payload:
                self.qwen_instruction = str(payload.get("qwen_instruction", "")).strip()
                if self.qwen_instruction:
                    logger.info("Qwen instruction updated.")
                else:
                    logger.info("Qwen instruction cleared.")

    def switch_engine(self, engine_name):
        engine_name = engine_name.lower()
        if engine_name not in ["f5", "kokoro", "qwen"]:
            logger.warning(f"Unknown engine: {engine_name}")
            return

        logger.info(f"Switching Engine: {self.engine_type} -> {engine_name}")
        self.unload_model()
        self.engine_type = engine_name
        self._publish_status("idle" if self.tts_enabled else "disabled", engine=self.engine_type)
        self._publish_metrics(event="engine_switch", engine=self.engine_type)

    def load_model(self):
        engine_before = self.engine_type
        if self._engine_loaded(engine_before):
            return

        load_start = time.time()
        self._publish_status("warming", engine=engine_before, phase="model_load")
        if self.engine_type == "f5" and self.tts_f5 is None:
            logger.info(f"Loading F5-TTS on {DEVICE}...")
            self.tts_f5 = F5TTS(model="F5TTS_v1_Base", device=DEVICE)

        elif self.engine_type == "kokoro" and self.tts_kokoro is None:
            logger.info(f"Loading Kokoro on {DEVICE}...")
            if not os.path.exists(KOKORO_MODEL):
                logger.error(f"Kokoro model not found at {KOKORO_MODEL}")
                return
            self.tts_kokoro = Kokoro(KOKORO_MODEL, KOKORO_VOICES)

        elif self.engine_type == "qwen" and self.tts_qwen is None:
            model_path = self._resolve_qwen_model_path()
            if not model_path:
                logger.error(
                    "Could not resolve Qwen model path. Set QWEN_TTS_MODEL or run fine-tuning first."
                )
                self._fallback_from_qwen("model path missing")
                return
            logger.info(f"Loading Qwen3-TTS from {model_path} on {DEVICE}...")
            try:
                from qwen_tts import Qwen3TTSModel
            except Exception as exc:
                logger.error(f"Failed to import qwen_tts: {exc}")
                self._fallback_from_qwen("qwen_tts import failed")
                return

            try:
                dtype = torch.bfloat16 if DEVICE == "cuda" else torch.float32
                self.tts_qwen = Qwen3TTSModel.from_pretrained(
                    model_path,
                    torch_dtype=dtype,
                    attn_implementation="sdpa",
                )
                self.tts_qwen.model = self.tts_qwen.model.to(DEVICE)
                self.tts_qwen.device = torch.device(DEVICE)
                self.qwen_model_path = model_path
                model_type = getattr(self.tts_qwen.model, "tts_model_type", "unknown")
                has_instruction = "yes" if self.qwen_instruction else "no"
                logger.info(
                    f"Qwen model loaded: type={model_type}, speaker={QWEN_SPEAKER}, instruction={has_instruction}"
                )
            except Exception as exc:
                logger.error(f"Failed to load Qwen3-TTS model: {exc}")
                self.tts_qwen = None
                self._fallback_from_qwen(str(exc))
                return

        if self._engine_loaded(self.engine_type):
            self.last_model_load_ms = int((time.time() - load_start) * 1000)
            self.last_engine_event_ts = int(time.time() * 1000)
            self._publish_metrics(
                event="model_loaded",
                engine=self.engine_type,
                load_ms=self.last_model_load_ms,
                cached=False,
                device=DEVICE,
            )
            self._publish_status("idle" if self.tts_enabled else "disabled", engine=self.engine_type)

    def unload_model(self):
        if self.tts_f5:
            del self.tts_f5
            self.tts_f5 = None
            if DEVICE == "cuda":
                torch.cuda.empty_cache()

        if self.tts_kokoro:
            del self.tts_kokoro
            self.tts_kokoro = None

        if self.tts_qwen:
            del self.tts_qwen
            self.tts_qwen = None
            if DEVICE == "cuda":
                torch.cuda.empty_cache()

        logger.info("Models unloaded.")
        self._publish_metrics(event="model_unloaded", engine=self.engine_type)

    def process_speech(self):
        idle_start = time.time()

        while self.running:
            try:
                text = self.speech_queue.get(timeout=1)
                if not self.tts_enabled:
                    logger.debug("Ignoring queued text because TTS is disabled")
                    continue
                self.load_model()

                gen_start = time.time()
                logger.info(f"Generating audio with {self.engine_type}...")

                wav = None
                sr = 24000

                if self.engine_type == "f5" and self.tts_f5:
                    wav, sr, _ = self.tts_f5.infer(
                        ref_file=REFERENCE_WAV if os.path.exists(REFERENCE_WAV) else None,
                        ref_text="",
                        gen_text=text,
                        speed=self.speed,
                    )

                elif self.engine_type == "kokoro" and self.tts_kokoro:
                    wav, sr = self.tts_kokoro.create(
                        text,
                        voice=self.voice,
                        speed=self.speed,
                        lang="en-us",
                    )

                elif self.engine_type == "qwen" and self.tts_qwen:
                    wav, sr = self._synthesize_qwen(text)
                    if abs(self.speed - 1.0) > 0.01:
                        logger.debug("Qwen engine does not support direct speed control; ignoring speed override.")

                gen_elapsed = int((time.time() - gen_start) * 1000)
                self.last_gen_ms = gen_elapsed

                if wav is not None:
                    if wav.dtype == np.int16:
                        wav = wav.astype(np.float32) / 32768.0

                    if SAVE_DATASET:
                        try:
                            dataset_dir = os.path.join(VOICE_DIR, "dataset")
                            os.makedirs(dataset_dir, exist_ok=True)
                            file_id = f"{int(time.time())}_{uuid.uuid4().hex[:6]}"
                            wav_path = os.path.join(dataset_dir, f"{file_id}.wav")
                            txt_path = os.path.join(dataset_dir, f"{file_id}.txt")
                            sf.write(wav_path, wav, sr)
                            with open(txt_path, "w", encoding="utf-8") as f:
                                f.write(text)
                            logger.info(f"[Dataset] Saved training sample: {file_id}")
                        except Exception as exc:
                            logger.error(f"[Dataset] Failed to save sample: {exc}")

                    self.last_audio_duration_s = round(len(wav) / sr, 3)
                    self._publish_metrics(
                        event="synth",
                        engine=self.engine_type,
                        gen_ms=gen_elapsed,
                        audio_duration_s=self.last_audio_duration_s,
                        model_load_ms=self.last_model_load_ms,
                        text_chars=len(text),
                        queue_depth=self.speech_queue.qsize(),
                    )

                    logger.info(f"Playing audio ({gen_elapsed}ms gen, {len(wav)/sr:.1f}s audio)")
                    self._publish_status("speaking", engine=self.engine_type)
                    sd.play(wav, samplerate=sr)
                    sd.wait()
                    self._publish_status("done", engine=self.engine_type)
                else:
                    logger.warning(f"No audio generated (engine={self.engine_type}).")
                    self._publish_metrics(
                        event="synth_empty",
                        engine=self.engine_type,
                        gen_ms=gen_elapsed,
                    )

                idle_start = time.time()

            except queue.Empty:
                if (self.tts_f5 or self.tts_kokoro or self.tts_qwen) and (
                    time.time() - idle_start > IDLE_TIMEOUT
                ):
                    logger.info("Idle timeout. Unloading.")
                    self.unload_model()
                continue
            except Exception as exc:
                logger.error(f"Speech generation error: {exc}")
                if self.engine_type == "qwen":
                    self.tts_qwen = None
                    self._fallback_from_qwen(str(exc))
                time.sleep(1)

    def prewarm(self):
        logger.info("Pre-warming TTS model...")
        self._publish_status("warming", engine=self.engine_type, phase="prewarm")
        start = time.time()
        self.load_model()

        try:
            if self.tts_kokoro:
                self.tts_kokoro.create("OK", voice=self.voice, speed=1.0, lang="en-us")
            elif self.tts_f5:
                self.tts_f5.infer(
                    ref_file=REFERENCE_WAV if os.path.exists(REFERENCE_WAV) else None,
                    ref_text="",
                    gen_text="OK",
                    speed=1.0,
                )
            elif self.tts_qwen:
                self._synthesize_qwen("OK")
            elapsed = int((time.time() - start) * 1000)
            logger.info(f"TTS pre-warmed in {elapsed}ms")
            self._publish_metrics(event="prewarm", engine=self.engine_type, prewarm_ms=elapsed)
            self._publish_status("idle" if self.tts_enabled else "disabled", engine=self.engine_type)
        except Exception as exc:
            logger.warning(f"Prewarm failed (non-critical): {exc}")
            self._publish_metrics(event="prewarm_failed", engine=self.engine_type, reason=str(exc)[:240])

    def start(self):
        self.running = True
        self.connect_mqtt()

        if PREWARM_TTS:
            self.prewarm()

        process_thread = threading.Thread(target=self.process_speech)
        process_thread.daemon = True
        process_thread.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Stopping...")
            self.running = False
            self.mqtt_client.loop_stop()
            self.unload_model()


if __name__ == "__main__":
    service = SpeakerService()
    service.start()
