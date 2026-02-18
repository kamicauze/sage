# The Architect (Studio)

The Architect is the "Conscious Creator" component of Sage. It is a **Repo-Agnostic** tool that can manage any project defined by a `manifest.yaml`.

## 🛠 CLI Reference

The `./sage` command wraps `architect/cli.py`.

### Commands
-   `init`: Scans the current repo (defined in `sage.yaml`) and ingests it into ChromaDB Vector Memory.
-   `status`: Shows current Monthly Spend, Memory usage, and Active Project.
-   `plan "<query>"`:
    -   Uses **RAG** to find relevant code.
    -   Scores your query to decide **Local** vs **Cloud**.
    -   Drafts a `plan.md`.
-   `build`:
    -   Reads `plan.md`.
    -   Generates code in `sandbox/`.
    -   Generates `test_*.py`.
    -   Runs `pytest`.
    -   **Self-Heals** (Rewrites code) if tests fail.

## ⚙️ Configuration

The Architect is controlled by `architect/projects/sage.yaml`.

### Budgeting
```yaml
policy:
  ai_budget:
    monthly_usd: 120.0
    daily_burst_usd: 5.0
```

### Routing
You can tune the sensitivity of the router here:
```yaml
policy:
  routing_thresholds:
    hybrid_score: 4  # Lower = More Cloud usage
    cloud_score: 8   # Higher = Harder to trigger Cloud
```

### Models
Define which model powers which faculty:
```yaml
policy:
  models:
    plan_local: "ollama/gemma3:12b"
    plan_deep: "google/gemini-1.5-pro"
    code_cloud: "anthropic/claude-3-opus"
    chat_cloud: "xai/grok-beta"
```

### External CLI Providers (Optional)
Architect can route to external coding-agent CLIs through `LLMClient` providers:
- `codex_cli`
- `claude_cli`

Configure command templates via env vars:
- `SAGE_CODEX_CLI_CMD`
- `SAGE_CLAUDE_CLI_CMD`

Expected command contract:
1. Reads prompt from `stdin`
2. Writes final text response to `stdout`

Example model entries:
```yaml
policy:
  models:
    code_cloud: "codex_cli/codex"
    plan_deep: "claude_cli/claude"
```

### API Security (Recommended)
For `architect.api.server`, configure token auth and CORS restrictions:

```bash
SAGE_ARCHITECT_API_TOKEN=change-me
SAGE_ARCHITECT_API_AUTH_REQUIRED=true
SAGE_ARCHITECT_API_CORS_ORIGINS=https://architect.example.com
SAGE_ARCHITECT_LOG_LEVEL=INFO
```

Accepted auth headers:
- `Authorization: Bearer <token>`
- `X-Architect-Token: <token>`
