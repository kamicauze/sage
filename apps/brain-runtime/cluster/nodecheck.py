"""
Node check: run on each machine to verify it is ready for its role in the cluster.

    ./sage nodecheck hub      # Mac Mini   : Mosquitto broker + switch controller (later the LLM brain)
    ./sage nodecheck home     # Pi 5       : Zigbee2MQTT + Zigbee dongle
    ./sage nodecheck voice    # 4070 Ti    : STT + TTS, mic and speaker plugged in here
    ./sage nodecheck vision   # Jetson Orin: camera + vision pipeline
    ./sage nodecheck --list   # from any machine: every node's last report, read from the broker

Each run prints PASS / WARN / FAIL lines, exits non-zero on any FAIL, and publishes a
retained summary to sage/nodes/<hostname>/<role> so --list shows the whole cluster in one place.
Environment: MQTT_HOST / MQTT_PORT (the hub's address), plus role-specific vars noted below.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

_probe = Path(__file__).resolve().parent
for _parent in [_probe, *_probe.parents]:
    if (_parent / "sage.py").exists():
        REPO_ROOT = _parent
        if str(_parent) not in sys.path:
            sys.path.insert(0, str(_parent))
        break
else:  # pragma: no cover
    REPO_ROOT = _probe

VOICE_DIR = REPO_ROOT / "apps" / "brain-runtime" / "voice"
NODES_TOPIC = "sage/nodes"

ROLES = {
    "hub": "Mac Mini: Mosquitto broker + switch controller (later: LLM brain)",
    "home": "Raspberry Pi 5: Zigbee2MQTT + Zigbee dongle",
    "voice": "RTX 4070 Ti: STT + TTS (mic and speaker attached here)",
    "vision": "Jetson Orin: camera + vision pipeline",
}

LOCAL_NAMES = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
ZIGBEE_DONGLE_HINTS = re.compile(
    r"zigbee|sonoff|itead|slzb|conbee|cc26|cc13|ezsp|efr32|silicon_labs|cp210|1a86|skyconnect|zbt", re.I)


@dataclass
class Check:
    level: str          # PASS | WARN | FAIL | INFO
    name: str
    detail: str = ""


@dataclass
class Report:
    role: str
    host: str = field(default_factory=lambda: socket.gethostname())
    checks: List[Check] = field(default_factory=list)

    def add(self, level: str, name: str, detail: str = "") -> Check:
        c = Check(level, name, detail)
        self.checks.append(c)
        icon = {"PASS": "✅", "WARN": "⚠️ ", "FAIL": "❌", "INFO": "ℹ️ "}[level]
        print(f"{icon} {level:<4} {name}" + (f": {detail}" if detail else ""))
        return c

    def counts(self) -> Dict[str, int]:
        out = {"PASS": 0, "WARN": 0, "FAIL": 0}
        for c in self.checks:
            if c.level in out:
                out[c.level] += 1
        return out

    @property
    def failed(self) -> bool:
        return self.counts()["FAIL"] > 0

    def summary(self) -> Dict:
        return {
            "host": self.host,
            "role": self.role,
            "ts": int(time.time()),
            "result": "FAIL" if self.failed else ("WARN" if self.counts()["WARN"] else "PASS"),
            "counts": self.counts(),
            "platform": f"{platform.system()} {platform.machine()}",
            "failures": [f"{c.name}: {c.detail}" for c in self.checks if c.level == "FAIL"],
        }


# ---- pure helpers (unit tested) --------------------------------------------------

def is_local_host(host: str, own_ips: Optional[List[str]] = None) -> bool:
    host = (host or "").strip().lower()
    if host in LOCAL_NAMES:
        return True
    try:
        if host in {socket.gethostname().lower(), socket.getfqdn().lower()}:
            return True
    except Exception:
        pass
    return host in set(own_ips or [])


def z2m_mqtt_server(config_text: str) -> Optional[str]:
    """Pull mqtt.server out of a Zigbee2MQTT configuration.yaml without a YAML dependency."""
    in_mqtt = False
    for line in config_text.splitlines():
        if re.match(r"^mqtt\s*:", line):
            in_mqtt = True
            continue
        if in_mqtt and re.match(r"^\S", line):  # next top-level key
            in_mqtt = False
        if in_mqtt:
            m = re.match(r"^\s+server\s*:\s*['\"]?([^'\"#\s]+)", line)
            if m:
                return m.group(1)
    return None


def host_from_url(url: str) -> str:
    m = re.match(r"^\w+://([^:/]+)", url or "")
    return m.group(1) if m else (url or "")


def pick_dongles(paths: List[str]) -> List[str]:
    """Serial devices that look like Zigbee coordinators (by-id names carry the vendor)."""
    by_id = [p for p in paths if "/by-id/" in p and ZIGBEE_DONGLE_HINTS.search(p)]
    if by_id:
        return by_id
    return [p for p in paths if re.search(r"/dev/tty(USB|ACM)\d+$", p)]


def format_node_table(reports: List[Dict], now: Optional[float] = None) -> str:
    now = now or time.time()
    if not reports:
        return "No node reports on the broker yet. Run ./sage nodecheck <role> on each machine."
    lines = [f"{'HOST':<20} {'ROLE':<7} {'RESULT':<6} {'AGE':>7}  FIRST FAILURE"]
    for r in sorted(reports, key=lambda r: (r.get("role", ""), r.get("host", ""))):
        age = int(now - r.get("ts", now))
        age_s = f"{age // 3600}h" if age >= 3600 else (f"{age // 60}m" if age >= 60 else f"{age}s")
        first = (r.get("failures") or [""])[0][:60]
        lines.append(f"{r.get('host', '?'):<20} {r.get('role', '?'):<7} {r.get('result', '?'):<6} {age_s:>7}  {first}")
    missing = sorted(set(ROLES) - {r.get("role") for r in reports})
    if missing:
        lines.append(f"\nNo report yet from: {', '.join(missing)}")
    return "\n".join(lines)


# ---- environment probes --------------------------------------------------------------

def lan_ip() -> Optional[str]:
    """The address other machines would use to reach this one (no packets are sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except Exception:
        return None
    finally:
        s.close()


def tcp_open(host: str, port: int, timeout: float = 2.0) -> Optional[str]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return None
    except OSError as exc:
        return str(exc)


def proc_running(pattern: str, exact: bool = False) -> bool:
    if shutil.which("pgrep") is None:
        return False
    cmd = ["pgrep", "-x" if exact else "-f", pattern]
    return subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def z2m_process_running() -> bool:
    """Zigbee2MQTT runs as `node index.js` (cwd .../zigbee2mqtt), so match node processes by cwd or argv.
    A plain `pgrep -f zigbee2mqtt` both misses that and matches any shell that merely mentions the word."""
    if shutil.which("pgrep") is None:
        return False
    pids = subprocess.run(["pgrep", "-x", "node"], capture_output=True, text=True).stdout.split()
    for pid in pids:
        try:
            cwd = os.readlink(f"/proc/{pid}/cwd")
        except OSError:
            cwd = ""
        try:
            cmd = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "ignore")
        except OSError:
            cmd = ""
        if "zigbee2mqtt" in cwd.lower() or "zigbee2mqtt" in cmd.lower():
            return True
    return False


def paho_version() -> str:
    try:
        import paho.mqtt as pm  # paho 2.x keeps __version__ here
        return str(getattr(pm, "__version__", "") or "")
    except Exception:
        return ""


def find_binary(name: str) -> Optional[str]:
    found = shutil.which(name)
    if found:
        return found
    for d in ("/opt/homebrew/sbin", "/usr/local/sbin", "/usr/sbin", "/opt/homebrew/bin"):
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    return None


def mqtt_peek(host: str, port: int, topics: List[str], timeout: float = 3.0) -> Dict[str, str]:
    from brain.devices.switch_controller import mqtt_client

    got: Dict[str, str] = {}
    client = mqtt_client()
    client.on_message = lambda c, u, m: got.__setitem__(m.topic, m.payload.decode("utf-8", "ignore"))
    client.connect(host, port, 30)
    for t in topics:
        client.subscribe(t)
    client.loop_start()
    concrete = [t for t in topics if "+" not in t and "#" not in t]
    deadline = time.time() + timeout
    while time.time() < deadline:
        # Wildcard-only peeks wait the full timeout so every retained message arrives.
        if concrete and all(t in got for t in concrete) and len(concrete) == len(topics):
            break
        time.sleep(0.1)
    client.loop_stop()
    client.disconnect()
    return got


def try_import(rep: Report, module: str, label: str, level_missing: str = "FAIL", hint: str = ""):
    try:
        mod = __import__(module, fromlist=["_"])
        version = getattr(mod, "__version__", "")
        rep.add("PASS", f"{label} importable", version)
        return mod
    except Exception as exc:
        rep.add(level_missing, f"{label} not importable", f"{type(exc).__name__}: {exc}"[:160] + (f". {hint}" if hint else ""))
        return None


def cuda_status(rep: Report, required: bool = True):
    torch = None
    try:
        import torch as _torch
        torch = _torch
    except Exception:
        pass
    if torch is not None:
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            try:
                free, total = torch.cuda.mem_get_info()
                rep.add("PASS", "CUDA available (torch)", f"{name}, {free / 2**30:.1f} of {total / 2**30:.1f} GB free")
            except Exception:
                rep.add("PASS", "CUDA available (torch)", name)
            return True
        rep.add("FAIL" if required else "WARN", "torch is installed but CUDA is not available",
                f"torch {torch.__version__}: on Jetson install NVIDIA's JetPack torch wheel; on x86 a CUDA build of torch")
        return False
    try:
        import ctranslate2
        n = ctranslate2.get_cuda_device_count()
        rep.add("PASS" if n else ("FAIL" if required else "WARN"), "CUDA via ctranslate2", f"{n} device(s)")
        return bool(n)
    except Exception:
        rep.add("FAIL" if required else "WARN", "cannot determine CUDA", "neither torch nor ctranslate2 importable")
        return False


# ---- common + role checks ---------------------------------------------------------------

def check_common(rep: Report, host: str, port: int) -> bool:
    v = sys.version_info
    rep.add("PASS" if v >= (3, 9) else "FAIL", "Python", f"{v.major}.{v.minor}.{v.micro} at {sys.executable}")
    rep.add("INFO", "this machine", f"{rep.host} ({platform.system()} {platform.machine()}), LAN IP {lan_ip() or '?'}")
    try:
        import paho.mqtt.client  # noqa: F401
        rep.add("PASS", "paho-mqtt importable", paho_version() or "?")
    except Exception:
        rep.add("FAIL", "paho-mqtt missing", "pip install 'paho-mqtt>=2'")
        return False
    if not host:
        rep.add("FAIL", "MQTT_HOST not set", "set it to the Mac Mini's IP (export MQTT_HOST=... or the role's env file)")
        return False
    err = tcp_open(host, port)
    if err:
        rep.add("FAIL", f"broker {host}:{port} unreachable", f"{err}. Is Mosquitto running on the Mini with a LAN listener?")
        return False
    rep.add("PASS", f"broker {host}:{port} reachable")
    return True


def check_hub(rep: Report, host: str, port: int, broker_ok: bool):
    binary = find_binary("mosquitto")
    rep.add("PASS" if binary else "FAIL", "mosquitto installed", binary or "brew install mosquitto (macOS) / apt install mosquitto")
    running = proc_running("mosquitto", exact=True)
    rep.add("PASS" if running else "FAIL", "mosquitto running", "" if running else "bash apps/brain-runtime/deploy/start_mini_hub.sh")
    if host and not is_local_host(host, [lan_ip() or ""]):
        rep.add("WARN", "MQTT_HOST points elsewhere", f"{host}: on the hub it should be localhost or this machine's IP")
    ip = lan_ip()
    if running and ip:
        err = tcp_open(ip, port)
        if err:
            rep.add("FAIL", f"broker not reachable on LAN address {ip}:{port}",
                    "Mosquitto 2 only listens on localhost by default. Start it with the repo's mosquitto.conf "
                    "(start_mini_hub.sh does), or add 'listener 1883' + 'allow_anonymous true' to its config")
        else:
            rep.add("PASS", f"broker reachable from the LAN at {ip}:{port}", "other nodes use this as MQTT_HOST")
        ws = tcp_open(ip, 9001)
        rep.add("PASS" if ws is None else "WARN", "websocket listener :9001", "for the PWA" if ws is None else "PWA will not connect")
    try:
        from brain.devices.switch_commands import SwitchRegistry
        reg = SwitchRegistry.load()
        rep.add("PASS", "switches.json loads", f"{len(reg)} switches, base topic '{reg.z2m_base}'")
    except Exception as exc:
        rep.add("FAIL", "switches.json invalid", str(exc)[:160])
        reg = None
    rep.add("PASS" if proc_running("[b]rain.devices.switch_controller") else "WARN", "switch controller running",
            "" if proc_running("[b]rain.devices.switch_controller") else "start_mini_hub.sh starts it")
    if broker_ok and reg is not None:
        try:
            got = mqtt_peek(host, port, [f"{reg.z2m_base}/bridge/state"], 3.0)
            state = got.get(f"{reg.z2m_base}/bridge/state", "")
            online = "online" in state.lower()
            rep.add("PASS" if online else "WARN", "Zigbee2MQTT (on the Pi) seen on this broker",
                    "online" if online else "not yet: point Zigbee2MQTT's mqtt.server at this Mini, then restart it")
        except Exception as exc:
            rep.add("WARN", "could not query the broker", str(exc)[:120])


def check_home(rep: Report, host: str, port: int, broker_ok: bool):
    own = [lan_ip() or ""]
    if host and is_local_host(host, own):
        rep.add("WARN", "MQTT_HOST is this Pi", "in the current layout the broker lives on the Mac Mini; set MQTT_HOST to the Mini's IP")
    if proc_running("mosquitto", exact=True):
        rep.add("WARN", "a Mosquitto broker is running on this Pi",
                "harmless, but nodes must all use the Mini's broker. Stop it once Zigbee2MQTT points at the Mini: sudo systemctl disable --now mosquitto")

    z2m_proc = z2m_process_running()
    systemd = ""
    if shutil.which("systemctl"):
        systemd = subprocess.run(["systemctl", "is-active", "zigbee2mqtt"], capture_output=True, text=True).stdout.strip()
    docker = ""
    if shutil.which("docker"):
        docker = subprocess.run(["docker", "ps", "--format", "{{.Names}}", "--filter", "name=zigbee2mqtt"],
                                capture_output=True, text=True).stdout.strip()
    if z2m_proc or systemd == "active" or docker:
        rep.add("PASS", "Zigbee2MQTT running", f"systemd={systemd or '-'} docker={docker or '-'}")
    else:
        rep.add("FAIL", "Zigbee2MQTT not running", "sudo systemctl start zigbee2mqtt (or start its container)")

    serial = glob.glob("/dev/serial/by-id/*") + glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*")
    dongles = pick_dongles(serial)
    if dongles:
        rep.add("PASS", "Zigbee dongle present", ", ".join(dongles[:2]))
    elif docker:
        rep.add("INFO", "no dongle visible on the host", "fine if passed straight into the container")
    else:
        rep.add("FAIL", "no Zigbee dongle found", "check it is plugged in: ls /dev/serial/by-id/")

    cfg_paths = [os.getenv("Z2M_CONFIG", ""), "/opt/zigbee2mqtt/data/configuration.yaml",
                 os.path.expanduser("~/zigbee2mqtt/data/configuration.yaml"),
                 os.path.expanduser("~/.z2m/configuration.yaml"), "/app/data/configuration.yaml"]
    cfg = next((p for p in cfg_paths if p and os.path.exists(p)), None)
    if cfg:
        try:
            server = z2m_mqtt_server(Path(cfg).read_text(encoding="utf-8", errors="ignore"))
        except PermissionError:
            server = None
            rep.add("WARN", "cannot read Zigbee2MQTT config", f"{cfg}: rerun with sudo or check permissions")
        if server:
            target = host_from_url(server)
            if host and target != host and not (is_local_host(target, own) and is_local_host(host, own)):
                rep.add("FAIL", "Zigbee2MQTT publishes to a different broker",
                        f"{cfg} has mqtt.server={server}, but MQTT_HOST={host}. Set mqtt.server: mqtt://{host}:{port} and restart Zigbee2MQTT")
            else:
                rep.add("PASS", "Zigbee2MQTT broker setting", f"{server} ({cfg})")
    else:
        rep.add("INFO", "Zigbee2MQTT config not found in the usual places", "set Z2M_CONFIG=/path/to/configuration.yaml to check it")

    if broker_ok:
        try:
            from brain.devices.switch_commands import SwitchRegistry
            base = SwitchRegistry.load().z2m_base
        except Exception:
            base = "zigbee2mqtt"
        try:
            got = mqtt_peek(host, port, [f"{base}/bridge/state"], 3.0)
            online = "online" in got.get(f"{base}/bridge/state", "").lower()
            rep.add("PASS" if online else "FAIL", "Zigbee2MQTT online on the hub broker",
                    "panel commands will reach it" if online else f"nothing on {base}/bridge/state at {host}")
        except Exception as exc:
            rep.add("FAIL", "could not query the hub broker", str(exc)[:120])
    rep.add("INFO", "next", "./sage switches --check  (from here or the Mini) to verify switches.json against the panel")


def check_voice(rep: Report, host: str, port: int, broker_ok: bool):
    cuda_status(rep, required=os.getenv("STT_DEVICE", "cuda") == "cuda")
    try_import(rep, "faster_whisper", "faster-whisper (STT)")
    try_import(rep, "pyaudio", "PyAudio (mic capture)", hint="apt install portaudio19-dev && pip install pyaudio")
    sd = try_import(rep, "sounddevice", "sounddevice (playback)")
    engine = os.getenv("TTS_ENGINE", "kokoro").lower()
    if engine == "kokoro":
        try_import(rep, "kokoro_onnx", "kokoro-onnx (TTS)")
        for f in ("kokoro-v0_19.onnx", "voices.bin"):
            p = VOICE_DIR / "models" / f
            rep.add("PASS" if p.exists() else "FAIL", f"Kokoro file {f}", str(p) if p.exists() else f"missing at {p}")
    else:
        rep.add("INFO", "TTS engine", engine)
    if sd is not None:
        try:
            devices = sd.query_devices()
            ins = [d["name"] for d in devices if d.get("max_input_channels", 0) > 0]
            outs = [d["name"] for d in devices if d.get("max_output_channels", 0) > 0]
            rep.add("PASS" if ins else "FAIL", "microphone(s)", ", ".join(ins[:3]) or "none: plug the mic into this machine")
            rep.add("PASS" if outs else "FAIL", "speaker(s)", ", ".join(outs[:3]) or "none: plug a speaker into this machine")
            try:
                di, do = sd.default.device
                rep.add("INFO", "default devices", f"in={di} out={do}; pin with TTS_OUTPUT_DEVICE=<name> if sound goes elsewhere")
            except Exception:
                pass
        except Exception as exc:
            rep.add("FAIL", "cannot list audio devices", str(exc)[:160])
    rep.add("INFO", "STT profile", f"model={os.getenv('STT_MODEL_PATH') or os.getenv('STT_MODEL_SIZE', 'medium.en')} "
                                   f"compute={os.getenv('STT_COMPUTE_TYPE', 'float16')}")
    rep.add("INFO", "next", "bash apps/brain-runtime/deploy/start_4070_voice.sh, then ./sage voicecheck all")


def check_vision(rep: Report, host: str, port: int, broker_ok: bool):
    tegra = Path("/etc/nv_tegra_release")
    if tegra.exists():
        rep.add("PASS", "Jetson (L4T)", tegra.read_text(errors="ignore").splitlines()[0][:100])
    else:
        rep.add("INFO", "not a Jetson", "fine if vision runs on another CUDA box")
    cuda_status(rep, required=True)

    try:
        major = int((paho_version() or "1").split(".")[0])
    except ValueError:
        major = 1
    rep.add("PASS" if major >= 2 else "FAIL", "paho-mqtt >= 2 (vision_service uses the v2 callback API)",
            "" if major >= 2 else "pip install -U 'paho-mqtt>=2'")

    cv2 = try_import(rep, "cv2", "OpenCV", hint="on Jetson prefer the JetPack OpenCV: sudo apt install python3-opencv")
    try_import(rep, "ultralytics", "ultralytics (YOLO)", level_missing="WARN", hint="pip install ultralytics, or set VISION_NO_YOLO=1")
    try_import(rep, "insightface", "insightface (faces)", level_missing="WARN", hint="pip install insightface onnxruntime-gpu")
    try:
        import onnxruntime as ort
        prov = ort.get_available_providers()
        gpu = any(p in prov for p in ("CUDAExecutionProvider", "TensorrtExecutionProvider"))
        rep.add("PASS" if gpu else "WARN", "onnxruntime GPU provider", ", ".join(prov)[:120])
    except Exception:
        rep.add("WARN", "onnxruntime not importable", "face recognition will be off")

    cam_index = int(os.getenv("VISION_CAMERA", "0"))
    videos = sorted(glob.glob("/dev/video*"))
    rep.add("PASS" if videos else "FAIL", "video devices", ", ".join(videos) or "no /dev/video*: plug the camera in (USB) or check the CSI ribbon")
    if cv2 is not None and videos:
        cap = cv2.VideoCapture(cam_index, getattr(cv2, "CAP_V4L2", 0))
        ok, frame = cap.read() if cap.isOpened() else (False, None)
        cap.release()
        if ok and frame is not None:
            rep.add("PASS", f"camera {cam_index} delivers frames", f"{frame.shape[1]}x{frame.shape[0]}")
        else:
            rep.add("FAIL", f"camera {cam_index} gives no frames",
                    "try VISION_CAMERA=1, check `v4l2-ctl --list-devices`; CSI cameras need a GStreamer pipeline")

    ollama = os.getenv("VISION_OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    model = os.getenv("VISION_VLM_MODEL", "moondream")
    if os.getenv("VISION_NO_VLM", "0") == "1":
        rep.add("INFO", "VLM disabled", "VISION_NO_VLM=1")
    else:
        try:
            import urllib.request
            with urllib.request.urlopen(f"{ollama}/api/tags", timeout=3) as resp:
                tags = [m.get("name", "") for m in json.load(resp).get("models", [])]
            have = any(t.split(":")[0] == model.split(":")[0] for t in tags)
            rep.add("PASS" if have else "FAIL", f"Ollama at {ollama} has '{model}'",
                    "" if have else f"ollama pull {model}  (models present: {', '.join(tags[:5]) or 'none'})")
        except Exception as exc:
            rep.add("FAIL", f"Ollama not reachable at {ollama}",
                    f"{exc}. Install Ollama on the Orin (curl -fsSL https://ollama.com/install.sh | sh) or set VISION_NO_VLM=1")
    rep.add("INFO", "next", "bash apps/brain-runtime/deploy/start_orin_vision.sh")


ROLE_CHECKS: Dict[str, Callable] = {"hub": check_hub, "home": check_home, "voice": check_voice, "vision": check_vision}


def publish_report(rep: Report, host: str, port: int):
    try:
        from brain.devices.switch_controller import mqtt_client
        client = mqtt_client()
        client.connect(host, port, 30)
        client.loop_start()
        topic = f"{NODES_TOPIC}/{rep.host}/{rep.role}"
        info = client.publish(topic, json.dumps(rep.summary()), retain=True)
        info.wait_for_publish(timeout=3)
        client.loop_stop()
        client.disconnect()
        print(f"\nreport published to {topic} (see all nodes: ./sage nodecheck --list)")
    except Exception as exc:
        print(f"\n(could not publish report: {exc})")


def list_nodes(host: str, port: int) -> int:
    err = tcp_open(host, port)
    if err:
        print(f"broker {host}:{port} unreachable: {err}")
        return 1
    got = mqtt_peek(host, port, [f"{NODES_TOPIC}/+/+"], 2.5)
    reports = []
    for payload in got.values():
        try:
            reports.append(json.loads(payload))
        except Exception:
            pass
    # mqtt_peek keeps the latest message per topic: one per host and role.
    print(format_node_table(reports))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Check this machine for its role in the Sage cluster")
    parser.add_argument("role", nargs="?", choices=sorted(ROLES))
    parser.add_argument("--list", action="store_true", help="Show every node's last report from the broker")
    parser.add_argument("--host", default=os.getenv("MQTT_HOST", ""))
    parser.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", "1883")))
    parser.add_argument("--no-publish", action="store_true", help="Do not publish the report to the broker")
    args = parser.parse_args(argv)
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass
    host = args.host or ("localhost" if args.role == "hub" else "")

    if args.list:
        return list_nodes(host or "localhost", args.port)
    if not args.role:
        parser.error("give a role (hub, home, voice, vision) or --list")

    rep = Report(role=args.role)
    print(f"Sage node check: {args.role} ({ROLES[args.role]})\n")
    broker_ok = check_common(rep, host, args.port)
    try:
        ROLE_CHECKS[args.role](rep, host, args.port, broker_ok)
    except Exception as exc:
        rep.add("FAIL", "check crashed", f"{type(exc).__name__}: {exc}"[:200])
    c = rep.counts()
    print(f"\nResult: {'FAIL' if rep.failed else 'PASS'}  ({c['PASS']} pass, {c['WARN']} warn, {c['FAIL']} fail)")
    if broker_ok and not args.no_publish:
        publish_report(rep, host, args.port)
    return 1 if rep.failed else 0


if __name__ == "__main__":
    sys.exit(main())
