import os
import aiohttp
import json
import time
import logging
from datetime import datetime
from typing import Callable, Awaitable, Optional
from dotenv import load_dotenv

# Load environment variables when this module is imported
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# Audit logger — writes to a dedicated file for later review
_audit_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(_audit_dir, exist_ok=True)
_audit_logger = logging.getLogger("cloud_audit")
_audit_logger.setLevel(logging.INFO)
_audit_logger.propagate = False
if not _audit_logger.handlers:
    _fh = logging.FileHandler(os.path.join(_audit_dir, "cloud_audit.jsonl"), encoding="utf-8")
    _fh.setFormatter(logging.Formatter("%(message)s"))
    _audit_logger.addHandler(_fh)


def _audit(entry: dict):
    """Append a JSON-lines audit record."""
    entry["ts"] = datetime.now().isoformat()
    try:
        _audit_logger.info(json.dumps(entry, ensure_ascii=False))
    except Exception:
        pass


class CloudBrain:
    """
    Handles connections to high-level cloud models (Grok, OpenAI).
    """
    def __init__(self):
        # Grok usually uses an OpenAI-compatible endpoint
        self.grok_key = os.getenv("XAI_API_KEY") or os.getenv("GROK_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.grok_base_url = "https://api.x.ai/v1" # Standard Grok endpoint

    async def _check_and_update_budget(self, cost_delta: float = 0.0):
        """
        Reads/Writes to the shared architect/usage.json file.
        This unifies budget logic between Architect and Brain.
        """
        usage_file = "architect/usage.json"
        now_key = datetime.now().strftime("%Y-%m")
        limit = 120.0 # From sage.yaml (hardcoded fallback)

        # Load
        if not os.path.exists(usage_file):
            data = {}
        else:
            try:
                with open(usage_file, 'r') as f:
                    data = json.load(f)
            except:
                data = {}

        current = data.get(now_key, 0.0)

        # Check Pre-flight
        if cost_delta == 0.0 and current >= limit:
            raise Exception(f"Budget exceeded (${current:.2f} >= ${limit})")

        # Update
        if cost_delta > 0.0:
            data[now_key] = current + cost_delta
            try:
                os.makedirs(os.path.dirname(usage_file), exist_ok=True)
                with open(usage_file, 'w') as f:
                    json.dump(data, f, indent=2)
            except Exception as e:
                print(f"[Budget] Failed to save usage: {e}")

    def _resolve_provider(self, provider, model=None):
        """Resolve API key, base URL, and model for a provider."""
        if provider == "grok":
            api_key = self.grok_key
            if not api_key:
                raise Exception("XAI_API_KEY or GROK_API_KEY not found in environment variables. Please add it to your .env file.")
            base_url = self.grok_base_url
            model = model or "grok-4"
        else:
            api_key = self.openai_key
            if not api_key:
                raise Exception("OPENAI_API_KEY not found in environment variables. Please add it to your .env file.")
            base_url = "https://api.openai.com/v1"
            model = model or "gpt-4-turbo"
        return api_key, base_url, model

    async def chat(self, provider, messages, model=None):
        await self._check_and_update_budget(0.0)
        api_key, base_url, model = self._resolve_provider(provider, model)

        # Audit request
        _audit({
            "event": "request",
            "provider": provider,
            "model": model,
            "streaming": False,
            "messages": messages,
        })

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.8
        }

        start_time = time.time()
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{base_url}/chat/completions", headers=headers, json=payload) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise Exception(f"{provider} error: {resp.status} - {text}")

                data = await resp.json()
                content = data['choices'][0]['message']['content']

                usage = data.get('usage', {})
                p_toks = usage.get('prompt_tokens', 0)
                c_toks = usage.get('completion_tokens', 0)
                cost = (p_toks * 2.50 / 1e6) + (c_toks * 10.00 / 1e6)

                await self._check_and_update_budget(cost)
                elapsed = time.time() - start_time
                print(f"[Cloud] {provider} Cost: ${cost:.5f}")

                # Audit response
                _audit({
                    "event": "response",
                    "provider": provider,
                    "model": model,
                    "streaming": False,
                    "elapsed_ms": int(elapsed * 1000),
                    "prompt_tokens": p_toks,
                    "completion_tokens": c_toks,
                    "cost": cost,
                    "response": content,
                })

                return content

    async def chat_stream(
        self,
        provider,
        messages,
        model=None,
        on_token: Optional[Callable[[str], Awaitable[None]]] = None,
    ):
        """
        Streaming variant of chat(). Uses SSE to deliver tokens as they arrive.
        Falls back to non-streaming chat() if on_token is None.
        """
        if on_token is None:
            return await self.chat(provider, messages, model=model)

        await self._check_and_update_budget(0.0)
        api_key, base_url, model = self._resolve_provider(provider, model)

        # Audit request
        _audit({
            "event": "request",
            "provider": provider,
            "model": model,
            "streaming": True,
            "messages": messages,
        })

        print(f"[Cloud:{provider}] Starting SSE stream (model={model})")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.8,
            "stream": True,
        }

        full_content = ""
        first_token_time = None
        token_count = 0
        start_time = time.time()

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise Exception(f"{provider} error: {resp.status} - {text}")

                buffer = ""
                async for chunk in resp.content.iter_any():
                    buffer += chunk.decode("utf-8", errors="replace")

                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()

                        if not line or not line.startswith("data: "):
                            continue

                        data_str = line[6:]  # strip "data: " prefix

                        if data_str == "[DONE]":
                            break

                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        delta = data.get("choices", [{}])[0].get("delta", {})
                        token = delta.get("content")

                        if token:
                            if first_token_time is None:
                                first_token_time = time.time()
                                ttft_ms = int((first_token_time - start_time) * 1000)
                                print(f"[Cloud:{provider}] First token at {ttft_ms}ms")
                            token_count += 1
                            full_content += token
                            await on_token(token)

        elapsed = time.time() - start_time
        ttft = (first_token_time - start_time) if first_token_time else elapsed
        words = len(full_content.split())
        print(
            f"[Cloud:{provider}] Stream done: {words} words ({token_count} tokens), "
            f"TTFT={ttft:.2f}s, total={elapsed:.2f}s"
        )

        # Estimate cost
        est_completion_tokens = int(words * 1.3)
        cost = est_completion_tokens * 10.00 / 1e6
        await self._check_and_update_budget(cost)
        print(f"[Cloud] {provider} Est. Cost: ${cost:.5f}")

        # Audit response
        _audit({
            "event": "response",
            "provider": provider,
            "model": model,
            "streaming": True,
            "elapsed_ms": int(elapsed * 1000),
            "ttft_ms": int(ttft * 1000),
            "token_count": token_count,
            "word_count": words,
            "cost": cost,
            "response": full_content,
        })

        return full_content

cloud_brain = CloudBrain()
