# Voice → Zigbee switches: the minimal loop

Everything else in Sage (LLM brain, Architect, memory, personalities, vision) is
out of the picture here. This is the smallest path that proves the microphone,
STT, TTS and the Zigbee panel all work together:

```
 mic ──▶ STT (brain.voice.transcriber) ──▶ sage/voice/transcript
                                                   │
                                                   ▼
                                  switch controller (brain.devices.switch_controller)
                                   rule-based parser, <1ms, no LLM
                                                   │
                       ┌───────────────────────────┴───────────────────────┐
                       ▼                                                   ▼
   zigbee2mqtt/<panel>/set  {"state_l2": "ON"}                  sage/voice/response {"text": "Desk lamp on."}
                       │                                                   │
                       ▼                                                   ▼
        Zigbee2MQTT ──▶ Zigbee panel                     TTS (brain.voice.speaker) ──▶ speaker
                       │
                       ▼
   zigbee2mqtt/<panel>  {"state_l1":"OFF","state_l2":"ON",...}  ──▶ controller remembers state
                                                                     ("is the fan on?", toggle)
```

The STT and TTS services are the existing ones, untouched. The only new pieces are
in `apps/brain-runtime/devices/`:

| File | Role |
|------|------|
| `switches.json` | Which switches exist, what you call them, which Zigbee gang they are |
| `switch_commands.py` | Parser: text → `{action, switches}`. Pure Python, unit tested |
| `switch_controller.py` | MQTT service: transcript in, panel command + spoken reply out |
| `switch_node.py` | Optional simulator (or Pi GPIO relays) that stands in for the panel |

## 1. Tell Sage about your panel

The Zigbee panel must be paired with [Zigbee2MQTT](https://www.zigbee2mqtt.io/)
pointed at the same Mosquitto broker Sage uses (`MQTT_HOST`/`MQTT_PORT`). Then ask
Zigbee2MQTT what it has:

```bash
./sage switches --discover
#   office_panel     TS0013     keys: state_l1, state_l2, state_l3
```

Copy the friendly name and the gang keys into `apps/brain-runtime/devices/switches.json`:

```json
{
  "zigbee2mqtt_base": "zigbee2mqtt",
  "switches": [
    {"id": "panel_1", "name": "main light", "aliases": ["big light", "office light"],
     "group": "lights", "room": "office", "zigbee_name": "office_panel", "state_key": "state_l1"},
    {"id": "panel_2", "name": "desk lamp", "aliases": ["lamp"],
     "group": "lights", "room": "office", "zigbee_name": "office_panel", "state_key": "state_l2"},
    {"id": "panel_3", "name": "fan",
     "group": "fans", "room": "office", "zigbee_name": "office_panel", "state_key": "state_l3"}
  ]
}
```

- `aliases` are what you say. `name` is also an alias and is what Sage says back.
- `group` enables "lights off" / "all lights on"; `room` enables "office lights off".
- A single-gang device uses `"state_key": "state"` (the default).
- If Zigbee2MQTT uses a different base topic, set `zigbee2mqtt_base` or `Z2M_BASE_TOPIC`.
- Other MQTT switches (Tasmota, Shelly, …) work too: give `command_topic`,
  `state_topic`, `payload_on`, `payload_off` explicitly.

Then check the whole chain from the machine that talks to the broker (the Pi):

```bash
./sage switches --check
```

It verifies: `switches.json` loads, the broker is reachable, Zigbee2MQTT is online,
every `zigbee_name`/`state_key` in the registry exists on a paired device, lists
paired switches you have not registered yet, and asks each panel for its live
state. Fix the ❌ lines and rerun until it says PASS.

## 2. Test each stage on its own

**Parser only, no broker, no audio:**

```bash
python -m brain.devices.switch_controller --text "turn on the desk lamp"
#   → zigbee2mqtt/office_panel/set {"state_l2": "ON"}
#   🔊 'Desk lamp on.'
python -m unittest tests.test_switch_commands
```

**Panel only, typed commands, no mic:** start the loop without STT and inject text.

```bash
./sage switches --no-stt          # broker + controller + TTS; Zigbee2MQTT drives the panel
./sage switches --say "lamp on"   # from another terminal
```

You should hear "Desk lamp on." and see the physical switch flip. If it does not,
watch the wire: `mosquitto_sub -v -t 'zigbee2mqtt/#' -t 'sage/#'`.

**No panel at hand:** `--sim` runs a fake panel that prints `💡 desk lamp -> ON`
and reports state back exactly like Zigbee2MQTT does.

```bash
./sage switches --sim --no-stt --no-tts
./sage switches --say "office lights off"
```

**Full loop with the mic:**

```bash
./sage switches            # real panel
./sage switches --sim      # fake panel
```

Speak, pause, and watch the three logs: `[Transcriber] 📝 Transcribed`, then
`[SwitchCtl] → zigbee2mqtt/...`, then `[Speaker] Playing audio`.

### Measure STT and TTS

With the transcriber and speaker running (on the voice box, pointed at the broker):

```bash
./sage voicecheck status    # are both services up, which engine/model
./sage voicecheck tts       # speaks the confirmation phrases; time-to-first-audio and gen time each
./sage voicecheck stt       # prompts you to say each switch command; WER, latency, parser hit/miss
./sage voicecheck all --report voice_report.json
./sage voicecheck wav clip1.wav clip2.wav   # offline, same STT settings (clip1.txt = expected text)
```

The STT number that matters is "parser would act correctly on N/M": a mishearing
like "switch of the fan" has a non-zero word error rate but still flips the fan.
Consistent misses of a device name are fixed by adding the misheard form as an alias.
Keep TTS quiet during the STT test (the transcriber pauses itself while TTS speaks).

## 3. What you can say

| Say | Does |
|-----|------|
| "turn on the lamp", "switch off the fan", "put the big light on" | one switch |
| "lamp on", "fan off" | same, short form |
| "lights off", "all lights on", "office lights off" | a group, optionally by room |
| "switch off everything" | all switches |
| "turn off the fan and the lamp" | several switches |
| "toggle the fan" | native Zigbee2MQTT TOGGLE |
| "is the fan on", "are the lights on" | spoken status from the last reported state |

Ordinary speech that merely mentions a device or "on" ("I'm on my way to the
kitchen") is ignored. Nothing is spoken when no command matched, unless
`SWITCH_REPLY_UNKNOWN=true`. Set `SWITCH_WAKE_WORD=sage` to require "Sage, …".

STT slips like "turn of the lamp" and "lights of" are corrected before parsing.
If the transcriber mishears a device name consistently, add the misheard form as
an alias rather than fighting the model.

## 4. Split across the Pi and the 4070

The Pi holds the Zigbee dongle, Zigbee2MQTT and Mosquitto, so the switch controller
belongs there too (it only needs `paho-mqtt`). STT and TTS run on the 4070 Ti, where
CUDA gives faster-whisper medium.en ~100ms transcriptions and room for Qwen TTS.

```bash
# Pi 5: broker + Zigbee2MQTT (already running) + switch controller
./sage switches --check                                   # once, to verify the panel
bash apps/brain-runtime/deploy/start_pi5_controller.sh    # SAGE_SWITCH_CONTROLLER=1 by default

# 4070: mic + speaker, pointed at the Pi's broker
cp apps/brain-runtime/deploy/env/rtx4070-voice.env.example apps/brain-runtime/deploy/env/rtx4070-voice.env
# edit MQTT_HOST, then:
bash apps/brain-runtime/deploy/start_4070_voice.sh
./sage voicecheck all                                     # measure STT/TTS from the same box
```

The Orin script (`start_orin_voice.sh`) remains as a low-VRAM fallback profile.

Typed test from any machine on the LAN, no mic:
`MQTT_HOST=<pi-ip> ./sage switches --say "lamp on"`.

## 5. Where this fits later

The brain (`apps/brain-runtime/main.py`) also subscribes to `sage/voice/transcript`.
Do not run `./sage pwa` / `./sage start` at the same time as `./sage switches`, or
both will answer every utterance. Once the basic loop is solid, the same
`parse_switch_command()` can be called first inside the brain's `home_control`
path so switch commands never reach the LLM, and everything else still does.
