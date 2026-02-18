"""
MCP (Model Context Protocol) API endpoints.
Provides access to all MCP services: Git, n8n, Filesystem, MQTT, Ollama, Memory.
"""
import os
import sys
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# Add shared directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../'))

from shared.mcp import MCPManager

router = APIRouter(prefix="/mcp", tags=["mcp"])

def _build_mcp_config() -> Dict[str, Dict[str, Any]]:
    n8n_config: Dict[str, Any] = {
        "base_url": (os.getenv("SAGE_N8N_BASE_URL") or "http://localhost:5678").strip()
    }
    n8n_api_key = (os.getenv("SAGE_N8N_API_KEY") or "").strip()
    if n8n_api_key:
        n8n_config["api_key"] = n8n_api_key

    return {
        "git": {"repo_path": os.getcwd()},
        "n8n": n8n_config,
        "mqtt": {"host": "localhost", "port": 1883},
        "ollama": {"base_url": "http://localhost:11434"},
        "memory": {"persist_directory": ".sage_memory"}
    }


# Initialize MCP manager
mcp = MCPManager(_build_mcp_config())


# ============================================================================
# STATUS ENDPOINTS
# ============================================================================

@router.get("/status")
async def get_mcp_status():
    """
    Get status of all MCP services.

    Returns:
        Dict with service status
    """
    return {
        "services": mcp.get_status(),
        "available": True
    }


# ============================================================================
# FILESYSTEM ENDPOINTS
# ============================================================================

class ReadFileRequest(BaseModel):
    path: str = Field(description="File path to read")
    encoding: str = Field(default="utf-8", description="File encoding")


class WriteFileRequest(BaseModel):
    path: str = Field(description="File path to write")
    content: str = Field(description="File content")
    atomic: bool = Field(default=True, description="Use atomic write")


class ListDirectoryRequest(BaseModel):
    path: str = Field(default=".", description="Directory path")
    recursive: bool = Field(default=False, description="List recursively")
    patterns: Optional[List[str]] = Field(default=None, description="File patterns")


@router.post("/filesystem/read")
async def filesystem_read(request: ReadFileRequest):
    """Read file with automatic encoding detection."""
    try:
        result = await mcp.filesystem.read_file(request.path, request.encoding)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/filesystem/write")
async def filesystem_write(request: WriteFileRequest):
    """Write file with atomic operation support."""
    try:
        result = await mcp.filesystem.write_file(
            request.path,
            request.content,
            atomic=request.atomic
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/filesystem/list")
async def filesystem_list(request: ListDirectoryRequest):
    """List directory contents."""
    try:
        result = await mcp.filesystem.list_directory(
            request.path,
            recursive=request.recursive,
            patterns=request.patterns
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# MQTT ENDPOINTS
# ============================================================================

class MQTTPublishRequest(BaseModel):
    topic: str = Field(description="MQTT topic")
    payload: Any = Field(description="Message payload")
    qos: int = Field(default=0, description="Quality of Service")
    retain: bool = Field(default=False, description="Retain message")


class MQTTRoomStateRequest(BaseModel):
    room: str = Field(description="Room name")


@router.post("/mqtt/connect")
async def mqtt_connect():
    """Connect to MQTT broker."""
    try:
        result = await mcp.mqtt.connect()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mqtt/publish")
async def mqtt_publish(request: MQTTPublishRequest):
    """Publish message to MQTT topic."""
    try:
        result = await mcp.mqtt.publish(
            request.topic,
            request.payload,
            qos=request.qos,
            retain=request.retain
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mqtt/room-state")
async def mqtt_get_room_state(request: MQTTRoomStateRequest):
    """Get current state of all sensors in a room."""
    try:
        result = await mcp.mqtt.get_room_state(request.room)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mqtt/topics")
async def mqtt_get_topics():
    """Discover all active MQTT topics."""
    try:
        result = await mcp.mqtt.get_all_topics()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# OLLAMA ENDPOINTS
# ============================================================================

class OllamaChatRequest(BaseModel):
    model: str = Field(description="Model name")
    messages: List[Dict[str, str]] = Field(description="Chat messages")
    options: Optional[Dict[str, Any]] = Field(default=None, description="Model options")


class OllamaQuickChatRequest(BaseModel):
    prompt: str = Field(description="User prompt")
    task: str = Field(default="chat", description="Task type (voice, code, chat)")
    system: Optional[str] = Field(default=None, description="System prompt")


class OllamaModelPullRequest(BaseModel):
    name: str = Field(description="Model name to pull")


@router.get("/ollama/models")
async def ollama_list_models():
    """List all locally available Ollama models."""
    try:
        result = await mcp.ollama.list_models()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ollama/chat")
async def ollama_chat(request: OllamaChatRequest):
    """Send chat completion request to Ollama."""
    try:
        result = await mcp.ollama.chat(
            request.model,
            request.messages,
            options=request.options
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ollama/quick-chat")
async def ollama_quick_chat(request: OllamaQuickChatRequest):
    """Quick chat with automatic model selection."""
    try:
        result = await mcp.ollama.quick_chat(
            request.prompt,
            task=request.task,
            system=request.system
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ollama/pull")
async def ollama_pull_model(request: OllamaModelPullRequest):
    """Pull/download a model from Ollama library."""
    try:
        result = await mcp.ollama.pull_model(request.name)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# MEMORY ENDPOINTS
# ============================================================================

class MemoryRememberRequest(BaseModel):
    text: str = Field(description="Memory text")
    collection: str = Field(default="sage_memories", description="Collection name")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Metadata")


class MemoryRecallRequest(BaseModel):
    query: str = Field(description="Search query")
    collection: str = Field(default="sage_memories", description="Collection name")
    n_results: int = Field(default=5, description="Number of results")


class MemoryEpisodeRequest(BaseModel):
    text: str = Field(description="Episode description")
    room: str = Field(description="Room name")
    duration_minutes: Optional[int] = Field(default=None, description="Duration")
    patterns: Optional[List[str]] = Field(default=None, description="Detected patterns")


class MemoryFactRequest(BaseModel):
    text: str = Field(description="Fact text")
    category: str = Field(default="general", description="Fact category")


@router.post("/memory/remember")
async def memory_remember(request: MemoryRememberRequest):
    """Store a memory."""
    try:
        result = await mcp.memory.remember(
            request.text,
            collection_name=request.collection,
            metadata=request.metadata
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memory/recall")
async def memory_recall(request: MemoryRecallRequest):
    """Semantic search for memories."""
    try:
        result = await mcp.memory.recall(
            request.query,
            collection_name=request.collection,
            n_results=request.n_results
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memory/collections")
async def memory_list_collections():
    """List all memory collections."""
    try:
        result = await mcp.memory.list_collections()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memory/episode")
async def memory_remember_episode(request: MemoryEpisodeRequest):
    """Remember a Brain episode."""
    try:
        result = await mcp.memory.remember_episode(
            request.text,
            request.room,
            duration_minutes=request.duration_minutes,
            patterns=request.patterns
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memory/fact")
async def memory_remember_fact(request: MemoryFactRequest):
    """Remember a fact about the user."""
    try:
        result = await mcp.memory.remember_fact(
            request.text,
            category=request.category
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# N8N ENDPOINTS
# ============================================================================

class N8NWebhookRequest(BaseModel):
    webhook_path: str = Field(description="Webhook path")
    data: Dict[str, Any] = Field(description="Data to send")


class N8NCreateWorkflowRequest(BaseModel):
    name: str = Field(min_length=1, description="Workflow name")
    nodes: List[Dict[str, Any]] = Field(min_items=1, description="n8n node definitions")
    connections: Dict[str, Any] = Field(default_factory=dict, description="n8n connection definitions")
    active: bool = Field(
        default=False,
        description="Whether the workflow should be active immediately after creation"
    )
    confirm_create: bool = Field(
        default=False,
        description="Explicit safety confirmation required to create a workflow"
    )


class N8NExecuteWorkflowRequest(BaseModel):
    workflow_id: str = Field(min_length=1, description="n8n workflow ID")
    data: Dict[str, Any] = Field(default_factory=dict, description="Input data for execution")


@router.post("/n8n/trigger")
async def n8n_trigger_webhook(request: N8NWebhookRequest):
    """Trigger an n8n workflow via webhook."""
    try:
        result = await mcp.n8n.trigger_webhook(
            request.webhook_path,
            request.data
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/n8n/workflows/create")
async def n8n_create_workflow(request: N8NCreateWorkflowRequest):
    """Create a new n8n workflow."""
    if not request.confirm_create:
        raise HTTPException(
            status_code=400,
            detail="Workflow creation blocked: set confirm_create=true to proceed."
        )

    try:
        result = await mcp.n8n.create_workflow(
            request.name,
            request.nodes,
            request.connections,
            active=request.active
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/n8n/workflows")
async def n8n_list_workflows():
    """List all n8n workflows."""
    try:
        result = await mcp.n8n.list_workflows()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/n8n/workflows/execute")
async def n8n_execute_workflow(request: N8NExecuteWorkflowRequest):
    """Execute an n8n workflow by workflow ID."""
    try:
        result = await mcp.n8n.trigger_workflow_by_id(
            request.workflow_id,
            request.data
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/n8n/executions/{execution_id}")
async def n8n_execution_status(execution_id: str):
    """Get execution status for a previously triggered n8n workflow."""
    try:
        result = await mcp.n8n.get_workflow_status(execution_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# CLEANUP
# ============================================================================

@router.on_event("shutdown")
async def shutdown_mcp():
    """Close all MCP connections on shutdown."""
    await mcp.close_all()
