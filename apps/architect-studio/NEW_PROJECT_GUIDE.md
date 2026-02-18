# Adding a New Project to Architect

**Complete Guide to Onboarding New Codebases**

---

## Quick Start (5 Minutes)

### Step 1: Create Project Manifest

Create a new YAML file in `architect/projects/`:

```bash
nano architect/projects/my_project.yaml
```

### Step 2: Basic Manifest Template

```yaml
schema_version: "1.1"

project:
  id: "my_project"                    # Unique ID (lowercase, underscores)
  name: "My Project"                  # Display name
  description: "What this project does"
  paths:
    repo_path: "/path/to/my/project"  # Absolute or relative path

stack:
  primary: "typescript"                # Main language
  tags: ["web", "api", "backend"]     # Technology tags

memory:
  enabled: true
  zones:
    - name: "API Layer"
      role: "truth"                    # Core logic
      paths: ["src/api"]

    - name: "Frontend"
      role: "soul"                     # User interface
      paths: ["src/components", "src/pages"]

    - name: "Database"
      role: "hands"                    # Data operations
      paths: ["src/models", "src/repositories"]

    - name: "Infrastructure"
      role: "body"                     # Deployment, config
      paths: ["infrastructure", "docker"]

commands:
  install: ["npm install"]
  build: ["npm run build"]
  test: ["npm test"]

policy:
  ai_budget:
    monthly_usd: 120.0
  routing_thresholds:
    hybrid_score: 4
    cloud_score: 8
```

### Step 3: Ingest Code into Memory

```bash
# Using the API
curl -X POST http://localhost:8000/memory/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "file_paths": [
      "src/api/index.ts",
      "src/components/App.tsx",
      "src/models/User.ts"
    ],
    "manifest_path": "architect/projects/my_project.yaml"
  }'

# Or use the ingest script (if available)
python architect/ingest.py --project my_project --pattern "src/**/*.ts"
```

### Step 4: Refresh UI

The project will appear automatically! Either:
- Refresh the page (http://localhost:3000)
- Click the project selector dropdown
- The new project will be listed

---

## Detailed Configuration

### Project ID

**Rules:**
- Lowercase letters, numbers, underscores only
- Must be unique across all projects
- Used for memory collection name
- Cannot be changed after ingestion

**Examples:**
- ✅ `my_app`, `ecommerce_api`, `flight_sim`
- ❌ `My App`, `e-commerce`, `flight.sim`

---

### Cognitive Zones

Zones organize your codebase conceptually. The Architect uses these to understand your project structure.

**The Four Roles:**

#### 1. **Truth** (Core Logic)
- **What:** Business logic, algorithms, core functionality
- **Examples:**
  - Physics engines
  - Calculation engines
  - Core APIs
  - State machines
  - Validation logic

#### 2. **Soul** (User Interface)
- **What:** User-facing code, AI personalities, interactions
- **Examples:**
  - React components
  - UI libraries
  - LLM prompts
  - User flows
  - Chatbot personalities

#### 3. **Hands** (Execution)
- **What:** Actions, integrations, external systems
- **Examples:**
  - Database operations
  - API clients
  - File I/O
  - Message queues
  - Payment processors

#### 4. **Body** (Infrastructure)
- **What:** Deployment, configuration, operations
- **Examples:**
  - Docker files
  - CI/CD configs
  - Infrastructure as code
  - Environment configs
  - Monitoring setup

**Custom Zone Example:**

```yaml
memory:
  zones:
    - name: "GraphQL API"
      role: "truth"
      paths: ["src/graphql/resolvers", "src/graphql/types"]

    - name: "React Components"
      role: "soul"
      paths: ["src/components/**/*.tsx"]

    - name: "Database Layer"
      role: "hands"
      paths: ["src/db", "src/migrations"]

    - name: "AWS Infrastructure"
      role: "body"
      paths: ["terraform", "cloudformation"]
```

---

### Stack Configuration

**Primary Language:**
Common values: `python`, `typescript`, `javascript`, `go`, `rust`, `java`, `csharp`, `ruby`, `php`, `swift`, `kotlin`, `unity`, `unreal`

**Tags:**
Use tags to categorize your project:
- **Type:** `web`, `mobile`, `desktop`, `cli`, `api`, `library`
- **Domain:** `ecommerce`, `fintech`, `gaming`, `iot`, `ml`, `blockchain`
- **Tech:** `react`, `vue`, `angular`, `nextjs`, `django`, `fastapi`, `express`

**Example:**

```yaml
stack:
  primary: "typescript"
  tags: ["web", "api", "graphql", "nextjs", "postgresql"]
```

---

### File Paths

**Repo Path Options:**

1. **Same repo (relative):**
   ```yaml
   paths:
     repo_path: "."  # Sage example
   ```

2. **Subdirectory:**
   ```yaml
   paths:
     repo_path: "projects/my_app"
   ```

3. **Different repo (absolute):**
   ```yaml
   paths:
     repo_path: "/home/user/projects/my_app"
   ```

4. **Symbolic link:**
   ```yaml
   paths:
     repo_path: "~/projects/my_app"  # Will expand
   ```

---

### Zone Paths (Glob Patterns)

**Supported patterns:**

```yaml
paths:
  - "src/api"                    # Specific directory
  - "src/components/**/*.tsx"    # Recursive with extension
  - "src/utils/*.ts"             # Single level
  - "backend"                    # Entire directory
  - "config/*.yaml"              # Config files
```

**Best Practices:**
- Be specific to reduce memory size
- Group related code together
- Don't overlap zones unnecessarily
- Include tests in relevant zones

---

### Commands

Define common operations for your project:

```yaml
commands:
  install: ["pip install -r requirements.txt"]
  build: ["npm run build", "tsc"]
  test: ["pytest", "npm test"]
  lint: ["eslint src/", "black ."]
  deploy: ["./deploy.sh production"]
```

**Usage:**
Currently for documentation. Future versions may execute these automatically.

---

### Policy Configuration

**Budget Settings:**

```yaml
policy:
  ai_budget:
    monthly_usd: 120.0        # Total monthly budget
    daily_burst_usd: 5.0      # Max per day

  routing_thresholds:
    hybrid_score: 4           # Score to use Google Gemini
    cloud_score: 8            # Score to use Claude/GPT

  models:
    plan_local: "ollama/gemma3:12b"
    plan_deep: "google/gemini-1.5-pro"
    code_cloud: "anthropic/claude-3-opus"
```

---

## Real-World Examples

### Example 1: Next.js Web App

```yaml
schema_version: "1.1"

project:
  id: "acme_web"
  name: "ACME Web App"
  description: "E-commerce platform"
  paths:
    repo_path: "/home/user/projects/acme-web"

stack:
  primary: "typescript"
  tags: ["web", "nextjs", "ecommerce", "react"]

memory:
  enabled: true
  zones:
    - name: "API Routes"
      role: "truth"
      paths: ["src/app/api/**/*.ts"]

    - name: "UI Components"
      role: "soul"
      paths: ["src/components/**/*.tsx", "src/app/**/*.tsx"]

    - name: "Database & Auth"
      role: "hands"
      paths: ["src/lib/db", "src/lib/auth"]

    - name: "Deployment"
      role: "body"
      paths: ["vercel.json", "next.config.js"]

commands:
  install: ["npm install"]
  build: ["npm run build"]
  test: ["npm run test"]
```

### Example 2: Python ML Project

```yaml
schema_version: "1.1"

project:
  id: "ml_classifier"
  name: "ML Classifier"
  description: "Machine learning classification system"
  paths:
    repo_path: "/data/ml-projects/classifier"

stack:
  primary: "python"
  tags: ["ml", "ai", "pytorch", "research"]

memory:
  enabled: true
  zones:
    - name: "Models"
      role: "truth"
      paths: ["src/models", "src/training"]

    - name: "Data Pipeline"
      role: "hands"
      paths: ["src/data", "src/preprocessing"]

    - name: "Experiments"
      role: "soul"
      paths: ["notebooks", "experiments"]

    - name: "Infrastructure"
      role: "body"
      paths: ["docker", "kubernetes"]

commands:
  install: ["pip install -r requirements.txt"]
  train: ["python train.py"]
  test: ["pytest tests/"]
```

### Example 3: Unity Game

```yaml
schema_version: "1.1"

project:
  id: "space_shooter"
  name: "Space Shooter VR"
  description: "VR space combat game"
  paths:
    repo_path: "/projects/games/space-shooter"

stack:
  primary: "unity"
  tags: ["vr", "gaming", "csharp", "quest"]

memory:
  enabled: true
  zones:
    - name: "Game Logic"
      role: "truth"
      paths: ["Assets/Scripts/Gameplay", "Assets/Scripts/AI"]

    - name: "UI & Menus"
      role: "soul"
      paths: ["Assets/Scripts/UI", "Assets/Prefabs/UI"]

    - name: "Input & Audio"
      role: "hands"
      paths: ["Assets/Scripts/Input", "Assets/Scripts/Audio"]

    - name: "Build Pipeline"
      role: "body"
      paths: ["ProjectSettings", "Build"]
```

---

## Ingesting Files

### Method 1: API Endpoint

**Ingest specific files:**

```bash
curl -X POST http://localhost:8000/memory/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "file_paths": [
      "src/index.ts",
      "src/app.ts",
      "src/config.ts"
    ],
    "manifest_path": "architect/projects/my_project.yaml"
  }'
```

**Response:**
```json
{
  "status": "success",
  "ingested_count": 3,
  "failed_count": 0,
  "ingested_files": [
    "src/index.ts",
    "src/app.ts",
    "src/config.ts"
  ]
}
```

### Method 2: Bulk Ingest Script

Create a helper script:

```python
# ingest_project.py
import os
import glob
import requests

def ingest_project(project_id, patterns):
    files = []
    for pattern in patterns:
        files.extend(glob.glob(pattern, recursive=True))

    response = requests.post('http://localhost:8000/memory/ingest', json={
        'file_paths': files,
        'manifest_path': f'architect/projects/{project_id}.yaml'
    })

    print(f"Ingested {len(files)} files")
    return response.json()

# Usage
ingest_project('my_project', [
    'src/**/*.ts',
    'src/**/*.tsx',
    'tests/**/*.ts'
])
```

### Method 3: Architect Ingest CLI (if exists)

```bash
python architect/ingest.py \
  --project my_project \
  --pattern "src/**/*.ts" \
  --pattern "tests/**/*.test.ts"
```

---

## Verification

### 1. Check Project Appears in API

```bash
curl http://localhost:8000/projects/ | jq '.projects[] | select(.id=="my_project")'
```

### 2. Check Memory Stats

```bash
curl http://localhost:8000/stats/memory?project_id=my_project | jq
```

Expected output:
```json
{
  "project_id": "my_project",
  "total_chunks": 45,
  "zones": {
    "API Layer": 20,
    "Frontend": 15,
    "Database": 10
  },
  "collection_exists": true
}
```

### 3. Test Memory Search

```bash
curl -X POST http://localhost:8000/memory/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "authentication",
    "project_id": "my_project",
    "n_results": 3
  }' | jq
```

### 4. Verify in UI

1. Open http://localhost:3000
2. Click project selector in sidebar
3. Your project should be listed
4. Select it
5. Go to Memory page
6. Search for code
7. Should see results from your project

---

## Best Practices

### ✅ Do's

1. **Start small** - Ingest core files first, expand later
2. **Logical zones** - Group related code together
3. **Clear names** - Use descriptive zone names
4. **Include tests** - Put tests in same zone as code
5. **Document paths** - Comment complex glob patterns
6. **Version control** - Commit manifest to git

### ❌ Don'ts

1. **Don't overlap zones** excessively - Causes duplicate memory
2. **Don't ingest node_modules** - Wastes memory on dependencies
3. **Don't use generic names** - "API", "Frontend" vs "GraphQL API", "React Components"
4. **Don't forget to test** - Search memory before building
5. **Don't hardcode paths** - Use relative paths when possible

---

## Troubleshooting

### Project doesn't appear in UI

**Check:**
1. YAML syntax valid? Use online validator
2. File saved in `architect/projects/` ?
3. API server restarted? (Usually not needed)
4. Browser cache? Hard refresh (Ctrl+Shift+R)

**Solution:**
```bash
# Validate YAML
python -c "import yaml; yaml.safe_load(open('architect/projects/my_project.yaml'))"

# Check API
curl http://localhost:8000/projects/ | jq '.total_projects'
```

### Memory search returns no results

**Check:**
1. Files ingested? Check memory stats
2. Paths correct? Verify file exists
3. Zone filter applied? Try without filter
4. Query too specific? Try broader terms

**Solution:**
```bash
# Check if any files ingested
curl "http://localhost:8000/stats/memory?project_id=my_project"

# List indexed files
curl "http://localhost:8000/memory/files/my_project"
```

### Ingestion fails

**Common causes:**
- File not found (wrong path)
- File too large
- Binary file (can't chunk)
- Permission denied

**Solution:**
```bash
# Check file exists
ls -la /path/to/file

# Check file type
file /path/to/file

# Try one file at a time
curl -X POST http://localhost:8000/memory/ingest \
  -d '{"file_paths": ["src/index.ts"], "manifest_path": "..."}'
```

---

## Advanced Configuration

### Custom Embeddings Model

```yaml
memory:
  enabled: true
  embedding_model: "all-MiniLM-L6-v2"  # Default
  # Or use a different model:
  # embedding_model: "paraphrase-multilingual-MiniLM-L12-v2"
```

### Multiple Repo Paths

```yaml
project:
  paths:
    repo_path: "/main/project"
    additional_paths:
      - "/shared/libraries"
      - "/common/utils"
```

### Per-Project Model Settings

```yaml
policy:
  models:
    plan_local: "ollama/codellama:13b"      # Use CodeLlama
    plan_deep: "anthropic/claude-3-opus"    # Use Claude for complex
    code_cloud: "openai/gpt-4o"             # Use GPT-4 for code
```

---

## Next Steps

After adding your project:

1. **Test build flow:**
   - Generate a simple plan
   - Verify routing decision
   - Check context retrieval

2. **Optimize zones:**
   - Review memory distribution
   - Adjust paths if unbalanced
   - Add/remove zones as needed

3. **Set budget:**
   - Monitor first few builds
   - Adjust monthly limit
   - Configure routing thresholds

4. **Build history:**
   - Create several builds
   - Review what works well
   - Refine prompts

---

## Example Workflow

```bash
# 1. Create manifest
nano architect/projects/my_app.yaml

# 2. Validate YAML
python -c "import yaml; yaml.safe_load(open('architect/projects/my_app.yaml'))"

# 3. Ingest core files
curl -X POST http://localhost:8000/memory/ingest \
  -H "Content-Type: application/json" \
  -d @ingest_payload.json

# 4. Verify ingestion
curl http://localhost:8000/stats/memory?project_id=my_app

# 5. Test search
curl -X POST http://localhost:8000/memory/search \
  -d '{"query":"main function","project_id":"my_app"}'

# 6. Open UI
# http://localhost:3000

# 7. Select project in sidebar

# 8. Generate first plan!
```

---

## Summary Checklist

- [ ] Created manifest YAML file
- [ ] Set unique project ID
- [ ] Configured cognitive zones
- [ ] Defined stack and tags
- [ ] Set repo path
- [ ] Ingested core files
- [ ] Verified in API (`/projects/`)
- [ ] Checked memory stats
- [ ] Tested memory search
- [ ] Selected in UI
- [ ] Generated test plan
- [ ] Reviewed and adjusted

---

**Your project is now ready for AI-powered development!** 🚀

The Architect can now:
- Generate implementation plans for your codebase
- Search your code semantically
- Understand your project structure
- Build features using your patterns
- Track your development history

---

**Need Help?**
- Check API docs: http://localhost:8000/docs
- Review existing projects: `architect/projects/sage.yaml`
- Search issues: github.com/anthropics/claude-code/issues

**Happy Building!** 🏗️
