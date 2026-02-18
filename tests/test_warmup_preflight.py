import asyncio
import importlib
import os
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch

# Allow importing warmup.py in lightweight test environments where runtime deps
# (aiohttp/paho) are not installed.
try:
    importlib.import_module("aiohttp")
except ModuleNotFoundError:
    aiohttp_stub = types.ModuleType("aiohttp")
    aiohttp_stub.ClientSession = object
    sys.modules["aiohttp"] = aiohttp_stub

try:
    importlib.import_module("dotenv")
except ModuleNotFoundError:
    dotenv_stub = types.ModuleType("dotenv")

    def _noop_load_dotenv(*args, **kwargs):
        return False

    dotenv_stub.load_dotenv = _noop_load_dotenv
    sys.modules["dotenv"] = dotenv_stub

try:
    importlib.import_module("paho.mqtt.client")
except ModuleNotFoundError:
    paho_module = types.ModuleType("paho")
    mqtt_module = types.ModuleType("paho.mqtt")
    mqtt_client_module = types.ModuleType("paho.mqtt.client")

    class _DummyClient:
        def connect(self, *args, **kwargs):
            return 0

        def disconnect(self):
            return 0

    mqtt_client_module.Client = _DummyClient
    paho_module.mqtt = mqtt_module
    mqtt_module.client = mqtt_client_module
    sys.modules["paho"] = paho_module
    sys.modules["paho.mqtt"] = mqtt_module
    sys.modules["paho.mqtt.client"] = mqtt_client_module

import brain.ai.warmup as warmup


class WarmupPreflightTests(unittest.TestCase):
    def test_invalid_tts_engine_is_critical(self):
        with patch.dict(os.environ, {"TTS_ENGINE": "not-real"}, clear=True):
            result = warmup.validate_runtime_config()

        self.assertFalse(result["ok"])
        self.assertTrue(any("TTS_ENGINE" in issue for issue in result["critical"]))

    def test_qwen_requires_model_when_fallback_disabled(self):
        env = {
            "TTS_ENGINE": "qwen",
            "TTS_AUTO_FALLBACK": "false",
        }
        with patch.dict(os.environ, env, clear=True):
            result = warmup.validate_runtime_config()

        self.assertFalse(result["ok"])
        self.assertTrue(any("QWEN_TTS_MODEL" in issue for issue in result["critical"]))

    def test_qwen_missing_model_warns_when_fallback_enabled(self):
        env = {
            "TTS_ENGINE": "qwen",
            "TTS_AUTO_FALLBACK": "true",
        }
        with patch.dict(os.environ, env, clear=True):
            result = warmup.validate_runtime_config()

        self.assertTrue(result["ok"])
        self.assertTrue(any("QWEN_TTS_MODEL" in issue for issue in result["warnings"]))

    def test_invalid_stt_silence_duration_is_critical(self):
        with patch.dict(os.environ, {"STT_SILENCE_DURATION": "not-a-number"}, clear=True):
            result = warmup.validate_runtime_config()

        self.assertFalse(result["ok"])
        self.assertTrue(any("STT_SILENCE_DURATION" in issue for issue in result["critical"]))

    def test_run_preflight_fails_on_critical_config_error(self):
        with patch.dict(os.environ, {"TTS_ENGINE": "bad-engine"}, clear=True):
            with patch.object(warmup, "check_ollama", new=AsyncMock(return_value=True)):
                with patch.object(warmup, "check_mqtt", new=AsyncMock(return_value=True)):
                    with patch.object(warmup, "check_cloud", new=AsyncMock(return_value=True)):
                        ok = asyncio.run(warmup.run_preflight_checks())

        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
