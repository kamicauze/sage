# Sage (The Symbiote)

**Sage** is an AI-powered ecosystem designed to be a "Living System".
It consists of a **Runtime Brain** (IoT/Sensors) and a **Self-Healing Architect** (Dev Studio).

> **✨ Recent Update**:
> - Architect optimized for **74% cost reduction** and **3-10x faster builds**
> - **PWA Interface** with real-time MQTT integration for mobile/desktop control
> - **Optional STT/TTS** controls - warm up services but control when they're active

## 🚀 Quick Start

### PWA Control Center (Recommended)

Start everything with one command:

```bash
./sage pwa
```

This launches:
- 🔌 MQTT Broker (real-time messaging)
- 🧠 Brain Core (AI processing)
- 🌐 PWA UI (http://localhost:3000/brain)

**Features:**
- Real-time brain monitoring
- STT/TTS toggle controls
- Live chat interface
- Mobile-friendly (install as app)
- Works on phone via Tailscale/WiFi

### Voice → Zigbee Switches (Minimal Loop)

To test STT/TTS end to end without the LLM brain, run only the microphone,
a rule-based switch controller, and the speaker:

```bash
./sage switches --discover      # list Zigbee2MQTT devices, fill devices/switches.json
./sage switches --check         # verify broker + Zigbee2MQTT + panel + switches.json
./sage switches                 # mic → STT → Zigbee panel → TTS confirmation
./sage switches --sim           # same, with a simulated panel (no hardware)
./sage switches --say "lamp on" # inject text instead of speaking
```

See [docs/VOICE_SWITCH_BASICS.md](docs/VOICE_SWITCH_BASICS.md).

### Distributed Hardware Setup (Pi 5 + Orin + RTX)

If you are splitting runtime by device:

- Pi 5 (MQTT broker + Zigbee2MQTT + switch controller): `bash apps/brain-runtime/deploy/start_pi5_controller.sh`
- RTX 4070 Ti 12GB (voice STT/TTS on CUDA): `bash apps/brain-runtime/deploy/start_4070_voice.sh`
- RTX 4070 Ti 12GB (brain + vision, optional alongside voice): `bash apps/brain-runtime/deploy/start_4070_core.sh`
- Jetson Orin Nano 8GB (edge STT/TTS fallback): `bash apps/brain-runtime/deploy/start_orin_voice.sh`

Deployment guide and env templates are in `apps/brain-runtime/deploy/`.

If you want to test modules locally on your 4070 before pushing to edge:

- `bash apps/brain-runtime/deploy/start_4070_lab.sh brain|stt|tts|vision|voice|core|pwa`

### Architect (Code Generation)

```bash
# 1. Check Status (Budget, Memory)
./sage status

# 2. Ingest your codebase (Build Memory)
./sage init

# 3. Plan a Feature (The Architect)
./sage plan "Add a pattern to detect when I am sleeping"
# -> Output: architect/workspaces/sage_brain/plan.md

# Interactive mode (with approval gates and diffs)
./sage plan -i "refactor authentication system"

# 4. Build & Self-Heal
./sage build
# -> Generates code, runs tests, fixes bugs automatically.

# Interactive mode (review each file change)
./sage build -i
```

**Performance**:
- Simple queries: 800ms (2.25x faster with lazy loading)
- Rebuilds: 10s instead of 100s (10x faster with incremental cache)
- Multi-file builds: 17s instead of 50s (3x faster with parallel generation)

## 🧠 The Architecture

See [docs/symbiote.md](docs/symbiote.md) for the full technical breakdown.

-   **Multi-Model**: Uses **Gemma 3** (Local), **Gemini** (Planning), **Claude** (Code), and **Grok** (Chat).
-   **Deterministic Routing**: Automatically picks the cheapest/smartest model for the task (score-based).
-   **Budget Control**: Hard-capped at **$20/mo** (optimized from $28 → $7.20 actual spend).
-   **Smart Features**:
    - 🎯 **Surgical Edits**: Only changes what's needed (30-70% token reduction)
    - 📦 **Incremental Builds**: SHA256-based caching (90% faster rebuilds)
    - 🚀 **Parallel Generation**: 3 concurrent workers (3x speedup)
    - 🔍 **Lazy Loading**: Skip RAG for simple tasks (2.25x faster)
    - 👁️ **Interactive Diffs**: Visual code review before writing

## 📂 Structure

-   `apps/brain-runtime/`: Runtime Brain code (Body).
-   `apps/architect-studio/`: Architect code (Builder/API/UI).
-   `packages/shared/`: Shared libraries used by Brain + Architect.
-   `artifacts/`: Large local artifacts (voice checkpoints/models/datasets), excluded from code indexing.
-   `generated/`: Generated workspaces/sandboxes (exclude from indexing).
-   `docs/`: Technical Documentation.
-   `sage`: The CLI Entrypoint.

Legacy root paths (`brain/`, `architect/`, `shared/`) are retained as compatibility symlinks.

## 📚 Documentation

- **[Optimization Journey](docs/ARCHITECT_OPTIMIZATION_JOURNEY.md)**: Detailed walkthrough of cost & performance optimizations (74% cost reduction, 3-10x speedup)
- **[Quick Start Guide](docs/ARCHITECT_QUICKSTART.md)**: CLI commands, configuration modes, best practices
- **[System Architecture](docs/symbiote.md)**: Full technical breakdown of Sage's multi-layer design

## 🎯 Key Features

### Architect (Dev Studio)
- **Self-Healing**: Automatically fixes test failures (3x retry loop)
- **Budget-Aware**: Hard limits prevent runaway costs ($20/mo default)
- **Context-Aware**: RAG-powered code generation with cognitive zones
- **Interactive**: Visual diffs and approval gates for safety
- **Optimized**: Surgical edits, caching, lazy loading, parallel execution

### Brain (Runtime)
- **IoT Integration**: MQTT sensors for environmental awareness
- **Pattern Recognition**: Behavioral pattern detection (sleep, work, gaming)
- **Privacy-First**: 3-layer architecture (facts → local AI → cloud personality)
- **Voice Interface**: Kenyan English + Sheng code-switching support (planned)

## 💰 Cost Comparison

| System | Monthly Cost | Build Speed | User Control |
|--------|--------------|-------------|--------------|
| Claude Code | $450 | Baseline | Low |
| Cursor | $60 | Fast | Medium |
| **Sage** | **$7.20** | **3-10x faster** | **High** |

**ROI**: Implementation cost ($1.41) pays for itself in 2 hours.

## License
Private.
