# The Symbiote: AI Development Studio Architecture

**Sage** is not just an IoT Brain; it is a **Symbiote**—a self-improving AI system capable of planning, coding, testing, and fixing itself.

## 1. Core Concepts

### The Brain (Runtime)
-   **Role**: The Subconscious / Body.
-   **Function**: handling sensors (MQTT), processing inputs, and executing "The Soul" (Chat/Persona).
-   **State**: Always on (Daemon/Service).

### The Architect (Builder)
-   **Role**: The Conscious Creator.
-   **Function**: Scans code, plans features, builds modules, runs tests.
-   **State**: On-Demand (CLI Tool).

### The Router (Guard)
-   **Role**: The Gatekeeper.
-   **Function**: Deterministically routes tasks to the appropriate model based on **Cost**, **Privacy**, and **Complexity**.
-   **Constraint**: Fully deterministic (Python), not LLM-based.

---

## 2. Quad-Mind Strategy
The Symbiote uses a "Tiered Mind" approach to balance intelligence and cost.

| Tier | Model | Use Case | Cost | Privacy |
| :--- | :--- | :--- | :--- | :--- |
| **Local** | `ollama/gemma3:12b` | Simple fixes, Code questions, Drafts. | Free | High (Offline) |
| **Hybrid** | `google/gemini-1.5-pro` | **Planning**, Architecture, Deep Refactors. | Low/Med | Cloud (Safe) |
| **Code** | `anthropic/claude-3-opus` | **Complex Coding**, Logic, Hard Bugs. | High | Cloud (Safe) |
| **Soul** | `xai/grok-beta` | **Chat**, Personality, Sheng Nuance. | Med | Cloud (Safe) |

### Routing Heuristics
The Router scores every request (0-10):
-   **+5 Points**: Keywords like `refactor`, `architecture`, `design`. -> **Escalates to HYBRID**.
-   **+3 Points**: Keywords like `sheng`, `persona`. -> **Escalates to SOUL**.
-   **+2 Points**: Keywords like `deploy`, `CI`.
-   **< 4 Points**: Defaults to **LOCAL**.

---

## 3. The Self-Healing Loop
The Architect implements a closed-loop "Test-Driven Repair" cycle:

1.  **Build**: Generates code based on `plan.md`. (Sandbox)
2.  **Test**: Generates `pytest` files for the new code.
3.  **Execute**: Runs `pytest`.
4.  **Repair**: If tests fail, feeds the **Error Log** back to the LLM to rewrite the code.
5.  **Repeat**: Retries up to 3 times before asking for human help.

---

## 4. Configuration
Everything is defined in `architect/projects/sage.yaml`.

```yaml
policy:
  ai_budget:
    monthly_usd: 120.0  # Hard Cap
    daily_burst_usd: 5.0 # Safety Brake
  routing:
    plan_local: "ollama/gemma3:12b"
    plan_deep: "google/gemini-1.5-pro"
    code_cloud: "anthropic/claude-3-opus"
```

## 5. Security & Safety
-   **Budget Enforcer**: Every call is checked against `usage.json`. If > Limit, it blocks.
-   **Sandbox**: Code is generated in `architect/workspaces/<id>/sandbox` first. It does NOT overwrite `brain/` until you explicitly approve (Implementation pending CLI verification step).
-   **Circuit Breaker**: If Cloud fails, falls back to Local.
