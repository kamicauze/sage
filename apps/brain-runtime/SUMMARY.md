# 🧠 Brain Service Summary

## Overview

The Brain service is the central intelligence hub of the Sage IoT ecosystem, implementing a **Three-Layer Architecture** designed for privacy-protected, mood-aware AI interactions. It processes raw sensor data through a deterministic engine, infers mood via local LLMs, and delivers personality-driven responses through a cloud fallback system.

## 🏗️ Three-Layer Architecture

1.  **Layer 1: Deterministic Engine** (`core/`)
    - **Purpose**: Transforms raw sensor data into "defendable facts".
    - **Logic**: Rule-based patterns (17 implemented) with explicit thresholds.
    - **Metrics**: Tracks 27 distinct measurements (stillness, pitch, etc.).
    - **Privacy**: Ensures raw vision/audio data never leaves this layer.

2.  **Layer 2: Local AI (Inference)** (`ai/`)
    - **Purpose**: Interprets deterministic facts to infer emotional state (Mood).
    - **Compression**: Reduces complex history into a tiny, privacy-safe brief for the cloud.
    - **Tech**: Powered by **Ollama** (Gemma 3 / Llama 3).

3.  **Layer 3: Persona (Cloud/Fallback)** (`ai/`)
    - **Purpose**: Delivers the final interaction using specific personalities (e.g., "Kenyan babe").
    - **Fallback**: Automatically switches to the Local LLM if the cloud (Grok) is unreachable.

## 📂 File Structure (Python Implementation)

```
brain/
├── main.py                 # Service entry point & MQTT orchestrator
├── requirements.txt         # Python dependencies (paho-mqtt, aiohttp)
├── .env                    # Environment configuration
│
├── core/                   # Layer 1: Deterministic Summary Engine
│   ├── summary_engine.py   # Pattern detection & fact summarization
│   ├── state_machine.py    # Home & room status management
│   ├── escalation.py       # "Pushiness" logic for reminders
│   └── event_buffer.py     # Circular history for pattern matching
│
├── ai/                     # Layers 2 & 3: AI Inference & Personas
│   ├── advisor.py          # Logic for coordinating local/cloud LLMs
│   ├── cloud_client.py     # Grok/API integration
│   ├── ollama_client.py    # Local LLM integration
│   ├── personalities.py    # Tone & character definitions (Kenyan babe)
│   └── warmup.py           # Pre-flight model checks
│
├── perception/             # Input Processing
│   └── parser.py           # Parses raw MQTT presence messages
│
└── action/                 # Output Routing
    └── router.py           # Routes AI suggestions to final output
```

## 🚀 Key Patterns & Intents

The system detects critical situations using rule-based logic in `summary_engine.py`:
- **Critical**: `OVERWORK_LATE`, `SLEEP_DEPRIVATION`, `FATIGUE_COMPOSITE`.
- **High/Med**: `BREAK_OVERDUE`, `SCREEN_HYPERFOCUS`, `SEDENTARY_PATTERN`.
- **Special**: `MEETING_IN_PROGRESS` (Do Not Disturb).

## 📡 Data Flow

1.  **MQTT Event**: Sensors publish to `sage/sensors/+/presence`.
2.  **Deterministic Pass**: `SummaryEngine` identifies active patterns and builds a 1-paragraph brief.
3.  **Mood Inference**: `Advisor` uses Local LLM to detect user mood (e.g., "exhausted 9/10").
4.  **Persona Pass**: `CloudClient` or Local LLM generates a personality-aware response.
5.  **Action Router**: Output is filtered (e.g., quiet hours) and delivered.

## ⚙️ Configuration

- **Environment**: Managed via `.env` (MQTT hosts, AI model aliases).
- **Docker**: Runs as a Python 3.11 container (see `docker-compose.yml`).
- **Dependencies**: `paho-mqtt` for bus comms, `aiohttp` for async AI calls.







