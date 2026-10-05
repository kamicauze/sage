"""
Setup check for the voice -> Zigbee switch loop. Run it ON the machine that talks to the
broker (the Pi, usually):

    ./sage switches --check
    python -m brain.devices.check_setup [--host H] [--port P] [--switches FILE] [--timeout S]

Read-only apart from one Zigbee2MQTT "get" request so the panel reports its state.
Prints PASS / WARN / FAIL lines and exits non-zero if anything FAILed.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_probe = Path(__file__).resolve().parent
for _parent in [_probe, *_probe.parents]:
    if (_parent / "sage.py").exists():
        if str(_parent) not in sys.path:
            sys.path.insert(0, str(_parent))
        break

try:
    from .switch_commands import SwitchRegistry
    from .switch_controller import summarize_z2m_devices
except ImportError:
    from brain.devices.switch_commands import SwitchRegistry  # type: ignore
    from brain.devices.switch_controller import summarize_z2m_devices  # type: ignore


class Report:
    def __init__(self):
        self.rows: List[Tuple[str, str]] = []

    def add(self, level: str, text: str):
        self.rows.append((level, text))
        icon = {"PASS": "✅", "WARN": "⚠️ ", "FAIL": "❌", "INFO": "ℹ️ "}[level]
        print(f"{icon} {level:<4} {text}")

    def ok(self, text): self.add("PASS", text)
    def warn(self, text): self.add("WARN", text)
    def fail(self, text): self.add("FAIL", text)
    def info(self, text): self.add("INFO", text)

    @property
    def failed(self) -> bool:
        return any(level == "FAIL" for level, _ in self.rows)


# ---- pure helpers (unit tested) ---------------------------------------------------

def bridge_online(payload) -> Optional[bool]:
    """zigbee2mqtt/bridge/state is 'online' (old) or {"state": "online"} (new)."""
    if payload is None:
        return None
    text = payload.decode() if isinstance(payload, bytes) else str(payload)
    text = text.strip()
    if text.startswith("{"):
        try:
            text = str(json.loads(text).get("state", ""))
        except json.JSONDecodeError:
            return None
    return text.lower() == "online"


def compare_registry_to_bridge(registry: SwitchRegistry, devices: List[Dict]) -> Dict[str, List[str]]:
    """
    Match switches.json against the Zigbee2MQTT device list.
    Returns {"ok": [...], "missing_device": [...], "missing_key": [...], "unregistered": [...]}.
    """
    rows = summarize_z2m_devices(devices)
    by_name = {r["friendly_name"]: r for r in rows}
    result = {"ok": [], "missing_device": [], "missing_key": [], "unregistered": []}
    used = set()
    for s in registry:
        if not s.is_zigbee:
            continue
        dev = by_name.get(s.zigbee_name)
        if dev is None:
            result["missing_device"].append(f"{s.id}: no device named '{s.zigbee_name}' in Zigbee2MQTT")
            continue
        used.add(s.zigbee_name)
        if dev["switch_keys"] and s.state_key not in dev["switch_keys"]:
            result["missing_key"].append(
                f"{s.id}: '{s.zigbee_name}' has keys {dev['switch_keys']}, not '{s.state_key}'"
            )
        else:
            result["ok"].append(f"{s.id} ({s.name}) -> {s.zigbee_name}.{s.state_key}")
    for r in rows:
        if r["switch_keys"] and r["friendly_name"] not in used:
            result["unregistered"].append(f"{r['friendly_name']} ({r['model']}) keys {r['switch_keys']}")
    return result


# ---- live checks ---------------------------------------------------------------------

def check_processes(rep: Report):
    if shutil.which("pgrep") is None:
        return
    from brain.cluster.nodecheck import z2m_process_running

    probes = (
        ("mosquitto", lambda: subprocess.call(["pgrep", "-x", "mosquitto"], stdout=subprocess.DEVNULL,
                                              stderr=subprocess.DEVNULL) == 0),
        ("zigbee2mqtt", z2m_process_running),   # node process with a zigbee2mqtt cwd/argv
    )
    for label, probe in probes:
        if probe():
            rep.ok(f"{label} process is running on this machine")
        else:
            rep.info(f"no local {label} process (fine if it runs on another host or in Docker)")
    if shutil.which("systemctl"):
        for unit in ("mosquitto", "zigbee2mqtt"):
            out = subprocess.run(["systemctl", "is-active", unit], capture_output=True, text=True).stdout.strip()
            if out:
                rep.info(f"systemd {unit}: {out}")


def check_tcp(rep: Report, host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=3):
            rep.ok(f"broker port open at {host}:{port}")
            return True
    except OSError as exc:
        rep.fail(f"cannot reach broker at {host}:{port} ({exc}). Check MQTT_HOST/MQTT_PORT and that mosquitto is up.")
        return False


def collect(host: str, port: int, topics: List[str], timeout: float, publish: Optional[Tuple[str, str]] = None) -> Dict[str, bytes]:
    """Subscribe to topics, optionally publish one message, and gather what arrives within timeout."""
    from brain.devices.switch_controller import mqtt_client  # lazy: needs paho

    got: Dict[str, bytes] = {}

    def on_message(c, userdata, msg):
        got[msg.topic] = msg.payload

    client = mqtt_client()
    client.on_message = on_message
    client.connect(host, port, 60)
    for t in topics:
        client.subscribe(t)
    client.loop_start()
    if publish:
        time.sleep(0.3)
        client.publish(*publish)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if all(t in got for t in topics if "+" not in t and "#" not in t):
            break
        time.sleep(0.1)
    client.loop_stop()
    client.disconnect()
    return got


def run_checks(host: str, port: int, switches_path: Optional[str], timeout: float) -> Report:
    rep = Report()
    print(f"Sage switch setup check  (broker {host}:{port})\n")

    # 1. registry
    try:
        registry = SwitchRegistry.load(switches_path)
        zig = [s for s in registry if s.is_zigbee]
        rep.ok(f"switches.json loaded: {len(registry)} switches, {len(zig)} via Zigbee2MQTT "
               f"(base topic '{registry.z2m_base}')")
        for s in registry:
            rep.info(f"   {s.id:<14} say: {', '.join(s.aliases[:4])}  ->  {s.command_topic}")
    except Exception as exc:
        rep.fail(f"switches.json could not be loaded: {exc}")
        return rep

    # 2. python deps
    try:
        import paho.mqtt.client  # noqa: F401
        rep.ok("paho-mqtt importable")
    except ImportError:
        rep.fail("paho-mqtt is not installed in this Python (pip install paho-mqtt)")
        return rep

    # 3. processes + broker
    check_processes(rep)
    if not check_tcp(rep, host, port):
        return rep

    base = registry.z2m_base
    topics = [f"{base}/bridge/state", f"{base}/bridge/info", f"{base}/bridge/devices"]
    try:
        got = collect(host, port, topics, timeout)
    except Exception as exc:
        rep.fail(f"MQTT connect/subscribe failed: {exc}")
        return rep
    rep.ok("MQTT connect + subscribe works")

    # 4. zigbee2mqtt bridge
    online = bridge_online(got.get(f"{base}/bridge/state"))
    if online is None:
        rep.fail(f"nothing retained on {base}/bridge/state: Zigbee2MQTT is not publishing to this broker "
                 f"(not running, wrong broker in its configuration.yaml, or base_topic is not '{base}')")
    elif online:
        rep.ok("Zigbee2MQTT bridge is online")
    else:
        rep.fail("Zigbee2MQTT bridge reports OFFLINE (check its logs: coordinator/dongle not found?)")

    info_raw = got.get(f"{base}/bridge/info")
    if info_raw:
        try:
            info = json.loads(info_raw.decode())
            coord = info.get("coordinator", {}) or {}
            rep.info(f"Zigbee2MQTT {info.get('version', '?')}, coordinator {coord.get('type', '?')} "
                     f"{(coord.get('meta') or {}).get('revision', '')}, permit_join={info.get('permit_join')}")
            if info.get("permit_join"):
                rep.warn("permit_join is ON: turn it off once the panel is paired")
        except Exception:
            pass

    # 5. devices vs registry
    devices_raw = got.get(f"{base}/bridge/devices")
    if not devices_raw:
        if online:
            rep.fail(f"no device list on {base}/bridge/devices")
        return rep
    try:
        devices = json.loads(devices_raw.decode())
    except Exception as exc:
        rep.fail(f"could not parse device list: {exc}")
        return rep
    rows = summarize_z2m_devices(devices)
    rep.info(f"{len(rows)} paired device(s): " + (", ".join(r["friendly_name"] for r in rows) or "none"))
    if not rows:
        rep.fail("no devices paired. Enable permit join in Zigbee2MQTT and put the panel in pairing mode "
                 "(usually hold a button ~5s until the LED blinks).")
        return rep

    cmp = compare_registry_to_bridge(registry, devices)
    for line in cmp["ok"]:
        rep.ok(line)
    for line in cmp["missing_device"]:
        rep.fail(line)
    for line in cmp["missing_key"]:
        rep.fail(line)
    for line in cmp["unregistered"]:
        rep.warn(f"paired but not in switches.json: {line}")
    if cmp["missing_device"] or cmp["missing_key"]:
        rep.info("fix names/keys in apps/brain-runtime/devices/switches.json (see --discover)")

    # 6. live state of each panel (one get request per panel)
    panels = sorted({s.zigbee_name for s in registry if s.is_zigbee and s.zigbee_name in
                     {r["friendly_name"] for r in rows}})
    for panel in panels:
        keys = [s.state_key for s in registry if s.is_zigbee and s.zigbee_name == panel]
        state_topic = f"{base}/{panel}"
        got_state = collect(host, port, [state_topic], timeout,
                            publish=(f"{base}/{panel}/get", json.dumps({k: "" for k in keys})))
        raw = got_state.get(state_topic)
        if not raw:
            rep.fail(f"{panel}: no state reply on {state_topic} after a get request. "
                     f"Device may be unreachable (out of range / powered off) or does not support get.")
            continue
        try:
            state = json.loads(raw.decode())
        except Exception:
            rep.fail(f"{panel}: state payload is not JSON: {raw[:80]!r}")
            continue
        shown = {k: state.get(k) for k in keys}
        missing = [k for k, v in shown.items() if v is None]
        if missing:
            rep.fail(f"{panel}: state has no {missing}; available keys: {sorted(state.keys())}")
        else:
            rep.ok(f"{panel} live state: {shown}")
        if "linkquality" in state:
            lq = state["linkquality"]
            (rep.warn if isinstance(lq, (int, float)) and lq < 40 else rep.info)(f"{panel} linkquality={lq}")

    print()
    if rep.failed:
        print("Result: FAIL. Fix the ❌ lines above, then rerun.")
    else:
        print("Result: PASS. Try:  ./sage switches --no-stt   and   ./sage switches --say \"lamp on\"")
    return rep


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Check the Zigbee switch setup end to end")
    parser.add_argument("--host", default=os.getenv("MQTT_HOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", "1883")))
    parser.add_argument("--switches", default=None, help="Path to switches.json")
    parser.add_argument("--timeout", type=float, default=4.0, help="Seconds to wait for retained/bridge messages")
    args = parser.parse_args(argv)
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass
    rep = run_checks(args.host, args.port, args.switches, args.timeout)
    return 1 if rep.failed else 0


if __name__ == "__main__":
    sys.exit(main())
