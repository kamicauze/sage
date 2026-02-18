# Architect API - Quick Start Guide

Get the Architect API running in 3 minutes!

## 1. Install Dependencies (30 seconds)

```bash
# From the sage project root
pip install fastapi uvicorn websockets pydantic python-multipart
```

## 2. Start the Server (10 seconds)

```bash
# Option 1: Using the start script
./architect/api/start.sh

# Option 2: Direct command
uvicorn architect.api.server:app --reload --port 8000
```

## 3. Test It! (30 seconds)

Open your browser to:
- **http://localhost:8000/docs** - Interactive API documentation

Or use curl:

```bash
# Health check
curl http://localhost:8000/

# Check budget usage
curl http://localhost:8000/stats/usage

# Generate a plan
curl -X POST http://localhost:8000/builds/plan \
  -H "Content-Type: application/json" \
  -d '{"query": "Add error logging to MQTT client"}'

# Search memory
curl -X POST http://localhost:8000/memory/search \
  -H "Content-Type: application/json" \
  -d '{"query": "MQTT connection", "n_results": 3}'
```

## Key Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Health check |
| `/stats/usage` | GET | Budget & usage stats |
| `/stats/memory` | GET | Memory system stats |
| `/builds/plan` | POST | Generate implementation plan |
| `/builds/build` | POST | Execute build from plan |
| `/memory/search` | POST | Search code semantically |
| `/memory/ingest` | POST | Ingest files into memory |
| `/ws/{client_id}` | WS | Real-time build streaming |

## Example: Full Workflow

```bash
# 1. Check current budget
curl http://localhost:8000/stats/usage | jq .

# 2. Generate a plan
curl -X POST http://localhost:8000/builds/plan \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Add reconnection logic with exponential backoff to MQTT client",
    "request_type": "feature"
  }' | jq .

# 3. Execute the build
curl -X POST http://localhost:8000/builds/build \
  -H "Content-Type: application/json" \
  -d '{"manifest_path": "architect/projects/sage.yaml"}' | jq .

# 4. Check what was built
curl http://localhost:8000/builds/artifacts/sage_brain | jq .
```

## WebSocket Example (JavaScript)

```javascript
// Connect to WebSocket
const ws = new WebSocket('ws://localhost:8000/ws/my-session-123');

// Listen for messages
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received:', data);
};

// Start a build stream
ws.send(JSON.stringify({
  action: 'start_build',
  build_id: 'my-build-001'
}));
```

## Troubleshooting

### Port already in use
```bash
# Use a different port
uvicorn architect.api.server:app --port 8001
```

### Import errors
```bash
# Make sure you're in the project root
cd /home/kamicauze/sage
python -m uvicorn architect.api.server:app
```

### ChromaDB errors
```bash
pip install chromadb --upgrade
```

## Next Steps

1. **Read the full docs**: [README.md](README.md)
2. **Explore the API**: http://localhost:8000/docs
3. **Build a frontend**: Use React/Vue to consume this API
4. **Integrate with CI/CD**: Call these endpoints from your build pipeline

## Architecture Overview

```
┌─────────────┐
│   Frontend  │ (React/Vue - to be built)
│   (Future)  │
└──────┬──────┘
       │ HTTP/WebSocket
┌──────▼──────────────────────┐
│   FastAPI Backend           │
│  (architect/api/server.py)  │
├─────────────────────────────┤
│  Routes:                    │
│  • /builds    (plan/build)  │
│  • /stats     (usage/budget)│
│  • /memory    (search)      │
│  • /ws        (streaming)   │
└──────┬──────────────────────┘
       │
┌──────▼──────────────────────┐
│   Architect Core            │
│  • router.py    (orchestration)
│  • builder.py   (code gen)  │
│  • memory.py    (RAG)       │
│  • llm.py       (AI calls)  │
└─────────────────────────────┘
```

---

**Ready to build a UI?** This API provides everything you need. Start with a simple React dashboard that calls `/stats/usage` and `/builds/plan`!
