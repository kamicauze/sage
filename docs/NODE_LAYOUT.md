# Node layout: which machine does what

This is the current source of truth for roles. `docs/CLUSTER_ARCHITECTURE.md` is the
longer-term plan. Differences from that plan: the Pi runs Zigbee2MQTT, and vision moved
from the 4070 to the Orin so the 4070's GPU is free for speech.

| Machine | Role | Runs now | Runs later | Start | Check |
|---|---|---|---|---|---|
| Mac Mini M4 Pro | **hub** | Mosquitto broker, voice switch controller | LLM brain (Gemma), intent, memory, Architect | `start_mini_hub.sh` | `./sage nodecheck hub` |
| Raspberry Pi 5 | **home** | Zigbee2MQTT with the Zigbee dongle | Room sensors | Zigbee2MQTT's own service | `./sage nodecheck home` |
| RTX 4070 Ti | **voice** | Whisper STT, Kokoro TTS (mic + speaker plugged in here) | Qwen Sheng voice | `start_4070_voice.sh` | `./sage nodecheck voice` |
| Jetson Orin | **vision** | Camera, YOLO, faces, moondream VLM | | `start_orin_vision.sh` | `./sage nodecheck vision` |

Start scripts are in `apps/brain-runtime/deploy/`; each reads `deploy/env/<name>.env`
(copy the matching `.env.example`). Every node sets `MQTT_HOST` to the **Mac Mini's IP**.

```
            ┌──────────── Mac Mini (hub) ────────────┐
            │  Mosquitto :1883 (+ :9001 websockets)  │
            │  switch controller · later: LLM brain  │
            └───▲───────────▲───────────▲────────────┘
                │           │           │        all MQTT
   ┌────────────┴──┐  ┌─────┴───────┐  ┌┴──────────────┐
   │ Pi 5 (home)   │  │ 4070 (voice)│  │ Orin (vision) │
   │ Zigbee2MQTT ──┼─▶│ mic → STT   │  │ camera → YOLO │
   │ dongle ⇢ panel│  │ TTS → spkr  │  │ faces · VLM   │
   └───────────────┘  └─────────────┘  └───────────────┘
```

A voice command travels: 4070 mic → STT → `sage/voice/transcript` → Mini switch
controller → `zigbee2mqtt/<panel>/set` → Pi (Zigbee2MQTT) → panel. The spoken reply
goes Mini → `sage/voice/response` → 4070 speaker.

## Bring-up order

Each step only depends on the ones before it. After each, run that node's check and
fix its ❌ lines. From any machine, `./sage nodecheck --list` shows every node's last
result, read from the broker.

### 1. Mac Mini (hub)

```bash
brew install mosquitto            # don't `brew services start` it: its default config is localhost-only
git clone https://github.com/kamicauze/sage && cd sage && git checkout ngigi/bold-thompson-fveo7k
python3 -m venv .venv && source .venv/bin/activate && pip install 'paho-mqtt>=2' python-dotenv
cp apps/brain-runtime/deploy/env/mini-hub.env.example apps/brain-runtime/deploy/env/mini-hub.env
bash apps/brain-runtime/deploy/start_mini_hub.sh   # prints the IP every other node uses
./sage nodecheck hub                               # second terminal
```

The check confirms the broker is reachable on the LAN address, not just localhost.
That is the most common failure with Mosquitto 2.

### 2. Pi 5 (home)

Point Zigbee2MQTT at the Mini in its `configuration.yaml` (usually `/opt/zigbee2mqtt/data/`),
then restart it with `sudo systemctl restart zigbee2mqtt`:

```yaml
mqtt:
  server: mqtt://<mini-ip>:1883
```

```bash
export MQTT_HOST=<mini-ip>
./sage nodecheck home        # dongle, Zigbee2MQTT running, its broker setting, online at the Mini
./sage switches --check      # switches.json names and gang keys vs the real panel
```

If the Pi was running its own Mosquitto, the check warns. Disable it once Zigbee2MQTT
is pointed at the Mini: `sudo systemctl disable --now mosquitto`.

### 3. RTX 4070 Ti (voice)

```bash
cp apps/brain-runtime/deploy/env/rtx4070-voice.env.example apps/brain-runtime/deploy/env/rtx4070-voice.env
# set MQTT_HOST=<mini-ip>
./sage nodecheck voice                             # CUDA, Whisper, mic, speaker, Kokoro files
bash apps/brain-runtime/deploy/start_4070_voice.sh
./sage voicecheck all                              # second terminal: STT accuracy + TTS latency
```

The mic and speaker must be plugged into the 4070: the transcriber reads the local
microphone and the speaker plays locally. Streaming audio from room nodes is later work.

### 4. Jetson Orin (vision)

```bash
cat /etc/nv_tegra_release                          # JetPack / L4T version
git clone https://github.com/kamicauze/sage && cd sage && git checkout ngigi/bold-thompson-fveo7k
sudo apt install -y python3-venv python3-opencv v4l-utils
# Reuse JetPack's CUDA-enabled OpenCV and torch instead of pip's CPU builds:
python3 -m venv --system-site-packages .venv && source .venv/bin/activate
pip install -U 'paho-mqtt>=2' python-dotenv requests numpy
pip install ultralytics                            # after NVIDIA's torch for your JetPack is installed
curl -fsSL https://ollama.com/install.sh | sh && ollama pull moondream
v4l2-ctl --list-devices                            # which /dev/videoN is the camera
cp apps/brain-runtime/deploy/env/orin-vision.env.example apps/brain-runtime/deploy/env/orin-vision.env
# set MQTT_HOST=<mini-ip> and VISION_CAMERA
./sage nodecheck vision
VISION_NO_VLM=1 bash apps/brain-runtime/deploy/start_orin_vision.sh   # YOLO first, then drop NO_VLM
```

Two Orin traps the check catches:

- **CPU-only torch.** If `pip install ultralytics` pulls torch from PyPI, it is a
  CPU-only build. Install NVIDIA's Jetson torch wheel first.
- **paho-mqtt 1.x.** The vision service needs paho-mqtt 2. The root requirements
  file pins 1.6.1, so don't install from it on the Orin.

## Topics at a glance

| Topic | From | To |
|---|---|---|
| `sage/voice/transcript` | 4070 STT | Mini switch controller (later: brain) |
| `sage/voice/response` | Mini | 4070 TTS |
| `zigbee2mqtt/<panel>/set`, `zigbee2mqtt/<panel>` | Mini / Pi | Pi / Mini |
| `sage/vision/...` | Orin | Mini (later: brain context) |
| `sage/nodes/<host>/<role>` | every node (`nodecheck`) | `nodecheck --list` |
