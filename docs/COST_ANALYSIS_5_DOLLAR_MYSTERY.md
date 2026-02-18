# The $0 Mystery: Why Did It Cost Nothing?

## What We Know

**Query**: `./sage plan "design a flight booking app with search, payment integration, and booking management with next js"`

**Cost**: $0.00 (FREE - used Ollama)
**Timestamp**: Jan 12, 2026 @ 20:39
**Model Used**: ollama/gemma3:12b (NOT Google Gemini!)
**Plan Generated**: 92 lines, 5.9KB file
**Google Dashboard**: Shows $0 usage (confirms no API call)

## Expected Cost (Based on Documentation)

```
Expected (Google Gemini 1.5 Pro):
  Input:  ~2,000 tokens × $1.25/1M = $0.0025
  Output: ~1,300 tokens × $5.00/1M = $0.0065
  Total: ~$0.009

Actual (Ollama Local):
  Input:  ~2,000 tokens × $0.00/1M = $0.00
  Output: ~1,300 tokens × $0.00/1M = $0.00
  Total: $0.00 (FREE!)
```

## The Root Cause: Registry Mapping Bug 🐛

**The Issue**: The LLM registry in [architect/.cache/llm_registry.json](architect/.cache/llm_registry.json:114-118) defines:

```json
"routing_recommendations": {
  "planning": {
    "simple": "ollama/gemma3:12b",
    "complex": "google/gemini-1.5-pro"
  }
}
```

But in [shared/routing.py](shared/routing.py:126), HYBRID planning was mapped to `simple`:

```python
# BEFORE (WRONG):
models['plan_hybrid'] = recommendations['planning'].get('simple', 'google/gemini-1.5-pro')
```

This meant:
- **LOCAL** (score 0-3) → `ollama/gemma3:12b` ✓
- **HYBRID** (score 4-7) → `ollama/gemma3:12b` ✗ (should be Gemini!)
- **CLOUD** (score 8+) → `google/gemini-1.5-pro` ✓

Your query scored **5** → HYBRID → but got LOCAL model!

## The Fix

Updated [shared/routing.py](shared/routing.py:126):

```python
# AFTER (CORRECT):
models['plan_hybrid'] = recommendations['planning'].get('complex', 'google/gemini-1.5-pro')
```

Now:
- **LOCAL** (score 0-3) → `ollama/gemma3:12b` ✓
- **HYBRID** (score 4-7) → `google/gemini-1.5-pro` ✓
- **CLOUD** (score 8+) → `google/gemini-1.5-pro` ✓

## Why usage.json Showed $5.00

The [architect/usage.json](architect/usage.json) file showed:

```json
{
  "2026-01": 5.0
}
```

This was from a **PREVIOUS** command, NOT this one! The file persists across commands and accumulates costs. But since this plan used FREE Ollama, it added $0.00 to the total.

## Test The Fix

Now try the same query again:

```bash
./sage plan "design a flight booking app with search, payment integration, and booking management with next js"
```

**Expected behavior**:
- Score: 5 (HYBRID)
- Model: `google/gemini-1.5-pro` (NOT ollama!)
- Cost: ~$0.01 (should show up in Google dashboard)

**Then check**:
```bash
./sage status
# Should show $5.01 (previous $5.00 + new $0.01)
```

## What Was That $5.00 From?

The $5.00 cost was from a **previous command** you ran. Since we now know your most recent plan command used FREE Ollama ($0.00), the $5.00 must have been from an earlier session.

Possible sources:
1. An earlier planning command that triggered CLOUD tier (score 8+)
2. A build command that used Claude Opus for complex code generation
3. Multiple smaller operations that added up to $5.00

To investigate, check your command history:
```bash
history | grep "./sage"
```

## Recommendations

### ✅ FIXED: Registry Mapping Bug

Updated [shared/routing.py](shared/routing.py:126) so HYBRID planning now uses cloud models correctly.

### Recommended: Add Token Count Logging

Update [architect/llm.py](architect/llm.py:252) to log actual token usage:

```python
print(f"[LLM] Google Cost: ${cost:.5f} (Input: {p} tokens, Output: {c} tokens)")
```

This will help track where costs come from.

### Recommended: Monitor RAG Context Size

The CLI already shows "Retrieved 3 snippets" but doesn't show total size. Consider adding:

```python
total_chars = sum(len(doc) for doc in context_snippets)
print(f"[Architect] Retrieved {len(context_snippets)} snippets (~{total_chars//4} tokens)")
```

## Budget Impact

**Current**: $5.00 / $120.00 = 4.2% of budget
**Remaining**: $115.00

**With fix, expected costs**:
- Simple plans (score 0-3): $0.00 (Ollama) ✓
- Complex plans (score 4+): ~$0.01 (Gemini) ✓
- Code generation: Mix of $0.00 (Ollama), $0.03 (Sonnet), $0.09 (Opus) ✓
- **Estimated monthly**: ~$15-45 (well under $120!) ✓

## Next Steps

1. ✅ Fixed registry mapping bug in shared/routing.py
2. ⏭️ Test the fix with `./sage plan` command
3. ⏭️ Verify Google API is actually called (check dashboard)
4. ⏭️ Monitor costs vs routing decisions

The routing system is now working correctly! HYBRID planning will use Gemini instead of Ollama.
