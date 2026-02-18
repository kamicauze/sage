# Usage Logging & Cost Tracking

## Overview

Sage now includes comprehensive API usage logging that tracks every LLM call with detailed token counts and costs. This helps you understand where your budget is going and optimize your usage.

## What's Logged

Every API call to Ollama, OpenAI, Anthropic, Google, or Grok is logged with:
- **Timestamp**: When the call was made
- **Provider**: ollama, openai, anthropic, google, xai
- **Model**: Specific model used (e.g., gemma3:12b, claude-sonnet-4.5, gemini-1.5-pro)
- **Input Tokens**: Number of tokens in the prompt
- **Output Tokens**: Number of tokens in the response
- **Cost**: Total cost in USD (FREE for Ollama)
- **Task**: Type of operation (chat, streaming, etc.)

## Where Logs Are Stored

### Monthly Budget Summary
[architect/usage.json](../architect/usage.json) - Tracks total monthly spend

```json
{
  "2026-01": 5.0
}
```

### Detailed Call Log
[architect/.cache/usage_log.jsonl](../architect/.cache/usage_log.jsonl) - JSONL format with one entry per API call

```json
{"timestamp": "2026-01-12T20:39:15.123456", "provider": "google", "model": "gemini-1.5-pro", "input_tokens": 2456, "output_tokens": 1234, "cost": 0.00892, "task": "chat"}
{"timestamp": "2026-01-12T20:40:22.789012", "provider": "ollama", "model": "gemma3:12b", "input_tokens": 1500, "output_tokens": 800, "cost": 0.0, "task": "streaming"}
{"timestamp": "2026-01-12T20:41:05.456789", "provider": "anthropic", "model": "claude-sonnet-4.5", "input_tokens": 3200, "output_tokens": 2100, "cost": 0.04110, "task": "chat"}
```

## Viewing Logs

### Quick Status
```bash
./sage status
```

Output:
```
--- The Symbiote Status ---
💰 Monthly Budget: $5.00 / $120.00
🧠 Memory Size:    2.7M
📂 Manifest:       architect/projects/sage.yaml

💡 Tip: Use './sage status --verbose' to see detailed API usage
---------------------------
```

### Detailed Usage Log
```bash
./sage status --verbose
```

Output:
```
--- The Symbiote Status ---
💰 Monthly Budget: $5.00 / $120.00
🧠 Memory Size:    2.7M
📂 Manifest:       architect/projects/sage.yaml

📊 Recent API Calls (last 10):
----------------------------------------------------------------------------------------------------
  20:39:15 | google     | gemini-1.5-pro            | In:  2,456 | Out:  1,234 | $0.00892
  20:40:22 | ollama     | gemma3:12b                | In:  1,500 | Out:    800 | $0.00000
  20:41:05 | anthropic  | claude-sonnet-4.5         | In:  3,200 | Out:  2,100 | $0.04110
  20:42:30 | ollama     | gemma3:12b                | In:    500 | Out:    550 | $0.00000
  20:43:15 | google     | gemini-1.5-pro            | In:  2,100 | Out:  1,300 | $0.00891
----------------------------------------------------------------------------------------------------
---------------------------
```

## Real-Time Logging

During command execution, you'll see detailed logs:

### Ollama (FREE)
```
[LLM] Sending request to gemma3:12b (Ollama)...
[LLM] Ollama FREE (Input: 1,500 tokens, Output: 800 tokens)
```

### Google Gemini
```
[LLM] Sending request to gemini-1.5-pro (Google)...
[LLM] Google Cost: $0.00892 (Input: 2,456 tokens, Output: 1,234 tokens)
```

### Anthropic Claude
```
[LLM] Sending request to claude-sonnet-4.5 → claude-sonnet-4-20250514 (Anthropic)...
[LLM] Anthropic (claude-sonnet-4.5) Cost: $0.04110 (Input: 3,200 tokens, Output: 2,100 tokens)
```

### OpenAI / Grok
```
[LLM] Sending request to gpt-4o via https://api.openai.com/v1...
[LLM] OpenAI Cost: $0.03250 (Input: 1,800 tokens, Output: 1,200 tokens)
```

## Analyzing Logs

### View All Calls (Raw)
```bash
cat architect/.cache/usage_log.jsonl
```

### Count Calls Per Provider
```bash
cat architect/.cache/usage_log.jsonl | jq -r '.provider' | sort | uniq -c
```

### Total Cost Per Provider
```bash
cat architect/.cache/usage_log.jsonl | jq -s 'group_by(.provider) | map({provider: .[0].provider, total_cost: map(.cost) | add})'
```

### Average Tokens Per Model
```bash
cat architect/.cache/usage_log.jsonl | jq -s 'group_by(.model) | map({model: .[0].model, avg_input: (map(.input_tokens) | add / length | round), avg_output: (map(.output_tokens) | add / length | round)})'
```

### Most Expensive Calls
```bash
cat architect/.cache/usage_log.jsonl | jq -s 'sort_by(.cost) | reverse | .[:5]'
```

## Cost Tracking by Model

### Current Rates (as of Jan 2026)

| Provider | Model | Input (per 1M) | Output (per 1M) | Context Window |
|----------|-------|----------------|-----------------|----------------|
| Ollama | gemma3:12b | $0.00 | $0.00 | 8K |
| Google | gemini-1.5-pro | $1.25 | $5.00 | 1M |
| Google | gemini-1.5-flash | $0.075 | $0.30 | 1M |
| Anthropic | claude-opus-4.5 | $5.00 | $25.00 | 200K |
| Anthropic | claude-sonnet-4.5 | $3.00 | $15.00 | 200K |
| Anthropic | claude-haiku-4.5 | $1.00 | $5.00 | 200K |
| OpenAI | gpt-4o | $2.50 | $10.00 | 128K |
| OpenAI | gpt-4o-mini | $0.15 | $0.60 | 128K |
| xAI | grok-beta | ~$5.00 | ~$15.00 | 128K |

## Budget Monitoring

### Monthly Limit
Default: **$120.00/month**

Set in [architect/projects/sage.yaml](../architect/projects/sage.yaml):
```yaml
policy:
  ai_budget:
    monthly_usd: 120.0
```

### Budget Exceeded Warning
If monthly spend exceeds limit, Sage will:
1. Print warning: `⚠️ Budget Warning: You've spent $125.00 this month (limit: $120.00)`
2. Continue execution (no hard stop)
3. Log warning to usage_log.jsonl

## Example: Typical Month

```bash
./sage status --verbose
```

```
📊 Recent API Calls (last 10):
----------------------------------------------------------------------------------------------------
  08:15:22 | ollama     | gemma3:12b                | In:  1,200 | Out:    650 | $0.00000  # Simple planning
  08:16:05 | google     | gemini-1.5-pro            | In:  2,800 | Out:  1,500 | $0.01100  # Complex planning
  08:17:30 | ollama     | gemma3:12b                | In:    800 | Out:    900 | $0.00000  # Code generation (simple)
  08:18:45 | anthropic  | claude-sonnet-4.5         | In:  3,500 | Out:  2,400 | $0.04650  # Code generation (medium)
  08:20:15 | anthropic  | claude-opus-4.5           | In:  4,200 | Out:  3,100 | $0.09850  # Security-critical code
  08:22:00 | ollama     | gemma3:12b                | In:    600 | Out:    700 | $0.00000  # Test generation
  08:25:30 | anthropic  | claude-sonnet-4.5         | In:  2,100 | Out:  1,800 | $0.03330  # Bug fix
----------------------------------------------------------------------------------------------------

Monthly Budget: $15.43 / $120.00
```

**Breakdown**:
- Ollama (FREE): 3 calls → $0.00
- Google Gemini: 1 call → $0.01
- Claude Sonnet: 2 calls → $0.08
- Claude Opus: 1 call → $0.10
- **Total**: $0.19 for one build cycle

**Estimated monthly** (50 build cycles): ~$9.50

## Related Documentation

- [ROUTING_REGISTRY_BUG_FIX.md](ROUTING_REGISTRY_BUG_FIX.md) - Registry mapping fix
- [COST_ANALYSIS_5_DOLLAR_MYSTERY.md](COST_ANALYSIS_5_DOLLAR_MYSTERY.md) - Cost investigation
- [BUILDER_ROUTING_FIX.md](BUILDER_ROUTING_FIX.md) - Builder routing implementation
- [ERROR_HANDLING_FLOW.md](ERROR_HANDLING_FLOW.md) - Self-healing costs

## Status

✅ **IMPLEMENTED** - Comprehensive usage logging with token counts and costs (2026-01-12)
