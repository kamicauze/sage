import os
import time
import json
import logging
import threading
import queue
import sys
from pathlib import Path
import numpy as np
import pyaudio
import paho.mqtt.client as mqtt
import torch
from faster_whisper import WhisperModel
from dotenv import load_dotenv

# Ensure workspace root is importable when run via apps/... path.
_probe = Path(__file__).resolve().parent
for _parent in [_probe, *_probe.parents]:
    if (_parent / "sage.py").exists():
        if str(_parent) not in sys.path:
            sys.path.insert(0, str(_parent))
        break

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[Transcriber] %(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("Transcriber")

load_dotenv()

# Configuration
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))

# STT Performance Tuning
# Options: tiny.en (fastest), small.en (balanced), medium.en (best quality)
# Set STT_MODEL_PATH to a local CTranslate2 directory for fine-tuned models
MODEL_SIZE = os.getenv("STT_MODEL_SIZE", "medium.en")
MODEL_PATH = os.getenv("STT_MODEL_PATH", "").strip()  # Fine-tuned CTranslate2 model dir
DEFAULT_LOCAL_MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "whisper-sheng-ct2")
if not MODEL_PATH and os.path.isdir(DEFAULT_LOCAL_MODEL_PATH) and os.listdir(DEFAULT_LOCAL_MODEL_PATH):
    MODEL_PATH = DEFAULT_LOCAL_MODEL_PATH
STT_LANGUAGE = os.getenv("STT_LANGUAGE", "")   # Language hint (e.g. "sw" for Sheng)
DEVICE = os.getenv("STT_DEVICE", "cuda")
COMPUTE_TYPE = os.getenv("STT_COMPUTE_TYPE", "float16")

# Audio Settings
FORMAT = pyaudio.paFloat32
CHANNELS = 1
RATE = 16000
CHUNK = 512  # Smaller chunks for more responsive VAD (32ms at 16kHz)

# VAD Settings - Silero VAD is smarter than energy threshold
USE_SILERO_VAD = os.getenv("STT_USE_SILERO_VAD", "true").lower() == "true"
VAD_THRESHOLD = float(os.getenv("STT_VAD_THRESHOLD", "0.5"))  # Silero probability threshold (0-1)
ENERGY_THRESHOLD = float(os.getenv("STT_ENERGY_THRESHOLD", "0.015"))  # Fallback energy threshold

# End-of-speech detection timing
# - SILENCE_DURATION: How long to wait after speech stops before processing
# - MIN_SPEECH_DURATION: Minimum speech length to process (avoid noise triggers)
# - MAX_SPEECH_DURATION: Maximum recording length (avoid runaway recordings)
SILENCE_DURATION = float(os.getenv("STT_SILENCE_DURATION", "0.5"))  # Tuned down from 0.7; Silero VAD handles boundaries
MIN_SPEECH_DURATION = float(os.getenv("STT_MIN_SPEECH_MS", "300")) / 1000  # 300ms minimum
MAX_SPEECH_DURATION = float(os.getenv("STT_MAX_SPEECH_SEC", "30"))  # 30 second max

# Transcription Speed Settings
BEAM_SIZE = int(os.getenv("STT_BEAM_SIZE", "1"))
STT_ENABLED_DEFAULT = os.getenv("STT_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}

class TranscriberService:
    def __init__(self):
        self.running = False
        self.mqtt_client = mqtt.Client()
        self.audio_queue = queue.Queue()
        self.model = None
        self.vad_model = None
        self.p = pyaudio.PyAudio()
        
        # Echo suppression: pause listening while TTS is speaking
        self.tts_speaking = False
        self.tts_cooldown_until = 0  # Timestamp when we can resume listening

        self.stt_enabled = STT_ENABLED_DEFAULT

    def _publish_status(self, status: str, **extra):
        payload = {"status": status}
        payload.update({k: v for k, v in extra.items() if v is not None})
        try:
            self.mqtt_client.publish("sage/stt/status", json.dumps(payload))
        except Exception as e:
            logger.debug(f"Failed to publish stt/status: {e}")

    def _publish_metrics(self, **extra):
        payload = {"ts": int(time.time() * 1000)}
        payload.update({k: v for k, v in extra.items() if v is not None})
        try:
            self.mqtt_client.publish("sage/stt/metrics", json.dumps(payload))
        except Exception as e:
            logger.debug(f"Failed to publish stt/metrics: {e}")
        
    def connect_mqtt(self):
        try:
            self.mqtt_client.on_message = self._on_message
            self.mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
            self.mqtt_client.subscribe("sage/config/performance")
            self.mqtt_client.subscribe("sage/tts/status")  # Listen for TTS status
            self.mqtt_client.subscribe("sage/stt/control")  # Runtime STT enable/disable
            self.mqtt_client.loop_start()
            logger.info(f"Connected to MQTT broker at {MQTT_HOST}:{MQTT_PORT}")
            
            # Publish status
            self._publish_status("starting", phase="mqtt_connected")
        except Exception as e:
            logger.error(f"Failed to connect to MQTT: {e}")
            sys.exit(1)
            
    def _on_message(self, client, userdata, msg):
        """Handle MQTT messages for config and TTS status."""
        global SILENCE_DURATION, MIN_SPEECH_DURATION
        
        topic = msg.topic

        # STT control from UI
        if topic == "sage/stt/control":
            try:
                data = json.loads(msg.payload.decode())
                enabled = bool(data.get("enabled", True))
                self.stt_enabled = enabled
                if enabled:
                    logger.info("🎤 STT enabled via control topic")
                    self._publish_status("listening")
                else:
                    logger.info("💤 STT disabled via control topic")
                    self._publish_status("offline")
            except Exception as e:
                logger.error(f"Failed to parse stt/control payload: {e}")
            return
        
        # Echo suppression: pause when TTS is speaking
        if topic == "sage/tts/status":
            try:
                data = json.loads(msg.payload.decode())
                tts_status = data.get("status", "")
                
                if tts_status == "speaking":
                    self.tts_speaking = True
                    logger.info("🔇 TTS speaking - STT paused")
                elif tts_status == "idle" or tts_status == "done":
                    self.tts_speaking = False
                    # Add cooldown to avoid catching tail end of TTS audio
                    self.tts_cooldown_until = time.time() + 0.8  # 800ms cooldown
                    logger.info("🎤 TTS done - STT resuming in 800ms")
                    
            except Exception as e:
                logger.debug(f"TTS status parse error: {e}")
            return
        
        # Config updates
        if topic == "sage/config/performance":
            try:
                config = json.loads(msg.payload.decode())
                
                if "silence_duration" in config:
                    SILENCE_DURATION = float(config["silence_duration"])
                    logger.info(f"Updated silence_duration: {SILENCE_DURATION}s")
                    
                if "min_speech_ms" in config:
                    MIN_SPEECH_DURATION = float(config["min_speech_ms"]) / 1000
                    logger.info(f"Updated min_speech_duration: {MIN_SPEECH_DURATION}s")
                    
            except Exception as e:
                logger.error(f"Failed to parse config: {e}")

    def load_model(self):
        model_id = MODEL_PATH if MODEL_PATH else MODEL_SIZE
        self._publish_status("warming", phase="stt_model_load", model=model_id)
        logger.info(f"Loading Whisper model ({model_id})...")
        load_start = time.time()
        try:
            self.model = WhisperModel(model_id, device=DEVICE, compute_type=COMPUTE_TYPE)
            if MODEL_PATH:
                logger.info(f"Fine-tuned Whisper loaded from {MODEL_PATH}")
            else:
                logger.info("Whisper model loaded successfully.")
            load_ms = int((time.time() - load_start) * 1000)
            self._publish_metrics(
                event="stt_model_loaded",
                model_id=model_id,
                model_load_ms=load_ms,
                device=DEVICE,
                compute_type=COMPUTE_TYPE,
            )
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            sys.exit(1)
            
    def load_vad(self):
        """Load Silero VAD model for smart speech detection."""
        if not USE_SILERO_VAD:
            logger.info("Silero VAD disabled, using energy-based detection")
            self._publish_metrics(event="vad_disabled")
            return
            
        self._publish_status("warming", phase="vad_load")
        logger.info("Loading Silero VAD model...")
        load_start = time.time()
        try:
            self.vad_model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                onnx=False
            )
            self.vad_model.eval()
            logger.info("Silero VAD loaded successfully.")
            self._publish_metrics(
                event="vad_loaded",
                vad_load_ms=int((time.time() - load_start) * 1000),
                vad_threshold=VAD_THRESHOLD,
            )
        except Exception as e:
            logger.warning(f"Failed to load Silero VAD: {e}. Falling back to energy-based.")
            self.vad_model = None
            self._publish_metrics(event="vad_fallback", reason=str(e)[:240])
            
    def is_speech(self, audio_chunk: np.ndarray) -> bool:
        """
        Detect if audio chunk contains speech.
        Uses Silero VAD if available, otherwise falls back to energy threshold.
        """
        if self.vad_model is not None:
            # Silero VAD expects torch tensor
            try:
                # Ensure audio is in correct format for Silero (16kHz, float32, -1 to 1)
                audio_tensor = torch.from_numpy(audio_chunk).float()
                
                # Silero needs at least 512 samples (32ms at 16kHz)
                if len(audio_tensor) < 512:
                    # Pad if too short
                    audio_tensor = torch.nn.functional.pad(audio_tensor, (0, 512 - len(audio_tensor)))
                
                with torch.no_grad():
                    speech_prob = self.vad_model(audio_tensor, RATE).item()
                
                return speech_prob > VAD_THRESHOLD
            except Exception as e:
                logger.debug(f"VAD error: {e}, falling back to energy")
                # Fallback to energy
                return np.mean(np.abs(audio_chunk)) > ENERGY_THRESHOLD
        else:
            # Energy-based fallback
            energy = np.mean(np.abs(audio_chunk))
            return energy > ENERGY_THRESHOLD

    def capture_audio(self):
        """
        Continuously capture audio with smart VAD.
        Uses Silero VAD for better end-of-speech detection.
        Includes echo suppression - pauses when TTS is speaking.
        """
        stream = self.p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK
        )
        
        
        logger.info("🎤 Listening...")
        if self.stt_enabled:
            self._publish_status("listening")
        else:
            self._publish_status("offline")
        
        frames = []
        is_speaking = False
        silence_start = None
        speech_start = None
        
        # Audio Level Publishing
        last_level_time = 0
        LEVEL_RATE = 0.1 # Publish every 100ms
        
        # Adaptive noise floor (running average of silence energy)
        noise_floor = 0.01
        noise_samples = 0
        
        while self.running:
            try:
                data = stream.read(CHUNK, exception_on_overflow=False)
                audio_chunk = np.frombuffer(data, dtype=np.float32)
                current_time = time.time()
                
                # Publish Audio Levels (RMS)
                if current_time - last_level_time > LEVEL_RATE:
                    rms = np.sqrt(np.mean(audio_chunk**2))
                    # Normalize roughly 0-1 for visualization (assuming float32 -1..1)
                    # Use a simple amplification for better visual feedback
                    vis_level = min(float(rms * 5.0), 1.0) 
                    self.mqtt_client.publish("sage/stt/levels", json.dumps({
                        "rms": float(rms),
                        "vis": vis_level
                    }))
                    last_level_time = current_time

                # STT disabled: keep stream open but skip speech detection and transcription
                if not self.stt_enabled:
                    if frames:
                        frames = []
                        is_speaking = False
                        silence_start = None
                        speech_start = None
                    continue
                
                
                # Echo suppression: skip processing while TTS is speaking or in cooldown
                if self.tts_speaking or current_time < self.tts_cooldown_until:
                    # Discard any accumulated frames to avoid processing TTS audio
                    if frames:
                        logger.debug("🔇 Discarding frames (TTS active)")
                        frames = []
                        is_speaking = False
                        silence_start = None
                        speech_start = None
                    continue
                
                # Check for speech
                speech_detected = self.is_speech(audio_chunk)
                
                if speech_detected:
                    if not is_speaking:
                        # Speech just started
                        is_speaking = True
                        speech_start = current_time
                        logger.debug("🗣️ Speech detected")
                        self._publish_status("hearing")
                    
                    frames.append(audio_chunk)
                    silence_start = None
                    
                    # Check max duration
                    if current_time - speech_start > MAX_SPEECH_DURATION:
                        logger.warning("Max speech duration reached, processing...")
                        self._process_frames(frames, speech_start)
                        frames = []
                        is_speaking = False
                        speech_start = None
                        
                else:
                    if is_speaking:
                        # We were speaking, now silent
                        frames.append(audio_chunk)  # Include trailing silence
                        
                        if silence_start is None:
                            silence_start = current_time
                        elif current_time - silence_start > SILENCE_DURATION:
                            # Silence long enough - check if we have enough speech
                            speech_duration = current_time - speech_start - SILENCE_DURATION
                            
                            if speech_duration >= MIN_SPEECH_DURATION:
                                logger.debug(f"✓ End of speech ({speech_duration:.1f}s)")
                                self._process_frames(frames, speech_start)
                            else:
                                logger.debug(f"✗ Too short ({speech_duration:.1f}s < {MIN_SPEECH_DURATION}s)")
                            
                            # Reset state
                            frames = []
                            is_speaking = False
                            silence_start = None
                            speech_start = None
                            self._publish_status("listening")
                    else:
                        # Update noise floor during silence
                        energy = np.mean(np.abs(audio_chunk))
                        noise_samples += 1
                        noise_floor = noise_floor * 0.99 + energy * 0.01  # Slow adaptation
                            
            except Exception as e:
                logger.error(f"Error capturing audio: {e}")
                
        stream.stop_stream()
        stream.close()
        
    def _process_frames(self, frames, speech_start):
        """Queue audio frames for transcription."""
        if not self.stt_enabled:
            return
        if frames:
            audio_data = np.concatenate(frames)
            self.audio_queue.put({
                "audio": audio_data,
                "start_time": speech_start,
                "duration": len(audio_data) / RATE
            })
            self._publish_status("processing", queue_depth=self.audio_queue.qsize())

    def process_audio(self):
        """
        Consume audio from queue and transcribe.
        Optimized for low-latency with smart VAD and fast decoding.
        """
        while self.running:
            try:
                item = self.audio_queue.get(timeout=1)
                if not self.stt_enabled:
                    continue
                
                # Extract audio and metadata
                if isinstance(item, dict):
                    audio_data = item["audio"]
                    speech_duration = item.get("duration", 0)
                else:
                    # Legacy format (just numpy array)
                    audio_data = item
                    speech_duration = len(audio_data) / RATE

                transcribe_start = time.time()
                
                # Optimized transcription settings for low latency
                transcribe_kwargs = dict(
                    beam_size=BEAM_SIZE,
                    best_of=1,
                    vad_filter=True,  # Additional VAD cleanup in Whisper
                    vad_parameters={
                        "min_silence_duration_ms": 200,
                        "speech_pad_ms": 100,
                    },
                    condition_on_previous_text=False,
                    initial_prompt=os.getenv("STT_INITIAL_PROMPT", "Sage assistant, home automation, coding help."),
                    temperature=0.0,
                    compression_ratio_threshold=2.4,
                    no_speech_threshold=0.6,
                )
                # Add language hint for fine-tuned Sheng model
                if STT_LANGUAGE:
                    transcribe_kwargs["language"] = STT_LANGUAGE

                segments, info = self.model.transcribe(audio_data, **transcribe_kwargs)
                
                full_text = ""
                for segment in segments:
                    full_text += segment.text
                    
                full_text = full_text.strip()
                
                transcribe_ms = int((time.time() - transcribe_start) * 1000)
                
                if full_text:
                    logger.info(f"📝 Transcribed ({transcribe_ms}ms, {speech_duration:.1f}s audio): '{full_text}'")
                    
                    # Publish transcript and metrics
                    self.mqtt_client.publish("sage/voice/transcript", full_text)
                    self._publish_metrics(
                        transcribe_ms=transcribe_ms,
                        audio_duration_s=round(speech_duration, 2),
                        text_length=len(full_text),
                        realtime_factor=round(transcribe_ms / 1000 / speech_duration, 2) if speech_duration > 0 else 0,
                        model_id=(MODEL_PATH if MODEL_PATH else MODEL_SIZE),
                    )
                else:
                    logger.debug(f"No speech detected in {speech_duration:.1f}s audio")

                if self.stt_enabled:
                    self._publish_status("listening")
                    
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Transcription error: {e}")
                self._publish_status("error", error=str(e)[:240])

    def start(self):
        self.running = True
        self.connect_mqtt()
        self._publish_status("warming", phase="startup")
        self.load_vad()  # Load VAD first (smaller model)
        self.load_model()  # Then Whisper
        
        # Start threads
        capture_thread = threading.Thread(target=self.capture_audio, name="AudioCapture")
        process_thread = threading.Thread(target=self.process_audio, name="Transcriber")
        
        capture_thread.daemon = True
        process_thread.daemon = True
        
        capture_thread.start()
        process_thread.start()
        
        logger.info("=" * 50)
        logger.info("🎤 Transcriber ready! Speak and pause to trigger.")
        logger.info(f"   VAD: {'Silero' if self.vad_model else 'Energy-based'}")
        logger.info(f"   Silence threshold: {SILENCE_DURATION}s")
        logger.info(f"   Min speech: {MIN_SPEECH_DURATION}s")
        logger.info("=" * 50)
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Stopping...")
            self.running = False
            self._publish_status("offline")
            self.mqtt_client.loop_stop()
            self.p.terminate()

if __name__ == "__main__":
    service = TranscriberService()
    service.start()
