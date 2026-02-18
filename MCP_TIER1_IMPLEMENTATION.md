# MCP Tier 1 Implementation - COMPLETE

**Date:** 2026-01-13
**Status:** ✅ Production Ready

---

## Overview

Implemented the critical Tier 1 MCP (Model Context Protocol) integrations for the Sage system:

1. ✅ **Filesystem MCP** - Advanced file operations
2. ✅ **MQTT MCP** - Message bus integration
3. ✅ **Ollama MCP** - Local LLM inference
4. ✅ **Memory MCP** - Semantic memory with ChromaDB
5. ✅ **Git MCP** - Already implemented (previous work)
6. ✅ **n8n Client** - Already implemented (previous work)

All MCPs follow a consistent async API pattern and can be used by both Architect and Brain.

---

## Implementation Details

### 1. Filesystem MCP Client

**File:** [shared/mcp/filesystem_client.py](shared/mcp/filesystem_client.py)
**Lines of Code:** ~660

**Features:**
- ✅ Async file read/write with automatic encoding detection
- ✅ Atomic writes (write to temp, then rename)
- ✅ File operations: copy, move, delete, append
- ✅ Directory operations: list, create, delete
- ✅ File watching with pattern matching
- ✅ File hashing (MD5, SHA1, SHA256)
- ✅ Disk usage statistics

**Key Methods:**
```python
fs = FilesystemMCPClient("/home/user/project")

# Read file with auto-encoding
result = await fs.read_file("src/main.py")

# Atomic write
result = await fs.write_file("config.json", json_data, atomic=True)

# Watch directory for changes
await fs.watch_directory(
    path="src",
    patterns=["**/*.py", "**/*.ts"],
    callback=on_file_change
)

# List directory recursively
result = await fs.list_directory(".", recursive=True, max_depth=3)

# Get file hash
result = await fs.get_file_hash("build.zip", algorithm="sha256")
```

**Use Cases:**
- **Architect:** Efficient codebase ingestion, hot-reload detection
- **Brain:** Monitor user's active files for context awareness

---

### 2. MQTT MCP Client

**File:** [shared/mcp/mqtt_client.py](shared/mcp/mqtt_client.py)
**Lines of Code:** ~480

**Features:**
- ✅ Publish/subscribe with QoS support
- ✅ Topic wildcards (+ and #)
- ✅ Retained messages
- ✅ Async message handling
- ✅ Topic discovery
- ✅ Convenience methods for Sage topics

**Key Methods:**
```python
mqtt = MQTTMCPClient("localhost", 1883)
await mqtt.connect()

# Publish sensor state
await mqtt.publish_state(
    room="office",
    sensor="presence",
    state={"detected": True, "confidence": 0.95}
)

# Subscribe to sensor updates
await mqtt.subscribe_to_sensor(
    room="office",
    sensor="presence",
    callback=on_presence_change
)

# Get room state
result = await mqtt.get_room_state("office")
# Returns: {"presence": {...}, "screen": {...}, "voice": {...}}

# Trigger Architect build via MQTT
await mqtt.trigger_architect_build(
    project_id="sage",
    request="Add error handling to MQTT client"
)

# Discover all topics
result = await mqtt.get_all_topics()
```

**Use Cases:**
- **Brain:** Sensor data access, state monitoring, device control
- **Architect:** Trigger builds via MQTT, monitor system events
- **Both:** Real-time communication, event-driven architecture

---

### 3. Ollama MCP Client

**File:** [shared/mcp/ollama_client.py](shared/mcp/ollama_client.py)
**Lines of Code:** ~540

**Features:**
- ✅ List/pull/delete models
- ✅ Chat completions (streaming and non-streaming)
- ✅ Text generation
- ✅ Embeddings
- ✅ Model info and stats
- ✅ Automatic model selection for tasks
- ✅ Convenience methods for Sage use cases

**Key Methods:**
```python
ollama = OllamaMCPClient("http://localhost:11434")

# List available models
result = await ollama.list_models()
# Returns: {"models": [{"name": "gemma3:12b", "size": 8000000000, ...}]}

# Pull a model
await ollama.pull_model("llama3.3")

# Chat with specific model
result = await ollama.chat(
    model="gemma3:12b",
    messages=[
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "Explain async/await"}
    ]
)

# Stream chat response
async for chunk in ollama.chat_stream("gemma3:12b", messages):
    print(chunk["content"], end="")

# Quick chat with auto model selection
result = await ollama.quick_chat(
    prompt="What is the weather?",
    task="chat"  # Auto-selects best model for "chat" task
)

# Brain: Classify voice intent
result = await ollama.brain_voice_intent(
    transcript="Turn on the lights in the office",
    context={"room": "office", "time": "evening"}
)
# Returns: {"intent": "COMMAND", "entities": {"device": "lights", ...}}

# Architect: Review plan with local LLM
result = await ollama.architect_plan_review(
    plan="Plan content here...",
    feedback="Check for security issues"
)
```

**Task-Based Model Recommendations:**
- **voice:** gemma3:2b, llama3.1:8b (fast, small)
- **code:** deepseek-coder, codellama (code-specialized)
- **chat:** gemma3:12b, llama3.3 (general conversation)
- **embedding:** nomic-embed-text (semantic search)

**Use Cases:**
- **Brain:** Voice intent classification, cheap inference
- **Architect:** Plan review, code generation assistance
- **Both:** Model management, embeddings for semantic search

---

### 4. Memory MCP Client

**File:** [shared/mcp/memory_client.py](shared/mcp/memory_client.py)
**Lines of Code:** ~520

**Features:**
- ✅ Semantic memory storage with ChromaDB
- ✅ Vector search/retrieval
- ✅ Multiple collections
- ✅ Metadata filtering
- ✅ Memory CRUD operations
- ✅ Specialized collections for episodes, facts, preferences

**Key Methods:**
```python
memory = MemoryMCPClient(".sage_memory")

# Remember something
result = await memory.remember(
    text="User prefers Python over JavaScript for backend",
    collection_name="sage_facts",
    metadata={"type": "preference", "category": "programming"}
)

# Semantic search
result = await memory.recall(
    query="programming language preferences",
    collection_name="sage_facts",
    n_results=5
)

# Remember episode (Brain)
await memory.remember_episode(
    text="Deep work session on React component",
    room="office",
    duration_minutes=90,
    patterns=["DEEP_FOCUS"]
)

# Remember fact
await memory.remember_fact(
    text="User is allergic to peanuts",
    category="health"
)

# Remember preference
await memory.remember_preference(
    preference="notification_time",
    value="morning",
    category="system"
)

# Recall recent episodes
result = await memory.recall_recent_episodes(
    room="office",
    hours_ago=24,
    n_results=10
)

# Get specific preference
result = await memory.get_preference("notification_time")
# Returns: {"value": "morning", "category": "system", ...}

# Architect: Remember generated code
await memory.architect_remember_code(
    code="function processData() {...}",
    file_path="src/utils.js",
    project_id="myapp",
    purpose="Data processing utility"
)

# Architect: Find similar code
result = await memory.architect_recall_similar_code(
    purpose="data processing",
    project_id="myapp",
    n_results=3
)
```

**Collections:**
- **sage_episodes:** Brain's observation episodes
- **sage_facts:** Facts about the user
- **sage_preferences:** User preferences
- **sage_conversations:** Conversation history
- **sage_architect_code:** Generated code snippets

**Use Cases:**
- **Brain:** Episodic memory, user preferences, conversation history
- **Architect:** Code reuse, semantic code search
- **Both:** Unified memory interface, context awareness

---

## Centralized MCP Manager

**File:** [shared/mcp/__init__.py](shared/mcp/__init__.py)

**Purpose:** Simplifies MCP initialization and access

```python
from shared.mcp import MCPManager

# Initialize with config
mcp = MCPManager({
    "git": {"repo_path": "/home/user/project"},
    "n8n": {"base_url": "http://localhost:5678"},
    "mqtt": {"host": "localhost", "port": 1883},
    "ollama": {"base_url": "http://localhost:11434"},
    "memory": {"persist_directory": ".sage_memory"}
})

# Access clients via properties
git_status = await mcp.git.get_status()
models = await mcp.ollama.list_models()
room_state = await mcp.mqtt.get_room_state("office")
memories = await mcp.memory.recall("programming preferences")

# Connect all services
await mcp.connect_all()

# Get status
status = mcp.get_status()
# Returns: {"git": True, "n8n": True, "mqtt": True, ...}

# Cleanup
await mcp.close_all()
```

---

## API Integration

**File:** [architect/api/routes/mcp.py](architect/api/routes/mcp.py)
**File:** [architect/api/server.py](architect/api/server.py) (updated)

### New API Endpoints

All endpoints accessible at `http://localhost:8000/mcp/...`

#### Status
```bash
GET /mcp/status
# Returns: {"services": {"git": true, "n8n": true, ...}}
```

#### Filesystem
```bash
POST /mcp/filesystem/read
Body: {"path": "src/main.py", "encoding": "utf-8"}

POST /mcp/filesystem/write
Body: {"path": "config.json", "content": "{...}", "atomic": true}

POST /mcp/filesystem/list
Body: {"path": "src", "recursive": true, "patterns": ["*.py"]}
```

#### MQTT
```bash
POST /mcp/mqtt/connect

POST /mcp/mqtt/publish
Body: {"topic": "sage/brain/office/lights", "payload": {"state": "on"}}

POST /mcp/mqtt/room-state
Body: {"room": "office"}

GET /mcp/mqtt/topics
```

#### Ollama
```bash
GET /mcp/ollama/models

POST /mcp/ollama/chat
Body: {
  "model": "gemma3:12b",
  "messages": [{"role": "user", "content": "Hello"}]
}

POST /mcp/ollama/quick-chat
Body: {"prompt": "Explain Python", "task": "chat"}

POST /mcp/ollama/pull
Body: {"name": "llama3.3"}
```

#### Memory
```bash
POST /mcp/memory/remember
Body: {"text": "User prefers dark mode", "collection": "sage_preferences"}

POST /mcp/memory/recall
Body: {"query": "dark mode", "collection": "sage_preferences", "n_results": 5}

GET /mcp/memory/collections

POST /mcp/memory/episode
Body: {
  "text": "Deep work session",
  "room": "office",
  "duration_minutes": 90
}

POST /mcp/memory/fact
Body: {"text": "User is allergic to peanuts", "category": "health"}
```

#### n8n
```bash
POST /mcp/n8n/trigger
Body: {"webhook_path": "git-auto-commit", "data": {...}}

GET /mcp/n8n/workflows
```

### Testing the API

```bash
# Start API server
cd /home/kamicauze/sage
.venv/bin/python -m uvicorn architect.api.server:app --host 127.0.0.1 --port 8000

# Test Ollama
curl -X GET http://localhost:8000/mcp/ollama/models

# Test Memory
curl -X POST http://localhost:8000/mcp/memory/remember \
  -H "Content-Type: application/json" \
  -d '{"text": "User prefers TypeScript", "collection": "sage_facts"}'

curl -X POST http://localhost:8000/mcp/memory/recall \
  -H "Content-Type: application/json" \
  -d '{"query": "programming language", "collection": "sage_facts"}'

# Test MQTT
curl -X POST http://localhost:8000/mcp/mqtt/connect
curl -X POST http://localhost:8000/mcp/mqtt/room-state \
  -H "Content-Type: application/json" \
  -d '{"room": "office"}'

# Test Filesystem
curl -X POST http://localhost:8000/mcp/filesystem/list \
  -H "Content-Type: application/json" \
  -d '{"path": ".", "recursive": false}'
```

---

## Dependencies

Add to [requirements.txt](requirements.txt):

```txt
# MCP Clients
aiofiles>=23.2.1
watchdog>=3.0.0
aiomqtt>=2.0.0
aiohttp>=3.9.0
chromadb>=0.4.22
```

Install:
```bash
.venv/bin/pip install aiofiles watchdog aiomqtt aiohttp chromadb
```

---

## Usage Examples

### Example 1: Architect with MCPs

```python
from shared.mcp import MCPManager

mcp = MCPManager()

# Use Ollama for cheap plan review
plan_result = await mcp.ollama.architect_plan_review(
    plan=generated_plan,
    feedback="Check for edge cases and security issues"
)

# Generate code with Architect
# ...

# Remember generated code
await mcp.memory.architect_remember_code(
    code=generated_code,
    file_path="src/auth.py",
    project_id="myapp",
    purpose="User authentication"
)

# Auto-commit with Git
await mcp.git.auto_commit_and_push(
    message="feat: Add user authentication\n\nGenerated by Architect",
    files=["src/auth.py"],
    create_branch="feature/auth",
    push_to_remote=True
)

# Trigger n8n workflow
await mcp.n8n.architect_build_complete(
    project_id="myapp",
    artifacts=["src/auth.py"],
    status="SUCCESS"
)
```

### Example 2: Brain with MCPs

```python
from shared.mcp import MCPManager

mcp = MCPManager()

# Connect to MQTT
await mcp.mqtt.connect()

# Subscribe to presence sensor
async def on_presence(msg):
    if msg["payload"]["detected"]:
        # User entered office
        await mcp.memory.remember_episode(
            text="User entered office",
            room="office",
            duration_minutes=None
        )

await mcp.mqtt.subscribe_to_sensor("office", "presence", on_presence)

# Process voice command
transcript = "Turn on the lights in the office"

# Use Ollama for intent classification
intent_result = await mcp.ollama.brain_voice_intent(
    transcript=transcript,
    context={"room": "office"}
)

if intent_result["intent_data"]["intent"] == "COMMAND":
    entities = intent_result["intent_data"]["entities"]

    # Execute command via MQTT
    await mcp.mqtt.publish_command(
        room=entities["room"],
        device=entities["device"],
        command={"action": entities["action"]}
    )

    # Remember the interaction
    await mcp.memory.remember_fact(
        text=f"User controlled {entities['device']} in {entities['room']}",
        category="home_automation"
    )
```

### Example 3: File Watching for Context

```python
from shared.mcp import MCPManager

mcp = MCPManager()

# Watch for file changes to understand what user is working on
async def on_file_modified(event):
    file_path = event["path"]

    # Read the file
    content_result = await mcp.filesystem.read_file(file_path)

    # Remember in context
    await mcp.memory.remember_fact(
        text=f"User is actively editing {file_path}",
        category="current_work"
    )

    # Semantic search for related memories
    related = await mcp.memory.recall(
        query=f"work on {file_path}",
        n_results=3
    )

    print(f"Context: User working on {file_path}")
    print(f"Related memories: {len(related['memories'])}")

await mcp.filesystem.watch_directory(
    path=".",
    patterns=["**/*.py", "**/*.ts", "**/*.tsx"],
    callback=on_file_modified
)
```

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                   SAGE SYSTEM                             │
│                                                           │
│  ┌────────────┐              ┌────────────┐             │
│  │ ARCHITECT  │◄────────────►│   BRAIN    │             │
│  │ (Builder)  │              │ (Assistant)│             │
│  └─────┬──────┘              └──────┬─────┘             │
│        │                             │                   │
│        │                             │                   │
│   ┌────▼─────────────────────────────▼──────┐           │
│   │         MCP MANAGER                      │           │
│   │  Centralized access to all MCPs          │           │
│   └────┬─────────────────────────────────────┘           │
│        │                                                  │
│   ┌────▼──────────────────────────────────────┐          │
│   │         MCP CLIENT LAYER                  │          │
│   │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐    │          │
│   │  │ Git  │ │ n8n  │ │ FS   │ │ MQTT │    │          │
│   │  └──────┘ └──────┘ └──────┘ └──────┘    │          │
│   │  ┌──────┐ ┌──────┐                       │          │
│   │  │Ollama│ │Memory│                       │          │
│   │  └──────┘ └──────┘                       │          │
│   └───────────────────────────────────────────┘          │
│                                                           │
│   ┌─────────────────────────────────────────┐            │
│   │         FASTAPI API SERVER              │            │
│   │  All MCPs accessible via REST endpoints │            │
│   └─────────────────────────────────────────┘            │
└──────────────────────────────────────────────────────────┘
```

---

## Benefits

### For Architect
- ✅ **Filesystem MCP:** Efficient codebase ingestion, hot-reload
- ✅ **Git MCP:** Auto-commit generated code
- ✅ **Ollama MCP:** Cheap plan review with local models
- ✅ **Memory MCP:** Code reuse via semantic search
- ✅ **n8n:** Workflow automation on build complete

### For Brain
- ✅ **MQTT MCP:** Sensor integration, device control
- ✅ **Ollama MCP:** Voice intent classification
- ✅ **Memory MCP:** Episodic memory, user preferences
- ✅ **Filesystem MCP:** Monitor user's active work
- ✅ **n8n:** Pattern-based automation

### For Both
- ✅ **Unified APIs:** Consistent interface across all MCPs
- ✅ **Shared Infrastructure:** Reduce code duplication
- ✅ **Better Observability:** Centralized monitoring
- ✅ **Future-Proof:** Easy to add more MCPs

---

## What's Next

### Tier 2 MCPs (Optional)
1. **PostgreSQL MCP** - Database operations
2. **Supabase MCP** - For projects using Supabase
3. **Slack/Discord MCP** - Notifications
4. **Calendar MCP** - Schedule awareness

### Integration Enhancements
1. Add MCP usage to Architect UI
2. Create voice-triggered MCP workflows
3. Build automated pipelines (code → commit → PR → notify)
4. Add MCP configuration to project manifests

---

## Files Created/Modified

### New Files
1. [shared/mcp/filesystem_client.py](shared/mcp/filesystem_client.py) - 660 lines
2. [shared/mcp/mqtt_client.py](shared/mcp/mqtt_client.py) - 480 lines
3. [shared/mcp/ollama_client.py](shared/mcp/ollama_client.py) - 540 lines
4. [shared/mcp/memory_client.py](shared/mcp/memory_client.py) - 520 lines
5. [shared/mcp/__init__.py](shared/mcp/__init__.py) - MCP Manager
6. [architect/api/routes/mcp.py](architect/api/routes/mcp.py) - REST API endpoints
7. `MCP_TIER1_IMPLEMENTATION.md` (this file)

### Modified Files
1. [architect/api/server.py](architect/api/server.py) - Registered MCP router

### Total Lines of Code
- **New MCP Clients:** ~2,200 lines
- **API Integration:** ~420 lines
- **Total:** ~2,620 lines

---

## Summary

**Status:** ✅ Complete

All Tier 1 MCPs are now implemented and production-ready:
- ✅ Filesystem, MQTT, Ollama, Memory clients created
- ✅ Git and n8n already implemented (previous work)
- ✅ Centralized MCP Manager for easy access
- ✅ REST API endpoints for all MCPs
- ✅ Comprehensive documentation

The Sage system now has a complete MCP infrastructure that enables:
- Advanced file operations
- Real-time sensor communication
- Local LLM inference
- Semantic memory
- Version control automation
- Workflow automation

**Ready for production use!** 🚀

---

**Built by:** Claude Sonnet 4.5
**Date:** 2026-01-13
**Status:** ✅ Production Ready
