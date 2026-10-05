# Sage Distributed Cluster Architecture

> **Current roles:** see [NODE_LAYOUT.md](NODE_LAYOUT.md). Changes from the plan below:
> the Pi 5 runs Zigbee2MQTT with the Zigbee dongle, and vision moved from the 4070 to the
> Jetson Orin so the 4070's GPU is free for speech. The Mini stays the hub.

## Nodes

### Mac Mini M4 Pro (24GB unified) — "The Brain"
Always-on primary coordinator. Runs the LLM, decision-making, and orchestration.

| Service | Details |
|---------|---------|
| MQTT Broker | Mosquitto — central hub, all nodes connect here |
| LLM | MLX serving Gemma 3 12B Q4 (~7GB) on port 8080 |
| Brain Core | Intent classification, routing, conversation history |
| Voice Handler | Receives STT transcripts via MQTT, dispatches to Brain/Architect/Agents |
| Kokoro TTS | ONNX-based, ~400-600ms on ARM, for fast first-response |
| Architect | Code planning/building via local MLX model + cloud fallback |
| Agent Framework | All agent configs, registry, bridge, lifecycle management |
| Cloud Client | Grok/OpenAI/Anthropic for heavy reasoning tasks |

**Memory budget**: ~7GB LLM + ~1GB Kokoro + ~2GB services + ~14GB headroom

### 4070 Ti Linux Box (12GB VRAM) — "The Senses"
GPU-heavy inference. Handles real-time audio and vision where CUDA matters.

| Service | Details |
|---------|---------|
| STT | faster-whisper + Silero VAD on CUDA (~119ms) |
| Qwen3-TTS | Fine-tuned Sheng voice (~2.4s, CUDA) |
| Vision Pipeline | InsightFace + YOLO + Moondream VLM |
| Training | Whisper LoRA, Qwen TTS LoRA, embedding model training |

**VRAM budget**: ~3GB STT + ~2.5GB Qwen TTS + ~3GB Vision = ~8.5GB active, 3.5GB headroom

### Jetson Orin Nano (8GB + 1TB SSD) — "The Subconscious"
Background processing, edge fallback, persistent storage.

| Service | Details |
|---------|---------|
| Summarizer | 3-4B model for context compression (sage/memory/summarize) |
| Edge STT | Whisper small INT8 — fallback if Linux box is busy/offline |
| Edge Kokoro TTS | For Jetson-local rooms |
| Storage | Agent logs, research artifacts, training data archive on 1TB SSD |

**VRAM budget**: ~2GB summarizer + ~0.7GB STT + ~1GB Kokoro = ~3.7GB, 4.3GB headroom

### Raspberry Pi 5 — "The Sensors"
Lightweight sensor hub per room. No ML inference.

| Service | Details |
|---------|---------|
| Microphone | Captures audio, publishes raw to sage/audio/{room} |
| Camera | Captures frames, publishes to sage/vision/{room}/frame |
| BT Speaker | Paired Bluetooth speaker for TTS audio playback |
| Presence | IR/motion sensor → sage/presence/{room} |
| GPIO | Physical controls (buttons, LEDs, relays) |

---

## Network

All nodes on same LAN. MQTT broker on Mac Mini is the single coordination point.

```
Pi 5 (room sensors)
  │
  ├── ethernet/wifi ──→ Mac Mini (MQTT broker + Brain)
  │                        ├── ethernet ──→ 4070 Ti (STT + TTS + Vision)
  │                        └── ethernet ──→ Jetson (Summarizer + Storage)
  │
  └── bluetooth ──→ Room Speaker
```

**Latency targets**:
- LAN round-trip: <1ms (ethernet), <3ms (wifi)
- MQTT publish/subscribe overhead: ~1-2ms
- Total cross-machine penalty: ~3-6ms (negligible vs inference time)

### Remote Access
Tailscale VPN for accessing Sage from mobile/laptop outside the home network.
Mac Mini runs the Tailscale node — all MQTT traffic tunnels through it.

---

## MQTT Topic Map

### Voice Pipeline
```
sage/audio/{room}              Pi → 4070 Ti      Raw audio chunks
sage/stt/transcript            4070 Ti → Mac      Transcribed text
sage/voice/response            Mac → 4070 Ti      Text to speak
sage/tts/audio/{room}          4070 Ti → Pi       Audio chunks for playback
sage/tts/speaking              4070 Ti → Mac      Echo suppression signal
sage/tts/status                4070 Ti → Mac      TTS engine status
sage/stt/status                4070 Ti → Mac      STT engine status
sage/stt/metrics               4070 Ti → Mac      STT latency metrics
```

### Brain
```
sage/brain/chat/request        Mac internal       Chat request
sage/brain/chat/response       Mac internal       Chat response (+ TTS trigger)
```

### Agents
```
sage/agent/{name}/status       Mac → all          Agent status updates
sage/agent/{name}/needs_approval  Mac → 4070 Ti   Agent asks user via voice
sage/agent/{name}/approval_response  4070 Ti → Mac  User's voice response
sage/agent/{name}/command      Mac internal       Agent lifecycle commands
```

### Memory / Subconscious
```
sage/memory/summarize          Mac → Jetson       Request context compression
sage/memory/summary/{task_id}  Jetson → Mac       Compressed summary response
```

### Vision
```
sage/vision/{room}/frame       Pi → 4070 Ti       Raw camera frames
sage/vision/{room}/state       4070 Ti → Mac       Scene description
sage/vision/{room}/face        4070 Ti → Mac       Face detection events
sage/vision/{room}/vlm         4070 Ti → Mac       VLM scene analysis
sage/vision/{room}/presence    4070 Ti → Mac       Person detected/left
```

### Presence & Home
```
sage/presence/{room}           Pi → Mac            Motion/IR presence
sage/home/command              Mac → SmartThings   Home automation commands
sage/home/state                SmartThings → Mac   Device state updates
```

### Health
```
sage/health/{node}/heartbeat   All → Mac           Periodic heartbeat
sage/health/{node}/metrics     All → Mac           CPU, RAM, VRAM, temp
```

---

## Setup Per Node

### Mac Mini (first — it's the hub)
```bash
# 1. System
brew install mosquitto python@3.11 git
brew services start mosquitto

# 2. Clone & venv
git clone git@github.com:kamicauze/sage.git ~/sage
cd ~/sage
python3.11 -m venv .venv
source .venv/bin/activate

# 3. MLX
pip install mlx mlx-lm
huggingface-cli download mlx-community/gemma-3-12b-it-4bit --local-dir ~/models/gemma-3-12b-4bit

# 4. Python deps (brain subset — no CUDA packages)
pip install paho-mqtt==1.6.1 requests python-dotenv aiohttp
pip install chromadb langchain langchain-community langchain-text-splitters sentence-transformers
pip install kokoro-onnx sounddevice soundfile numpy
pip install aiofiles watchdog aiomqtt pyyaml

# 5. Configure
cp apps/brain-runtime/deploy/env/rtx4070-core.env.example .env
# Edit .env — see "Mac Mini .env" section below

# 6. Mosquitto — allow remote connections
echo -e "\nlistener 1883 0.0.0.0\nallow_anonymous true" >> /opt/homebrew/etc/mosquitto/mosquitto.conf
brew services restart mosquitto

# 7. Start
mlx_lm.server --model ~/models/gemma-3-12b-4bit --port 8080 &
python sage.py start
```

### 4070 Ti Linux Box
```bash
# Update .env to point MQTT at Mac Mini
MQTT_HOST=<mac-mini-ip>
MQTT_PORT=1883

# Only run voice services
python sage.py voice
```

### Jetson Orin Nano
```bash
# Run setup script (already exists)
bash setup_jetson.sh <mac-mini-ip>

# Start voice + summarizer
python sage.py voice  # edge STT + TTS
# TODO: start summarizer service (sage/memory/summarize listener)
```

### Raspberry Pi 5
```bash
bash setup_pi.sh
# Update .env: MQTT_HOST=<mac-mini-ip>
# Start sensor services (mic capture, camera, presence)
```

---

## Mac Mini .env
```bash
# MQTT — this machine is the broker
MQTT_HOST=localhost
MQTT_PORT=1883

# LLM via MLX (OpenAI-compatible API)
OLLAMA_HOST=http://localhost:8080/v1
OLLAMA_MODEL_FAST=gemma-3-12b-4bit
OLLAMA_MODEL_MID=gemma-3-12b-4bit
OLLAMA_MODEL_DEEP=gemma-3-12b-4bit

# Cloud fallback
XAI_API_KEY=<your-grok-key>
OPENAI_API_KEY=<your-openai-key>

# TTS — Kokoro only (fast, no CUDA needed)
TTS_ENGINE=kokoro
TTS_PREWARM=false
SAGE_STREAM_TTS=true

# Intent
INTENT_USE_LLM=true

# Routing
FORCE_CLOUD_REASONING=false
```

## 4070 Ti .env
```bash
MQTT_HOST=<mac-mini-ip>
MQTT_PORT=1883

# STT
STT_DEVICE=cuda
STT_MODEL_SIZE=medium.en
STT_COMPUTE_TYPE=float16
STT_SILENCE_DURATION=0.5

# TTS — Qwen for Sheng personality
TTS_ENGINE=qwen
QWEN_TTS_MODEL=brain/voice/models/qwen3-tts-sheng-1.7b
```

## Jetson .env
```bash
MQTT_HOST=<mac-mini-ip>
MQTT_PORT=1883

STT_MODEL_SIZE=small
STT_DEVICE=cuda
STT_COMPUTE_TYPE=int8_float16

TTS_ENGINE=kokoro
TTS_PREWARM=false
TTS_IDLE_TIMEOUT=90
```

---

## MLX Integration Notes

`mlx_lm.server` serves an OpenAI-compatible API at `/v1/chat/completions`.
Sage's current code calls Ollama's `/api/chat` endpoint. Two options:

**Option A — Ollama on Mac** (zero code changes):
Ollama uses Metal/MLX under the hood on Apple Silicon. `ollama pull gemma3:12b` and everything works.

**Option B — Native MLX** (small adapter needed):
Create `mlx_client.py` mirroring `ollama_client.py` but targeting `/v1/chat/completions`.
Or add a provider switch in the existing ollama_client. More control over quantization and model loading.

### What must stay on CUDA (4070 Ti)
- faster-whisper (CTranslate2 backend)
- Qwen3-TTS inference
- InsightFace / YOLO vision
- All fine-tuning / LoRA training

### What runs on MLX (Mac Mini)
- Primary LLM (Gemma 3 12B Q4)
- Intent classification (Tier 1 rules + MLX Tier 3 fallback)
- Architect reasoning

### What runs on Jetson
- Summarizer (3-4B model for context compression)
- Edge STT fallback (Whisper small INT8)
- Edge Kokoro TTS

---

## TODO
- [ ] MLX client adapter (or confirm Ollama-on-Mac works for v1)
- [ ] Jetson summarizer service (listens on sage/memory/summarize)
- [ ] Pi sensor services (mic capture → MQTT, camera → MQTT)
- [ ] Room-aware speaker routing (presence → nearest BT speaker)
- [ ] Tailscale setup for remote access
- [ ] Health monitoring (heartbeat + metrics topics)
- [ ] Self-heal agent wiring to health topics
