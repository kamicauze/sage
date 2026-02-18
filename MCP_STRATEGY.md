# MCP Strategy for Sage (Architect + Brain)

**Goal:** Maximize productivity and capabilities using Model Context Protocol servers across the entire Sage system

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    SAGE SYSTEM                           │
│  ┌──────────────┐              ┌──────────────┐        │
│  │  ARCHITECT   │◄────────────►│    BRAIN     │        │
│  │  (Builder)   │   Bridge     │  (Assistant) │        │
│  └──────────────┘              └──────────────┘        │
│         │                              │                │
│         │                              │                │
│    ┌────▼──────────────────────────────▼─────┐         │
│    │          MCP SERVER LAYER                │         │
│    │  (Shared infrastructure & services)      │         │
│    └──────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────┘
```

---

## TIER 1: CRITICAL MCPs (Implement First)

### 1. Git MCP ⭐⭐⭐⭐⭐
**Value:** MAXIMUM - Benefits both Architect and Brain
**Use Cases:**
- **Architect:** Auto-commit generated code, create feature branches
- **Brain:** "Commit my work", "Create a PR", "What changed today?"
- **Bridge:** Voice-triggered commits via Brain → Architect → Git MCP

**Implementation:**
```bash
# Install
npm install -g @modelcontextprotocol/server-git

# Configure for Architect
# architect/api/mcp/git_client.py
from mcp import Client

class GitMCPClient:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.client = Client("npx -y @modelcontextprotocol/server-git")

    async def commit_changes(self, message: str, files: list[str] = None):
        """Commit generated files with semantic message."""
        return await self.client.call_tool("git_commit", {
            "repo": self.repo_path,
            "message": message,
            "files": files or []
        })

    async def create_branch(self, name: str):
        """Create feature branch for new work."""
        return await self.client.call_tool("git_branch", {
            "repo": self.repo_path,
            "name": name
        })

    async def get_diff(self, file: str = None):
        """Get current changes."""
        return await self.client.call_tool("git_diff", {
            "repo": self.repo_path,
            "file": file
        })

# Configure for Brain (voice commands)
# brain/action/git_actions.py
async def handle_git_command(intent: str, context: dict):
    """Handle voice git commands."""
    git = GitMCPClient(os.getcwd())

    if "commit" in intent:
        await git.commit_changes(
            message=f"chore: {context['description']}",
            files=context.get('files')
        )
        return "Changes committed"

    elif "what changed" in intent:
        diff = await git.get_diff()
        return summarize_diff(diff)
```

**Voice Examples:**
- "Commit my changes with message 'fix bug in voice handler'"
- "Create a branch called feature/mqtt-improvements"
- "What did I change today?"

---

### 2. Filesystem MCP ⭐⭐⭐⭐⭐
**Value:** MAXIMUM - Better file operations, real-time watching
**Use Cases:**
- **Architect:** Efficient codebase ingestion, large file handling
- **Brain:** File monitoring for conversation context
- **Both:** Replace shell commands with proper file operations

**Implementation:**
```bash
npm install -g @modelcontextprotocol/server-filesystem
```

```python
# architect/api/mcp/fs_client.py
class FilesystemMCPClient:
    async def read_file(self, path: str):
        """Read file with automatic encoding detection."""
        return await self.client.call_tool("read_file", {"path": path})

    async def write_file(self, path: str, content: str):
        """Write file atomically."""
        return await self.client.call_tool("write_file", {
            "path": path,
            "content": content
        })

    async def watch_directory(self, path: str, patterns: list[str]):
        """Watch for file changes (hot reload)."""
        return await self.client.call_tool("watch_directory", {
            "path": path,
            "patterns": patterns  # ["**/*.py", "**/*.ts"]
        })

    async def get_directory_tree(self, path: str, max_depth: int = 3):
        """Get directory structure for context."""
        return await self.client.call_tool("list_directory", {
            "path": path,
            "recursive": True,
            "max_depth": max_depth
        })

# Brain use case: Monitor your work
# brain/perception/file_watcher.py
async def watch_current_work():
    """Track what user is actively working on."""
    fs = FilesystemMCPClient()

    async for event in fs.watch_directory(".", ["**/*.py", "**/*.ts"]):
        if event['type'] == 'modified':
            # User is editing this file - add to conversation context
            memory.remember_fact(f"Currently working on {event['path']}")
```

**Voice Examples:**
- "What files have I been working on?"
- "Watch the brain directory for changes"
- "Show me the directory structure"

---

### 3. MQTT MCP ⭐⭐⭐⭐⭐
**Value:** CRITICAL for Brain - Central to entire system communication
**Use Cases:**
- **Brain:** Sensor data access, service orchestration
- **Architect:** Could generate MQTT-based features
- **Both:** Real-time status monitoring

**Custom Implementation Required:**
```python
# Create custom MCP server for MQTT
# shared/mcp/mqtt_server.py
from mcp.server import Server
import asyncio_mqtt as aiomqtt

class MQTTMCPServer(Server):
    """MCP server wrapping MQTT broker."""

    def __init__(self):
        super().__init__("mqtt")
        self.client = None

    @self.tool()
    async def publish(self, topic: str, payload: dict):
        """Publish to MQTT topic."""
        await self.client.publish(topic, json.dumps(payload))
        return {"status": "published", "topic": topic}

    @self.tool()
    async def subscribe(self, topic: str):
        """Subscribe to MQTT topic."""
        async with self.client.filtered_messages(topic) as messages:
            async for message in messages:
                yield {
                    "topic": message.topic,
                    "payload": json.loads(message.payload)
                }

    @self.tool()
    async def get_sensor_state(self, room: str):
        """Get current sensor state for a room."""
        # Query state from brain's state machine
        state = await get_room_state(room)
        return state

# Usage in Brain
# brain/action/mqtt_actions.py
async def voice_mqtt_control(command: str):
    mqtt = MQTTMCPClient()

    if "turn on" in command:
        await mqtt.publish("sage/home/lights", {"state": "on"})

    elif "room status" in command:
        state = await mqtt.get_sensor_state("office")
        return f"Office: {'occupied' if state['presence'] else 'empty'}"
```

**Voice Examples:**
- "What's the status of the office sensor?"
- "Turn on the lights in the living room"
- "Show me all active MQTT topics"

---

### 4. Ollama/Local LLM MCP ⭐⭐⭐⭐
**Value:** HIGH - Direct model management
**Use Cases:**
- **Brain:** Model switching, streaming inference
- **Architect:** Use local models for cheap planning
- **Both:** Monitoring model performance

**Implementation:**
```bash
# Ollama has native MCP support
npm install -g @modelcontextprotocol/server-ollama
```

```python
# brain/ai/ollama_mcp.py
class OllamaMCPClient:
    async def chat(self, prompt: str, model: str = "gemma3:12b"):
        """Send chat with automatic model selection."""
        return await self.client.call_tool("ollama_chat", {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False
        })

    async def chat_stream(self, prompt: str, model: str):
        """Stream responses for low latency."""
        async for chunk in self.client.call_tool_stream("ollama_chat", {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True
        }):
            yield chunk['message']['content']

    async def list_models(self):
        """Get available models."""
        return await self.client.call_tool("ollama_list")

    async def pull_model(self, name: str):
        """Download new model."""
        return await self.client.call_tool("ollama_pull", {"name": name})

# Voice use case
# "Download llama3.3 model"
# "Switch to the faster model"
# "What local models do I have?"
```

---

## TIER 2: HIGH-VALUE MCPs (Implement Next)

### 5. PostgreSQL/Database MCP ⭐⭐⭐⭐
**Value:** HIGH - For projects that use databases
**Use Cases:**
- **Architect:** Generate migrations, introspect schemas
- **Brain:** Could track personal data in DB
- **Both:** Query project databases

```bash
npm install -g @modelcontextprotocol/server-postgres
```

```python
# architect/api/mcp/database_client.py
class DatabaseMCPClient:
    async def introspect_schema(self, connection_string: str):
        """Get current database schema."""
        return await self.client.call_tool("postgres_introspect", {
            "connection": connection_string
        })

    async def run_migration(self, sql: str, connection_string: str):
        """Execute database migration."""
        return await self.client.call_tool("postgres_execute", {
            "connection": connection_string,
            "sql": sql
        })

    async def query(self, sql: str, connection_string: str):
        """Query database."""
        return await self.client.call_tool("postgres_query", {
            "connection": connection_string,
            "query": sql
        })

# Architect use case:
# User: "Add a posts table with title and content columns"
# Architect:
#   1. Introspects current schema
#   2. Generates migration SQL
#   3. Runs migration via MCP
#   4. Updates ORM models
#   5. Commits via Git MCP
```

---

### 6. Memory/ChromaDB MCP ⭐⭐⭐⭐
**Value:** HIGH - Unified memory interface
**Use Cases:**
- **Brain:** Semantic search over conversations
- **Architect:** Semantic code search
- **Both:** Shared memory querying

**Custom Implementation:**
```python
# shared/mcp/memory_server.py
class MemoryMCPServer(Server):
    def __init__(self):
        super().__init__("memory")
        self.chroma = chromadb.Client()

    @self.tool()
    async def search_memories(self, query: str, collection: str, n_results: int = 5):
        """Semantic search across memories."""
        coll = self.chroma.get_collection(collection)
        results = coll.query(query_texts=[query], n_results=n_results)
        return results

    @self.tool()
    async def remember(self, text: str, collection: str, metadata: dict):
        """Store new memory."""
        coll = self.chroma.get_or_create_collection(collection)
        coll.add(documents=[text], metadatas=[metadata])

    @self.tool()
    async def recall_conversation(self, days_ago: int = 0):
        """Recall what was discussed N days ago."""
        results = await self.search_memories(
            query=f"conversation from {days_ago} days ago",
            collection="sage_episodes"
        )
        return summarize_episodes(results)

# Voice examples:
# "What did we talk about yesterday?"
# "Remember that I prefer Python over JavaScript"
# "Search my memories for database schema discussions"
```

---

### 7. Supabase MCP ⭐⭐⭐
**Value:** MEDIUM-HIGH - For projects using Supabase
**Use Cases:**
- **Architect:** Generate Supabase features (auth, DB, storage)
- **Brain:** Could use Supabase for cloud sync
- **Both:** Run migrations, manage data

```bash
npm install -g @modelcontextprotocol/server-supabase
```

```python
# architect/api/mcp/supabase_client.py
class SupabaseMCPClient:
    async def run_migration(self, project_url: str, api_key: str, sql: str):
        """Run Supabase migration."""
        return await self.client.call_tool("supabase_migrate", {
            "project_url": project_url,
            "api_key": api_key,
            "sql": sql
        })

    async def generate_types(self, project_url: str, api_key: str):
        """Generate TypeScript types from schema."""
        return await self.client.call_tool("supabase_gen_types", {
            "project_url": project_url,
            "api_key": api_key
        })

    async def invoke_function(self, project_url: str, api_key: str, name: str, args: dict):
        """Call Supabase edge function."""
        return await self.client.call_tool("supabase_invoke", {
            "project_url": project_url,
            "api_key": api_key,
            "function": name,
            "args": args
        })

# Architect workflow:
# User: "Add user authentication with Supabase"
# Architect:
#   1. Creates auth schema migration (Supabase MCP)
#   2. Generates TypeScript types (Supabase MCP)
#   3. Creates auth components
#   4. Commits (Git MCP)
```

---

### 8. Slack/Discord/Notifications MCP ⭐⭐⭐
**Value:** MEDIUM - Team communication
**Use Cases:**
- **Brain:** Send notifications based on patterns
- **Architect:** Notify when builds complete
- **Both:** Team collaboration

```bash
npm install -g @modelcontextprotocol/server-slack
```

```python
# brain/action/notifications.py
class NotificationsMCPClient:
    async def send_slack(self, channel: str, message: str):
        """Send Slack message."""
        return await self.client.call_tool("slack_send", {
            "channel": channel,
            "text": message
        })

# Brain use case: Pattern-based notifications
# brain/core/summary_engine.py
async def notify_pattern(pattern: str, context: dict):
    """Notify when concerning pattern detected."""
    slack = NotificationsMCPClient()

    if pattern == "OVERWORK_LATE":
        await slack.send_slack(
            channel="#health-alerts",
            message=f"⚠️ Working late detected: {context['duration']}h past bedtime"
        )

    elif pattern == "SCREEN_HYPERFOCUS":
        await slack.send_slack(
            channel="#productivity",
            message=f"🔍 Deep focus session: {context['duration']} min without break"
        )
```

---

### 9. Google Calendar/Time MCP ⭐⭐⭐
**Value:** MEDIUM - Context awareness
**Use Cases:**
- **Brain:** Meeting detection, schedule awareness
- **Architect:** Time-based task planning
- **Both:** Productivity optimization

```python
# brain/perception/calendar_context.py
class CalendarMCPClient:
    async def get_current_event(self):
        """Get current calendar event."""
        return await self.client.call_tool("calendar_current")

    async def check_availability(self, start: datetime, end: datetime):
        """Check if time slot is free."""
        return await self.client.call_tool("calendar_check", {
            "start": start.isoformat(),
            "end": end.isoformat()
        })

# Brain integration:
# - Detect meetings automatically
# - Suppress notifications during calls
# - "Am I free at 3pm?"
# - "What's my next meeting?"
```

---

## TIER 3: SPECIALIZED MCPs (Project-Specific)

### 10. Docker/Container MCP ⭐⭐
**Value:** MEDIUM - Infrastructure management
```python
# For managing Sage services
# "Restart the MQTT broker"
# "Check brain container logs"
# "Deploy new Architect version"
```

### 11. Sentry/Error Tracking MCP ⭐⭐
**Value:** MEDIUM - Quality monitoring
```python
# Track errors in generated code
# Monitor Brain stability
# Alert on critical failures
```

### 12. Linear/Jira MCP ⭐⭐
**Value:** LOW-MEDIUM - Task management
```python
# Create issues from failed builds
# Link commits to tickets
# "What's my current sprint?"
```

---

## IMPLEMENTATION ROADMAP

### Week 1: Foundation (TIER 1)
**Day 1-2:** Git MCP
- Architect: Auto-commit, branching
- Brain: Voice git commands
- Test: "Commit my changes", "Create branch feature/test"

**Day 3-4:** Filesystem MCP
- Architect: Better file operations
- Brain: File watching
- Test: "Watch this directory", "What changed?"

**Day 5:** MQTT MCP
- Brain: Enhanced sensor control
- Test: "Office status?", "Turn on lights"

### Week 2: AI & Memory (TIER 1-2)
**Day 1-2:** Ollama MCP
- Brain: Model management
- Test: "Switch to faster model", "Pull llama3.3"

**Day 3-4:** Memory/ChromaDB MCP
- Both: Unified memory access
- Test: "What did we discuss yesterday?"

**Day 5:** Database MCP (if needed for projects)
- Architect: Schema introspection
- Test: "Add users table"

### Week 3: Integrations (TIER 2-3)
**As needed:** Supabase, Slack, Calendar, etc.
- Add based on active projects
- Configure per-project in manifests

---

## CONFIGURATION IN PROJECT MANIFESTS

```yaml
# architect/projects/sage.yaml
project:
  id: sage_brain

mcp:
  enabled: true
  servers:
    # TIER 1: Always enabled
    - name: git
      enabled: true
      auto_commit: false  # Manual approval
      auto_branch: true   # Auto-create branches

    - name: filesystem
      enabled: true
      watch_patterns: ["**/*.py", "**/*.ts"]

    - name: mqtt
      enabled: true
      broker: "localhost:1883"
      topics:
        subscribe: ["sage/#"]
        publish: ["sage/brain/#", "sage/architect/#"]

    - name: ollama
      enabled: true
      host: "http://localhost:11434"
      models: ["gemma3:12b", "llama3.1:8b"]

    # TIER 2: Project-specific
    - name: memory
      enabled: true
      collections: ["sage_episodes", "sage_facts", "sage_preferences"]

    - name: database
      enabled: false  # Only if project uses DB

    - name: supabase
      enabled: false  # Only for Supabase projects

    # TIER 3: Optional
    - name: slack
      enabled: false
      webhook: ${SLACK_WEBHOOK_URL}
```

---

## BENEFITS SUMMARY

### For Architect
✅ Auto-commit generated code (Git MCP)
✅ Better file operations (Filesystem MCP)
✅ Database schema introspection (Database MCP)
✅ Supabase feature generation (Supabase MCP)
✅ Local LLM for cheap planning (Ollama MCP)

### For Brain
✅ Voice-triggered git commands (Git MCP)
✅ File monitoring for context (Filesystem MCP)
✅ Enhanced MQTT control (MQTT MCP)
✅ Model management (Ollama MCP)
✅ Unified memory access (Memory MCP)
✅ Calendar awareness (Calendar MCP)
✅ Proactive notifications (Slack MCP)

### For Both
✅ Shared infrastructure
✅ Consistent APIs
✅ Better observability
✅ Reduced code duplication

---

## COST ANALYSIS

**Free/Open Source:**
- Git MCP: Free
- Filesystem MCP: Free
- MQTT MCP: Free (custom implementation)
- Ollama MCP: Free (local inference)
- Memory MCP: Free (custom ChromaDB wrapper)
- Database MCP: Free (tool only, DB separate)

**Paid Services (if used):**
- Supabase MCP: Free tier available, Pro $25/mo
- Slack MCP: Free
- Sentry MCP: Free tier, Pro $26/mo
- Linear MCP: Free tier, Pro $8/user/mo

**Recommendation:** Start with free tier (Tier 1), add paid as needed

---

## NEXT STEP

**Implement Git MCP first** - gives immediate 10x productivity boost for both Architect and Brain.

Timeline: 4-6 hours
Value: Massive

Ready to start?
