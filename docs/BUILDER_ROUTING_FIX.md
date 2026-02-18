# Builder Routing Fix

## Problem

The builder ([architect/builder.py](../architect/builder.py)) was not respecting the intelligent routing system. It always used the default local Ollama model, regardless of task complexity.

**Impact**:
- Simple tasks: Used Ollama ✓ (correct, saves money)
- Medium tasks: Used Ollama ✗ (should use Claude Sonnet)
- Complex tasks: Used Ollama ✗ (should use Claude Opus)

This meant the expensive Claude credits were never being used, and complex code generation was getting subpar results.

## Solution

Added dynamic routing to all 5 LLM call sites in the builder:

### 1. Plan Parsing (Line 136)
**Task**: Parse markdown plan into JSON file list
**Routing**: Simple parsing → Usually LOCAL (Ollama)

```python
# Before
response = self.llm.chat([{"role": "user", "content": prompt}])

# After
decision = quick_route(prompt, task_type='code')
print(f"[Router] Using {decision.provider}/{decision.model} for plan parsing (score: {decision.score})")
response = self.llm.chat(
    [{"role": "user", "content": prompt}],
    provider=decision.provider,
    model=decision.model
)
```

### 2. Surgical Edits (Line 276)
**Task**: Make targeted modifications to existing files
**Routing**: Based on edit complexity → LOCAL/HYBRID/CLOUD

```python
# Before
code = self.llm.chat([
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": user_prompt}
], stream=self.stream)

# After
decision = quick_route(user_prompt, task_type='code')
print(f"[Router] Using {decision.provider}/{decision.model} for surgical edit (score: {decision.score})")
code = self.llm.chat([
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": user_prompt}
], provider=decision.provider, model=decision.model, stream=self.stream)
```

### 3. Full Generation (Line 314)
**Task**: Generate complete new files from scratch
**Routing**: Based on generation complexity → LOCAL/HYBRID/CLOUD

```python
# Before
code = self.llm.chat([
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": user_prompt}
], stream=self.stream)

# After
decision = quick_route(user_prompt, task_type='code')
print(f"[Router] Using {decision.provider}/{decision.model} for full generation (score: {decision.score})")
code = self.llm.chat([
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": user_prompt}
], provider=decision.provider, model=decision.model, stream=self.stream)
```

### 4. Test Generation (Line 361)
**Task**: Generate pytest unit tests for code
**Routing**: Usually LOCAL (tests are simpler)

```python
# Before
test_code = self.llm.chat([
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": user_prompt}
])

# After
decision = quick_route(user_prompt, task_type='code')
print(f"[Router] Using {decision.provider}/{decision.model} for test generation (score: {decision.score})")
test_code = self.llm.chat([
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": user_prompt}
], provider=decision.provider, model=decision.model)
```

### 5. Bug Fixing (Line 413)
**Task**: Fix code based on error logs
**Routing**: Based on error complexity → LOCAL/HYBRID/CLOUD

```python
# Before
fixed_code = self.llm.chat([
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": user_prompt}
])

# After
decision = quick_route(user_prompt, task_type='code')
print(f"[Router] Using {decision.provider}/{decision.model} for bug fixing (score: {decision.score})")
fixed_code = self.llm.chat([
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": user_prompt}
], provider=decision.provider, model=decision.model)
```

## Expected Behavior

### Simple Code (Score 0-3) → LOCAL
```bash
./sage plan "add a logging function"
# Plan parsing: ollama/gemma3:12b (score: 0-2)
# Code generation: ollama/gemma3:12b (score: 0-3)
# Cost: FREE
```

### Medium Code (Score 4-7) → HYBRID
```bash
./sage plan "refactor the authentication module"
# Plan parsing: ollama/gemma3:12b (score: 2)
# Code generation: anthropic/claude-sonnet-4.5 (score: 5)
# Cost: ~$0.03-0.05
```

### Complex Code (Score 8+) → CLOUD
```bash
./sage plan "completely redesign authentication with OAuth2 security"
# Plan parsing: ollama/gemma3:12b (score: 2)
# Code generation: anthropic/claude-opus-4.5 (score: 10+)
# Cost: ~$0.07-0.10
```

## Verification

The builder now logs routing decisions for each operation:

```
[Builder] Parsing plan structure...
[Router] Using ollama/gemma3:12b for plan parsing (score: 2)
[Builder] Found 2 files to build.
[Builder] Generating: shared/utils.py...
[Router] Using ollama/gemma3:12b for full generation (score: 1)
[Builder] Wrote 245 bytes to architect/workspaces/sage_brain/sandbox/shared/utils.py
```

For complex tasks:
```
[Builder] Generating: brain/auth/oauth_flow.py...
[Router] Using anthropic/claude-sonnet-4.5 for full generation (score: 6)
[LLM] Anthropic (claude-sonnet-4.5) Cost: $0.04231 (1234 in, 2456 out)
```

## Cost Impact

### Before Fix
- All code generation: FREE (Ollama)
- Quality: Variable (poor for complex tasks)
- Monthly cost: $0

### After Fix (With Routing)
- Simple tasks (60%): FREE (Ollama)
- Medium tasks (30%): $3/$15 (Sonnet)
- Complex tasks (10%): $5/$25 (Opus)
- Quality: Optimal for complexity level
- **Monthly cost: ~$25** (within $120 budget)

## Testing

To test the routing:

```bash
# Test simple routing (should use Ollama)
./sage plan "add a print function"

# Test medium routing (should use Sonnet)
./sage plan "refactor the config loader with validation"

# Test complex routing (should use Opus)
./sage plan "completely redesign refactor rewrite the entire authentication system with OAuth2"
```

Watch the logs for `[Router] Using` messages to confirm correct model selection.

## Related Files

- [architect/builder.py](../architect/builder.py) - Builder implementation with routing
- [shared/routing.py](../shared/routing.py) - Routing logic and scoring
- [architect/llm.py](../architect/llm.py) - LLM client with cost tracking
- [SETUP_COMPLETE.md](../SETUP_COMPLETE.md) - Full system setup documentation

## Status

✅ **COMPLETE** - All builder LLM calls now use dynamic routing based on task complexity.
