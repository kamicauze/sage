import aiohttp
import json
from typing import AsyncIterator, Optional, Callable, Awaitable

# Global connection pool for reuse (reduces connection overhead)
_connector = None
_session = None

def _get_connector():
    global _connector
    if _connector is None or _connector.closed:
        _connector = aiohttp.TCPConnector(
            limit=10,
            keepalive_timeout=60,
            enable_cleanup_closed=True
        )
    return _connector

async def _get_session():
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(connector=_get_connector())
    return _session


async def ollama_chat(base_url, model, messages, format_json=False, options=None):
    """
    Sends a chat message to an Ollama server (non-streaming, for backward compatibility).
    """
    if options is None: options = {}
    
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": options
    }
    
    if format_json:
        payload["format"] = "json"

    session = await _get_session()
    async with session.post(f"{base_url}/api/chat", json=payload) as resp:
        if resp.status != 200:
            text = await resp.text()
            raise Exception(f"Ollama error ({model}) {resp.status}: {text}")
        
        data = await resp.json()
        return data.get("message", {}).get("content", "")


async def ollama_chat_stream(
    base_url: str,
    model: str,
    messages: list,
    options: dict = None,
    on_token: Optional[Callable[[str], Awaitable[None]]] = None,
    format_json: bool = False
) -> str:
    """
    Streaming chat for low-latency responses.
    Calls on_token callback as each token arrives.
    Returns the full response when complete.

    Args:
        base_url: Ollama server URL
        model: Model name
        messages: Chat messages
        options: Ollama options (temperature, etc.)
        on_token: Async callback called with each token as it arrives
        format_json: Whether to enforce JSON output format

    Returns:
        Complete response text
    """
    if options is None:
        options = {}

    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": options
    }

    if format_json:
        payload["format"] = "json"

    full_response = ""
    session = await _get_session()

    import time
    start_time = time.time()
    first_token_time = None
    token_count = 0

    async with session.post(f"{base_url}/api/chat", json=payload) as resp:
        if resp.status != 200:
            text = await resp.text()
            raise Exception(f"Ollama error ({model}) {resp.status}: {text}")

        async for line in resp.content:
            if not line:
                continue
            try:
                chunk = json.loads(line.decode('utf-8'))
                token = chunk.get("message", {}).get("content", "")
                if token:
                    if first_token_time is None:
                        first_token_time = time.time()
                        print(f"[Ollama] First token: {int((first_token_time - start_time) * 1000)}ms")
                    token_count += 1
                    full_response += token
                    if on_token:
                        await on_token(token)

                # Check if done
                if chunk.get("done", False):
                    break
            except json.JSONDecodeError:
                continue

    total_time = time.time() - start_time
    if token_count > 0:
        tokens_per_sec = token_count / total_time
        print(f"[Ollama] Generated {token_count} tokens in {int(total_time * 1000)}ms ({tokens_per_sec:.1f} tok/s)")

    return full_response


async def ollama_chat_stream_iter(
    base_url: str,
    model: str,
    messages: list,
    options: dict = None,
    format_json: bool = False
) -> AsyncIterator[str]:
    """
    Async generator that yields tokens as they arrive.
    Useful for piping directly to TTS.
    """
    if options is None:
        options = {}

    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": options
    }

    if format_json:
        payload["format"] = "json"

    session = await _get_session()
    
    async with session.post(f"{base_url}/api/chat", json=payload) as resp:
        if resp.status != 200:
            text = await resp.text()
            raise Exception(f"Ollama error ({model}) {resp.status}: {text}")
        
        async for line in resp.content:
            if not line:
                continue
            try:
                chunk = json.loads(line.decode('utf-8'))
                token = chunk.get("message", {}).get("content", "")
                if token:
                    yield token
                
                if chunk.get("done", False):
                    break
            except json.JSONDecodeError:
                continue









