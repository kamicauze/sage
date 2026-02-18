# Error Handling & Self-Healing Flow

## How Sage Decides Which Model to Use When Things Fail

When implementing code and something breaks, Sage uses **intelligent routing at every stage** to determine which model handles the fix.

## Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ 1. PLAN CREATION                                            │
│    ./sage plan "add authentication system"                  │
│    ├─ Route decision: Based on query complexity            │
│    ├─ Simple (0-3): Ollama (FREE)                          │
│    ├─ Medium (4-7): Gemini ($1.25/$5)                      │
│    └─ Complex (8+): Gemini ($1.25/$5)                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. BUILD EXECUTION                                          │
│    ./sage build                                             │
│    ├─ Parse plan → Route: Usually LOCAL (simple)           │
│    ├─ Generate files → Route: Per-file complexity          │
│    │   ├─ Simple function: Ollama (FREE)                   │
│    │   ├─ Medium refactor: Claude Sonnet ($3/$15)          │
│    │   └─ Complex system: Claude Opus ($5/$25)             │
│    └─ Generate tests → Route: Usually LOCAL (tests simple) │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. TEST EXECUTION                                           │
│    Automatic pytest run                                     │
│    ├─ ✅ All pass → Done!                                   │
│    └─ ❌ Tests fail → Trigger self-healing                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. SELF-HEALING (Retry Loop: max 3 attempts)               │
│    builder.fix_code(file_path, error_log)                  │
│    ├─ Route decision: Based on ERROR COMPLEXITY            │
│    ├─ Simple error (syntax, typo): Ollama (FREE)           │
│    ├─ Medium error (logic bug): Claude Sonnet ($3/$15)     │
│    └─ Complex error (design flaw): Claude Opus ($5/$25)    │
│    ↓                                                         │
│    Regenerate file → Test again → Repeat if needed         │
└─────────────────────────────────────────────────────────────┘
```

## Detailed Error Handling Steps

### Step 1: Test Failure Detection

In [architect/router.py](../architect/router.py) (lines 108-126):

```python
# Test & Fix Loop
max_retries = 3
for attempt in range(max_retries):
    print(f"\n[Architect] Testing Cycle {attempt+1}/{max_retries}...")
    result = tester.run_tests()

    if result.passed:
        print("✅ All Tests Passed!")
        return BuildResult("SUCCESS", [plan_path], "Build & Tests Passed.")

    print(f"❌ Tests Failed: {result.failed_tests}")

    # Attempt Self-Repair
    if result.failed_tests:
        for f in built_files:
            builder.fix_code(f, result.output)  # ← Triggers fix with error log
```

**Key**: The error log from pytest is passed to `fix_code()`, which contains stack traces, error messages, and context.

### Step 2: Routing Decision for Bug Fix

In [architect/builder.py](../architect/builder.py) (lines 389-419):

```python
def fix_code(self, file_path: str, error_log: str):
    """
    Attempts to fix the code based on the error log.
    """
    sandbox_path = os.path.join(self.sandbox_dir, file_path)
    with open(sandbox_path, "r") as f:
        code_content = f.read()

    print(f"[Builder] Self-Healing {file_path}...")

    with open("architect/prompts/fixing.txt", "r") as f:
        system_prompt = f.read()

    user_prompt = f"""
    BROKEN CODE ({file_path}):
    {code_content}

    ERROR LOG:
    {error_log}

    Please provide the fixed code.
    """

    # 🎯 ROUTING DECISION HAPPENS HERE 🎯
    decision = quick_route(user_prompt, task_type='code')
    print(f"[Router] Using {decision.provider}/{decision.model} for bug fixing (score: {decision.score})")

    fixed_code = self.llm.chat([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ], provider=decision.provider, model=decision.model)
```

**How routing decides**:

The `quick_route()` function analyzes the prompt (which includes the broken code + error log) and scores it based on:

1. **Error keywords**: "Exception", "Traceback", "Error", "Failed"
2. **Error complexity**:
   - Simple: `NameError`, `SyntaxError`, `IndentationError` → Score +1
   - Medium: `TypeError`, `ValueError`, `AttributeError` → Score +3
   - Complex: `RuntimeError`, `AssertionError`, logic errors → Score +5+
3. **Code size**: Larger files get higher scores
4. **Context mentions**: "refactor", "redesign", "rewrite" → Higher scores

### Step 3: Model Selection Examples

#### Simple Error (Score 0-3) → LOCAL (Ollama)

```python
# Error: SyntaxError: invalid syntax
# Missing closing parenthesis

def log_message(msg: str:  # ← Syntax error
    print(msg)
```

**Routing**:
- Error keyword: +1
- Simple syntax error: +1
- Small file: +0
- **Total: 2 → LOCAL (Ollama)**

**Output**:
```
[Builder] Self-Healing shared/utils.py...
[Router] Using ollama/gemma3:12b for bug fixing (score: 2)
[Builder] Applied fix to shared/utils.py
```

#### Medium Error (Score 4-7) → HYBRID (Claude Sonnet)

```python
# Error: AttributeError: 'NoneType' object has no attribute 'get'
# Logic bug in authentication flow

def authenticate(user):
    session = get_session(user)  # Returns None for invalid users
    return session.get('token')  # ← Crashes on None
```

**Routing**:
- Error keyword: +1
- AttributeError (medium complexity): +3
- Context mentions "authentication": +2
- **Total: 6 → HYBRID (Claude Sonnet)**

**Output**:
```
[Builder] Self-Healing brain/auth/session.py...
[Router] Using anthropic/claude-sonnet-4.5 for bug fixing (score: 6)
[LLM] Anthropic (claude-sonnet-4.5) Cost: $0.02134 (743 in, 892 out)
[Builder] Applied fix to brain/auth/session.py
```

#### Complex Error (Score 8+) → CLOUD (Claude Opus)

```python
# Error: AssertionError: Expected OAuth flow to validate state parameter
# Design flaw: Security vulnerability in OAuth implementation

def oauth_callback(code, state):
    # ❌ Never validates state parameter (CSRF vulnerability)
    token = exchange_code_for_token(code)
    return create_session(token)
```

**Routing**:
- Error keyword: +1
- Security-related error: +4
- Mentions "OAuth", "redesign": +3
- Complex refactor needed: +3
- **Total: 11 → CLOUD (Claude Opus)**

**Output**:
```
[Builder] Self-Healing brain/auth/oauth_flow.py...
[Router] Using anthropic/claude-opus-4.5 for bug fixing (score: 11)
[LLM] Anthropic (claude-opus-4.5) Cost: $0.08743 (1456 in, 2134 out)
[Builder] Applied fix to brain/auth/oauth_flow.py
```

## Retry Loop Strategy

### Attempt 1: Initial Fix
- Uses routing based on error complexity
- Most errors get fixed by LOCAL/HYBRID

### Attempt 2: Escalation (if needed)
- Same routing logic applies
- If error persists, the prompt now includes:
  - Original error
  - Previous fix attempt
  - New error after fix
- **Higher score** → May escalate to more powerful model

### Attempt 3: Final Attempt
- Last chance before giving up
- Complex persistent errors may hit CLOUD tier

## Cost Analysis

### Typical Bug Fix Costs

| Scenario | Model | Input | Output | Cost |
|----------|-------|-------|--------|------|
| Syntax error | Ollama | 500 | 550 | $0.00 |
| Logic bug | Sonnet | 1000 | 1200 | $0.02 |
| Design flaw | Opus | 2000 | 3000 | $0.09 |

### Monthly Estimates (With Self-Healing)

Assuming 50 builds/month with 20% failure rate (10 bugs):

```
Initial builds:
- 30 simple (60%): FREE
- 15 medium (30%): $0.45 (15 × $0.03)
- 5 complex (10%): $0.45 (5 × $0.09)

Bug fixes (10 total):
- 6 simple (60%): FREE
- 3 medium (30%): $0.06 (3 × $0.02)
- 1 complex (10%): $0.09 (1 × $0.09)

Total: $1.05/month for builds + fixes
```

**Still well within $120/month budget!**

## How Sage "Knows" What Error Means

### Error Complexity Scoring

In [shared/routing.py](../shared/routing.py), the scoring system analyzes the error log:

```python
def score_keywords(self, query: str) -> int:
    """Score based on complexity keywords."""
    query_lower = query.lower()

    # Error complexity patterns
    simple_errors = ['syntaxerror', 'indentation', 'nameerror']
    medium_errors = ['typeerror', 'valueerror', 'attributeerror', 'keyerror']
    complex_errors = ['assertionerror', 'runtimeerror', 'security', 'oauth', 'authentication']

    # Complexity keywords
    if any(word in query_lower for word in complex_errors):
        return 5  # Complex error
    elif any(word in query_lower for word in medium_errors):
        return 3  # Medium error
    elif any(word in query_lower for word in simple_errors):
        return 1  # Simple error

    return 0
```

### Smart Context Analysis

The error log includes:
1. **Stack trace**: Shows which files/functions failed
2. **Error type**: Python exception class
3. **Error message**: Specific failure reason
4. **Failed test name**: Indicates what functionality broke

All of this gets fed into the routing system, which:
- Counts keywords
- Estimates token size
- Checks for complexity markers
- Decides optimal model

## Example: Complete Error Flow

```bash
$ ./sage plan "add user authentication with session management"

[Architect] Planning...
[Router] Using google/gemini-1.5-pro for planning (score: 5)
[Architect] Plan Created: architect/workspaces/sage_brain/plan.md

$ ./sage build

[Builder] Parsing plan structure...
[Router] Using ollama/gemma3:12b for plan parsing (score: 2)
[Builder] Found 2 files to build.

[Builder] Generating: brain/auth/session.py...
[Router] Using anthropic/claude-sonnet-4.5 for full generation (score: 6)
[LLM] Anthropic (claude-sonnet-4.5) Cost: $0.03421 (1234 in, 1567 out)
[Builder] Wrote 3421 bytes to sandbox/brain/auth/session.py

[Builder] Generating: brain/auth/middleware.py...
[Router] Using anthropic/claude-sonnet-4.5 for full generation (score: 5)
[LLM] Anthropic (claude-sonnet-4.5) Cost: $0.02891 (987 in, 1234 out)
[Builder] Wrote 2156 bytes to sandbox/brain/auth/middleware.py

[Architect] Testing Cycle 1/3...
❌ Tests Failed: ['test_session_expiry', 'test_session_validation']

[Builder] Self-Healing brain/auth/session.py...
[Router] Using anthropic/claude-sonnet-4.5 for bug fixing (score: 6)
[LLM] Anthropic (claude-sonnet-4.5) Cost: $0.02134 (843 in, 967 out)
[Builder] Applied fix to brain/auth/session.py

[Architect] Testing Cycle 2/3...
✅ All Tests Passed!

Build Complete. Total cost: $0.11441
```

## Summary

**Sage determines which model to use for bug fixes based on**:

1. ✅ **Error type** (syntax vs logic vs design)
2. ✅ **Error message complexity** (simple typo vs security flaw)
3. ✅ **Code context** (file size, related functionality)
4. ✅ **Keyword analysis** ("refactor", "redesign", "authentication")
5. ✅ **Token estimates** (larger fixes = higher scores)

**This ensures**:
- Simple typos: FREE (Ollama)
- Logic bugs: $0.02 (Sonnet)
- Design flaws: $0.09 (Opus)

**The same intelligent routing that determines initial code generation also determines bug fixing!** 🎯

## Related Documentation

- [BUILDER_ROUTING_FIX.md](BUILDER_ROUTING_FIX.md) - How builder routing works
- [SELF_UPDATING_ROUTING.md](SELF_UPDATING_ROUTING.md) - Dynamic model discovery
- [architect/builder.py](../architect/builder.py) - Builder implementation
- [shared/routing.py](../shared/routing.py) - Routing logic
