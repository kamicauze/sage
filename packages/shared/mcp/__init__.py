"""
MCP (Model Context Protocol) Integration Package.

This package provides clients for various MCP servers used by Sage system:
- Git: Version control operations
- n8n: Workflow automation
- Filesystem: Advanced file operations
- MQTT: Message bus for sensors and communication
- Ollama: Local LLM inference
- Memory: Semantic memory with ChromaDB

All clients follow a consistent async API pattern and can be used by both
Architect and Brain components.
"""
from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .filesystem_client import FilesystemMCPClient
    from .git_client import GitMCPClient
    from .memory_client import MemoryMCPClient
    from .mqtt_client import MQTTMCPClient
    from .n8n_client import N8NClient
    from .ollama_client import OllamaMCPClient

_LAZY_EXPORTS = {
    "GitMCPClient": ("git_client", "GitMCPClient"),
    "N8NClient": ("n8n_client", "N8NClient"),
    "FilesystemMCPClient": ("filesystem_client", "FilesystemMCPClient"),
    "MQTTMCPClient": ("mqtt_client", "MQTTMCPClient"),
    "OllamaMCPClient": ("ollama_client", "OllamaMCPClient"),
    "MemoryMCPClient": ("memory_client", "MemoryMCPClient"),
}

__all__ = [
    "GitMCPClient",
    "N8NClient",
    "FilesystemMCPClient",
    "MQTTMCPClient",
    "OllamaMCPClient",
    "MemoryMCPClient",
    "MCPManager"
]


def __getattr__(name: str):
    """Lazy-load MCP client classes to avoid hard dependency at import time."""
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, class_name = target
    module = importlib.import_module(f"{__name__}.{module_name}")
    value = getattr(module, class_name)
    globals()[name] = value
    return value


class MCPManager:
    """
    Centralized manager for all MCP clients.
    Simplifies initialization and access to MCP services.
    """

    def __init__(self, config: dict = None):
        """
        Initialize MCP manager.

        Args:
            config: Configuration dict with MCP settings
        """
        self.config = config or {}
        self._git = None
        self._n8n = None
        self._filesystem = None
        self._mqtt = None
        self._ollama = None
        self._memory = None

    @property
    def git(self) -> "GitMCPClient":
        """Get Git MCP client."""
        if self._git is None:
            GitMCPClient = __getattr__("GitMCPClient")
            repo_path = self.config.get("git", {}).get("repo_path")
            self._git = GitMCPClient(repo_path)
        return self._git

    @property
    def n8n(self) -> "N8NClient":
        """Get n8n client."""
        if self._n8n is None:
            N8NClient = __getattr__("N8NClient")
            base_url = self.config.get("n8n", {}).get("base_url", "http://localhost:5678")
            api_key = self.config.get("n8n", {}).get("api_key")
            self._n8n = N8NClient(base_url, api_key)
        return self._n8n

    @property
    def filesystem(self) -> "FilesystemMCPClient":
        """Get Filesystem MCP client."""
        if self._filesystem is None:
            FilesystemMCPClient = __getattr__("FilesystemMCPClient")
            base_path = self.config.get("filesystem", {}).get("base_path")
            self._filesystem = FilesystemMCPClient(base_path)
        return self._filesystem

    @property
    def mqtt(self) -> "MQTTMCPClient":
        """Get MQTT MCP client."""
        if self._mqtt is None:
            MQTTMCPClient = __getattr__("MQTTMCPClient")
            mqtt_config = self.config.get("mqtt", {})
            self._mqtt = MQTTMCPClient(
                host=mqtt_config.get("host", "localhost"),
                port=mqtt_config.get("port", 1883),
                username=mqtt_config.get("username"),
                password=mqtt_config.get("password")
            )
        return self._mqtt

    @property
    def ollama(self) -> "OllamaMCPClient":
        """Get Ollama MCP client."""
        if self._ollama is None:
            OllamaMCPClient = __getattr__("OllamaMCPClient")
            base_url = self.config.get("ollama", {}).get("base_url", "http://localhost:11434")
            self._ollama = OllamaMCPClient(base_url)
        return self._ollama

    @property
    def memory(self) -> "MemoryMCPClient":
        """Get Memory MCP client."""
        if self._memory is None:
            MemoryMCPClient = __getattr__("MemoryMCPClient")
            persist_dir = self.config.get("memory", {}).get("persist_directory", ".sage_memory")
            self._memory = MemoryMCPClient(persist_dir)
        return self._memory

    async def connect_all(self):
        """Connect all MCP clients that require connection."""
        if self._mqtt:
            await self._mqtt.connect()

    async def close_all(self):
        """Close all MCP client connections."""
        if self._n8n:
            await self._n8n.close()
        if self._filesystem:
            await self._filesystem.close()
        if self._mqtt:
            await self._mqtt.disconnect()
        if self._ollama:
            await self._ollama.close()

    def get_status(self) -> dict:
        """Get status of all MCP clients."""
        return {
            "git": self._git is not None,
            "n8n": self._n8n is not None,
            "filesystem": self._filesystem is not None,
            "mqtt": self._mqtt is not None,
            "ollama": self._ollama is not None,
            "memory": self._memory is not None
        }
