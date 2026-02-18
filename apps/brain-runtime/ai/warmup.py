import os
import asyncio
import aiohttp
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

# Load .env from brain directory
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in TRUE_VALUES


def _parse_env_bool(name: str, default: bool):
    value = os.getenv(name)
    if value is None:
        return default, True

    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True, True
    if normalized in FALSE_VALUES:
        return False, True
    return default, False


def _is_non_placeholder_key(key: str | None) -> bool:
    if not key:
        return False

    normalized = key.strip().lower()
    if not normalized:
        return False
    if "your_" in normalized or "placeholder" in normalized:
        return False
    return True


def validate_runtime_config():
    critical = []
    warnings = []

    tts_engine = (os.getenv("TTS_ENGINE", "kokoro") or "kokoro").strip().lower()
    if tts_engine not in {"kokoro", "f5", "qwen"}:
        critical.append(
            f"TTS_ENGINE='{tts_engine}' is invalid (allowed: kokoro|f5|qwen)."
        )

    auto_fallback, fallback_valid = _parse_env_bool("TTS_AUTO_FALLBACK", True)
    if not fallback_valid:
        warnings.append(
            "TTS_AUTO_FALLBACK is not a valid boolean; treating it as enabled."
        )

    if tts_engine == "qwen":
        qwen_model = (os.getenv("QWEN_TTS_MODEL") or "").strip()
        if not qwen_model:
            message = "TTS_ENGINE=qwen requires QWEN_TTS_MODEL to be set."
            if auto_fallback:
                warnings.append(
                    message + " Speaker will fallback to another engine if available."
                )
            else:
                critical.append(message + " Auto-fallback is disabled.")
        elif not os.path.isdir(qwen_model):
            message = f"QWEN_TTS_MODEL path not found: {qwen_model}"
            if auto_fallback:
                warnings.append(
                    message + " Speaker will fallback to another engine if available."
                )
            else:
                critical.append(message + " Auto-fallback is disabled.")

    stt_model_path = (os.getenv("STT_MODEL_PATH") or "").strip()
    if stt_model_path and not os.path.isdir(stt_model_path):
        warnings.append(
            f"STT_MODEL_PATH does not exist: {stt_model_path}. Transcriber may fail to load."
        )

    _, stream_tts_valid = _parse_env_bool("SAGE_STREAM_TTS", True)
    if not stream_tts_valid:
        warnings.append(
            "SAGE_STREAM_TTS is not a valid boolean (use true/false)."
        )

    silence_value = (os.getenv("STT_SILENCE_DURATION", "0.5") or "0.5").strip()
    try:
        silence_duration = float(silence_value)
        if silence_duration < 0.2 or silence_duration > 2.0:
            warnings.append(
                f"STT_SILENCE_DURATION={silence_duration} is outside recommended range (0.2-2.0)."
            )
    except ValueError:
        critical.append(
            f"STT_SILENCE_DURATION must be a number; got '{silence_value}'."
        )

    return {
        "ok": len(critical) == 0,
        "critical": critical,
        "warnings": warnings,
    }


async def check_runtime_config():
    print("Checking Runtime Config...", end=" ", flush=True)
    result = validate_runtime_config()
    if result["ok"] and not result["warnings"]:
        print("✅ VALID")
        return result

    if result["ok"]:
        print("⚠️ WARNINGS")
    else:
        print("❌ INVALID")

    for issue in result["critical"]:
        print(f"  - CRITICAL: {issue}")
    for issue in result["warnings"]:
        print(f"  - WARNING: {issue}")
    return result

async def check_ollama():
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    print(f"Checking Ollama at {host}...", end=" ", flush=True)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{host}/api/tags") as resp:
                if resp.status == 200:
                    print("✅ ONLINE")
                    return True
                else:
                    print(f"❌ ERROR ({resp.status})")
                    return False
    except Exception as e:
        print(f"❌ OFFLINE ({str(e)})")
        return False

async def check_cloud(require_key: bool = False):
    grok_key = os.getenv("XAI_API_KEY") or os.getenv("GROK_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    print("Checking Cloud APIs...", end=" ", flush=True)
    status = []
    has_grok_key = _is_non_placeholder_key(grok_key)
    has_openai_key = _is_non_placeholder_key(openai_key)

    if has_grok_key:
        status.append("Grok: ✅")
    else:
        status.append("Grok: ⚠️ (Missing/Default Key)")
        
    if has_openai_key:
        status.append("OpenAI: ✅")
    else:
        status.append("OpenAI: ⚠️ (Missing/Default Key)")
        
    print(", ".join(status))
    if require_key:
        return has_grok_key or has_openai_key
    return True # Non-blocking in mixed/local mode

async def check_mqtt():
    host = os.getenv("MQTT_HOST", "localhost")
    port_raw = os.getenv("MQTT_PORT", "1883")
    try:
        port = int(port_raw)
    except ValueError:
        print(f"Checking MQTT Broker at {host}:{port_raw}...", end=" ", flush=True)
        print("❌ FAILED (MQTT_PORT must be an integer)")
        return False

    print(f"Checking MQTT Broker at {host}:{port}...", end=" ", flush=True)
    
    client = mqtt.Client()
    try:
        # paho-mqtt connect uses keepalive (in seconds) as the 3rd argument, not a timeout keyword
        client.connect(host, port, 5)
        print("✅ CONNECTED")
        client.disconnect()
        return True
    except Exception as e:
        print(f"❌ FAILED ({str(e)})")
        return False

async def run_preflight_checks():
    print("\n" + "="*40)
    print("✈️  SAGE PRE-FLIGHT CHECKLIST")
    print("="*40)
    config_result = await check_runtime_config()

    force_cloud_reasoning = _env_flag("SAGE_FORCE_CLOUD_REASONING", False)
    if force_cloud_reasoning:
        print("Cloud-only reasoning mode enabled: skipping Ollama health check.")
        cloud_ok, mqtt_ok = await asyncio.gather(
            check_cloud(require_key=True),
            check_mqtt(),
        )
        print("="*40)
        if config_result["ok"] and cloud_ok and mqtt_ok:
            print("🟢 ALL SYSTEMS GO. CLEARED FOR TAKEOFF.\n")
            return True
        print("🔴 CRITICAL CHECKS FAILED. REVIEW PRE-FLIGHT OUTPUT.\n")
        return False

    ollama_ok, mqtt_ok, _ = await asyncio.gather(
        check_ollama(),
        check_mqtt(),
        check_cloud()
    )

    print("="*40)
    if config_result["ok"] and ollama_ok and mqtt_ok: # Ollama and MQTT are critical in mixed/local mode
        print("🟢 ALL SYSTEMS GO. CLEARED FOR TAKEOFF.\n")
        return True
    print("🔴 CRITICAL CHECKS FAILED. REVIEW PRE-FLIGHT OUTPUT.\n")
    return False

if __name__ == "__main__":
    asyncio.run(run_preflight_checks())
