"""
Switch Controller: the smallest possible "brain" for voice-controlled switches.

    sage/voice/transcript  (from STT)  -->  parse  -->  zigbee2mqtt/<panel>/set  {"state_l1": "ON"}
                                                   -->  sage/voice/response      (spoken confirmation for TTS)
    zigbee2mqtt/<panel>    (state)     -->  remembered, so "is the fan on" and toggle work

Run modes:
    python -m brain.devices.switch_controller                   # live: listen on MQTT
    python -m brain.devices.switch_controller --text "lamp on"  # dry run: parse only, no MQTT
    python -m brain.devices.switch_controller --say "lamp on"   # inject a transcript over MQTT (no mic needed)
    python -m brain.devices.switch_controller --discover        # list Zigbee2MQTT devices + their switch keys

Environment:
    MQTT_HOST / MQTT_PORT      broker (default localhost:1883)
    SAGE_SWITCHES_FILE         registry path (default devices/switches.json)
    Z2M_BASE_TOPIC             Zigbee2MQTT base topic (default from switches.json, else "zigbee2mqtt")
    SWITCH_WAKE_WORD           if set, only transcripts starting with it are acted on (e.g. "sage")
    SWITCH_REPLY_UNKNOWN       "true" to speak "No switch command" when nothing matched (default false)
    SWITCH_TTS                 "false" to skip publishing spoken replies (default true)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

# Make `brain.*` importable whether we run as a module or as a script.
_probe = Path(__file__).resolve().parent
for _parent in [_probe, *_probe.parents]:
    if (_parent / "sage.py").exists():
        if str(_parent) not in sys.path:
            sys.path.insert(0, str(_parent))
        break

try:
    from .switch_commands import (
        SwitchCommand,
        SwitchRegistry,
        parse_switch_command,
        spoken_reply,
        strip_wake_word,
    )
except ImportError:  # run as a plain script
    from brain.devices.switch_commands import (  # type: ignore
        SwitchCommand,
        SwitchRegistry,
        parse_switch_command,
        spoken_reply,
        strip_wake_word,
    )

def make_logger(name: str) -> logging.Logger:
    """Per-service logger with its own prefix (basicConfig would let the first importer win)."""
    log = logging.getLogger(name)
    if not log.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(f"[{name}] %(asctime)s - %(levelname)s - %(message)s"))
        log.addHandler(handler)
        log.setLevel(logging.INFO)
        log.propagate = False
    return log


logger = make_logger("SwitchCtl")

TRANSCRIPT_TOPIC = "sage/voice/transcript"
RESPONSE_TOPIC = "sage/voice/response"
EVENT_TOPIC = "sage/switch/events"


def mqtt_client():
    """paho-mqtt 1.x and 2.x compatible client constructor."""
    import paho.mqtt.client as mqtt

    try:
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)  # paho >= 2.0
    except AttributeError:
        return mqtt.Client()  # paho 1.x


def _truthy(value: Optional[str], default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class SwitchController:
    """
    MQTT-agnostic core so it can be unit tested with a fake client.
    The client only needs .publish(topic, payload, retain=False) and, for live use,
    .subscribe(topic) / .on_message.
    """

    def __init__(
        self,
        registry: SwitchRegistry,
        client=None,
        wake_word: str = "",
        reply_unknown: bool = False,
        speak: bool = True,
    ):
        self.registry = registry
        self.client = client
        self.wake_word = wake_word
        self.reply_unknown = reply_unknown
        self.speak = speak
        self.states: Dict[str, str] = {}      # switch id -> "on" | "off" (last reported by the device)
        self.last_command: Optional[SwitchCommand] = None

    # ---- transcript handling ----------------------------------------------------

    @staticmethod
    def extract_text(payload) -> str:
        """STT publishes plain text; other producers may send {"text": ...}."""
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8", errors="ignore")
        payload = str(payload or "").strip()
        if payload.startswith("{"):
            try:
                data = json.loads(payload)
                return str(data.get("text") or data.get("transcript") or "").strip()
            except json.JSONDecodeError:
                return payload
        return payload

    def handle_transcript(self, text: str) -> Optional[SwitchCommand]:
        started = time.time()
        text = (text or "").strip()
        if not text:
            return None
        logger.info(f"🎤 heard: '{text}'")

        if self.wake_word:
            stripped = strip_wake_word(text, self.wake_word)
            if stripped is None:
                logger.info(f"   ignored (no wake word '{self.wake_word}')")
                return None
            text = stripped

        cmd = parse_switch_command(text, self.registry)
        if cmd is None:
            logger.info("   no switch command")
            self._publish_event({"event": "no_match", "text": text})
            if self.reply_unknown:
                self._say("I did not catch a switch command.")
            return None

        self.last_command = cmd
        self.execute(cmd)
        logger.info(f"   {cmd.describe()} ({int((time.time() - started) * 1000)}ms)")
        return cmd

    # ---- execution --------------------------------------------------------------

    def execute(self, cmd: SwitchCommand):
        if cmd.action == "status":
            self._say(spoken_reply(cmd, self.states))
            self._publish_event({"event": "status", "text": cmd.text, "switches": [s.id for s in cmd.switches]})
            return

        applied = []
        merged: Dict[str, Dict[str, str]] = {}   # zigbee2mqtt topic -> {state_key: value}
        for switch in cmd.switches:
            desired = cmd.action
            if desired == "toggle" and not switch.payload_toggle:
                # Device has no native toggle: compute from last known state.
                desired = "off" if self.states.get(switch.id) == "on" else "on"
            applied.append({"id": switch.id, "state": desired})
            if switch.is_zigbee and switch.payload_on.startswith("{"):
                # Gangs on the same panel go out as one JSON message: {"state_l1": "OFF", "state_l2": "OFF"}.
                merged.setdefault(switch.command_topic, {})[switch.state_key] = desired.upper()
            else:
                self._publish(switch.command_topic, switch.payload_for(desired))
        for topic, payload in merged.items():
            self._publish(topic, json.dumps(payload))

        self._publish_event({"event": "command", "text": cmd.text, "action": cmd.action, "applied": applied})
        self._say(spoken_reply(cmd, self.states))

    def record_state(self, topic: str, payload) -> Dict[str, str]:
        """Update known states from a message on any registered state topic. Returns {id: state} changes."""
        changes: Dict[str, str] = {}
        for switch in self.registry.by_state_topic(topic):
            state = switch.parse_state(payload)
            if state is not None:
                self.states[switch.id] = state
                changes[switch.id] = state
        return changes

    def request_states(self):
        """Ask Zigbee2MQTT devices to report their current state (they answer on the state topic)."""
        seen = set()
        for switch in self.registry:
            if not switch.is_zigbee or switch.get_topic in seen:
                continue
            seen.add(switch.get_topic)
            keys = [s.state_key for s in self.registry if s.get_topic == switch.get_topic]
            self._publish(switch.get_topic, json.dumps({k: "" for k in keys}))

    # ---- publishing -------------------------------------------------------------

    def _publish(self, topic: str, payload: str, retain: bool = False):
        logger.info(f"   → {topic} {payload}")
        if self.client is not None:
            self.client.publish(topic, payload, retain=retain)

    def _publish_event(self, event: Dict):
        event = {"ts": int(time.time() * 1000), **event}
        if self.client is not None:
            self.client.publish(EVENT_TOPIC, json.dumps(event))

    def _say(self, text: str):
        logger.info(f"   🔊 '{text}'")
        if not self.speak or self.client is None:
            return
        self.client.publish(RESPONSE_TOPIC, json.dumps({"text": text, "type": "success", "source": "switch_controller"}))

    # ---- live MQTT --------------------------------------------------------------

    def run(self, host: str, port: int):
        client = mqtt_client()  # paho imported lazily so tests do not need it
        self.client = client

        def on_connect(c, userdata, flags, rc, *_props):
            logger.info(f"Connected to MQTT broker at {host}:{port} (rc={rc})")
            c.subscribe(TRANSCRIPT_TOPIC)
            for topic in self.registry.state_topics():
                c.subscribe(topic)
            self._publish_event({"event": "online", "switches": [s.id for s in self.registry]})
            self.request_states()

        def on_message(c, userdata, msg):
            try:
                if msg.topic == TRANSCRIPT_TOPIC:
                    self.handle_transcript(self.extract_text(msg.payload))
                else:
                    changes = self.record_state(msg.topic, msg.payload)
                    for sid, state in changes.items():
                        logger.info(f"   state: {sid} = {state}")
            except Exception as exc:  # never let one bad message kill the loop
                logger.error(f"Error handling {msg.topic}: {exc}")

        client.on_connect = on_connect
        client.on_message = on_message
        client.connect(host, port, 60)

        logger.info("=" * 50)
        logger.info("🔀 Switch controller ready")
        for s in self.registry:
            logger.info(f"   {s.name:<14} {s.command_topic}  {s.payload_for('on')}")
        logger.info(f"   wake word: {self.wake_word or '(none)'}")
        logger.info("   say e.g. 'turn on the lamp', 'lights off', 'is the fan on'")
        logger.info("=" * 50)
        try:
            client.loop_forever()
        except KeyboardInterrupt:
            logger.info("Stopping...")
            self._publish_event({"event": "offline"})
            client.disconnect()


def summarize_z2m_devices(devices: List[Dict]) -> List[Dict]:
    """Reduce the zigbee2mqtt/bridge/devices payload to what switches.json needs."""
    out = []
    for dev in devices or []:
        if dev.get("type") == "Coordinator":
            continue
        definition = dev.get("definition") or {}
        keys = []

        def walk(exposes):
            for e in exposes or []:
                if e.get("type") == "switch":
                    for f in e.get("features", []):
                        if f.get("property"):
                            keys.append(f["property"])
                elif e.get("property") and e.get("type") == "binary" and str(e.get("property")).startswith("state"):
                    keys.append(e["property"])
                if e.get("features") and e.get("type") != "switch":
                    walk(e["features"])

        walk(definition.get("exposes"))
        out.append({
            "friendly_name": dev.get("friendly_name"),
            "model": definition.get("model") or dev.get("model_id"),
            "description": definition.get("description", ""),
            "switch_keys": sorted(set(keys)),
        })
    return out


def discover(host: str, port: int, base: str, timeout: float = 5.0) -> int:
    topic = f"{base}/bridge/devices"
    found: Dict[str, List] = {}

    def on_message(c, userdata, msg):
        try:
            found["devices"] = json.loads(msg.payload.decode())
        except Exception as exc:
            logger.error(f"Could not parse {topic}: {exc}")

    client = mqtt_client()
    client.on_message = on_message
    client.connect(host, port, 60)
    client.subscribe(topic)
    client.loop_start()
    deadline = time.time() + timeout
    while "devices" not in found and time.time() < deadline:
        time.sleep(0.1)
    client.loop_stop()
    client.disconnect()

    if "devices" not in found:
        print(f"No devices list on {topic} within {timeout}s. Is Zigbee2MQTT running against this broker?")
        return 1

    rows = summarize_z2m_devices(found["devices"])
    if not rows:
        print("Zigbee2MQTT is up but has no paired devices. Enable 'permit join' and pair the panel.")
        return 1
    print(f"Zigbee2MQTT devices on {host}:{port} ({base}/...):\n")
    for row in rows:
        keys = ", ".join(row["switch_keys"]) or "(no switch exposes)"
        print(f"  {row['friendly_name']:<28} {row['model'] or '?':<18} keys: {keys}")
        if row["description"]:
            print(f"  {'':<28} {row['description']}")
    print("\nPut friendly_name into 'zigbee_name' and a key into 'state_key' in devices/switches.json.")
    return 0


def build_from_env(registry: Optional[SwitchRegistry] = None, client=None) -> SwitchController:
    registry = registry or SwitchRegistry.load()
    return SwitchController(
        registry,
        client=client,
        wake_word=os.getenv("SWITCH_WAKE_WORD", "").strip(),
        reply_unknown=_truthy(os.getenv("SWITCH_REPLY_UNKNOWN"), False),
        speak=_truthy(os.getenv("SWITCH_TTS"), True),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Sage voice switch controller")
    parser.add_argument("--text", help="Dry run: parse this text and print what would happen (no MQTT)")
    parser.add_argument("--say", help="Publish this text to sage/voice/transcript and exit (needs MQTT)")
    parser.add_argument("--discover", action="store_true", help="List Zigbee2MQTT devices and their switch keys")
    parser.add_argument("--host", default=os.getenv("MQTT_HOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", "1883")))
    parser.add_argument("--switches", help="Path to switches.json", default=None)
    args = parser.parse_args(argv)

    try:
        from dotenv import load_dotenv  # optional
        load_dotenv()
    except Exception:
        pass

    registry = SwitchRegistry.load(args.switches)

    if args.discover:
        return discover(args.host, args.port, registry.z2m_base)

    if args.text is not None:
        ctl = build_from_env(registry, client=None)
        cmd = ctl.handle_transcript(args.text)
        return 0 if cmd else 1

    if args.say is not None:
        client = mqtt_client()
        client.connect(args.host, args.port, 60)
        client.loop_start()
        info = client.publish(TRANSCRIPT_TOPIC, args.say)
        info.wait_for_publish()
        client.loop_stop()
        client.disconnect()
        print(f"published to {TRANSCRIPT_TOPIC}: '{args.say}'")
        return 0

    ctl = build_from_env(registry)
    ctl.run(args.host, args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
