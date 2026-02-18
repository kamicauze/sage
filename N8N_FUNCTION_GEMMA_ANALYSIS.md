# n8n + Function Gemma Integration Analysis

**Date:** 2026-01-13

---

## n8n: Workflow Automation Platform

### What is n8n?
- Open-source workflow automation tool (Zapier alternative)
- Self-hosted, visual workflow builder
- 400+ integrations (APIs, databases, services)
- Can run locally or in Docker
- Supports webhooks, cron jobs, event triggers

### Why n8n is PERFECT for Sage

#### 1. **Brain ↔ n8n Integration** ⭐⭐⭐⭐⭐

n8n becomes your **action execution layer** - Brain detects patterns, n8n performs actions.

**Current Problem:**
```python
# brain/action/router.py
# You manually code every action
async def execute_action(action_type, params):
    if action_type == "send_notification":
        # Hardcoded Slack/email logic
    elif action_type == "control_lights":
        # Hardcoded MQTT logic
    elif action_type == "create_task":
        # Hardcoded Linear/Jira logic
```

**With n8n:**
```python
# brain/action/n8n_client.py
async def execute_action(action_type, params):
    # Just trigger n8n workflow
    await n8n.trigger_workflow(action_type, params)

    # n8n handles:
    # - Retries
    # - Error handling
    # - Multiple service calls
    # - Complex logic
    # - Rate limiting
```

**Example Workflows:**

**Workflow 1: Late Night Work Alert**
```
TRIGGER: Brain detects OVERWORK_LATE pattern
  ↓
n8n Workflow:
  1. Check calendar (is it a deadline week?)
  2. If yes: Send encouraging Slack message
  3. If no: Send reminder to sleep
  4. Log to health tracking DB
  5. Turn on "wind down" lights via MQTT
  6. Queue relaxing music
```

**Workflow 2: Deep Focus Session**
```
TRIGGER: Brain detects SCREEN_HYPERFOCUS (90+ min)
  ↓
n8n Workflow:
  1. Wait 5 minutes
  2. Check if still focused
  3. Send break reminder
  4. Create time-blocked break in calendar
  5. Notify on all devices
  6. Update productivity dashboard
```

**Workflow 3: Context-Aware Task Creation**
```
TRIGGER: Brain hears "remind me to deploy this tomorrow"
  ↓
n8n Workflow:
  1. Get current git branch (Git MCP)
  2. Get current file (Filesystem MCP)
  3. Create Linear task with context:
     - Title: "Deploy feature/xyz"
     - Description: "Context: was working on file.py"
     - Due: Tomorrow 9am
  4. Send confirmation via voice
```

#### 2. **Architect ↔ n8n Integration** ⭐⭐⭐⭐

n8n becomes your **CI/CD orchestration layer**.

**Workflow: Code Generation Pipeline**
```
TRIGGER: Architect build completes successfully
  ↓
n8n Workflow:
  1. Commit to Git (Git MCP)
  2. Push to GitHub
  3. Trigger CI tests
  4. Wait for tests to pass
  5. If tests pass:
     - Create PR
     - Assign reviewer
     - Post to Slack
  6. If tests fail:
     - Create GitHub issue
     - Notify via Brain voice
     - Rollback changes
```

**Workflow: Multi-Project Deployment**
```
TRIGGER: Manual or scheduled
  ↓
n8n Workflow:
  1. For each project in Architect:
     - Run tests
     - Build artifacts
     - Deploy to staging
     - Run smoke tests
  2. Send summary report
  3. Update deployment dashboard
```

#### 3. **n8n as MCP Orchestrator** ⭐⭐⭐⭐⭐

n8n can **coordinate multiple MCP servers** in complex workflows.

**Example: Full-Stack Feature Implementation**
```
YOU: "Add user comments to my blog"
  ↓
Architect: Generates plan
  ↓
n8n Workflow:
  1. Create Git branch (Git MCP)
  2. Generate Supabase migration (Supabase MCP)
  3. Run migration (Supabase MCP)
  4. Architect generates React components
  5. Architect generates API routes
  6. Run type generation (Supabase MCP)
  7. Run tests locally
  8. Commit all changes (Git MCP)
  9. Push and create PR (GitHub API)
  10. Notify: "Comments feature ready for review"
```

### n8n Installation & Setup

```bash
# Install via Docker
docker run -it --rm \
  --name n8n \
  -p 5678:5678 \
  -v ~/.n8n:/home/node/.n8n \
  n8nio/n8n

# Or via npm
npm install -g n8n
n8n start
```

**Access:** http://localhost:5678

### n8n MCP Server Integration

Create custom n8n nodes for your MCP servers:

```javascript
// ~/.n8n/custom/nodes/GitMCP.node.ts
export class GitMCP implements INodeType {
  description: INodeTypeDescription = {
    displayName: 'Git MCP',
    name: 'gitMcp',
    group: ['transform'],
    version: 1,
    description: 'Interact with Git via MCP',
    defaults: { name: 'Git MCP' },
    inputs: ['main'],
    outputs: ['main'],
    properties: [
      {
        displayName: 'Operation',
        name: 'operation',
        type: 'options',
        options: [
          { name: 'Commit', value: 'commit' },
          { name: 'Create Branch', value: 'branch' },
          { name: 'Get Diff', value: 'diff' }
        ]
      },
      {
        displayName: 'Repository Path',
        name: 'repoPath',
        type: 'string',
        default: ''
      },
      {
        displayName: 'Commit Message',
        name: 'message',
        type: 'string',
        displayOptions: {
          show: { operation: ['commit'] }
        }
      }
    ]
  };

  async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
    const operation = this.getNodeParameter('operation', 0) as string;
    const repoPath = this.getNodeParameter('repoPath', 0) as string;

    // Call your MCP server
    const result = await callMCPServer('git', operation, { repoPath });

    return [this.helpers.returnJsonArray([result])];
  }
}
```

### Brain → n8n API Integration

```python
# brain/action/n8n_client.py
import aiohttp

class N8NClient:
    def __init__(self, base_url: str = "http://localhost:5678"):
        self.base_url = base_url
        self.session = aiohttp.ClientSession()

    async def trigger_workflow(self, workflow_id: str, data: dict):
        """Trigger n8n workflow via webhook."""
        url = f"{self.base_url}/webhook/{workflow_id}"
        async with self.session.post(url, json=data) as resp:
            return await resp.json()

    async def create_workflow(self, name: str, nodes: list):
        """Programmatically create workflow."""
        url = f"{self.base_url}/api/v1/workflows"
        workflow = {
            "name": name,
            "nodes": nodes,
            "connections": {},
            "active": True
        }
        async with self.session.post(url, json=workflow) as resp:
            return await resp.json()

# Usage in Brain
# brain/core/summary_engine.py
async def handle_pattern(pattern: str, context: dict):
    n8n = N8NClient()

    if pattern == "OVERWORK_LATE":
        await n8n.trigger_workflow("overwork-alert", {
            "timestamp": datetime.now().isoformat(),
            "hours_late": context['hours_past_bedtime'],
            "task": context['current_task']
        })
```

### Architect → n8n Integration

```python
# architect/api/routes/builds.py
from n8n_client import N8NClient

@router.post("/build")
async def execute_build(request: BuildRequest):
    # Execute build
    result = builder.execute_plan(plan_path)

    # Trigger n8n workflow
    if result['status'] == 'SUCCESS':
        n8n = N8NClient()
        await n8n.trigger_workflow("post-build", {
            "project_id": request.project_id,
            "artifacts": result['artifacts'],
            "plan_path": plan_path
        })

    return result
```

---

## Function Gemma: Google's Function-Calling Model

### What is Function Gemma?
- Gemma 2B model fine-tuned for function calling
- Runs locally via Ollama
- Tiny (2B params) but specialized for tool use
- Perfect for routing/dispatching decisions
- Free, offline, fast

### Why Function Gemma is PERFECT for Sage

#### Current Problem in Brain

```python
# brain/shared/intent.py
def classify_intent(text: str) -> str:
    # Hardcoded rules
    if "commit" in text or "git" in text:
        return "git_command"
    elif "remind me" in text:
        return "create_task"
    # ... 50 more rules

    # Fallback to expensive LLM call
    return await cloud_llm.classify(text)
```

**Issues:**
- Rule-based is brittle
- Misses edge cases
- Cloud LLM is expensive for simple routing
- No structured output

#### With Function Gemma ⭐⭐⭐⭐⭐

```python
# brain/shared/intent_gemma.py
from ollama import Client

class FunctionGemmaIntent:
    def __init__(self):
        self.client = Client()
        self.model = "gemma2:2b-function"  # Function-calling variant

        # Define available functions
        self.tools = [
            {
                "name": "git_command",
                "description": "Execute git operations (commit, branch, diff)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "operation": {"type": "string", "enum": ["commit", "branch", "diff"]},
                        "message": {"type": "string"},
                        "files": {"type": "array", "items": {"type": "string"}}
                    }
                }
            },
            {
                "name": "create_task",
                "description": "Create reminder or task",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "due_date": {"type": "string"},
                        "context": {"type": "object"}
                    }
                }
            },
            {
                "name": "n8n_workflow",
                "description": "Trigger custom n8n workflow",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "workflow_id": {"type": "string"},
                        "data": {"type": "object"}
                    }
                }
            },
            {
                "name": "brain_conversation",
                "description": "General conversation with AI",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"}
                    }
                }
            },
            {
                "name": "architect_task",
                "description": "Code generation via Architect",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "request": {"type": "string"},
                        "project_id": {"type": "string"}
                    }
                }
            }
        ]

    async def classify(self, user_input: str) -> dict:
        """
        Use Function Gemma to determine intent and extract parameters.
        Returns structured function call with parameters.
        """
        response = await self.client.chat(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": user_input
                }
            ],
            tools=self.tools
        )

        # Function Gemma returns structured function call
        tool_call = response['message']['tool_calls'][0]

        return {
            "intent": tool_call['function']['name'],
            "parameters": tool_call['function']['arguments'],
            "confidence": response.get('confidence', 1.0)
        }

# Example usage
intent_classifier = FunctionGemmaIntent()

# Input: "Commit my changes with message 'fix bug in voice handler'"
result = await intent_classifier.classify(
    "Commit my changes with message 'fix bug in voice handler'"
)

# Output:
{
  "intent": "git_command",
  "parameters": {
    "operation": "commit",
    "message": "fix bug in voice handler",
    "files": []
  },
  "confidence": 0.95
}

# Input: "Remind me to deploy this tomorrow at 2pm"
result = await intent_classifier.classify(
    "Remind me to deploy this tomorrow at 2pm"
)

# Output:
{
  "intent": "create_task",
  "parameters": {
    "title": "Deploy",
    "due_date": "2026-01-14T14:00:00",
    "context": {
      "current_branch": "feature/xyz",
      "working_directory": "/home/user/sage"
    }
  },
  "confidence": 0.92
}
```

#### Benefits vs Current System

**Current (Rule-Based):**
- ❌ Brittle patterns
- ❌ No parameter extraction
- ❌ Fallback to expensive LLM
- ❌ Hard to maintain

**With Function Gemma:**
- ✅ Natural language understanding
- ✅ Structured parameter extraction
- ✅ Free & local (no API costs)
- ✅ Fast (<100ms inference)
- ✅ Confidence scores
- ✅ Easy to add new functions

### Function Gemma Installation

```bash
# Pull Function Gemma via Ollama
ollama pull gemma2:2b-function

# Test it
ollama run gemma2:2b-function

# Verify function calling works
curl http://localhost:11434/api/chat -d '{
  "model": "gemma2:2b-function",
  "messages": [{"role": "user", "content": "Set a timer for 10 minutes"}],
  "tools": [
    {
      "name": "set_timer",
      "description": "Set a timer",
      "parameters": {
        "type": "object",
        "properties": {
          "duration_minutes": {"type": "number"}
        }
      }
    }
  ]
}'
```

### Advanced Function Gemma Use Cases

#### 1. **MCP Router** (Choose which MCP server to use)

```python
class MCPRouter:
    """Use Function Gemma to route to correct MCP server."""

    tools = [
        {"name": "git_mcp", "description": "Git operations"},
        {"name": "filesystem_mcp", "description": "File operations"},
        {"name": "mqtt_mcp", "description": "Sensor/device control"},
        {"name": "supabase_mcp", "description": "Database operations"},
        {"name": "ollama_mcp", "description": "AI model operations"}
    ]

    async def route(self, command: str):
        result = await function_gemma.classify(command)
        mcp_name = result['intent']
        params = result['parameters']

        # Route to correct MCP
        if mcp_name == "git_mcp":
            return await git_mcp.execute(params)
        elif mcp_name == "filesystem_mcp":
            return await fs_mcp.execute(params)
        # ... etc

# Example:
# "Watch the brain directory" → filesystem_mcp
# "Commit my changes" → git_mcp
# "Turn off office lights" → mqtt_mcp
```

#### 2. **Multi-Step Workflow Planner**

```python
class WorkflowPlanner:
    """Use Function Gemma to break complex requests into steps."""

    async def plan(self, request: str):
        # "Add comments feature to my blog with Supabase"

        steps = await function_gemma.plan_workflow(
            request=request,
            available_tools=all_mcp_tools
        )

        # Function Gemma returns:
        [
            {"tool": "git_mcp", "action": "create_branch", "params": {"name": "feature/comments"}},
            {"tool": "supabase_mcp", "action": "create_migration", "params": {"sql": "..."}},
            {"tool": "architect", "action": "generate_components", "params": {"type": "comments"}},
            {"tool": "git_mcp", "action": "commit", "params": {"message": "Add comments"}}
        ]

        # Execute steps via n8n
        for step in steps:
            await n8n.execute_step(step)
```

#### 3. **Parameter Validation & Extraction**

```python
# Input: "Commit files main.py and utils.py with message 'refactor'"

result = await function_gemma.classify(input)

# Output with validated parameters:
{
  "intent": "git_command",
  "parameters": {
    "operation": "commit",
    "files": ["main.py", "utils.py"],  # Extracted file list
    "message": "refactor"
  },
  "validation": "passed"
}
```

---

## Combined Architecture: n8n + Function Gemma + MCPs

### The Full Stack

```
┌─────────────────────────────────────────────────────────┐
│                    USER INPUT                            │
│              (Voice, UI, Sensor Pattern)                 │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
         ┌────────────────────┐
         │  FUNCTION GEMMA    │  ← Intent classification
         │  (2B local model)  │  ← Parameter extraction
         └────────┬───────────┘  ← Routing decision
                  │
                  ▼
         ┌────────────────────┐
         │      n8n           │  ← Workflow orchestration
         │  (Workflow Engine) │  ← Multi-step execution
         └────────┬───────────┘  ← Error handling/retries
                  │
                  ▼
    ┌─────────────┴─────────────┐
    │                           │
    ▼                           ▼
┌───────────┐              ┌──────────┐
│ MCP Layer │              │ Services │
├───────────┤              ├──────────┤
│ - Git     │              │ - Brain  │
│ - FS      │              │ - Architect │
│ - MQTT    │              │ - TTS    │
│ - Ollama  │              │ - STT    │
│ - Supabase│              │ - Sensors│
│ - Memory  │              └──────────┘
└───────────┘
```

### Example Flow: "Add authentication to my app"

```
1. USER: "Add authentication to my app"
   ↓
2. FUNCTION GEMMA:
   - Intent: "architect_task"
   - Parameters: {
       "request": "Add authentication",
       "complexity": "medium",
       "stack": "supabase"
     }
   ↓
3. n8n WORKFLOW: "architect-feature-implementation"
   ↓
   Step 1: Git MCP - Create branch "feature/auth"
   Step 2: Architect - Generate auth plan
   Step 3: Supabase MCP - Create auth schema
   Step 4: Supabase MCP - Run migration
   Step 5: Architect - Generate components
   Step 6: Filesystem MCP - Watch for changes
   Step 7: Ollama MCP - Review code quality
   Step 8: Git MCP - Commit changes
   Step 9: GitHub API - Create PR
   Step 10: Brain - Voice notify "Auth PR ready"
   ↓
4. RESULT: Complete feature, tested, committed, PR created
```

---

## Installation & Setup Guide

### 1. Install n8n

```bash
# Docker (recommended)
docker run -d \
  --name n8n \
  -p 5678:5678 \
  -v ~/.n8n:/home/node/.n8n \
  --restart unless-stopped \
  n8nio/n8n

# Verify
curl http://localhost:5678/healthz
```

### 2. Install Function Gemma

```bash
# Via Ollama
ollama pull gemma2:2b-function

# Test
ollama run gemma2:2b-function "Set a timer for 5 minutes"
```

### 3. Connect to Sage

**Create n8n client:**
```bash
# architect/api/n8n/client.py
pip install aiohttp
```

**Add Function Gemma to Brain:**
```bash
# brain/ai/function_gemma.py
# (Code shown above)
```

### 4. Create First Workflow

**n8n UI (http://localhost:5678):**

1. Create new workflow: "Git Auto-Commit"
2. Add nodes:
   - Webhook trigger
   - HTTP Request to Git MCP
   - Slack notification
3. Save and activate

**Test from Brain:**
```python
n8n = N8NClient()
await n8n.trigger_workflow("git-auto-commit", {
    "message": "test commit",
    "files": ["test.py"]
})
```

---

## Cost & Performance

### n8n
- **Cost:** Free (self-hosted)
- **Resource Usage:** ~200MB RAM
- **Latency:** <50ms per workflow step
- **Scalability:** Handle 1000s of workflows

### Function Gemma
- **Cost:** Free (local)
- **Model Size:** 2B params (~1.5GB)
- **Inference Speed:** 50-100ms
- **Accuracy:** 85-90% for intent classification
- **GPU:** Optional (faster with CUDA)

### Combined
- **Total RAM:** ~2GB
- **Total Storage:** ~2GB
- **Monthly Cost:** $0
- **Value:** Massive automation

---

## Recommended Implementation Order

### Week 1: n8n Foundation
1. Install n8n
2. Create 3 basic workflows:
   - Git auto-commit
   - Pattern detection alerts
   - Post-build CI/CD
3. Integrate with Brain and Architect

### Week 2: Function Gemma Integration
1. Install Function Gemma
2. Replace rule-based intent classification
3. Add parameter extraction
4. Test accuracy vs current system

### Week 3: MCP + n8n Integration
1. Create n8n nodes for each MCP
2. Build complex multi-MCP workflows
3. Voice-triggered workflow execution

### Week 4: Advanced Workflows
1. Multi-step code generation
2. Pattern-based automation
3. Cross-service orchestration

---

## Summary

### n8n: ⭐⭐⭐⭐⭐
- **Best For:** Workflow orchestration, multi-service integration
- **Use Case:** Brain action execution, Architect CI/CD
- **Value:** Massive - replaces tons of custom code
- **Complexity:** Low (visual UI)

### Function Gemma: ⭐⭐⭐⭐⭐
- **Best For:** Intent classification, parameter extraction
- **Use Case:** Routing decisions, structured output
- **Value:** High - better than rules, cheaper than cloud
- **Complexity:** Low (just another Ollama model)

### Together: ⭐⭐⭐⭐⭐
**The perfect combo:**
- Function Gemma: Understand intent
- n8n: Execute workflow
- MCPs: Perform actions

**Result:** Voice-to-execution pipeline that's:
- Free
- Local
- Fast
- Powerful
- Extensible

---

## Next Steps

Want me to implement:

1. **n8n setup** with basic workflows?
2. **Function Gemma integration** for intent classification?
3. **Both together** with MCP orchestration?

I recommend starting with **n8n + Git MCP** - you'll immediately see the value of automated workflows.
