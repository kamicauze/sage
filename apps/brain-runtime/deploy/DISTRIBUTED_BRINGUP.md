# Distributed Bring-Up (Mac mini 24GB + Pi + Jetson + RTX 4070)

This profile assumes:
- Mac mini LAN IP: `192.168.1.81`
- Mac mini is always-on brain/router.
- RTX 4070 runs STT + TTS.
- Pi runs sensor broker/controller.
- Jetson runs perception.

## 1) Raspberry Pi: broker + sensors

```bash
cd /home/pi/sage
bash apps/brain-runtime/deploy/start_pi5_controller.sh apps/brain-runtime/deploy/env/pi5-controller.env
```

## 2) Mac mini: start MLX server

```bash
cd /Users/kamicauze/sage
source .venv/bin/activate
python -m mlx_lm.server \
  --model mlx-community/Qwen2.5-14B-Instruct-4bit \
  --host 127.0.0.1 \
  --port 8080
```

Keep this terminal open.

## 3) Mac mini: start always-on core (brain/api/ui, no local STT/TTS)

Open a second terminal:

```bash
cd /Users/kamicauze/sage
bash apps/brain-runtime/deploy/start_macmini_core.sh apps/brain-runtime/deploy/env/mac-mini-core.env
```

## 4) RTX 4070 Linux: start voice worker (STT + TTS)

```bash
cd /home/<user>/sage
SAGE_ENV_FILE=apps/brain-runtime/deploy/env/rtx4070-voice.env \
bash apps/brain-runtime/deploy/start_4070_lab.sh voice
```

## 5) Jetson: start perception worker

```bash
cd /home/<user>/sage
SAGE_ENV_FILE=apps/brain-runtime/deploy/env/jetson-vision.env \
bash apps/brain-runtime/deploy/start_4070_lab.sh vision
```

## 6) Verify topics / health

- STT publishes: `sage/voice/transcript`
- Brain replies: `sage/voice/response`
- TTS status: `sage/tts/status`
- STT status: `sage/stt/status`

UI:
- `http://192.168.1.81:3000/brain`
