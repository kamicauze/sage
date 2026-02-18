# Routing Registry Bug Fix

## Problem

When running `./sage plan` with queries scoring 4-7 (HYBRID tier), the system was incorrectly using `ollama/gemma3:12b` (FREE local model) instead of `google/gemini-1.5-pro` (cloud model).

**Example**:
```bash
./sage plan "design a flight booking app with search, payment integration, and booking management with next js"

[Router] Decision: HYBRID (Score: 5). Reason: Moderate complexity (score=5 >= 4): keywords=5
[Router] Selected Model: ollama/gemma3:12b  # ✗ WRONG! Should be google/gemini-1.5-pro
[LLM] Sending request to gemma3:12b (Ollama)...
```

**Impact**:
- HYBRID planning queries used local model instead of cloud
- No cost savings (local is already free), but lower quality plans
- User's Google API was never called despite having credits
- Simulation documents showed expected Gemini usage, but reality used Ollama

## Root Cause

The LLM registry ([architect/.cache/llm_registry.json](../architect/.cache/llm_registry.json)) defines two planning tiers:

```json
"routing_recommendations": {
  "planning": {
    "simple": "ollama/gemma3:12b",
    "complex": "google/gemini-1.5-pro"
  }
}
```

The bug was in [shared/routing.py](../shared/routing.py) line 126, which mapped HYBRID to `simple` instead of `complex`:

```python
# BEFORE (WRONG):
if 'planning' in recommendations:
    models['plan_hybrid'] = recommendations['planning'].get('simple', 'google/gemini-1.5-pro')
    models['plan_cloud'] = recommendations['planning'].get('complex', 'google/gemini-1.5-pro')
```

This meant:
- **LOCAL** (score 0-3) → `planning.simple` → `ollama/gemma3:12b` ✓
- **HYBRID** (score 4-7) → `planning.simple` → `ollama/gemma3:12b` ✗
- **CLOUD** (score 8+) → `planning.complex` → `google/gemini-1.5-pro` ✓

## The Fix

Updated [shared/routing.py](../shared/routing.py) line 126:

```python
# AFTER (CORRECT):
if 'planning' in recommendations:
    models['plan_hybrid'] = recommendations['planning'].get('complex', 'google/gemini-1.5-pro')
    models['plan_cloud'] = recommendations['planning'].get('complex', 'google/gemini-1.5-pro')
```

Now:
- **LOCAL** (score 0-3) → `ollama/gemma3:12b` ✓
- **HYBRID** (score 4-7) → `google/gemini-1.5-pro` ✓
- **CLOUD** (score 8+) → `google/gemini-1.5-pro` ✓

## Testing The Fix

### Before Fix
```bash
./sage plan "design a flight booking app with search, payment integration, and booking management"

[Router] Decision: HYBRID (Score: 5)
[Router] Selected Model: ollama/gemma3:12b  # ✗ Wrong
```

### After Fix
```bash
./sage plan "design a flight booking app with search, payment integration, and booking management"

[Router] Decision: HYBRID (Score: 5)
[Router] Selected Model: google/gemini-1.5-pro  # ✓ Correct!
[LLM] Google Cost: $0.00892
```

## Verification Steps

1. Run a HYBRID-tier planning query (score 4-7):
   ```bash
   ./sage plan "add user authentication with OAuth"
   ```

2. Check the output:
   - Should show `[Router] Selected Model: google/gemini-1.5-pro`
   - Should show `[LLM] Google Cost: $X.XXXXX`
   - Google API dashboard should show API call

3. Check cost tracking:
   ```bash
   ./sage status
   # Should show increased cost from previous total
   ```

## Cost Impact

### Before Fix
- Simple plans (0-3): $0.00 (Ollama) ✓
- Complex plans (4-7): $0.00 (Ollama) ✗ Lower quality
- Very complex (8+): ~$0.01 (Gemini) ✓

### After Fix
- Simple plans (0-3): $0.00 (Ollama) ✓
- Complex plans (4-7): ~$0.01 (Gemini) ✓ Better quality!
- Very complex (8+): ~$0.01 (Gemini) ✓

**Expected monthly increase**: ~$5-10 for better planning quality (still well under $120 budget)

## Related Documentation

- [COST_ANALYSIS_5_DOLLAR_MYSTERY.md](COST_ANALYSIS_5_DOLLAR_MYSTERY.md) - Investigation that led to this fix
- [BUILDER_ROUTING_FIX.md](BUILDER_ROUTING_FIX.md) - Builder routing implementation
- [ERROR_HANDLING_FLOW.md](ERROR_HANDLING_FLOW.md) - Self-healing routing
- [FLIGHT_BOOKING_SIMULATION.md](FLIGHT_BOOKING_SIMULATION.md) - Expected costs (now more accurate!)

## Status

✅ **FIXED** - HYBRID planning now correctly uses cloud models (2026-01-12)
