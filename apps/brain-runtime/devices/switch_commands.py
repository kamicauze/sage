"""
Rule-based switch command parsing plus the switch registry. Pure Python: no MQTT, no models.

    registry = SwitchRegistry.load()
    cmd = parse_switch_command("turn on the desk lamp", registry)
    cmd.action      -> "on"
    cmd.switches    -> [Switch(id="panel_2", ...)]
    cmd.switches[0].command_topic, cmd.switches[0].payload_for("on")
                    -> "zigbee2mqtt/office_panel/set", '{"state_l2": "ON"}'

Two wire protocols per switch:
  zigbee2mqtt  the Zigbee panel behind a Zigbee2MQTT bridge. Commands are JSON on
               zigbee2mqtt/<friendly_name>/set, state comes back as JSON on
               zigbee2mqtt/<friendly_name>. Multi-gang panels use state_l1, state_l2, ...
  sage         plain ON/OFF on sage/switch/<id>/set, used by the simulator and GPIO node.

Parser goals:
  - Deterministic and fast (<1ms) so it can sit directly on the STT transcript stream.
  - Tolerant of common STT slips ("turn of the lamp", "lights of").
  - Conservative: needs a command verb or a tight "<device> on/off" phrase, so
    ordinary speech that merely mentions a room or "on" does not flip anything.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

DEFAULT_REGISTRY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "switches.json")
DEFAULT_Z2M_BASE = "zigbee2mqtt"

SAGE_COMMAND_TOPIC = "sage/switch/{id}/set"
SAGE_STATE_TOPIC = "sage/switch/{id}/state"

# Words that make an utterance an instruction rather than a mention.
COMMAND_VERBS = {"turn", "switch", "put", "flip", "toggle", "set", "power", "kill", "cut"}
ALL_WORDS = {"all", "everything", "every"}
STATUS_HINTS = ("is the ", "are the ", "what is ", "whats ", "what's ", "status of ", "state of ", "is ", "are ")


def normalize_state(payload) -> Optional[str]:
    """Accept ON/OFF, 1/0, true/false; return 'on'/'off' or None."""
    text = str(payload if payload is not None else "").strip().lower()
    if text in {"on", "1", "true"}:
        return "on"
    if text in {"off", "0", "false"}:
        return "off"
    return None


@dataclass
class Switch:
    id: str
    name: str
    aliases: List[str] = field(default_factory=list)
    group: str = ""
    room: str = ""
    protocol: str = "sage"              # "sage" | "zigbee2mqtt"
    zigbee_name: str = ""               # Zigbee2MQTT friendly name
    state_key: str = "state"            # JSON key for this gang ("state", "state_l1", ...)
    command_topic: str = ""
    state_topic: str = ""
    get_topic: str = ""                 # zigbee2mqtt/<name>/get, to ask for current state
    payload_on: str = ""
    payload_off: str = ""
    payload_toggle: str = ""            # if set, sent for toggle instead of computing locally
    gpio_pin: Optional[int] = None
    active_high: bool = True
    z2m_base: str = DEFAULT_Z2M_BASE

    def __post_init__(self):
        self.protocol = (self.protocol or "sage").lower()
        if self.protocol not in {"sage", "zigbee2mqtt"}:
            raise ValueError(f"{self.id}: unknown protocol '{self.protocol}'")

        if self.protocol == "zigbee2mqtt":
            if not self.zigbee_name:
                raise ValueError(f"{self.id}: zigbee2mqtt switches need 'zigbee_name'")
            base = self.z2m_base.rstrip("/")
            self.command_topic = self.command_topic or f"{base}/{self.zigbee_name}/set"
            self.state_topic = self.state_topic or f"{base}/{self.zigbee_name}"
            self.get_topic = self.get_topic or f"{base}/{self.zigbee_name}/get"
            self.payload_on = self.payload_on or json.dumps({self.state_key: "ON"})
            self.payload_off = self.payload_off or json.dumps({self.state_key: "OFF"})
            self.payload_toggle = self.payload_toggle or json.dumps({self.state_key: "TOGGLE"})
        else:
            self.command_topic = self.command_topic or SAGE_COMMAND_TOPIC.format(id=self.id)
            self.state_topic = self.state_topic or SAGE_STATE_TOPIC.format(id=self.id)
            self.payload_on = self.payload_on or "ON"
            self.payload_off = self.payload_off or "OFF"

        names = [self.name] + list(self.aliases)
        seen = set()
        cleaned = []
        for n in names:
            key = normalize_text(n)
            if key and key not in seen:
                seen.add(key)
                cleaned.append(key)
        self.aliases = cleaned

    @property
    def is_zigbee(self) -> bool:
        return self.protocol == "zigbee2mqtt"

    def payload_for(self, state: str) -> str:
        if state == "toggle" and self.payload_toggle:
            return self.payload_toggle
        return self.payload_on if state == "on" else self.payload_off

    def parse_state(self, payload) -> Optional[str]:
        """Read this switch's state out of a message on its state_topic."""
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8", errors="ignore")
        text = str(payload or "").strip()
        if text.startswith("{"):
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                return None
            if self.state_key in data:
                return normalize_state(data.get(self.state_key))
            if not self.is_zigbee and "state" in data:
                return normalize_state(data.get("state"))
            return None
        if self.is_zigbee:
            return None  # zigbee2mqtt state is always JSON
        if text == self.payload_on:
            return "on"
        if text == self.payload_off:
            return "off"
        return normalize_state(text)

    @classmethod
    def from_dict(cls, data: Dict, z2m_base: str = DEFAULT_Z2M_BASE) -> "Switch":
        sid = str(data.get("id") or "").strip()
        if not sid:
            raise ValueError("switch entry is missing 'id'")
        protocol = str(data.get("protocol") or ("zigbee2mqtt" if data.get("zigbee_name") else "sage"))
        return cls(
            id=sid,
            name=str(data.get("name") or sid.replace("_", " ")),
            aliases=list(data.get("aliases") or []),
            group=str(data.get("group") or ""),
            room=str(data.get("room") or ""),
            protocol=protocol,
            zigbee_name=str(data.get("zigbee_name") or ""),
            state_key=str(data.get("state_key") or "state"),
            command_topic=str(data.get("command_topic") or ""),
            state_topic=str(data.get("state_topic") or ""),
            get_topic=str(data.get("get_topic") or ""),
            payload_on=str(data.get("payload_on") or ""),
            payload_off=str(data.get("payload_off") or ""),
            payload_toggle=str(data.get("payload_toggle") or ""),
            gpio_pin=data.get("gpio_pin"),
            active_high=bool(data.get("active_high", True)),
            z2m_base=z2m_base,
        )


class SwitchRegistry:
    def __init__(self, switches: List[Switch], z2m_base: str = DEFAULT_Z2M_BASE):
        self.switches: List[Switch] = list(switches)
        self.z2m_base = z2m_base
        ids = [s.id for s in self.switches]
        if len(ids) != len(set(ids)):
            raise ValueError(f"duplicate switch ids in registry: {ids}")

    @classmethod
    def load(cls, path: Optional[str] = None) -> "SwitchRegistry":
        path = path or os.getenv("SAGE_SWITCHES_FILE") or DEFAULT_REGISTRY_PATH
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return cls.from_data(data)

    @classmethod
    def from_data(cls, data) -> "SwitchRegistry":
        z2m_base = DEFAULT_Z2M_BASE
        entries = data
        if isinstance(data, dict):
            z2m_base = os.getenv("Z2M_BASE_TOPIC") or str(data.get("zigbee2mqtt_base") or DEFAULT_Z2M_BASE)
            entries = data.get("switches", [])
        return cls([Switch.from_dict(e, z2m_base) for e in entries], z2m_base=z2m_base)

    def get(self, switch_id: str) -> Optional[Switch]:
        for s in self.switches:
            if s.id == switch_id:
                return s
        return None

    def by_group(self, group: str) -> List[Switch]:
        return [s for s in self.switches if s.group == group]

    def groups(self) -> List[str]:
        return sorted({s.group for s in self.switches if s.group})

    def by_command_topic(self, topic: str) -> List[Switch]:
        return [s for s in self.switches if s.command_topic == topic]

    def by_state_topic(self, topic: str) -> List[Switch]:
        return [s for s in self.switches if s.state_topic == topic]

    def state_topics(self) -> List[str]:
        return sorted({s.state_topic for s in self.switches})

    def __len__(self):
        return len(self.switches)

    def __iter__(self):
        return iter(self.switches)


@dataclass
class SwitchCommand:
    action: str                    # "on" | "off" | "toggle" | "status"
    switches: List[Switch]
    text: str                      # normalized utterance that produced this
    target: str = ""               # what was matched: alias, group name, or "all"

    def describe(self) -> str:
        names = ", ".join(s.name for s in self.switches)
        return f"{self.action} -> {names}"


_PUNCT_RE = re.compile(r"[^\w\s']+")
_SPACE_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    text = (text or "").lower().replace("’", "'")
    text = _PUNCT_RE.sub(" ", text)
    text = _SPACE_RE.sub(" ", text).strip()
    # Common STT slips.
    text = re.sub(r"\b(turn|switch|put|flip|lights?|lamp|fan) of\b", r"\1 off", text)
    text = re.sub(r"\bturn(on|off)\b", r"turn \1", text)
    return text


def strip_wake_word(text: str, wake_word: str) -> Optional[str]:
    """Return text with the wake word removed, or None if the wake word is required but absent."""
    wake = normalize_text(wake_word)
    if not wake:
        return text
    norm = normalize_text(text)
    m = re.match(rf"^(?:hey |ok |okay |yo )?{re.escape(wake)}\b[, ]*(.*)$", norm)
    if not m:
        return None
    return m.group(1).strip()


def _has_word(text: str, word: str) -> bool:
    return re.search(rf"\b{re.escape(word)}\b", text) is not None


def _find_action(text: str) -> Optional[str]:
    if _has_word(text, "toggle") or _has_word(text, "flip"):
        return "toggle"
    has_on = _has_word(text, "on")
    has_off = _has_word(text, "off")
    if has_on and not has_off:
        return "on"
    if has_off and not has_on:
        return "off"
    if has_on and has_off:
        # e.g. "turn off the light on the desk": take the one right after the verb, else the last one.
        m = re.search(r"\b(turn|switch|put|flip|set|power)\s+(on|off)\b", text)
        if m:
            return m.group(2)
        return "on" if text.rfind(" on") > text.rfind(" off") else "off"
    if any(w in text for w in ("kill", "cut")):
        return "off"
    return None


def _match_targets(text: str, registry: SwitchRegistry):
    """Return (switches, target_label). Longest alias wins; explicit aliases beat groups."""
    words = set(text.split())

    if words & ALL_WORDS:
        for group in registry.groups():
            if _has_word(text, group) or _has_word(text, group.rstrip("s")):
                return registry.by_group(group), f"all {group}"
        return list(registry.switches), "all"

    matched: List[Switch] = []
    labels: List[str] = []
    # Longest alias first so "kitchen light" beats "kitchen" and "light".
    candidates = sorted(
        ((alias, s) for s in registry for alias in s.aliases),
        key=lambda pair: -len(pair[0]),
    )
    consumed = text
    positions: List[int] = []
    for alias, switch in candidates:
        if switch in matched:
            continue
        m = re.search(rf"\b{re.escape(alias)}\b", consumed)
        if m:
            matched.append(switch)
            labels.append(alias)
            positions.append(m.start())
            consumed = consumed[:m.start()] + " " * len(alias) + consumed[m.end():]
    if matched:
        # Keep the order the devices were spoken in ("the fan and the lamp").
        order = sorted(range(len(matched)), key=lambda i: positions[i])
        return [matched[i] for i in order], ", ".join(labels[i] for i in order)

    # Bare group words: "lights on", "turn off the fans", optionally narrowed by room
    # ("office lights off" only touches lights whose room is "office").
    for group in registry.groups():
        if _has_word(text, group) or _has_word(text, group.rstrip("s")):
            members = registry.by_group(group)
            rooms = sorted({s.room for s in members if s.room}, key=len, reverse=True)
            for room in rooms:
                if _has_word(text, room):
                    return [s for s in members if s.room == room], f"{room} {group}"
            return members, group

    return [], ""


def parse_switch_command(text: str, registry: SwitchRegistry) -> Optional[SwitchCommand]:
    norm = normalize_text(text)
    if not norm:
        return None

    switches, target = _match_targets(norm, registry)
    if not switches:
        return None

    is_status = norm.startswith(STATUS_HINTS) and not (set(norm.split()) & COMMAND_VERBS)
    if is_status:
        return SwitchCommand(action="status", switches=switches, text=norm, target=target)

    action = _find_action(norm)
    if action is None:
        return None

    has_verb = bool(set(norm.split()) & COMMAND_VERBS)
    # Tight forms without a verb: "lamp on", "office lights off", "on lamp".
    tight = re.fullmatch(r"(?:the |my )?(.+?) (on|off)|(on|off) (?:the |my )?(.+)", norm) is not None
    if not has_verb and not tight:
        return None

    return SwitchCommand(action=action, switches=switches, text=norm, target=target)


def spoken_reply(cmd: SwitchCommand, states: Optional[Dict[str, str]] = None) -> str:
    """Short, TTS-friendly confirmation text."""
    states = states or {}
    names = [s.name for s in cmd.switches]
    if len(names) == 1:
        subject = names[0]
    elif cmd.target.startswith("all") or cmd.target.split(" ")[-1] in {s.group for s in cmd.switches}:
        subject = cmd.target          # "all", "all lights", "lights", "office lights"
    else:
        subject = " and ".join(names)

    if cmd.action == "status":
        parts = []
        for s in cmd.switches:
            st = states.get(s.id)
            sentence = f"{s.name} is {st}" if st else f"{s.name} is unknown"
            parts.append(sentence[0].upper() + sentence[1:])
        return ". ".join(parts) + "."
    if cmd.action == "toggle":
        return f"Toggled {subject}."
    return f"{subject} {cmd.action}.".capitalize()
