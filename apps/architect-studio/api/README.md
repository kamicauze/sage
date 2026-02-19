# Architect API

FastAPI backend for the Sage Architect system.

## Features

- **Plan Generation**: Generate implementation plans using AI
- **Build Execution**: Execute builds from plans with automatic testing
- **Memory Search**: Semantic search over ingested codebase
- **Usage Tracking**: Monitor AI usage and budget
- **Real-time Updates**: WebSocket support for build progress streaming
- **Approval Queue**: Human-in-the-middle controls for risky actions

## Installation

### 1. Install Dependencies

```bash
# Install main requirements first
pip install -r requirements.txt

# Install API-specific requirements
pip install -r architect/api/requirements.txt
```

### 2. Configure Environment

Make sure you have `brain/.env` configured with your API keys:

```bash
# Ollama (local)
OLLAMA_HOST=http://localhost:11434

# Optional cloud providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
XAI_API_KEY=...
```

### 3. Start the Server

```bash
# From project root
uvicorn architect.api.server:app --reload --port 8000

# Or run directly
python architect/api/server.py
```

The API will be available at:
- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- WebSocket: `ws://localhost:8000/ws/{client_id}`

## API Endpoints

### Health & Stats

#### `GET /`
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-01-13T10:30:00",
  "architect_version": "1.0.0"
}
```

#### `GET /stats/usage`
Get usage and budget statistics.

**Query Parameters:**
- `daily_limit` (float): Daily burst limit in USD (default: 5.0)
- `monthly_limit` (float): Monthly budget limit in USD (default: 120.0)

**Response:**
```json
{
  "current_month": "2026-01",
  "monthly_spend": 80.40,
  "monthly_limit": 120.0,
  "daily_spend": 2.30,
  "daily_limit": 5.0,
  "budget_percentage": 67.0,
  "recent_calls": [...]
}
```

#### `GET /stats/usage/history`
Get detailed usage history.

**Query Parameters:**
- `limit` (int): Maximum entries to return (default: 100)

#### `GET /stats/memory`
Get memory system statistics.

**Query Parameters:**
- `project_id` (string): Project ID (default: "sage_brain")

### Build Endpoints

#### `POST /builds/plan`
Generate an implementation plan.

**Request Body:**
```json
{
  "query": "Add MQTT reconnection logic with exponential backoff",
  "request_type": "feature",
  "manifest_path": "architect/projects/sage.yaml"
}
```

**Response:**
```json
{
  "status": "SUCCESS",
  "plan_content": "# Implementation Plan\n...",
  "plan_path": "architect/workspaces/sage_brain/plan.md",
  "routing_decision": {
    "route": "CLOUD",
    "score": 9,
    "reason": "Complex architectural change",
    "provider": "anthropic",
    "model": "claude-3-opus",
    "estimated_cost_min": 0.15,
    "estimated_cost_max": 0.50
  },
  "context_snippets": [...],
  "summary": "Plan generated successfully"
}
```

#### `POST /builds/build`
Execute a build from existing plan.

**Request Body:**
```json
{
  "manifest_path": "architect/projects/sage.yaml"
}
```

#### `GET /builds/plan/{project_id}`
Get the current plan for a project.

#### `GET /builds/artifacts/{project_id}`
List all generated artifacts for a project.

#### `DELETE /builds/plan/{project_id}`
Delete the current plan for a project.

### Memory Endpoints

#### `POST /memory/search`
Search memory for relevant code snippets.

**Request Body:**
```json
{
  "query": "MQTT connection handling",
  "project_id": "sage_brain",
  "n_results": 5,
  "zone_filter": "hands"
}
```

**Response:**
```json
{
  "results": [
    {
      "content": "def connect_mqtt():\n    ...",
      "source": "brain/mqtt/client.py",
      "zone_name": "The Hands",
      "role": "hands",
      "distance": 0.23
    }
  ],
  "query": "MQTT connection handling",
  "total_results": 5
}
```

#### `POST /memory/ingest`
Ingest files into memory.

**Request Body:**
```json
{
  "file_paths": ["brain/mqtt/client.py", "brain/mqtt/config.py"],
  "manifest_path": "architect/projects/sage.yaml"
}
```

#### `GET /memory/zones/{project_id}`
Get all cognitive zones for a project.

#### `GET /memory/files/{project_id}`
List all indexed files.

#### `DELETE /memory/collection/{project_id}`
Delete entire memory collection (WARNING: permanent).

### Approval Endpoints

#### `POST /approvals/proposals`
Create a new approval proposal.

**Request Body:**
```json
{
  "title": "Switch model for LOCAL routing",
  "summary": "Move LOCAL from gemma to qwen2.5:14b",
  "source": "sage.research",
  "risk": "high",
  "actions": [
    {
      "type": "model_switch",
      "target": "ollama/qwen2.5:14b",
      "payload": { "route": "LOCAL" }
    }
  ],
  "metadata": {
    "candidate_id": "cand-001"
  },
  "expires_in_seconds": 900
}
```

#### `GET /approvals/pending`
List pending approvals.

#### `GET /approvals/{proposal_id}`
Get a proposal by ID.

#### `POST /approvals/{proposal_id}/decision`
Submit decision (`approve` or `deny`).

**Request Body:**
```json
{
  "decision": "approve",
  "reviewer": "mobile_user",
  "reason": "Latency and quality looked good in canary"
}
```

### Chat Endpoints

#### `POST /chat`
Send a user message and get an assistant reply.

**Request Body:**
```json
{
  "message": "What's pending today?",
  "conversation_id": "optional-existing-id",
  "provider": "brain",
  "system_prompt": "optional system instruction"
}
```

`provider` options:
- `brain`: routes to Brain runtime over MQTT (`sage/brain/chat/request` -> `sage/brain/chat/response`)
- `ollama` / cloud providers: uses Architect `LLMClient` directly

For `provider=brain`, make sure:
- MQTT broker is reachable at `MQTT_HOST:MQTT_PORT`
- Brain runtime is running and subscribed to chat request topic

#### `GET /chat/{conversation_id}`
Fetch stored messages for a conversation.

#### `DELETE /chat/{conversation_id}`
Delete a conversation and all stored messages.

### WebSocket

#### `WS /ws/{client_id}`
Real-time build progress streaming.

**Connect:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/my-client-id');
```

**Send:**
```json
{
  "action": "start_build",
  "build_id": "my-build-123"
}
```

**Receive:**
```json
{
  "type": "build_progress",
  "build_id": "my-build-123",
  "phase": "generating",
  "message": "Generated file 2/3",
  "progress": 66,
  "timestamp": "2026-01-13T10:30:00"
}
```

## Usage Examples

### Python

```python
import requests

# Generate plan
response = requests.post("http://localhost:8000/builds/plan", json={
    "query": "Add error handling to MQTT client"
})
plan = response.json()
print(f"Plan generated: {plan['plan_path']}")

# Check usage
usage = requests.get("http://localhost:8000/stats/usage").json()
print(f"Budget used: {usage['budget_percentage']}%")

# Search memory
results = requests.post("http://localhost:8000/memory/search", json={
    "query": "error handling",
    "n_results": 3
}).json()
print(f"Found {results['total_results']} results")
```

### cURL

```bash
# Health check
curl http://localhost:8000/

# Generate plan
curl -X POST http://localhost:8000/builds/plan \
  -H "Content-Type: application/json" \
  -d '{"query": "Add logging to MQTT client"}'

# Get usage stats
curl http://localhost:8000/stats/usage

# Search memory
curl -X POST http://localhost:8000/memory/search \
  -H "Content-Type: application/json" \
  -d '{"query": "MQTT", "n_results": 5}'
```

### JavaScript/TypeScript

```typescript
// Generate plan
const response = await fetch('http://localhost:8000/builds/plan', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    query: 'Add retry logic to API calls'
  })
});
const plan = await response.json();

// WebSocket for real-time updates
const ws = new WebSocket('ws://localhost:8000/ws/my-client');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Build progress:', data);
};
ws.send(JSON.stringify({
  action: 'start_build',
  build_id: 'build-123'
}));
```

## Architecture

```
architect/api/
├── __init__.py
├── server.py          # Main FastAPI app
├── models.py          # Pydantic schemas
├── websocket.py       # WebSocket handlers
├── routes/
│   ├── builds.py      # Plan & build endpoints
│   ├── stats.py       # Usage & stats endpoints
│   └── memory.py      # Memory search endpoints
├── requirements.txt   # API dependencies
└── README.md         # This file
```

## Development

### Running Tests

```bash
pytest architect/api/tests/
```

### Hot Reload

The server runs with `--reload` by default, so changes are automatically picked up.

### API Documentation

FastAPI automatically generates interactive docs:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### CORS Configuration

Set allowed origins with `SAGE_ARCHITECT_API_CORS_ORIGINS` (comma-separated):

```bash
SAGE_ARCHITECT_API_CORS_ORIGINS=https://architect.example.com,https://app.example.com
```

For local mobile-web development (Expo web), include the Expo origin as well, e.g.:

```bash
SAGE_ARCHITECT_API_CORS_ORIGINS=http://localhost:3000,http://localhost:19006
```

## Production Deployment

### Using Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt architect/api/requirements.txt ./
RUN pip install -r requirements.txt -r architect/api/requirements.txt

COPY . .

CMD ["uvicorn", "architect.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables

```bash
# Server config
PORT=8000
HOST=0.0.0.0
RELOAD=false

# API auth / security
# If token is set, auth defaults to required=true unless explicitly disabled.
SAGE_ARCHITECT_API_TOKEN=change-me
SAGE_ARCHITECT_API_AUTH_REQUIRED=true
SAGE_ARCHITECT_API_CORS_ORIGINS=https://architect.example.com

# API keys (from brain/.env)
OLLAMA_HOST=http://localhost:11434
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
```

### Auth Header

Use one of:
- `Authorization: Bearer <token>`
- `X-Architect-Token: <token>`

### Correlation Header

Requests may include:
- `X-Architect-Correlation-Id: <your-id>`

If omitted, the API generates one and returns:
- `X-Architect-Correlation-Id`

### Reverse Proxy (nginx)

```nginx
server {
    listen 80;
    server_name architect.yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

## Troubleshooting

### Import Errors

Make sure you're running from the project root:
```bash
cd /path/to/sage
python -m uvicorn architect.api.server:app
```

### ChromaDB Issues

If memory endpoints fail, check ChromaDB installation:
```bash
pip install chromadb --upgrade
```

### WebSocket Connection Failed

Ensure your client supports WebSocket upgrades. Some proxies may block WebSocket connections.

## License

Part of the Sage project.
