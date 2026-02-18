# Sage Brain Service

The Brain service is the central intelligence hub of the Sage IoT ecosystem. It implements a sophisticated **Three-Layer Architecture** to process sensor data, infer user mood, and provide personality-driven interactions while maintaining strict privacy.

## 🏗️ Architecture: The Three-Layer System

Sage operates on the principle of separating raw facts from emotional interpretation and final expression.

### Layer 1: Deterministic Summary Engine (`core/`)
The foundational layer that converts raw sensor measurements into defendable, rule-based facts.
- **Patterns**: Detects 17 specific behavioral patterns (e.g., `SCREEN_HYPERFOCUS`, `OVERWORK_LATE`).
- **Measurements**: Tracks 27 distinct data points across vision geometry, audio presence, and motion.
- **Privacy Anchor**: Raw vision/audio data is processed into metrics here and discarded. Only high-level summaries move up.

### Layer 2: Local AI Inference (`ai/`)
Incurs the "Soul" or reasoning part of the system.
- **Mood Detection**: Uses a local LLM (via Ollama) to infer the user's emotional state (e.g., "frustrated", "exhausted") based on Layer 1 patterns.
- **Context Compression**: Distills the entire home state and history into a small, privacy-safe text brief.

### Layer 3: Persona & Expressiveness (`ai/`)
The outer shell that interacts with the user.
- **Personality**: Currently implements the "Kenyan babe" persona (warm, caring, authentically Kenyan).
- **Hybrid Delivery**: Uses Cloud LLMs (Grok) for high-quality personality, falling back to Local LLMs automatically if offline.

---

## 📂 File Layout

```
brain/
├── main.py                 # Core orchestrator & MQTT client
├── core/                   # Layer 1: Deterministic logic
│   ├── summary_engine.py   # Pattern matching & metrics
│   ├── state_machine.py    # Home/Room occupancy state
│   └── escalation.py       # Priority & reminder logic
├── ai/                     # Layers 2 & 3: AI logic
│   ├── advisor.py          # Coordinator for LLM requests
│   ├── client_*.py         # Local/Cloud API clients
│   └── personalities.py    # Prompt definitions for personas
├── perception/             # Sensor input parsers
└── action/                 # Output & routing handlers
```

---

## 🛠️ Getting Started

### Prerequisites
- **MQTT Broker**: (Mosquitto)
- **Ollama**: Local AI server (configured with `gemma3` or `llama3.1`).
- **Python 3.11+**

### Running with Docker (Recommended)
The service is designed to run in a containerized environment alongside its infrastructure.
```bash
docker-compose up -d
```

### Running Standalone
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Set up environment:
   Create a `.env` file with your MQTT and Ollama configurations.
3. Start the service:
   ```bash
   python main.py
   ```

## 📡 MQTT Interface
- **Subscriptions**: `sage/sensors/+/presence`
- **Output**: Suggestions and action plans are routed through `action/router.py`.

## 📜 Principles
1. **Facts First**: Every interpretation must be traceable back to a timestamped sensor event.
2. **Privacy by Design**: No raw audio/video leaves the local network.
3. **Graceful Degradation**: The system remains functional (local personality) even without internet access.
