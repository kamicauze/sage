# Implementation Cost Estimate: Sage Architect Improvements

**Date**: 2026-01-12
**Model Used for Estimation**: Claude Sonnet 4.5
**Current Codebase**: 1,866 lines (architect module only)

---

## Cost Model Assumptions

### Token Rates (Claude Sonnet 4.5)
- **Input**: $3.00 per 1M tokens
- **Output**: $15.00 per 1M tokens

### Average Token Counts
- **1 line of Python code**: ~4 tokens (reading)
- **1 line of Python code**: ~6 tokens (generating)
- **Documentation/Comments**: ~3 tokens per line
- **Context overhead per task**: ~2,000 tokens (system prompts, conversation)

### Task Complexity Multipliers
- **Bug Fix**: 1x (read existing, make small change)
- **Feature Addition**: 2x (read existing, design, implement)
- **Refactor**: 3x (read multiple files, redesign, implement, test)
- **New System**: 4x (design from scratch, integrate)

---

## Phase 1: Critical Bug Fixes (Week 1)

### 1.1 Fix Budget Check Async Bug
**File**: `architect/llm.py` (lines 67-73)

**Work Required**:
- Read llm.py (177 lines × 4 tokens = 708 tokens)
- Analyze async issue (500 tokens)
- Generate fix (50 tokens)

**Tokens**: 708 + 500 + 50 = **1,258 tokens**
**Cost**: $0.00 (negligible)

---

### 1.2 Fix Zone Filter Bug
**File**: `architect/memory.py` (line 96)

**Work Required**:
- Read memory.py (104 lines × 4 tokens = 416 tokens)
- Generate fix (20 tokens)
- Test query (500 tokens context)

**Tokens**: 416 + 20 + 500 = **936 tokens**
**Cost**: $0.00 (negligible)

---

### 1.3 Remove Duplicate Imports
**File**: `architect/router.py` (lines 15-19)

**Work Required**:
- Read router.py (189 lines × 4 tokens = 756 tokens)
- Generate fix (10 tokens)

**Tokens**: 756 + 10 = **766 tokens**
**Cost**: $0.00 (negligible)

---

### 1.4 Implement Google Gemini Provider
**File**: `architect/llm.py` (lines 81-86)

**Work Required**:
- Read llm.py (708 tokens)
- Research Gemini API docs (via WebSearch + WebFetch: ~8,000 tokens)
- Design integration (1,500 tokens)
- Implement new method (150 lines × 6 tokens = 900 tokens)
- Update error handling (300 tokens)

**Tokens**: 708 + 8,000 + 1,500 + 900 + 300 = **11,408 tokens**
**Cost**: Input (11,408 × $3/1M) + Output (900 × $15/1M) = **$0.05**

---

### 1.5 Add Interactive Mode Flag
**Files**: `architect/router.py`, `sage.py`

**Work Required**:
- Read router.py (756 tokens)
- Read sage.py (262 lines × 4 tokens = 1,048 tokens)
- Design CLI flag system (1,000 tokens)
- Implement mode parameter (200 tokens output)
- Add approval prompts (100 tokens output)

**Tokens**: 756 + 1,048 + 1,000 + 300 = **3,104 tokens**
**Cost**: Input (2,804 × $3/1M) + Output (300 × $15/1M) = **$0.01**

---

### 1.6 Implement Diff Viewer
**New File**: `architect/diff_viewer.py` (~150 lines)

**Work Required**:
- Research diff libraries (2,000 tokens)
- Read existing builder.py (206 × 4 = 824 tokens)
- Design diff viewer class (1,500 tokens)
- Implement with rich/colorama (150 lines × 6 = 900 tokens)
- Integration into builder (200 tokens)

**Tokens**: 2,000 + 824 + 1,500 + 900 + 200 = **5,424 tokens**
**Cost**: Input (4,524 × $3/1M) + Output (900 × $15/1M) = **$0.03**

---

**Phase 1 Total**:
- **Tokens**: 22,896
- **Cost**: **$0.09**
- **Time**: 1 week (with human review/testing)

---

## Phase 2: Core Improvements (Week 2)

### 2.1 Surgical Edits (Replace Full File Generation)
**Files**: `architect/builder.py`, new `architect/editor.py`

**Work Required**:
- Read builder.py (206 × 4 = 824 tokens)
- Read existing prompts (500 tokens)
- Design edit system (3,000 tokens context)
- Implement editor.py (250 lines × 6 = 1,500 tokens)
- Refactor builder to use editor (500 tokens)
- Update prompts for edit format (200 tokens)
- Testing iterations (2,000 tokens)

**Tokens**: 824 + 500 + 3,000 + 1,500 + 500 + 200 + 2,000 = **8,524 tokens**
**Cost**: Input (7,024 × $3/1M) + Output (1,500 × $15/1M) = **$0.04**

---

### 2.2 Incremental Builds with Checkpoints
**Files**: `architect/builder.py`, new `architect/checkpoint.py`

**Work Required**:
- Read builder.py (824 tokens)
- Read router.py (756 tokens)
- Design checkpoint system (2,500 tokens)
- Implement checkpoint.py (180 lines × 6 = 1,080 tokens)
- Refactor builder for incremental mode (800 tokens)
- Add file-by-file testing (600 tokens)

**Tokens**: 824 + 756 + 2,500 + 1,080 + 800 + 600 = **6,560 tokens**
**Cost**: Input (4,980 × $3/1M) + Output (1,580 × $15/1M) = **$0.04**

---

### 2.3 Real-Time Context Loading
**Files**: `architect/builder.py`, `architect/memory.py`

**Work Required**:
- Read builder.py (824 tokens)
- Read memory.py (416 tokens)
- Design dynamic context system (2,000 tokens)
- Implement context refresh in builder (400 tokens)
- Update memory query logic (300 tokens)
- Test with large codebase (1,500 tokens)

**Tokens**: 824 + 416 + 2,000 + 400 + 300 + 1,500 = **5,440 tokens**
**Cost**: Input (4,740 × $3/1M) + Output (700 × $15/1M) = **$0.03**

---

**Phase 2 Total**:
- **Tokens**: 20,524
- **Cost**: **$0.11**
- **Time**: 1 week

---

## Phase 3: UX Polish (Week 3)

### 3.1 Streaming Output
**Files**: `architect/llm.py`, `architect/builder.py`

**Work Required**:
- Read llm.py (708 tokens)
- Research streaming APIs (1,500 tokens)
- Implement streaming for Ollama (300 tokens)
- Implement streaming for OpenAI (200 tokens)
- Implement streaming for Anthropic (200 tokens)
- Update builder to stream (400 tokens)

**Tokens**: 708 + 1,500 + 1,100 = **3,308 tokens**
**Cost**: Input (2,208 × $3/1M) + Output (1,100 × $15/1M) = **$0.02**

---

### 3.2 Conversation Refinement
**Files**: `architect/router.py`, new `architect/conversation.py`

**Work Required**:
- Read router.py (756 tokens)
- Design conversation state management (2,000 tokens)
- Implement conversation.py (120 lines × 6 = 720 tokens)
- Add refine command to CLI (200 tokens)
- Integrate with router (400 tokens)

**Tokens**: 756 + 2,000 + 720 + 200 + 400 = **4,076 tokens**
**Cost**: Input (3,356 × $3/1M) + Output (720 × $15/1M) = **$0.02**

---

### 3.3 Explain Mode
**New File**: `architect/explainer.py` (~200 lines)

**Work Required**:
- Read existing files for patterns (2,000 tokens)
- Design explainer system (1,500 tokens)
- Implement explainer.py (200 lines × 6 = 1,200 tokens)
- Add explain command to CLI (150 tokens)
- Create explanation prompt template (300 tokens)

**Tokens**: 2,000 + 1,500 + 1,200 + 150 + 300 = **5,150 tokens**
**Cost**: Input (3,950 × $3/1M) + Output (1,200 × $15/1M) = **$0.03**

---

**Phase 3 Total**:
- **Tokens**: 12,534
- **Cost**: **$0.07**
- **Time**: 1 week

---

## Phase 4: Advanced Features (Week 4+)

### 4.1 Test-Driven Mode
**Files**: `architect/tester.py`, `architect/builder.py`

**Work Required**:
- Read tester.py (76 × 4 = 304 tokens)
- Read builder.py (824 tokens)
- Design TDD workflow (2,500 tokens)
- Implement test-first generation (600 tokens)
- Update builder logic (500 tokens)
- Create TDD prompt template (400 tokens)

**Tokens**: 304 + 824 + 2,500 + 600 + 500 + 400 = **5,128 tokens**
**Cost**: Input (3,628 × $3/1M) + Output (1,500 × $15/1M) = **$0.03**

---

### 4.2 Watch Mode
**New File**: `architect/watcher.py` (~300 lines)

**Work Required**:
- Research file watching libraries (1,500 tokens)
- Design watch system (2,000 tokens)
- Implement watcher.py (300 lines × 6 = 1,800 tokens)
- Integrate with router (400 tokens)
- Add watch command (100 tokens)

**Tokens**: 1,500 + 2,000 + 1,800 + 400 + 100 = **5,800 tokens**
**Cost**: Input (4,000 × $3/1M) + Output (1,800 × $15/1M) = **$0.04**

---

### 4.3 Undo/Rollback System
**Files**: `architect/checkpoint.py` (extend), `sage.py`

**Work Required**:
- Read checkpoint.py (assume 180 × 4 = 720 tokens)
- Design rollback mechanism (1,500 tokens)
- Implement undo command (400 tokens)
- Add checkpoint history (300 tokens)
- CLI integration (200 tokens)

**Tokens**: 720 + 1,500 + 400 + 300 + 200 = **3,120 tokens**
**Cost**: Input (2,220 × $3/1M) + Output (900 × $15/1M) = **$0.02**

---

**Phase 4 Total**:
- **Tokens**: 14,048
- **Cost**: **$0.09**
- **Time**: 1-2 weeks

---

## Total Implementation Cost Summary

| Phase | Features | Tokens (Input) | Tokens (Output) | Cost | Time |
|-------|----------|----------------|-----------------|------|------|
| **Phase 1** | Bug fixes + Interactive + Diff | ~18,000 | ~4,900 | **$0.09** | 1 week |
| **Phase 2** | Surgical edits + Incremental + Context | ~16,700 | ~3,800 | **$0.11** | 1 week |
| **Phase 3** | Streaming + Refinement + Explain | ~9,500 | ~3,000 | **$0.07** | 1 week |
| **Phase 4** | TDD + Watch + Undo | ~9,800 | ~4,200 | **$0.09** | 1-2 weeks |
| **TOTAL** | All 12 improvements | **~54,000** | **~15,900** | **$0.36** | **4-5 weeks** |

---

## Additional Cost Considerations

### Testing & Debugging (30% overhead)
- Running generated code multiple times
- Fixing bugs discovered during testing
- Iterating on prompts for better output

**Estimated**: +10,000 tokens input, +3,000 tokens output = **+$0.08**

### Documentation Updates
- Update README.md with new features
- Update docs/symbiote.md
- Add usage examples

**Estimated**: ~5,000 tokens = **+$0.02**

### Integration Testing
- Test new features work together
- Update existing tests
- End-to-end workflow validation

**Estimated**: ~8,000 tokens = **+$0.03**

---

## **Grand Total Estimate**

### Tokens
- **Input**: ~77,000 tokens
- **Output**: ~22,000 tokens
- **Total**: ~99,000 tokens

### Cost
- **Base Implementation**: $0.36
- **Testing & Debugging**: $0.08
- **Documentation**: $0.02
- **Integration**: $0.03
- **TOTAL**: **$0.49** (~50 cents)

### Time
- **Development**: 4-5 weeks (with human oversight)
- **Per Phase**: ~1 week each

---

## Cost Comparison to Manual Development

### Human Developer Cost (US Market)
- **Mid-level developer**: $75/hour
- **Estimated time**: 80-120 hours (2-3 weeks full-time)
- **Cost**: $6,000 - $9,000

### AI-Assisted Development Cost
- **Claude API**: $0.49
- **Human oversight**: 10-15 hours @ $75/hour = $750 - $1,125
- **Total**: **$750 - $1,125**

**Savings**: 80-90% cost reduction

---

## ROI Analysis

### Monthly Sage Architect Usage (Hypothetical)
- 20 feature requests per month
- Average 3 plan/build cycles per feature
- Current cost per request: ~$0.15 (using cloud models)
- **Monthly cloud cost**: $9.00

### After Improvements
With better surgical edits and incremental builds:
- Fewer full file rewrites (30% token reduction)
- Better caching/context reuse (20% token reduction)
- Improved first-attempt success (fewer retries, 25% reduction)

**New monthly cost**: ~$5.00

**Monthly savings**: $4.00
**Payback period**: 0.12 months (~4 days)

---

## Risk Factors

### Token Usage May Increase Due To:
1. **Larger context windows**: Reading more files for better accuracy (+30%)
2. **Multi-turn refinement**: Conversation history grows (+20%)
3. **Failed attempts**: Some implementations need iteration (+15%)

**Adjusted high estimate**: $0.75 (still less than $1)

### Cost Mitigation Strategies:
1. Use Claude Haiku for simple tasks (not Sonnet)
2. Implement prompt caching (50% input token savings on repeated context)
3. Batch related changes into single requests
4. Use local models (Ollama) for testing/dry-runs

---

## Recommended Budget Allocation

For full implementation with buffer:

| Category | Budget | Notes |
|----------|--------|-------|
| Development | $0.50 | Base implementation |
| Testing | $0.25 | Multiple test cycles |
| Buffer (50%) | $0.38 | Iteration, failed attempts |
| **TOTAL** | **$1.13** | Comfortable budget with safety margin |

---

## Conclusion

**Implementing all 12 improvements to Sage Architect will cost approximately $0.50 - $1.00 in Claude API tokens**, with most of the cost coming from context loading and iterative refinement.

This is an **extremely cost-effective investment** considering:
1. The improvements will save money long-term (better token efficiency)
2. Manual development would cost 5,000-10,000x more
3. Payback period is less than 1 week of normal usage
4. The system becomes significantly more capable and user-friendly

**Recommendation**: Proceed with all phases. The ROI is exceptional.
