"""
Switch Node: stands in for the real switches when you have no hardware attached.

With a real Zigbee panel you do NOT run this: Zigbee2MQTT is the node. Run it to
test the voice loop on a laptop (sim backend), or on a Pi driving relays (gpio backend).

It subscribes to every command topic in switches.json (zigbee2mqtt/<panel>/set or
sage/switch/<id>/set), applies the command, and reports state back on the switch's
state topic exactly the way the real device would ({"state_l1": "ON"} or plain ON).

    python -m brain.devices.switch_node                  # sim (prints)
    python -m brain.devices.switch_node --backend gpio   # on the Pi, pins from "gpio_pin"
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

_probe = Path(__file__).resolve().parent
for _parent in [_probe, *_probe.parents]:
    if (_parent / "sage.py").exists():
        if str(_parent) not in sys.path:
            sys.path.insert(0, str(_parent))
        break

try:
    from .switch_commands import Switch, SwitchRegistry, normalize_state
    from .switch_controller import make_logger, mqtt_client
except ImportError:
    from brain.devices.switch_commands import Switch, SwitchRegistry, normalize_state  # type: ignore
    from brain.devices.switch_controller import make_logger, mqtt_client  # type: ignore

logger = make_logger("SwitchNode")


class SimBackend:
    name = "sim"

    def __init__(self, registry: SwitchRegistry):
        self.registry = registry

    def apply(self, switch: Switch, state: str):
        icon = "💡" if state == "on" else "⚫"
        logger.info(f"{icon}  {switch.name:<16} -> {state.upper()}")

    def close(self):
        pass


class GpioBackend:
    name = "gpio"

    def __init__(self, registry: SwitchRegistry):
        from gpiozero import OutputDevice  # only needed on the Pi

        self.devices = {}
        for switch in registry:
            if switch.gpio_pin is None:
                logger.warning(f"{switch.id}: no gpio_pin in switches.json, skipping")
                continue
            self.devices[switch.id] = OutputDevice(int(switch.gpio_pin), active_high=switch.active_high, initial_value=False)
            logger.info(f"{switch.name}: GPIO{switch.gpio_pin} (active_{'high' if switch.active_high else 'low'})")

    def apply(self, switch: Switch, state: str):
        dev = self.devices.get(switch.id)
        if dev is None:
            logger.warning(f"{switch.id}: no GPIO device bound")
            return
        dev.on() if state == "on" else dev.off()
        logger.info(f"GPIO{switch.gpio_pin} {switch.name} -> {state.upper()}")

    def close(self):
        for dev in self.devices.values():
            try:
                dev.off()
                dev.close()
            except Exception:
                pass


BACKENDS = {"sim": SimBackend, "gpio": GpioBackend}


class SwitchNode:
    def __init__(self, registry: SwitchRegistry, backend, client=None):
        self.registry = registry
        self.backend = backend
        self.client = client
        self.states: Dict[str, str] = {s.id: "off" for s in registry}

    def _desired_state(self, switch: Switch, raw: str) -> Optional[str]:
        """Work out what a command payload asks of this particular switch, or None if it is not addressed."""
        if raw.startswith("{"):
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                return None
            if switch.state_key not in data:
                return None
            value = str(data[switch.state_key]).strip().lower()
        else:
            if switch.is_zigbee:
                return None
            value = raw.strip().lower()
            if raw == switch.payload_on:
                value = "on"
            elif raw == switch.payload_off:
                value = "off"
        if value == "toggle":
            return "off" if self.states.get(switch.id) == "on" else "on"
        return normalize_state(value)

    def handle_command(self, topic: str, payload) -> Dict[str, str]:
        """Apply a command message. Returns {switch_id: new_state} for every switch it touched."""
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8", errors="ignore")
        raw = str(payload).strip()
        touched: Dict[str, str] = {}
        for switch in self.registry.by_command_topic(topic):
            state = self._desired_state(switch, raw)
            if state is None:
                continue
            self.backend.apply(switch, state)
            self.states[switch.id] = state
            touched[switch.id] = state
        if not touched and self.registry.by_command_topic(topic):
            logger.warning(f"{topic}: payload '{raw}' did not address any switch")
        for state_topic in {s.state_topic for s in self.registry if s.id in touched}:
            self.publish_state(state_topic)
        return touched

    def state_payload(self, state_topic: str) -> str:
        members: List[Switch] = self.registry.by_state_topic(state_topic)
        if any(m.is_zigbee for m in members):
            return json.dumps({m.state_key: self.states[m.id].upper() for m in members})
        switch = members[0]
        return switch.payload_for(self.states[switch.id])

    def publish_state(self, state_topic: str):
        if self.client is None:
            return
        self.client.publish(state_topic, self.state_payload(state_topic), retain=True)

    def run(self, host: str, port: int):
        client = mqtt_client()
        self.client = client

        def on_connect(c, userdata, flags, rc, *_props):
            logger.info(f"Connected to MQTT broker at {host}:{port} (rc={rc})")
            for topic in sorted({s.command_topic for s in self.registry}):
                c.subscribe(topic)
            for topic in self.registry.state_topics():
                self.publish_state(topic)  # announce initial (off) state

        def on_message(c, userdata, msg):
            try:
                self.handle_command(msg.topic, msg.payload)
            except Exception as exc:
                logger.error(f"Error handling {msg.topic}: {exc}")

        client.on_connect = on_connect
        client.on_message = on_message
        client.connect(host, port, 60)

        logger.info("=" * 50)
        logger.info(f"🔌 Switch node ready (backend={self.backend.name})")
        for switch in self.registry:
            logger.info(f"   {switch.name:<16} {switch.command_topic}  [{switch.state_key}]")
        logger.info("=" * 50)
        try:
            client.loop_forever()
        except KeyboardInterrupt:
            logger.info("Stopping...")
        finally:
            self.backend.close()
            client.disconnect()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Sage switch node (simulator / GPIO relay driver)")
    parser.add_argument("--backend", choices=sorted(BACKENDS), default=os.getenv("SWITCH_BACKEND", "sim"))
    parser.add_argument("--host", default=os.getenv("MQTT_HOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", "1883")))
    parser.add_argument("--switches", help="Path to switches.json", default=None)
    args = parser.parse_args(argv)

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass

    registry = SwitchRegistry.load(args.switches)
    backend = BACKENDS[args.backend](registry)
    SwitchNode(registry, backend).run(args.host, args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
