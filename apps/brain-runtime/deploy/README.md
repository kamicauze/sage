# Distributed Runtime Deployment

This setup splits Sage runtime workloads across three devices:

1. Raspberry Pi 5: MQTT broker + sensor input controller.
2. Jetson Orin Nano 8GB: STT + TTS voice services.
3. RTX 4070 Ti 12GB host: Brain runtime + vision service.

## 0) Local Validation On 4070 (Before Edge Deploy)

Use this first to validate each module independently on one machine.

```bash
cp apps/brain-runtime/deploy/env/local-4070-test.env.example apps/brain-runtime/deploy/env/local-4070-test.env
```

Run modules one-by-one:

- Brain only: `bash apps/brain-runtime/deploy/start_4070_lab.sh brain`
- STT only: `bash apps/brain-runtime/deploy/start_4070_lab.sh stt`
- TTS only: `bash apps/brain-runtime/deploy/start_4070_lab.sh tts`
- Vision only: `bash apps/brain-runtime/deploy/start_4070_lab.sh vision`
- Voice pair (STT+TTS): `bash apps/brain-runtime/deploy/start_4070_lab.sh voice`
- Brain + Vision: `bash apps/brain-runtime/deploy/start_4070_lab.sh core`
- Full phone-ready PWA: `bash apps/brain-runtime/deploy/start_4070_lab.sh pwa`

For phone access in PWA mode, open:

- `http://<your-4070-host-ip>:3000/brain`

Then install to home screen from Safari/Chrome.

## Topic Contract

Use these canonical MQTT topics so every node stays compatible:

- Sensors to Brain: `sage/sensors/<room>/presence`
- Voice transcript to Brain: `sage/voice/transcript`
- Brain response to TTS: `sage/voice/response`

The vision service now publishes both:

- `sage/presence/<location>` (legacy)
- `sage/sensors/<location>/presence` (canonical)

## 1) Pi 5 Controller

```bash
cp apps/brain-runtime/deploy/env/pi5-controller.env.example apps/brain-runtime/deploy/env/pi5-controller.env
bash apps/brain-runtime/deploy/start_pi5_controller.sh
```

If your sensor stack is separate, set `SAGE_SENSOR_CMD` in the env file so it runs under the same supervisor.

## 2) Orin Voice Node

```bash
cp apps/brain-runtime/deploy/env/orin-voice.env.example apps/brain-runtime/deploy/env/orin-voice.env
# Update MQTT_HOST to the Pi 5 IP
bash apps/brain-runtime/deploy/start_orin_voice.sh
```

Default profile is VRAM-safe for 8GB:

- STT: `small` + `int8_float16`
- TTS: `kokoro`
- TTS prewarm disabled + aggressive idle unload

## 3) RTX Core + Vision Node

```bash
cp apps/brain-runtime/deploy/env/rtx4070-core.env.example apps/brain-runtime/deploy/env/rtx4070-core.env
# Update MQTT_HOST to the Pi 5 IP
bash apps/brain-runtime/deploy/start_4070_core.sh
```

Default profile is tuned for continuous runtime on 12GB:

- Vision: `yolov8n`
- VLM interval: 75s
- Brain and vision share broker via Pi 5

## Optional Layout Variants

- Keep brain + vision on 4070 and move only STT to Orin.
- Keep TTS on Orin (low-latency local audio), leave heavy VLM on 4070.
- If Orin hits memory pressure, keep `TTS_ENGINE=kokoro` and avoid Qwen.
