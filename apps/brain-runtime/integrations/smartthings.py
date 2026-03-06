import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

DEFAULT_SMARTTHINGS_API_URL = "https://api.smartthings.com/v1"
DEFAULT_SMARTTHINGS_TIMEOUT_SEC = 12.0


class SmartThingsError(RuntimeError):
    pass


@dataclass
class SmartThingsHomeCommand:
    kind: str
    raw_target: str = ""
    command: str = ""
    capability: str = ""
    arguments: List[Any] = None
    component: str = "main"
    display_target: str = ""

    def __post_init__(self):
        if self.arguments is None:
            self.arguments = []


def _normalize_name(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", (value or "").strip().lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def _load_device_aliases(raw: Optional[str] = None) -> Dict[str, str]:
    source = (raw if raw is not None else os.getenv("SMARTTHINGS_DEVICE_ALIASES", "")).strip()
    if not source:
        return {}

    # Preferred format: JSON object {"kitchen lights":"<deviceId>"}
    try:
        parsed = json.loads(source)
        if isinstance(parsed, dict):
            aliases = {}
            for key, value in parsed.items():
                if not isinstance(key, str) or not isinstance(value, str):
                    continue
                norm_key = _normalize_name(key)
                norm_value = value.strip()
                if norm_key and norm_value:
                    aliases[norm_key] = norm_value
            if aliases:
                return aliases
    except Exception:
        pass

    # Fallback format: "kitchen lights=<deviceId>,bedroom lamp=<deviceId>"
    aliases = {}
    for token in source.split(","):
        part = token.strip()
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        norm_key = _normalize_name(key)
        norm_value = value.strip()
        if norm_key and norm_value:
            aliases[norm_key] = norm_value
    return aliases


def parse_home_control_command(text: str) -> Optional[SmartThingsHomeCommand]:
    query = (text or "").strip()
    if not query:
        return None

    lowered = query.lower()

    if "list devices" in lowered or "what devices" in lowered or "show devices" in lowered:
        return SmartThingsHomeCommand(kind="list_devices")

    if "list scenes" in lowered or "what scenes" in lowered or "show scenes" in lowered:
        return SmartThingsHomeCommand(kind="list_scenes")

    scene_match = re.search(
        r"\b(?:run|start|activate|trigger)\s+(?:the\s+)?(?P<scene>.+?)(?:\s+scene)?\s*$",
        lowered,
    )
    if scene_match:
        scene_name = _strip_trailing_polite(scene_match.group("scene"))
        if scene_name:
            return SmartThingsHomeCommand(
                kind="run_scene",
                raw_target=scene_name,
                display_target=scene_name,
            )

    dim_match = re.search(
        r"\b(?:set|dim|brighten)\s+(?:the\s+)?(?P<device>.+?)\s+(?:to\s+)?(?P<level>\d{1,3})\s*%?\s*$",
        lowered,
    )
    if dim_match:
        device = _strip_trailing_polite(dim_match.group("device"))
        level = int(dim_match.group("level"))
        level = max(0, min(100, level))
        if device:
            return SmartThingsHomeCommand(
                kind="device_command",
                raw_target=device,
                display_target=device,
                capability="switchLevel",
                command="setLevel",
                arguments=[level],
            )

    onoff_match = re.search(
        r"\b(?:turn|switch)\s+(?P<state>on|off)\s+(?:the\s+)?(?P<device>.+?)\s*$",
        lowered,
    )
    if not onoff_match:
        onoff_match = re.search(
            r"\b(?:turn|switch)\s+(?:the\s+)?(?P<device>.+?)\s+(?P<state>on|off)\s*$",
            lowered,
        )
    if onoff_match:
        device = _strip_trailing_polite(onoff_match.group("device"))
        state = onoff_match.group("state")
        if device:
            return SmartThingsHomeCommand(
                kind="device_command",
                raw_target=device,
                display_target=device,
                capability="switch",
                command=state,
            )

    lock_match = re.search(
        r"\b(?P<action>lock|unlock)\s+(?:the\s+)?(?P<device>.+?)\s*$",
        lowered,
    )
    if lock_match:
        device = _strip_trailing_polite(lock_match.group("device"))
        action = lock_match.group("action")
        if device:
            return SmartThingsHomeCommand(
                kind="device_command",
                raw_target=device,
                display_target=device,
                capability="lock",
                command=action,
            )

    return None


def _strip_trailing_polite(value: str) -> str:
    text = re.sub(r"[?.!,]+$", "", (value or "").strip())
    text = re.sub(r"\b(please|now|for me)\s*$", "", text).strip()
    return text


class SmartThingsClient:
    def __init__(self):
        self.api_url = (
            os.getenv("SMARTTHINGS_API_URL", DEFAULT_SMARTTHINGS_API_URL).strip().rstrip("/")
            or DEFAULT_SMARTTHINGS_API_URL
        )
        self.token = (os.getenv("SMARTTHINGS_TOKEN") or "").strip()
        self.location_id = (os.getenv("SMARTTHINGS_LOCATION_ID") or "").strip()
        self.aliases = _load_device_aliases()
        try:
            self.timeout_sec = float(os.getenv("SMARTTHINGS_TIMEOUT_SEC", str(DEFAULT_SMARTTHINGS_TIMEOUT_SEC)))
        except Exception:
            self.timeout_sec = DEFAULT_SMARTTHINGS_TIMEOUT_SEC
        self._enabled = os.getenv("SMARTTHINGS_ENABLED", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

        self._devices_cache: List[Dict[str, Any]] = []
        self._devices_cache_ts = 0.0
        self._scenes_cache: List[Dict[str, Any]] = []
        self._scenes_cache_ts = 0.0

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def configured(self) -> bool:
        return bool(self.token)

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        try:
            import aiohttp
        except Exception as e:
            raise SmartThingsError(
                "aiohttp is required for SmartThings calls. Install apps/brain-runtime/requirements.txt."
            ) from e

        url = f"{self.api_url}{path}"
        timeout = aiohttp.ClientTimeout(total=self.timeout_sec)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.request(
                method.upper(),
                url,
                headers=self._headers(),
                json=payload,
            ) as resp:
                raw = (await resp.text()).strip()
                if resp.status >= 400:
                    detail = raw[:220] if raw else f"HTTP {resp.status}"
                    raise SmartThingsError(f"{method.upper()} {path} failed: {detail}")
                if not raw:
                    return {}
                try:
                    return json.loads(raw)
                except Exception:
                    return {}

    async def list_devices(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        now = time.time()
        if (
            not force_refresh
            and self._devices_cache
            and (now - self._devices_cache_ts) < 30.0
        ):
            return list(self._devices_cache)

        data = await self._request_json("GET", "/devices")
        items = data.get("items", []) if isinstance(data, dict) else []
        if not isinstance(items, list):
            items = []
        if self.location_id:
            items = [d for d in items if str(d.get("locationId", "")).strip() == self.location_id]

        self._devices_cache = items
        self._devices_cache_ts = now
        return list(items)

    async def list_scenes(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        now = time.time()
        if (
            not force_refresh
            and self._scenes_cache
            and (now - self._scenes_cache_ts) < 30.0
        ):
            return list(self._scenes_cache)

        data = await self._request_json("GET", "/scenes")
        items = data.get("items", []) if isinstance(data, dict) else []
        if not isinstance(items, list):
            items = []
        if self.location_id:
            items = [s for s in items if str(s.get("locationId", "")).strip() == self.location_id]

        self._scenes_cache = items
        self._scenes_cache_ts = now
        return list(items)

    async def resolve_device(self, target: str) -> Optional[Dict[str, Any]]:
        target_norm = _normalize_name(target)
        if not target_norm:
            return None

        alias_device_id = self.aliases.get(target_norm)
        devices = await self.list_devices()

        if alias_device_id:
            for device in devices:
                if str(device.get("deviceId", "")).strip() == alias_device_id:
                    return device
            # Alias points directly to id even if not currently listed in filtered location
            return {"deviceId": alias_device_id, "label": target}

        # Exact match on label/name first.
        for device in devices:
            label = str(device.get("label", "")).strip()
            name = str(device.get("name", "")).strip()
            if target_norm in {_normalize_name(label), _normalize_name(name)}:
                return device

        # Fuzzy substring fallback.
        for device in devices:
            label = str(device.get("label", "")).strip()
            name = str(device.get("name", "")).strip()
            joined = f"{label} {name}"
            if target_norm and target_norm in _normalize_name(joined):
                return device

        return None

    async def resolve_scene(self, target: str) -> Optional[Dict[str, Any]]:
        target_norm = _normalize_name(target)
        if not target_norm:
            return None

        scenes = await self.list_scenes()
        for scene in scenes:
            name = str(scene.get("sceneName", "")).strip()
            if target_norm == _normalize_name(name):
                return scene
        for scene in scenes:
            name = str(scene.get("sceneName", "")).strip()
            if target_norm in _normalize_name(name):
                return scene
        return None

    async def execute_device_command(self, *, device_id: str, command: SmartThingsHomeCommand) -> None:
        payload = {
            "commands": [
                {
                    "component": command.component or "main",
                    "capability": command.capability,
                    "command": command.command,
                    "arguments": command.arguments or [],
                }
            ]
        }
        await self._request_json("POST", f"/devices/{device_id}/commands", payload=payload)

    async def execute_scene(self, scene_id: str) -> None:
        await self._request_json("POST", f"/scenes/{scene_id}/execute")


def _device_display_name(device: Dict[str, Any], fallback: str) -> str:
    label = str(device.get("label", "")).strip()
    if label:
        return label
    name = str(device.get("name", "")).strip()
    return name or fallback


async def handle_home_control_request(text: str) -> Dict[str, Any]:
    """
    Execute explicit home-control commands through SmartThings.

    Returns:
      {
        "handled": bool,   # parser recognized a direct command
        "success": bool,   # command succeeded
        "text": str,       # user-facing message
      }
    """
    command = parse_home_control_command(text)
    if not command:
        return {"handled": False, "success": False, "text": ""}

    client = SmartThingsClient()
    if not client.enabled:
        return {"handled": False, "success": False, "text": ""}

    if not client.configured:
        return {
            "handled": True,
            "success": False,
            "text": (
                "SmartThings is enabled but not configured. "
                "Set SMARTTHINGS_TOKEN in apps/brain-runtime/.env."
            ),
        }

    try:
        if command.kind == "list_devices":
            devices = await client.list_devices(force_refresh=True)
            if not devices:
                return {
                    "handled": True,
                    "success": True,
                    "text": "SmartThings is connected, but I could not find any devices.",
                }
            names = [_device_display_name(d, "Unnamed device") for d in devices]
            preview = ", ".join(names[:8])
            suffix = "" if len(names) <= 8 else f", and {len(names) - 8} more"
            return {
                "handled": True,
                "success": True,
                "text": f"Your SmartThings devices: {preview}{suffix}.",
            }

        if command.kind == "list_scenes":
            scenes = await client.list_scenes(force_refresh=True)
            if not scenes:
                return {
                    "handled": True,
                    "success": True,
                    "text": "SmartThings is connected, but there are no scenes available.",
                }
            names = [str(scene.get("sceneName", "Unnamed scene")).strip() for scene in scenes]
            preview = ", ".join(names[:8])
            suffix = "" if len(names) <= 8 else f", and {len(names) - 8} more"
            return {
                "handled": True,
                "success": True,
                "text": f"Your SmartThings scenes: {preview}{suffix}.",
            }

        if command.kind == "run_scene":
            scene = await client.resolve_scene(command.raw_target)
            if not scene:
                return {
                    "handled": True,
                    "success": False,
                    "text": (
                        f"I couldn't find a SmartThings scene named '{command.display_target}'. "
                        "Try saying 'list scenes'."
                    ),
                }
            await client.execute_scene(str(scene.get("sceneId")))
            scene_name = str(scene.get("sceneName", command.display_target)).strip()
            return {"handled": True, "success": True, "text": f"Ran the '{scene_name}' scene."}

        if command.kind == "device_command":
            device = await client.resolve_device(command.raw_target)
            if not device:
                return {
                    "handled": True,
                    "success": False,
                    "text": (
                        f"I couldn't find a SmartThings device named '{command.display_target}'. "
                        "Try saying 'list devices' or add SMARTTHINGS_DEVICE_ALIASES."
                    ),
                }
            device_id = str(device.get("deviceId", "")).strip()
            await client.execute_device_command(device_id=device_id, command=command)
            device_name = _device_display_name(device, command.display_target)
            verb = command.command
            if command.command == "setLevel" and command.arguments:
                verb = f"set to {command.arguments[0]}%"
            return {
                "handled": True,
                "success": True,
                "text": f"Done. {device_name} {verb}.",
            }
    except SmartThingsError as e:
        return {"handled": True, "success": False, "text": f"SmartThings error: {e}"}
    except Exception as e:
        return {"handled": True, "success": False, "text": f"SmartThings request failed: {e}"}

    return {"handled": True, "success": False, "text": "I could not run that SmartThings command."}
