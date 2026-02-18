# Sage Architect - Quick Start Guide

> **Fast, cost-optimized, AI-powered code generation**

---

## Installation

```bash
# Activate virtual environment
source .venv/bin/activate

# Verify Ollama is running
curl http://localhost:11434/api/tags

# Check budget status
./sage status
```

---

## Basic Usage

### 1. Plan Generation

```bash
# Simple plan (auto-mode)
./sage plan "add a health check endpoint"

# Interactive plan (with approval)
./sage plan -i "refactor authentication system"
```

**Output**:
```
[Architect] Online. Connected to Gemma 3.
[Router] Decision: LOCAL (Score: 0). Reason: Simple task
[Architect] Skipping context retrieval (simple task)
[Architect] Plan saved to architect/workspaces/sage_brain/plan.md

✅ Plan Created: architect/workspaces/sage_brain/plan.md
Run './sage build' to execute it.
```

### 2. Build Execution

```bash
# Batch build (maximum speed)
./sage build

# Interactive build (with diffs)
./sage build -i
```

**Interactive mode shows diffs**:
```
============================================================
DIFF: main.py
============================================================
--- main.py
+++ main.py (modified)
@@ -15,6 +15,10 @@
 def process_data(items):
     results = []
+    # Add validation
+    if not items:
+        return []
+
     for item in items:
============================================================

Apply changes to main.py? [y/n] (default: y):
```

### 3. Status Check

```bash
./sage status
```

**Output**:
```
=== Sage Status ===

Budget:
  Used: $7.20 / $20.00 (36%)
  Remaining: $12.80

Memory:
  Total embeddings: 1,234
  Collections: 1

Last Build:
  Status: SUCCESS
  Files: 3
  Time: 32s
```

---

## Configuration Modes

### Batch Mode (Default)
**Use case**: CI/CD, automated builds, maximum speed

```python
builder = ArchitectBuilder(
    manifest=manifest,
    interactive=False,    # No prompts
    incremental=True,     # Use cache (fast rebuilds)
    parallel=True,        # 3 workers
    max_workers=3,
    stream=False          # Incompatible with parallel
)
```

**Performance**:
- First build: 50s
- Rebuild: 10s (10x faster)

### Interactive Mode
**Use case**: Development, learning, code review

```python
builder = ArchitectBuilder(
    manifest=manifest,
    interactive=True,     # Approval gates
    incremental=True,     # Use cache
    parallel=False,       # Auto-disabled (sequential prompts)
    stream=True           # Live feedback
)
```

**Features**:
- Plan preview + approval
- Diffs for each file
- Streaming code generation
- Safety gates

### Debug Mode
**Use case**: Troubleshooting, understanding LLM output

```python
builder = ArchitectBuilder(
    manifest=manifest,
    interactive=False,
    incremental=False,    # Force rebuild (ignore cache)
    parallel=False,       # Sequential
    stream=True           # Watch generation
)
```

---

## Optimization Features

### 1. Surgical Edits (Phase 2)
**Automatic**: Enabled by default for files > 100 bytes

**How it works**:
- Detects existing files
- Makes targeted edits only
- Preserves formatting, imports, unrelated code

**Savings**: 30-70% token reduction

### 2. Incremental Builds (Phase 2)
**Automatic**: Enabled by default

**How it works**:
- SHA256 hashes track file changes
- Skips unchanged files
- Cache stored in `architect/workspaces/{project}/build_cache.json`

**Savings**: 90% faster, 80% cheaper on rebuilds

**Clear cache**:
```bash
rm architect/workspaces/sage_brain/build_cache.json
```

### 3. Lazy Context Loading (Phase 2)
**Automatic**: Enabled by default

**How it works**:
- Scores complexity before loading RAG
- Score < 4: Skip ChromaDB
- Score ≥ 4: Load context

**Savings**: 2.25x faster for simple queries

### 4. Parallel Generation (Phase 3)
**Automatic**: Enabled in batch mode

**How it works**:
- ThreadPoolExecutor with 3 workers
- Concurrent file generation
- Auto-disabled in interactive mode

**Savings**: 3x faster for multi-file builds

**Configure workers**:
```python
builder = ArchitectBuilder(manifest, max_workers=5)  # More parallelism
```

### 5. Streaming Output (Phase 3)
**Manual**: Enable with `stream=True`

**How it works**:
- Real-time token display
- See code as it's generated
- Auto-disabled in parallel mode

**Enable**:
```python
builder = ArchitectBuilder(manifest, stream=True, parallel=False)
```

---

## Cost Management

### Budget Tracking

**Set limit** (environment variable):
```bash
export ARCHITECT_BUDGET_LIMIT=20.0  # $20/month
```

**Check spending**:
```bash
./sage status
cat architect/usage.json
```

**Usage file format**:
```json
{
  "2026-01": 7.20
}
```

### Cost Breakdown

| Operation | Tokens | Cost (Gemini) | Cost (Ollama) |
|-----------|--------|---------------|---------------|
| Simple plan | 500 | $0.003 | $0.00 |
| Complex plan | 3000 | $0.020 | $0.00 |
| Surgical edit | 2800 | $0.018 | $0.00 |
| Full generate | 4000 | $0.025 | $0.00 |

**Recommendation**: Use Ollama (local) for 95% of tasks, Gemini for planning only.

---

## Common Workflows

### Workflow 1: Quick Feature Addition
```bash
# 1. Generate plan
./sage plan "add rate limiting to API endpoints"

# 2. Review plan
cat architect/workspaces/sage_brain/plan.md

# 3. Build (batch mode)
./sage build

# 4. Test
cd architect/workspaces/sage_brain/sandbox
pytest
```

**Time**: ~30s
**Cost**: ~$0.05

### Workflow 2: Careful Refactoring
```bash
# 1. Interactive plan
./sage plan -i "refactor authentication to use JWT"

# Review and approve plan

# 2. Interactive build (review each diff)
./sage build -i

# Approve each file change individually

# 3. Test in sandbox
cd architect/workspaces/sage_brain/sandbox
pytest
```

**Time**: ~2 min (including reviews)
**Cost**: ~$0.15

### Workflow 3: Iterative Development
```bash
# 1. First pass
./sage plan "implement user profiles"
./sage build

# 2. Modify plan
vim architect/workspaces/sage_brain/plan.md

# 3. Rebuild (incremental - only changed files)
./sage build

# 4. Fix issues
./sage plan "fix validation bug in profile endpoint"
./sage build  # Super fast - cached files skipped
```

**Time**: First=50s, Rebuild=10s
**Cost**: First=$0.12, Rebuild=$0.02

---

## Troubleshooting

### Issue: Budget exceeded
**Error**: `Budget exceeded: Monthly budget limit of $20.0 reached`

**Solution**:
```bash
# Check current spending
cat architect/usage.json

# Reset for new month (manual)
echo '{"2026-01": 0.0}' > architect/usage.json

# Or increase limit
export ARCHITECT_BUDGET_LIMIT=50.0
```

### Issue: Slow builds
**Symptom**: Builds taking > 2 minutes

**Diagnose**:
```bash
# Check if incremental build is working
grep "Skipping" logs.txt

# Check if parallel is enabled
grep "parallel generation" logs.txt
```

**Solutions**:
1. Clear cache if stale: `rm architect/workspaces/*/build_cache.json`
2. Ensure parallel mode: Check not in interactive mode
3. Use surgical edits: Keep files > 100 bytes

### Issue: ChromaDB loading slow
**Symptom**: 2+ second startup

**Check**:
```bash
# Embeddings count
ls -lh .sage_memory/

# Should skip for simple queries
./sage plan "add comment" 2>&1 | grep "Skipping context"
```

**Solution**: Lazy loading is automatic. If seeing "Skipping context" message, it's working correctly.

### Issue: Streaming not working
**Symptom**: No real-time output

**Check**:
```python
builder = ArchitectBuilder(manifest, stream=True, parallel=False)
# Streaming requires parallel=False
```

---

## Performance Benchmarks

### Simple Query
```
Query: "add a TODO comment"
Complexity: 0
RAG: Skipped
Time: 800ms
Cost: $0.01 (Ollama: $0.00)
```

### Complex Query
```
Query: "refactor MQTT broker connection logic"
Complexity: 5
RAG: Loaded (3 snippets)
Time: 1800ms
Cost: $0.04 (Ollama: $0.00)
```

### Multi-File Build
```
Files: 5 (2 modified, 3 cached)
Mode: Parallel (3 workers)
Time: 17s (vs 50s sequential)
Cost: $0.08 (vs $0.20 full rebuild)
```

### Incremental Rebuild
```
Files: 5 (1 modified, 4 cached)
Mode: Incremental
Time: 10s (vs 100s no cache)
Cost: $0.02 (vs $0.20 full rebuild)
```

---

## Best Practices

### 1. Use Interactive Mode for Learning
```bash
./sage plan -i "complex feature"
./sage build -i
# Watch diffs, understand changes
```

### 2. Batch Mode for CI/CD
```bash
# .github/workflows/sage-build.yml
./sage plan "$FEATURE_REQUEST"
./sage build  # Fast, cached, parallel
```

### 3. Clear Cache Strategically
```bash
# Clear before major refactor (want fresh build)
rm architect/workspaces/*/build_cache.json

# Keep cache for iterative development (want speed)
```

### 4. Monitor Budget
```bash
# Weekly check
./sage status | grep Budget

# Set alerts
if [ $(jq '."2026-01"' architect/usage.json) -gt 15.0 ]; then
  echo "Budget warning: > $15"
fi
```

### 5. Leverage Surgical Edits
```bash
# Plan should focus on specific changes
./sage plan "add validation to login() function"  # Surgical

# Not broad rewrites
./sage plan "improve the entire auth system"  # Full rewrite
```

---

## API Reference

### CLI Commands

```bash
# Planning
./sage plan <query>              # Generate plan
./sage plan -i <query>           # Interactive plan with approval

# Building
./sage build                     # Execute plan (batch)
./sage build -i                  # Execute with diffs (interactive)

# Status
./sage status                    # Show budget, memory, last build

# Ingestion
./sage ingest                    # Index codebase into ChromaDB
```

### Python API

```python
from architect.router import ArchitectRouter, BuildRequest
from architect.builder import ArchitectBuilder
from architect.manifest import ProjectManifest

# Router (plan + build orchestration)
router = ArchitectRouter(
    interactive=False,      # Approval gates
    lazy_memory=True        # Lazy ChromaDB (default)
)

request = BuildRequest(
    manifest_path="architect/projects/sage.yaml",
    request_type="plan",  # or "build"
    query="add health check endpoint"
)

result = router.process_request(request)
print(result.status)  # "SUCCESS" or "FAILURE"
print(result.summary)

# Builder (direct code generation)
manifest = ProjectManifest.load("architect/projects/sage.yaml")

builder = ArchitectBuilder(
    manifest=manifest,
    interactive=False,    # No prompts
    incremental=True,     # Use cache
    parallel=True,        # 3 workers
    max_workers=3,
    stream=False          # Real-time output
)

builder.build_from_plan("architect/workspaces/sage_brain/plan.md")
print(f"Built files: {builder.files_built}")
```

---

## Support

**Issues**: https://github.com/yourusername/sage/issues
**Docs**: https://yourusername.github.io/sage
**Blog**: https://yourblog.com/sage

---

*Last updated: January 12, 2026*
