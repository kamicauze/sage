# Unified Routing: STT → Brain ↔ Architect

## Overview

This plan implements a **unified routing system** that allows voice commands (STT) to flow through the Brain and dispatch to either:
- **Brain Pathway**: IoT queries, mood, chat, home control
- **Architect Pathway**: Code planning, building, debugging

The key innovation is a **shared scoring function** that considers:
1. Query semantics (keywords)
2. RAG context size (from local ChromaDB)
3. Task type (chat vs plan vs code)
4. Explicit user escalation ("think hard", "use cloud")

---

## Architecture

```
                              ┌─────────────────────────────────────┐
                              │           STT Service               │
                              │  (Whisper / Google Speech / etc)    │
                              └──────────────┬──────────────────────┘
                                             │
                                             │ MQTT: sage/voice/transcript
                                             ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│                              BRAIN (main.py)                                   │
│                                                                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                      INTENT CLASSIFIER                                   │  │
│  │                      (Always Local - Fast)                               │  │
│  │                                                                          │  │
│  │  Input: "Add expense tracking to the brain project"                      │  │
│  │  Output: {                                                               │  │
│  │    "intent": "architect_task",    // or "brain_query"                    │  │
│  │    "project": "sage_brain",       // parsed from "brain project"         │  │
│  │    "query": "Add expense tracking",                                      │  │
│  │    "signals": { "explicit_cloud": false, "complexity_hint": null }       │  │
│  │  }                                                                       │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│                                             │                                  │
│                    ┌────────────────────────┴────────────────────────┐        │
│                    │                                                  │        │
│                    ▼                                                  ▼        │
│  ┌─────────────────────────────────┐        ┌─────────────────────────────┐  │
│  │       BRAIN PATHWAY             │        │    ARCHITECT BRIDGE         │  │
│  │                                 │        │                             │  │
│  │  model_policy.py                │        │  1. Import ArchitectRouter  │  │
│  │  → reason-based routing         │        │  2. Build BuildRequest      │  │
│  │  → fast/mid/deep (all local)    │        │  3. Call process_request()  │  │
│  │  → cloud handoff (Grok)         │        │  4. Return result via MQTT  │  │
│  │                                 │        │                             │  │
│  └─────────────────────────────────┘        └─────────────────────────────┘  │
│                                                          │                    │
└──────────────────────────────────────────────────────────┼────────────────────┘
                                                           │
                                                           ▼
                              ┌─────────────────────────────────────────────────┐
                              │              ARCHITECT                          │
                              │                                                 │
                              │  ┌───────────────────────────────────────────┐  │
                              │  │         SHARED SCORING FUNCTION           │  │
                              │  │         (shared/routing.py)               │  │
                              │  │                                           │  │
                              │  │  score = 0                                │  │
                              │  │  + keyword_score(query)      # 0-5        │  │
                              │  │  + context_score(rag_docs)   # 0-5        │  │
                              │  │  + explicit_score(signals)   # 0-3        │  │
                              │  │  + token_estimate_score()    # 0-2        │  │
                              │  │                                           │  │
                              │  │  if score < 4:  LOCAL                     │  │
                              │  │  if score < 8:  HYBRID                    │  │
                              │  │  else:          CLOUD                     │  │
                              │  └───────────────────────────────────────────┘  │
                              │                    │                            │
                              │    ┌───────────────┼───────────────┐            │
                              │    ▼               ▼               ▼            │
                              │  LOCAL          HYBRID          CLOUD           │
                              │  Gemma3         Gemini          Claude          │
                              │  (plan/code)    (plan)          (code)          │
                              │                                                 │
                              └─────────────────────────────────────────────────┘
```

---

## File Structure (New/Modified)

```
sage/
├── shared/                          # NEW: Shared modules between Brain & Architect
│   ├── __init__.py
│   ├── routing.py                   # Unified scoring function
│   └── intent.py                    # Intent classifier
│
├── brain/
│   ├── main.py                      # MODIFIED: Add voice topic handler
│   ├── voice/                       # NEW: Voice processing
│   │   ├── __init__.py
│   │   └── handler.py               # STT → Intent → Dispatch
│   └── bridges/                     # NEW: Cross-service bridges
│       ├── __init__.py
│       └── architect_bridge.py      # Calls Architect from Brain
│
├── architect/
│   ├── router_logic.py              # MODIFIED: Use shared/routing.py
│   └── ...
```

---

## Implementation

### Phase 1: Shared Scoring Module

**File: `shared/routing.py`**

```python
"""
Unified Routing Logic
Shared between Brain and Architect for consistent model selection.
"""
from dataclasses import dataclass
from typing import List, Dict, Optional

@dataclass
class RouteDecision:
    route: str          # LOCAL, HYBRID, CLOUD
    score: int          # 0-15
    reason: str
    provider: str       # ollama, google, anthropic, xai
    model: str          # gemma3:12b, gemini-1.5-pro, claude-3-opus, grok-beta
    task_type: str      # plan, code, chat, reflex

# Keyword weights
COMPLEXITY_KEYWORDS = {
    'refactor': 5, 'architecture': 5, 'design': 5, 'rewrite': 5, 'migration': 5,
    'deploy': 2, 'docker': 2, 'ci': 2, 'pipeline': 2, 'kubernetes': 3,
    'security': 3, 'auth': 2, 'oauth': 3,
}

PERSONA_KEYWORDS = {
    'sheng': 3, 'personality': 3, 'creative': 3, 'poem': 3, 'story': 3,
}

EXPLICIT_ESCALATION = {
    'think hard': 5, 'use cloud': 5, 'be thorough': 3, 'take your time': 2,
}

class UnifiedRouter:
    def __init__(self, policy: Dict):
        self.policy = policy
        self.thresholds = policy.get('routing_thresholds', {
            'hybrid_score': 4,
            'cloud_score': 8
        })
        self.models = policy.get('models', {
            'local': 'ollama/gemma3:12b',
            'plan_hybrid': 'google/gemini-1.5-pro',
            'code_cloud': 'anthropic/claude-3-opus',
            'chat_cloud': 'xai/grok-beta',
        })

    def score_keywords(self, query: str) -> int:
        """Score based on complexity/persona keywords."""
        q = query.lower()
        score = 0
        
        for kw, weight in COMPLEXITY_KEYWORDS.items():
            if kw in q:
                score = max(score, weight)  # Take highest, don't stack
        
        for kw, weight in PERSONA_KEYWORDS.items():
            if kw in q:
                score += weight
                
        return min(score, 8)  # Cap at 8

    def score_context(self, rag_docs: List[str]) -> int:
        """Score based on RAG retrieval size."""
        n = len(rag_docs)
        if n > 20:
            return 5
        if n > 10:
            return 3
        if n > 5:
            return 2
        return 0

    def score_explicit(self, query: str) -> int:
        """Score based on explicit user escalation phrases."""
        q = query.lower()
        for phrase, weight in EXPLICIT_ESCALATION.items():
            if phrase in q:
                return weight
        return 0

    def score_token_estimate(self, query: str, rag_docs: List[str]) -> int:
        """Estimate if the task will need large context window."""
        total_chars = len(query) + sum(len(d) for d in rag_docs)
        # Rough estimate: 4 chars ≈ 1 token
        est_tokens = total_chars // 4
        
        if est_tokens > 8000:
            return 2  # Needs large context → prefer cloud
        return 0

    def route(
        self,
        query: str,
        task_type: str,  # 'plan', 'code', 'chat', 'reflex'
        rag_docs: List[str] = None,
        force_local: bool = False
    ) -> RouteDecision:
        """
        Determine the optimal route for a request.
        """
        if rag_docs is None:
            rag_docs = []

        if force_local:
            return self._build_decision("LOCAL", 0, "Forced local", task_type)

        # Calculate composite score
        kw_score = self.score_keywords(query)
        ctx_score = self.score_context(rag_docs)
        exp_score = self.score_explicit(query)
        tok_score = self.score_token_estimate(query, rag_docs)
        
        total = kw_score + ctx_score + exp_score + tok_score
        
        # Determine route
        if total >= self.thresholds['cloud_score']:
            route = "CLOUD"
            reason = f"High complexity (score={total}): kw={kw_score}, ctx={ctx_score}, exp={exp_score}"
        elif total >= self.thresholds['hybrid_score']:
            route = "HYBRID"
            reason = f"Moderate complexity (score={total})"
        else:
            route = "LOCAL"
            reason = f"Simple task (score={total})"

        return self._build_decision(route, total, reason, task_type)

    def _build_decision(self, route: str, score: int, reason: str, task_type: str) -> RouteDecision:
        """Build the final decision with provider/model."""
        
        if route == "LOCAL":
            full_model = self.models.get('local', 'ollama/gemma3:12b')
        elif route == "HYBRID":
            if task_type == 'plan':
                full_model = self.models.get('plan_hybrid', 'google/gemini-1.5-pro')
            else:
                full_model = self.models.get('local', 'ollama/gemma3:12b')
        else:  # CLOUD
            if task_type == 'code':
                full_model = self.models.get('code_cloud', 'anthropic/claude-3-opus')
            elif task_type == 'chat':
                full_model = self.models.get('chat_cloud', 'xai/grok-beta')
            else:
                full_model = self.models.get('plan_hybrid', 'google/gemini-1.5-pro')

        # Parse provider/model
        if '/' in full_model:
            provider, model = full_model.split('/', 1)
        else:
            provider, model = 'ollama', full_model

        return RouteDecision(
            route=route,
            score=score,
            reason=reason,
            provider=provider,
            model=model,
            task_type=task_type
        )
```

---

### Phase 2: Intent Classifier

**File: `shared/intent.py`**

```python
"""
Intent Classifier
Runs locally (fast) to determine where to route a voice command.
"""
import re
from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass
class Intent:
    type: str           # 'architect_task', 'brain_query', 'home_control', 'chat'
    project: Optional[str]
    query: str
    signals: Dict[str, Any]

# Project aliases (voice-friendly names → manifest IDs)
PROJECT_ALIASES = {
    'brain': 'sage_brain',
    'sage brain': 'sage_brain',
    'the brain': 'sage_brain',
    'sage': 'sage_brain',
    'flight review': 'flight_review',
    'flight': 'flight_review',
}

# Architect trigger phrases
ARCHITECT_TRIGGERS = [
    r'\b(add|create|build|implement|write|fix|refactor|delete|remove)\b.*\b(feature|function|class|module|pattern|test|bug)\b',
    r'\b(add|create|build|implement)\b.*\bto\b.*\b(project|brain|sage)\b',
    r'\bplan\b.*\b(for|to)\b',
    r'\bbuild\b.*\bplan\b',
]

# Home control triggers
HOME_TRIGGERS = [
    r'\b(turn|switch)\b.*\b(on|off)\b.*\b(light|lamp|fan|ac)\b',
    r'\b(set|start|stop)\b.*\b(timer|alarm|reminder)\b',
    r'\bwhat.*(temperature|humidity|motion)\b',
]

def classify_intent(transcript: str) -> Intent:
    """
    Classify a voice transcript into an intent.
    This runs on the local LLM (fast) or even rule-based.
    """
    text = transcript.lower().strip()
    signals = {
        'explicit_cloud': 'use cloud' in text or 'think hard' in text,
        'explicit_local': 'use local' in text or 'quick' in text,
    }
    
    # 1. Check for Architect triggers
    for pattern in ARCHITECT_TRIGGERS:
        if re.search(pattern, text):
            project = _extract_project(text)
            query = _clean_query(text, project)
            return Intent(
                type='architect_task',
                project=project,
                query=query,
                signals=signals
            )
    
    # 2. Check for Home Control triggers
    for pattern in HOME_TRIGGERS:
        if re.search(pattern, text):
            return Intent(
                type='home_control',
                project=None,
                query=text,
                signals=signals
            )
    
    # 3. Default: Brain query (chat/mood/general)
    return Intent(
        type='brain_query',
        project=None,
        query=text,
        signals=signals
    )

def _extract_project(text: str) -> Optional[str]:
    """Extract project name from text."""
    for alias, project_id in PROJECT_ALIASES.items():
        if alias in text:
            return project_id
    return 'sage_brain'  # Default project

def _clean_query(text: str, project: Optional[str]) -> str:
    """Remove project mentions and trigger words from query."""
    # Remove "to the brain", "to sage", etc.
    for alias in PROJECT_ALIASES.keys():
        text = re.sub(rf'\bto\s+(the\s+)?{alias}\b', '', text)
    return text.strip()
```

---

### Phase 3: Voice Handler in Brain

**File: `brain/voice/handler.py`**

```python
"""
Voice Command Handler
Processes STT transcripts and dispatches to appropriate pathway.
"""
import asyncio
import sys
import os

# Add paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from shared.intent import classify_intent, Intent
from shared.routing import UnifiedRouter

class VoiceHandler:
    def __init__(self, brain_callback, architect_bridge):
        """
        Args:
            brain_callback: async fn(intent, context) -> response
            architect_bridge: ArchitectBridge instance
        """
        self.brain_callback = brain_callback
        self.architect = architect_bridge
        
        # Load policy from manifest (or env)
        self.router = UnifiedRouter(self._load_policy())

    def _load_policy(self):
        """Load routing policy from sage.yaml or defaults."""
        # In production, load from architect/projects/sage.yaml
        return {
            'routing_thresholds': {'hybrid_score': 4, 'cloud_score': 8},
            'models': {
                'local': 'ollama/gemma3:12b',
                'plan_hybrid': 'google/gemini-1.5-pro',
                'code_cloud': 'anthropic/claude-3-opus',
                'chat_cloud': 'xai/grok-beta',
            }
        }

    async def handle_transcript(self, transcript: str, context: dict = None):
        """
        Main entry point for voice commands.
        
        Args:
            transcript: Raw STT output
            context: Optional context (room, time, etc.)
        
        Returns:
            Response dict with type, text, etc.
        """
        print(f"[Voice] Received: '{transcript}'")
        
        # 1. Classify Intent (Always Local, Fast)
        intent = classify_intent(transcript)
        print(f"[Voice] Intent: {intent.type} -> project={intent.project}")
        
        # 2. Dispatch based on intent
        if intent.type == 'architect_task':
            return await self._handle_architect(intent)
        elif intent.type == 'home_control':
            return await self._handle_home_control(intent, context)
        else:
            return await self._handle_brain_query(intent, context)

    async def _handle_architect(self, intent: Intent):
        """Dispatch to Architect for code tasks."""
        if not self.architect:
            return {"type": "error", "text": "Architect not available"}
        
        # Determine task type from query
        task_type = 'plan'  # Default to planning
        if any(kw in intent.query.lower() for kw in ['fix', 'bug', 'error']):
            task_type = 'code'
        
        # Get routing decision
        # Note: RAG retrieval happens inside Architect, so we pass empty here
        # The Architect will re-route after RAG if needed
        decision = self.router.route(
            query=intent.query,
            task_type=task_type,
            force_local=intent.signals.get('explicit_local', False)
        )
        
        print(f"[Voice] Routing to Architect: {decision.route} ({decision.model})")
        
        # Call Architect
        result = await self.architect.dispatch(
            project_id=intent.project,
            query=intent.query,
            task_type=task_type,
            routing_hint=decision
        )
        
        return result

    async def _handle_home_control(self, intent: Intent, context: dict):
        """Handle home automation commands."""
        # This goes to Brain's action system
        return await self.brain_callback(intent, context, reason='home_control')

    async def _handle_brain_query(self, intent: Intent, context: dict):
        """Handle general queries (chat, mood, info)."""
        return await self.brain_callback(intent, context, reason='user_intent')
```

---

### Phase 4: Architect Bridge

**File: `brain/bridges/architect_bridge.py`**

```python
"""
Architect Bridge
Allows Brain to trigger Architect tasks.
"""
import sys
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Add architect to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from architect.router import ArchitectRouter, BuildRequest
from shared.routing import RouteDecision

class ArchitectBridge:
    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._router = None  # Lazy init
    
    def _get_router(self):
        if self._router is None:
            self._router = ArchitectRouter()
        return self._router

    async def dispatch(
        self,
        project_id: str,
        query: str,
        task_type: str = 'plan',
        routing_hint: RouteDecision = None
    ) -> dict:
        """
        Dispatch a task to the Architect.
        
        Args:
            project_id: The manifest project ID (e.g., 'sage_brain')
            query: The user's request
            task_type: 'plan' or 'build'
            routing_hint: Pre-computed routing decision
        
        Returns:
            Result dict with status, artifacts, summary
        """
        manifest_path = f"architect/projects/{project_id.replace('_', '/')}.yaml"
        
        # Fallback to sage.yaml if specific manifest not found
        if not os.path.exists(manifest_path):
            manifest_path = "architect/projects/sage.yaml"

        request = BuildRequest(
            manifest_path=manifest_path,
            request_type=task_type,
            query=query,
            context={'routing_hint': routing_hint.__dict__ if routing_hint else None}
        )

        # Run in executor to not block async loop
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self._executor,
            self._sync_process,
            request
        )
        
        return {
            "type": "architect_result",
            "status": result.status,
            "artifacts": result.artifacts,
            "summary": result.summary
        }

    def _sync_process(self, request: BuildRequest):
        """Synchronous wrapper for the Architect."""
        router = self._get_router()
        return router.process_request(request)
```

---

### Phase 5: Integrate into Brain main.py

**Modifications to `brain/main.py`:**

```python
# Add to imports
from voice.handler import VoiceHandler
from bridges.architect_bridge import ArchitectBridge

# Add after sage/escalator/buffer/summarizer init
architect_bridge = ArchitectBridge()

async def brain_callback(intent, context, reason):
    """Callback for Voice -> Brain pathway."""
    # Build event for existing pipeline
    event_data = {
        "type": reason,
        "text": intent.query,
        "intent": intent.type,
        "ts": int(time.time() * 1000)
    }
    await on_event(event_data)
    return {"type": "acknowledged"}

voice_handler = VoiceHandler(brain_callback, architect_bridge)

# Add new MQTT topic handler in on_message
def on_message(client, userdata, msg):
    try:
        topic = msg.topic
        payload_str = msg.payload.decode()
        
        # NEW: Voice transcript handler
        if topic == "sage/voice/transcript":
            transcript = payload_str
            context = {"local_hour": datetime.now().hour}
            asyncio.run_coroutine_threadsafe(
                voice_handler.handle_transcript(transcript, context),
                loop
            )
            return
        
        # ... existing presence handling ...

# Add subscription in main_loop
client.subscribe("sage/voice/transcript")  # NEW
client.subscribe("sage/sensors/+/presence")
```

---

## MQTT Topics

| Topic | Direction | Payload | Purpose |
|-------|-----------|---------|---------|
| `sage/voice/transcript` | STT → Brain | `"Add expense tracking to brain"` | Raw voice transcript |
| `sage/voice/response` | Brain → TTS | `{"text": "Planning that now..."}` | Voice response |
| `sage/architect/status` | Architect → Brain | `{"status": "building", "progress": 50}` | Build progress |
| `sage/architect/result` | Architect → Brain | `{"status": "SUCCESS", "summary": "..."}` | Build complete |

---

## Routing Decision Matrix

| Query Example | Keywords | RAG Docs | Score | Route | Model |
|---------------|----------|----------|-------|-------|-------|
| "What's the temperature?" | 0 | 0 | 0 | LOCAL | gemma3 |
| "Add a simple log statement" | 2 | 3 | 5 | HYBRID | gemini |
| "Refactor the state machine" | 5 | 5 | 10 | CLOUD | claude |
| "Write a poem in Sheng" | 3 | 0 | 3 | LOCAL | gemma3 |
| "Think hard and redesign auth" | 5 + 5 | 10 | 15 | CLOUD | claude |

---

## Testing Strategy

1. **Unit Tests**
   - `test_shared_routing.py`: Test scoring function with various inputs
   - `test_intent_classifier.py`: Test intent extraction from transcripts

2. **Integration Tests**
   - Mock MQTT publish to `sage/voice/transcript`
   - Verify correct pathway dispatch

3. **E2E Test**
   - Actual STT → MQTT → Brain → Architect → Result
   - Verify plan.md generation

---

## Migration Path

1. **Phase 1**: Create `shared/` module, add tests ✓
2. **Phase 2**: Update `architect/router_logic.py` to use shared scoring
3. **Phase 3**: Add voice handler to Brain
4. **Phase 4**: Add Architect bridge
5. **Phase 5**: Wire up MQTT topics
6. **Phase 6**: Add STT service (Whisper container)

---

## Budget Considerations

The unified router inherits the existing budget logic:
- All cloud calls check `architect/usage.json` before executing
- Monthly cap: $120
- Daily burst cap: $5

Local calls (Ollama) are free and have no budget impact.

---

## Open Questions

1. **STT Service**: Whisper locally or cloud (Google/Deepgram)?
2. **TTS Response**: Should Architect results be spoken back?
3. **Approval Flow**: For CLOUD routes, should we ask "This will use Claude, proceed?"
4. **Streaming**: For long builds, should we stream progress to voice?

