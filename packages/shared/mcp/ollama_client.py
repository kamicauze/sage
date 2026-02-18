"""
Ollama MCP Client.
Provides local LLM inference with model management capabilities.
Used by Brain for voice processing and Architect for cheap planning.
"""
import aiohttp
from typing import Dict, List, Optional, Any, AsyncIterator
from datetime import datetime


class OllamaMCPClient:
    """
    Client for Ollama local LLM operations.
    Can be used by both Architect and Brain for model management and inference.
    """

    def __init__(self, base_url: str = "http://localhost:11434"):
        """
        Initialize Ollama client.

        Args:
            base_url: Ollama API base URL
        """
        self.base_url = base_url.rstrip("/")
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close(self):
        """Close the aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()

    async def list_models(self) -> Dict[str, Any]:
        """
        List all locally available models.

        Returns:
            Dict with list of models
        """
        try:
            session = await self._get_session()
            url = f"{self.base_url}/api/tags"

            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    models = data.get("models", [])
                    return {
                        "success": True,
                        "models": [
                            {
                                "name": m["name"],
                                "size": m.get("size", 0),
                                "modified": m.get("modified_at"),
                                "digest": m.get("digest"),
                                "family": m.get("details", {}).get("family"),
                                "parameter_size": m.get("details", {}).get("parameter_size")
                            }
                            for m in models
                        ],
                        "count": len(models)
                    }
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status}: {await response.text()}"
                    }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to list models: {str(e)}"
            }

    async def pull_model(self, name: str) -> Dict[str, Any]:
        """
        Pull/download a model from Ollama library.

        Args:
            name: Model name (e.g., "llama3.3", "gemma3:12b")

        Returns:
            Dict with pull result
        """
        try:
            session = await self._get_session()
            url = f"{self.base_url}/api/pull"

            async with session.post(url, json={"name": name}) as response:
                if response.status == 200:
                    # Stream progress
                    status = ""
                    async for line in response.content:
                        if line:
                            import json
                            data = json.loads(line)
                            status = data.get("status", "")

                    return {
                        "success": True,
                        "model": name,
                        "status": status
                    }
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status}: {await response.text()}"
                    }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to pull model: {str(e)}"
            }

    async def delete_model(self, name: str) -> Dict[str, Any]:
        """
        Delete a model.

        Args:
            name: Model name

        Returns:
            Dict with deletion result
        """
        try:
            session = await self._get_session()
            url = f"{self.base_url}/api/delete"

            async with session.delete(url, json={"name": name}) as response:
                if response.status == 200:
                    return {
                        "success": True,
                        "model": name,
                        "deleted": True
                    }
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status}: {await response.text()}"
                    }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to delete model: {str(e)}"
            }

    async def show_model_info(self, name: str) -> Dict[str, Any]:
        """
        Get detailed model information.

        Args:
            name: Model name

        Returns:
            Dict with model info
        """
        try:
            session = await self._get_session()
            url = f"{self.base_url}/api/show"

            async with session.post(url, json={"name": name}) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "success": True,
                        "model": name,
                        "info": data
                    }
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status}: {await response.text()}"
                    }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to get model info: {str(e)}"
            }

    async def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        stream: bool = False,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send chat completion request.

        Args:
            model: Model name
            messages: List of message dicts with 'role' and 'content'
            stream: Stream response
            options: Model options (temperature, top_k, etc.)

        Returns:
            Dict with chat response
        """
        try:
            session = await self._get_session()
            url = f"{self.base_url}/api/chat"

            payload = {
                "model": model,
                "messages": messages,
                "stream": stream,
                "options": options or {}
            }

            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    if stream:
                        # Return async iterator for streaming
                        return {
                            "success": True,
                            "stream": True,
                            "response": response
                        }
                    else:
                        data = await response.json()
                        return {
                            "success": True,
                            "model": model,
                            "message": data.get("message", {}),
                            "content": data.get("message", {}).get("content", ""),
                            "done": data.get("done", False),
                            "total_duration": data.get("total_duration"),
                            "load_duration": data.get("load_duration"),
                            "prompt_eval_count": data.get("prompt_eval_count"),
                            "eval_count": data.get("eval_count")
                        }
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status}: {await response.text()}"
                    }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to chat: {str(e)}"
            }

    async def chat_stream(
        self,
        model: str,
        messages: List[Dict[str, str]],
        options: Optional[Dict[str, Any]] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream chat completion response.

        Args:
            model: Model name
            messages: List of message dicts
            options: Model options

        Yields:
            Dict with streaming chunks
        """
        try:
            session = await self._get_session()
            url = f"{self.base_url}/api/chat"

            payload = {
                "model": model,
                "messages": messages,
                "stream": True,
                "options": options or {}
            }

            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    import json
                    async for line in response.content:
                        if line:
                            data = json.loads(line)
                            yield {
                                "success": True,
                                "content": data.get("message", {}).get("content", ""),
                                "done": data.get("done", False)
                            }
                else:
                    yield {
                        "success": False,
                        "error": f"HTTP {response.status}: {await response.text()}"
                    }
        except Exception as e:
            yield {
                "success": False,
                "error": f"Failed to stream chat: {str(e)}"
            }

    async def generate(
        self,
        model: str,
        prompt: str,
        stream: bool = False,
        options: Optional[Dict[str, Any]] = None,
        system: Optional[str] = None,
        context: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        Generate completion from prompt.

        Args:
            model: Model name
            prompt: Input prompt
            stream: Stream response
            options: Model options
            system: System prompt
            context: Context from previous generation

        Returns:
            Dict with generation response
        """
        try:
            session = await self._get_session()
            url = f"{self.base_url}/api/generate"

            payload = {
                "model": model,
                "prompt": prompt,
                "stream": stream,
                "options": options or {}
            }

            if system:
                payload["system"] = system
            if context:
                payload["context"] = context

            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    if stream:
                        return {
                            "success": True,
                            "stream": True,
                            "response": response
                        }
                    else:
                        data = await response.json()
                        return {
                            "success": True,
                            "model": model,
                            "response": data.get("response", ""),
                            "done": data.get("done", False),
                            "context": data.get("context", []),
                            "total_duration": data.get("total_duration"),
                            "eval_count": data.get("eval_count")
                        }
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status}: {await response.text()}"
                    }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to generate: {str(e)}"
            }

    async def embeddings(
        self,
        model: str,
        prompt: str
    ) -> Dict[str, Any]:
        """
        Generate embeddings for prompt.

        Args:
            model: Model name
            prompt: Input text

        Returns:
            Dict with embeddings
        """
        try:
            session = await self._get_session()
            url = f"{self.base_url}/api/embeddings"

            payload = {
                "model": model,
                "prompt": prompt
            }

            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "success": True,
                        "model": model,
                        "embedding": data.get("embedding", [])
                    }
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status}: {await response.text()}"
                    }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to generate embeddings: {str(e)}"
            }

    # Convenience methods for Sage system

    async def recommend_model_for_task(self, task: str) -> Dict[str, Any]:
        """
        Recommend best available model for task.

        Args:
            task: Task type (e.g., "voice", "code", "chat")

        Returns:
            Dict with recommended model
        """
        try:
            models_result = await self.list_models()
            if not models_result["success"]:
                return models_result

            models = models_result["models"]

            # Task-based recommendations
            task_preferences = {
                "voice": ["gemma3:2b", "llama3.1:8b", "phi3:mini"],  # Fast, small
                "code": ["deepseek-coder", "codellama", "llama3.3"],  # Code-specialized
                "chat": ["gemma3:12b", "llama3.3", "llama3.1:8b"],  # General chat
                "embedding": ["nomic-embed-text", "mxbai-embed-large"]  # Embeddings
            }

            preferences = task_preferences.get(task, ["gemma3:12b", "llama3.3"])

            # Find first available preferred model
            available_names = [m["name"] for m in models]
            for pref in preferences:
                for name in available_names:
                    if pref in name:
                        return {
                            "success": True,
                            "task": task,
                            "recommended_model": name
                        }

            # Fallback to any available model
            if models:
                return {
                    "success": True,
                    "task": task,
                    "recommended_model": models[0]["name"],
                    "note": "No task-specific model found, using first available"
                }

            return {
                "success": False,
                "error": "No models available"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to recommend model: {str(e)}"
            }

    async def quick_chat(
        self,
        prompt: str,
        task: str = "chat",
        system: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Quick chat with automatic model selection.

        Args:
            prompt: User prompt
            task: Task type for model selection
            system: Optional system prompt

        Returns:
            Dict with chat response
        """
        try:
            # Get recommended model
            model_result = await self.recommend_model_for_task(task)
            if not model_result["success"]:
                return model_result

            model = model_result["recommended_model"]

            # Build messages
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            # Chat
            return await self.chat(model, messages)
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to quick chat: {str(e)}"
            }

    async def brain_voice_intent(
        self,
        transcript: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process voice transcript for intent classification (Brain use case).

        Args:
            transcript: Voice transcript
            context: Optional context (room, time, etc.)

        Returns:
            Dict with intent classification
        """
        try:
            system_prompt = """You are a voice intent classifier for a smart home assistant.
Classify the user's intent into one of these categories:
- QUERY: User asking a question
- COMMAND: User giving a command
- CHAT: General conversation
- PATTERN: Expressing feelings or patterns (tired, stressed, etc.)

Also extract entities like room names, device names, times, etc.

Respond in JSON format:
{
    "intent": "COMMAND",
    "entities": {"device": "lights", "room": "office", "action": "on"},
    "confidence": 0.95
}"""

            prompt = f"Transcript: {transcript}"
            if context:
                prompt += f"\nContext: {context}"

            result = await self.quick_chat(
                prompt=prompt,
                task="voice",
                system=system_prompt
            )

            if result["success"]:
                # Parse JSON response
                import json
                try:
                    intent_data = json.loads(result["content"])
                    result["intent_data"] = intent_data
                except:
                    result["intent_data"] = {"intent": "UNKNOWN"}

            return result
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to classify intent: {str(e)}"
            }

    async def architect_plan_review(
        self,
        plan: str,
        feedback: str = "Review this plan for completeness and potential issues"
    ) -> Dict[str, Any]:
        """
        Review Architect plan with local LLM (cheap alternative to API).

        Args:
            plan: Generated plan
            feedback: Review instructions

        Returns:
            Dict with review result
        """
        try:
            system_prompt = """You are a code review assistant.
Review the implementation plan and provide feedback on:
- Completeness
- Potential issues
- Missing edge cases
- Security concerns

Be concise and actionable."""

            prompt = f"{feedback}\n\nPlan:\n{plan}"

            return await self.quick_chat(
                prompt=prompt,
                task="code",
                system=system_prompt
            )
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to review plan: {str(e)}"
            }


# Context manager support
class OllamaMCPClientContext:
    """Context manager for OllamaMCPClient."""

    def __init__(self, *args, **kwargs):
        self.client = OllamaMCPClient(*args, **kwargs)

    async def __aenter__(self):
        return self.client

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.close()
