import json
import os
import time
from typing import Awaitable, Callable, Optional

import aiohttp

from .ollama_client import ollama_chat, ollama_chat_stream


_connector = None
_session = None


def _get_connector():
    global _connector
    if _connector is None or _connector.closed:
        _connector = aiohttp.TCPConnector(
            limit=10,
            keepalive_timeout=60,
            enable_cleanup_closed=True,
        )
    return _connector


async def _get_session():
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(connector=_get_connector())
    return _session


def get_local_llm_backend() -> str:
    backend = (os.getenv("SAGE_LOCAL_LLM_BACKEND", "ollama") or "ollama").strip().lower()
    if backend not in {"ollama", "mlx"}:
        print(f"[LLM] Unknown SAGE_LOCAL_LLM_BACKEND='{backend}', falling back to 'ollama'")
        return "ollama"
    return backend


def get_local_llm_base_url(backend: Optional[str] = None, tier: Optional[str] = None) -> str:
    resolved = backend or get_local_llm_backend()
    tier_key = (tier or "").strip().lower()
    if resolved == "mlx":
        if tier_key == "fast":
            return (
                os.getenv("MLX_HOST_FAST")
                or os.getenv("MLX_HOST")
                or "http://127.0.0.1:8080"
            ).rstrip("/")
        if tier_key == "mid":
            return (
                os.getenv("MLX_HOST_MID")
                or os.getenv("MLX_HOST")
                or "http://127.0.0.1:8080"
            ).rstrip("/")
        if tier_key == "deep":
            return (
                os.getenv("MLX_HOST_DEEP")
                or os.getenv("MLX_HOST_MID")
                or os.getenv("MLX_HOST")
                or "http://127.0.0.1:8080"
            ).rstrip("/")
        return (os.getenv("MLX_HOST", "http://127.0.0.1:8080") or "http://127.0.0.1:8080").rstrip("/")

    if tier_key == "fast":
        return (os.getenv("OLLAMA_HOST_FAST") or os.getenv("OLLAMA_HOST") or "http://localhost:11434").rstrip("/")
    if tier_key == "mid":
        return (os.getenv("OLLAMA_HOST_MID") or os.getenv("OLLAMA_HOST") or "http://localhost:11434").rstrip("/")
    if tier_key == "deep":
        return (
            os.getenv("OLLAMA_HOST_DEEP")
            or os.getenv("OLLAMA_HOST_MID")
            or os.getenv("OLLAMA_HOST")
            or "http://localhost:11434"
        ).rstrip("/")
    return (os.getenv("OLLAMA_HOST", "http://localhost:11434") or "http://localhost:11434").rstrip("/")


def _resolve_model(model: Optional[str], backend: str, tier: Optional[str] = None) -> str:
    if model and str(model).strip():
        return str(model).strip()
    tier_key = (tier or "").strip().lower()
    if backend == "mlx":
        if tier_key == "fast":
            return (
                os.getenv("MLX_MODEL_FAST")
                or os.getenv("MLX_MODEL")
                or os.getenv("MLX_MODEL_MID")
                or "mlx-community/Qwen2.5-3B-Instruct-4bit"
            )
        if tier_key == "deep":
            return (
                os.getenv("MLX_MODEL_DEEP")
                or os.getenv("MLX_MODEL_MID")
                or os.getenv("MLX_MODEL")
                or "mlx-community/Qwen2.5-7B-Instruct-4bit"
            )
        return (
            os.getenv("MLX_MODEL")
            or os.getenv("MLX_MODEL_MID")
            or os.getenv("MLX_MODEL_FAST")
            or "mlx-community/Qwen2.5-3B-Instruct-4bit"
        )
    if tier_key == "fast":
        return os.getenv("OLLAMA_MODEL_FAST", "qwen2.5:3b")
    if tier_key == "deep":
        return os.getenv("OLLAMA_MODEL_DEEP") or os.getenv("OLLAMA_MODEL_MID", "gemma3:12b")
    if tier_key == "mid":
        return os.getenv("OLLAMA_MODEL_MID", "gemma3:12b")
    return os.getenv("OLLAMA_MODEL_FAST", "qwen2.5:3b")


def _mlx_chat_endpoint() -> str:
    endpoint = (os.getenv("MLX_CHAT_ENDPOINT", "/v1/chat/completions") or "/v1/chat/completions").strip()
    if not endpoint.startswith("/"):
        endpoint = f"/{endpoint}"
    return endpoint


def _mlx_headers() -> dict:
    headers = {"Content-Type": "application/json"}
    api_key = (os.getenv("MLX_API_KEY") or "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _to_openai_payload(
    model: str,
    messages: list,
    stream: bool,
    options: Optional[dict] = None,
    format_json: bool = False,
) -> dict:
    options = options or {}
    payload = {
        "model": model,
        "messages": messages,
        "stream": stream,
        "temperature": options.get("temperature", 0.2),
    }

    num_predict = options.get("num_predict")
    if isinstance(num_predict, int) and num_predict > 0:
        payload["max_tokens"] = num_predict

    if format_json:
        payload["response_format"] = {"type": "json_object"}

    return payload


def _extract_openai_text(data: dict) -> str:
    try:
        choices = data.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            chunks = [part.get("text", "") for part in content if isinstance(part, dict)]
            return "".join(chunks)
        return str(content or "")
    except Exception:
        return ""


async def _mlx_chat(
    base_url: str,
    model: str,
    messages: list,
    format_json: bool = False,
    options: Optional[dict] = None,
) -> str:
    endpoint = _mlx_chat_endpoint()
    payload = _to_openai_payload(model, messages, stream=False, options=options, format_json=format_json)
    session = await _get_session()
    async with session.post(f"{base_url}{endpoint}", json=payload, headers=_mlx_headers()) as resp:
        if resp.status != 200:
            text = await resp.text()
            raise Exception(f"MLX error ({model}) {resp.status}: {text}")
        data = await resp.json()
        return _extract_openai_text(data)


async def _mlx_chat_stream(
    base_url: str,
    model: str,
    messages: list,
    options: Optional[dict] = None,
    on_token: Optional[Callable[[str], Awaitable[None]]] = None,
    format_json: bool = False,
) -> str:
    endpoint = _mlx_chat_endpoint()
    payload = _to_openai_payload(model, messages, stream=True, options=options, format_json=format_json)
    session = await _get_session()

    full_response = ""
    start_time = time.time()
    first_token_time = None
    token_count = 0
    buffer = ""
    saw_stream_chunks = False

    async with session.post(f"{base_url}{endpoint}", json=payload, headers=_mlx_headers()) as resp:
        if resp.status != 200:
            text = await resp.text()
            raise Exception(f"MLX error ({model}) {resp.status}: {text}")

        async for raw in resp.content:
            if not raw:
                continue
            buffer += raw.decode("utf-8", errors="ignore")

            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if not line:
                    continue

                # OpenAI/MLX stream format: "data: {...}" lines with final "data: [DONE]"
                if line.startswith("data:"):
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    saw_stream_chunks = True
                else:
                    data_str = line

                try:
                    chunk = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                token = ""
                choices = chunk.get("choices") or []
                if choices:
                    delta = choices[0].get("delta") or {}
                    token = delta.get("content") or ""

                if token:
                    if first_token_time is None:
                        first_token_time = time.time()
                        print(f"[MLX] First token: {int((first_token_time - start_time) * 1000)}ms")
                    token_count += 1
                    full_response += token
                    if on_token:
                        await on_token(token)

    # Some servers ignore `stream=true` and return one JSON payload.
    if not full_response and not saw_stream_chunks and buffer.strip():
        try:
            data = json.loads(buffer.strip())
            full_response = _extract_openai_text(data)
        except json.JSONDecodeError:
            pass

    total_time = time.time() - start_time
    if token_count > 0 and total_time > 0:
        print(f"[MLX] Generated {token_count} tokens in {int(total_time * 1000)}ms ({token_count / total_time:.1f} tok/s)")
    return full_response


async def local_chat(
    model: str,
    messages: list,
    format_json: bool = False,
    options: Optional[dict] = None,
    tier: Optional[str] = None,
) -> str:
    backend = get_local_llm_backend()
    resolved_model = _resolve_model(model, backend, tier=tier)
    base_url = get_local_llm_base_url(backend, tier=tier)

    if backend == "mlx":
        return await _mlx_chat(
            base_url=base_url,
            model=resolved_model,
            messages=messages,
            format_json=format_json,
            options=options,
        )

    return await ollama_chat(
        base_url=base_url,
        model=resolved_model,
        messages=messages,
        format_json=format_json,
        options=options,
    )


async def local_chat_stream(
    model: str,
    messages: list,
    options: Optional[dict] = None,
    on_token: Optional[Callable[[str], Awaitable[None]]] = None,
    format_json: bool = False,
    tier: Optional[str] = None,
) -> str:
    backend = get_local_llm_backend()
    resolved_model = _resolve_model(model, backend, tier=tier)
    base_url = get_local_llm_base_url(backend, tier=tier)

    if backend == "mlx":
        return await _mlx_chat_stream(
            base_url=base_url,
            model=resolved_model,
            messages=messages,
            options=options,
            on_token=on_token,
            format_json=format_json,
        )

    return await ollama_chat_stream(
        base_url=base_url,
        model=resolved_model,
        messages=messages,
        options=options,
        on_token=on_token,
        format_json=format_json,
    )
