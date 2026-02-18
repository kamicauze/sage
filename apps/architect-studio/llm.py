import os
import json
import shlex
import subprocess
import requests
import time
from datetime import datetime
from typing import List, Dict, Generator, Union
from architect.paths import BRAIN_ENV_FILE, USAGE_FILE as USAGE_FILE_PATH, USAGE_LOG_FILE as USAGE_LOG_FILE_PATH

# Load environment variables from brain/.env
try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency fallback
    def load_dotenv(*args, **kwargs):
        return False

load_dotenv(str(BRAIN_ENV_FILE))  # Load from brain directory

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_MODEL = "gemma3:12b"
USAGE_FILE = USAGE_FILE_PATH
USAGE_LOG_FILE = USAGE_LOG_FILE_PATH

class BudgetExceededError(Exception):
    pass

class LLMClient:
    def __init__(self, model: str = DEFAULT_MODEL, budget_limit: float = 120.0):
        self.model = model
        self.base_url = f"{OLLAMA_HOST}/api/chat"
        self.budget_limit = budget_limit
        self.request_timeout = float(os.getenv("LLM_HTTP_TIMEOUT_SEC", "120"))
        self.rates = {
            "gemma3:12b": {"input": 0.0, "output": 0.0},
            # Add other models here clearly
        }

    def _get_usage_key(self):
        return datetime.now().strftime("%Y-%m")

    def _load_usage(self) -> float:
        if not USAGE_FILE.exists():
            return 0.0
        try:
            with open(USAGE_FILE, 'r') as f:
                data = json.load(f)
            return data.get(self._get_usage_key(), 0.0)
        except Exception:
            return 0.0

    def _log_usage(self, provider: str, model: str, input_tokens: int, output_tokens: int, cost: float, task: str = "unknown"):
        """Log detailed usage to JSONL file for analysis."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "provider": provider,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": cost,
            "task": task
        }

        USAGE_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(USAGE_LOG_FILE, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')

    def _update_usage(self, cost: float):
        key = self._get_usage_key()
        if not USAGE_FILE.exists():
            data = {}
        else:
            try:
                with open(USAGE_FILE, 'r') as f:
                    data = json.load(f)
            except Exception:
                data = {}

        current = data.get(key, 0.0)
        data[key] = current + cost

        USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(USAGE_FILE, 'w') as f:
            json.dump(data, f, indent=2)

    def _check_budget(self):
        current_spend = self._load_usage()
        if current_spend >= self.budget_limit:
            raise BudgetExceededError(f"Monthly budget limit of ${self.budget_limit} reached. Current spend: ${current_spend:.2f}")

    def _messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """Flatten role-based chat messages into a plain prompt for CLI tools."""
        parts = []
        for msg in messages:
            role = msg.get("role", "user").upper()
            content = msg.get("content", "")
            parts.append(f"[{role}]\n{content}")
        return "\n\n".join(parts).strip()

    def _chat_external_cli(self, messages: List[Dict[str, str]], model: str, provider: str) -> str:
        """
        Call an external coding-agent CLI via a user-provided command template.

        Expected contract:
        - Command reads prompt text from stdin
        - Command prints final answer to stdout
        """
        env_var = {
            "codex_cli": "SAGE_CODEX_CLI_CMD",
            "claude_cli": "SAGE_CLAUDE_CLI_CMD",
        }.get(provider)

        if not env_var:
            return f"Error: Unsupported CLI provider '{provider}'."

        cmd_template = os.getenv(env_var, "").strip()
        if not cmd_template:
            return (
                f"Error: {env_var} not configured. "
                f"Set it to a command that reads prompt from stdin and writes response to stdout."
            )

        try:
            cmd = shlex.split(cmd_template)
        except ValueError as e:
            return f"Error: Invalid {env_var} command syntax: {e}"

        prompt = self._messages_to_prompt(messages)
        if model:
            prompt = f"[MODEL]\n{model}\n\n{prompt}"

        try:
            print(f"[LLM] Sending request to external CLI provider '{provider}'...")
            result = subprocess.run(
                cmd,
                input=prompt,
                text=True,
                capture_output=True,
                timeout=self.request_timeout,
            )
        except FileNotFoundError:
            return f"Error: CLI executable not found for {provider}. Command: {cmd_template}"
        except subprocess.TimeoutExpired:
            return f"Error: External CLI timeout for {provider} after {self.request_timeout}s"
        except Exception as e:
            return f"Error calling external CLI ({provider}): {e}"

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            return f"Error calling external CLI ({provider}): {stderr or f'exit code {result.returncode}'}"

        content = (result.stdout or "").strip()
        if not content:
            return f"Error calling external CLI ({provider}): empty response"

        self._log_usage(provider, model or provider, 0, 0, 0.0, "cli")
        self._update_usage(0.0)
        return content

    def chat(self, messages: List[Dict[str, str]], stream: bool = False, provider: str = "ollama", model: str = None) -> str:
        """
        Send a chat request to the LLM.
        """
        # Pre-check budget before making any API calls
        try:
            self._check_budget()
        except BudgetExceededError as e:
            return f"Error: {e}"
        
        if provider == "openai":
            result = self._chat_openai(messages, model)
        elif provider == "anthropic":
            result = self._chat_anthropic(messages, model)
        elif provider == "xai":
            result = self._chat_openai(messages, model, base_url="https://api.x.ai/v1")
        elif provider == "google":
            result = self._chat_google(messages, model)
        elif provider in ("codex_cli", "claude_cli"):
            result = self._chat_external_cli(messages, model, provider)
        else:
            result = None

        # Fallback to Ollama only for cloud API providers.
        # External CLI providers should return explicit errors directly.
        cloud_providers = {"openai", "anthropic", "xai", "google"}
        if provider in cloud_providers and isinstance(result, str) and result.strip().lower().startswith("error"):
            print(f"[LLM] Cloud provider failed, falling back to Ollama...")
            return self._chat_ollama(messages, model or self.model, stream)

        if result:
            return result

        # Default: Ollama
        return self._chat_ollama(messages, model or self.model, stream)

    def _chat_ollama(self, messages, model, stream=False):
        """Handle Ollama API calls."""
        payload = {
            "model": model or self.model,
            "messages": messages,
            "stream": stream,
            "options": {"temperature": 0.2, "num_ctx": 8192}
        }
        
        try:
            print(f"[LLM] Sending request to {model or self.model} (Ollama)...")
            response = requests.post(
                self.base_url,
                json=payload,
                stream=stream,
                timeout=self.request_timeout,
            )
            response.raise_for_status()

            if stream:
                # Streaming response
                content = ""
                for line in response.iter_lines():
                    if line:
                        chunk = json.loads(line)
                        if "message" in chunk and "content" in chunk["message"]:
                            delta = chunk["message"]["content"]
                            content += delta
                            print(delta, end='', flush=True)
                        if chunk.get("done", False):
                            # Extract token counts if available
                            if "eval_count" in chunk:
                                output_tokens = chunk.get("eval_count", 0)
                                input_tokens = chunk.get("prompt_eval_count", 0)
                                self._log_usage("ollama", model, input_tokens, output_tokens, 0.0, "streaming")
                                print(f"\n[LLM] Ollama FREE (Input: {input_tokens:,} tokens, Output: {output_tokens:,} tokens)")
                            break
                print()  # Newline after streaming
                self._update_usage(0.0)
                return content
            else:
                # Non-streaming response
                resp_json = response.json()
                content = resp_json["message"]["content"]
                # Extract token counts if available
                output_tokens = resp_json.get("eval_count", 0)
                input_tokens = resp_json.get("prompt_eval_count", 0)
                if output_tokens > 0:
                    self._log_usage("ollama", model, input_tokens, output_tokens, 0.0, "non-streaming")
                    print(f"[LLM] Ollama FREE (Input: {input_tokens:,} tokens, Output: {output_tokens:,} tokens)")
                self._update_usage(0.0)
                return content

        except Exception as e:
            print(f"[LLM] Error calling Ollama: {e}")
            return f"Error: {str(e)}"

    def _chat_openai(self, messages, model, base_url="https://api.openai.com/v1"):
        api_key = os.getenv("OPENAI_API_KEY")
        if "x.ai" in base_url:
            api_key = os.getenv("XAI_API_KEY") or api_key
            
        if not api_key: return "Error: API Key not found."

        print(f"[LLM] Sending request to {model} via {base_url}...")
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"model": model or "gpt-4o", "messages": messages, "temperature": 0.2}
        
        try:
            resp = requests.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.request_timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data['choices'][0]['message']['content']
            
            usage = data.get('usage', {})
            p = usage.get('prompt_tokens', 0)
            c = usage.get('completion_tokens', 0)
            cost = (p * 2.50 / 1e6) + (c * 10.00 / 1e6)

            self._log_usage("openai", model or "gpt-4o", p, c, cost, "chat")
            self._update_usage(cost)
            print(f"[LLM] OpenAI Cost: ${cost:.5f} (Input: {p:,} tokens, Output: {c:,} tokens)")
            return content
        except Exception as e:
            return f"Error calling Cloud: {e}"

    def _chat_anthropic(self, messages, model):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key: return "Error: ANTHROPIC_API_KEY not found."

        system_msg = "You are a helpful assistant."
        filtered = []
        for m in messages:
            if m['role'] == 'system': system_msg = m['content']
            else: filtered.append(m)

        # Map friendly names to API model IDs
        model_map = {
            "claude-opus-4.5": "claude-opus-4-20250514",
            "claude-sonnet-4.5": "claude-sonnet-4-20250514",
            "claude-haiku-4.5": "claude-4-0-haiku-20250514",
        }
        api_model = model_map.get(model, model or "claude-3-opus-20240229")

        print(f"[LLM] Sending request to {model} → {api_model} (Anthropic)...")
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
        payload = {
            "model": api_model,
            "max_tokens": 8192,
            "system": system_msg,
            "messages": filtered
        }

        # Pricing per 1M tokens (updated Jan 2026)
        pricing = {
            "claude-opus-4.5": {"input": 5.0, "output": 25.0},
            "claude-sonnet-4.5": {"input": 3.0, "output": 15.0},
            "claude-haiku-4.5": {"input": 1.0, "output": 5.0},
        }
        rates = pricing.get(model, {"input": 15.0, "output": 75.0})

        try:
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
                timeout=self.request_timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data['content'][0]['text']

            usage = data.get('usage', {})
            p = usage.get('input_tokens', 0)
            c = usage.get('output_tokens', 0)
            cost = (p * rates['input'] / 1e6) + (c * rates['output'] / 1e6)

            self._log_usage("anthropic", model, p, c, cost, "chat")
            self._update_usage(cost)
            print(f"[LLM] Anthropic ({model}) Cost: ${cost:.5f} (Input: {p:,} tokens, Output: {c:,} tokens)")
            return content
        except Exception as e:
             return f"Error calling Anthropic: {e}"

    def _chat_google(self, messages, model):
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key: return "Error: GOOGLE_API_KEY not found."

        # Convert messages to Gemini format
        system_msg = ""
        user_parts = []
        for m in messages:
            if m['role'] == 'system':
                system_msg = m['content']
            elif m['role'] == 'user':
                user_parts.append(m['content'])
            elif m['role'] == 'assistant':
                # Gemini alternates user/model, combine for simplicity
                pass

        combined_prompt = system_msg + "\n\n" + "\n".join(user_parts) if system_msg else "\n".join(user_parts)

        # Map friendly names to API model IDs
        # Google Gemini uses simple model names, latest models may have -preview suffix
        model_map = {
            "gemini-3-pro": "gemini-3-pro-preview",
            "gemini-3-pro-preview": "gemini-3-pro-preview",
            "gemini-3-flash": "gemini-3-flash-preview",
            "gemini-3-flash-preview": "gemini-3-flash-preview",
            "gemini-2.5-pro": "gemini-2.5-pro",
            "gemini-1.5-pro": "gemini-1.5-pro",
            "gemini-1.5-flash": "gemini-1.5-flash",
            "gemini-2.0-flash": "gemini-2.0-flash",
            "gemini-pro": "gemini-pro",
        }
        api_model = model_map.get(model, model or "gemini-3-flash-preview")

        print(f"[LLM] Sending request to {model or 'gemini-1.5-pro'} → {api_model} (Google)...")
        headers = {"Content-Type": "application/json"}

        # Gemini API endpoint
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{api_model}:generateContent?key={api_key}"

        payload = {
            "contents": [{
                "parts": [{"text": combined_prompt}]
            }],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 4096
            }
        }

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=self.request_timeout)
            resp.raise_for_status()
            data = resp.json()

            content = data['candidates'][0]['content']['parts'][0]['text']

            # Dynamic cost calculation based on model
            pricing = {
                "gemini-3-pro-preview": {"input": 2.0, "output": 12.0},
                "gemini-3-flash-preview": {"input": 0.5, "output": 3.0},
                "gemini-2.5-pro": {"input": 2.5, "output": 10.0},
                "gemini-1.5-pro": {"input": 1.25, "output": 5.0},
                "gemini-1.5-flash": {"input": 0.075, "output": 0.3},
                "gemini-2.0-flash": {"input": 0.08, "output": 0.3},
            }
            rates = pricing.get(api_model, {"input": 1.25, "output": 5.0})

            usage = data.get('usageMetadata', {})
            p = usage.get('promptTokenCount', 0)
            c = usage.get('candidatesTokenCount', 0)
            cost = (p * rates['input'] / 1e6) + (c * rates['output'] / 1e6)

            self._log_usage("google", model or "gemini-1.5-pro", p, c, cost, "chat")
            self._update_usage(cost)
            print(f"[LLM] Google Cost: ${cost:.5f} (Input: {p:,} tokens, Output: {c:,} tokens)")
            return content
        except Exception as e:
            return f"Error calling Google Gemini: {e}"

if __name__ == "__main__":
    # Test
    client = LLMClient()
    print(client.chat([{"role": "user", "content": "Hello, Architect."}]))
