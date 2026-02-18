# Self-Updating LLM Routing

Sage can now **research and update its own routing configuration** using web search + AI analysis.

## Overview

Instead of manually updating pricing/models when providers change, Sage uses its own intelligence to:
1. Research latest models and pricing from provider websites
2. Analyze cost/quality tradeoffs
3. Recommend optimal routing strategy
4. Update configuration automatically

**It's Sage researching Sage's tools!** 🧠

## Usage

```bash
# Research latest models and update routing
./sage update

# Example output:
# ============================================================
# SAGE LLM MODEL UPDATE
# ============================================================
#
# [Updater] Researching anthropic models...
# [Router] Using google/gemini-1.5-pro for research (score: 4)
# [Updater] Found 3 models for anthropic
#
# [Updater] Researching openai models...
# [Updater] Found 2 models for openai
#
# [Updater] Researching google models...
# [Updater] Found 2 models for google
#
# [Updater] Analyzing optimal routing strategy...
# [Updater] Strategy analysis complete
# [Updater] Estimated monthly cost: $45.00
#
# ============================================================
# DISCOVERED MODELS
# ============================================================
# Total models: 8
# Registry: architect/.cache/llm_registry.json
#
# ============================================================
# ROUTING RECOMMENDATIONS
# ============================================================
# {
#   "planning": {
#     "simple": "ollama/gemma3:12b",
#     "complex": "google/gemini-1.5-pro"
#   },
#   "code": {
#     "simple": "ollama/gemma3:12b",
#     "medium": "anthropic/claude-sonnet-4.5",
#     "complex": "anthropic/claude-opus-4.5"
#   },
#   "chat": "xai/grok-beta",
#   "testing": "ollama/gemma3:12b"
# }
#
# ============================================================
# BUDGET ESTIMATE
# ============================================================
# {
#   "planning": 15.0,
#   "code": 25.0,
#   "chat": 5.0
# }
#
# Total estimated: $45/month
# Your budget: $120/month
# Safety margin: $75/month
#
# ============================================================
# STRATEGY REASONING
# ============================================================
# Use local Ollama for all simple tasks (free). Reserve Gemini for
# complex planning ($1.25/$5 per 1M). Use Claude Sonnet for most code
# generation ($3/$15), escalate to Opus only for critical/complex code
# ($5/$25). This minimizes cost while maintaining quality for complex
# work. Estimated 60% of tasks use free local model.
#
# ============================================================
#
# Apply these recommendations to sage.yaml? [y/n]:
```

## How It Works

### 1. Web Research Phase

The updater uses Sage's own routing system to decide which LLM to use for research:

```python
# Research prompt
research_prompt = f"""
Research the latest LLM models from {provider} as of January 2026.
Find: pricing, context window, capabilities, speed, quality.
Return structured JSON.
"""

# Let routing decide (simple query = local/free, complex = cloud)
decision = quick_route(research_prompt, task_type='chat')

# Use chosen model to research
response = llm.chat([...], provider=decision.provider, model=decision.model)
```

**Cost**: Typically uses free local Ollama for research (score < 4)

### 2. Strategy Analysis Phase

After discovering all models, Sage analyzes optimal routing:

```python
analysis_prompt = f"""
You are a budget optimizer. Analyze these {len(models)} models and
recommend routing strategy for $120/month budget.

Available models:
- anthropic/claude-opus-4.5: $5/$25 per 1M, 200K context, high quality
- anthropic/claude-sonnet-4.5: $3/$15 per 1M, 200K context, high quality
- google/gemini-1.5-pro: $1.25/$5 per 1M, 1M context, good quality
- ollama/gemma3:12b: FREE, 8K context, medium quality

Optimize for:
1. Planning (architecture, design)
2. Code (implementation, editing)
3. Chat (user interaction)

Return optimal routing strategy with cost estimates.
"""

# Use CLOUD for this critical one-time decision
strategy = llm.chat([...], provider="google", model="gemini-1.5-pro")
```

**Cost**: ~$0.01 for strategy analysis (runs once per update)

### 3. Update Registry

Results are saved to `architect/.cache/llm_registry.json`:

```json
{
  "last_updated": "2026-01-12T10:30:00",
  "models": {
    "anthropic/claude-opus-4.5": {
      "input_cost": 5.0,
      "output_cost": 25.0,
      "context_window": 200000,
      "capabilities": ["code", "reasoning"],
      "speed": "medium",
      "quality": "high"
    },
    ...
  },
  "routing_recommendations": {
    "planning": {"simple": "ollama/gemma3:12b", "complex": "google/gemini-1.5-pro"},
    "code": {"simple": "ollama/gemma3:12b", "medium": "anthropic/claude-sonnet-4.5", "complex": "anthropic/claude-opus-4.5"}
  },
  "budget_estimate": 45.0,
  "reasoning": "Use local for simple tasks, reserve cloud for complex..."
}
```

### 4. Dynamic Loading

The routing system automatically loads from registry:

```python
class UnifiedRouter:
    def _load_models(self, policy):
        # Priority 1: Check registry (from ./sage update)
        if os.path.exists("architect/.cache/llm_registry.json"):
            return self._load_from_registry()

        # Priority 2: Use policy config (sage.yaml)
        return policy.get('models', {...})

        # Priority 3: Hardcoded defaults
        return {...}
```

## Benefits

### 1. Always Up-to-Date
- No manual price tracking
- Discovers new models automatically
- Adapts to API changes

### 2. Cost Optimized
- AI analyzes cost/quality tradeoffs
- Recommends cheapest viable options
- Prevents budget overruns

### 3. Self-Maintaining
- Sage researches its own tools
- Uses its own routing intelligence
- Minimal human intervention

### 4. Transparent
- Shows reasoning for recommendations
- Estimates budget impact
- Requires approval before applying

## Example: Discovering New Models

When Claude releases a new model:

```bash
./sage update

# Output:
# [Updater] Found NEW model: anthropic/claude-haiku-4.5
#   Cost: $1/$5 (cheaper than current!)
#   Quality: medium-high
#   Speed: fast
#
# [Updater] Recommendation: Use Haiku for code editing (3x cheaper than Opus)
# [Updater] Estimated savings: $30/month
#
# Apply? [y/n]: y
#
# ✅ Configuration updated!
# New routing: code.medium = anthropic/claude-haiku-4.5
```

## Example: Price Changes

When Anthropic updates pricing:

```bash
./sage update

# Output:
# [Updater] PRICING CHANGE DETECTED
#   Claude Opus: $15/$75 → $5/$25 (67% cheaper!)
#
# [Updater] New strategy: Use Opus more aggressively
#   Before: Opus only for score >= 12
#   After:  Opus for score >= 8
#
# [Updater] Budget impact: Can handle 3x more complex tasks
```

## Technical Details

### Files Modified

1. **architect/llm_updater.py** (NEW)
   - Web research logic
   - Strategy analysis
   - Config updates

2. **sage.py**
   - Added `./sage update` command
   - Interactive approval flow

3. **shared/routing.py**
   - Dynamic registry loading
   - Fallback to config/defaults

### Dependencies

- **Existing**: `requests` (for web fetching)
- **New**: `pyyaml` (for config updates)
- **Optional**: `beautifulsoup4` (for HTML parsing)

Install:
```bash
pip install pyyaml beautifulsoup4
```

### Frequency

**Recommended**: Run monthly or when:
- Provider announces new models
- Pricing changes
- Budget adjustments needed

**Cost**: ~$0.01-0.05 per update (mostly free local research)

## Future Enhancements

1. **Scheduled Updates**: Auto-run weekly via cron
2. **Web Scraping**: Parse pricing pages directly (avoid LLM extraction)
3. **Community Registry**: Crowd-sourced pricing database
4. **A/B Testing**: Track actual costs vs estimates
5. **Rollback**: Undo bad routing changes

## Philosophy

This embodies Sage's **self-healing** design:
- Don't hardcode what can be discovered
- Use AI to maintain AI infrastructure
- Keep humans in the loop for critical decisions
- Optimize for long-term cost/quality balance

**Sage doesn't just use AI—it uses AI to improve how it uses AI.** 🧠♻️
