# Flight Booking App: Complete Build Simulation

## Executive Summary

**Task**: Build a flight booking app from scratch
**Total Cost**: $0.32 (66% cheaper than using only premium models)
**Time**: ~3-5 minutes
**Files Created**: 16 (8 source + 8 tests)
**Tests Passing**: 8/8 ✓

## Complete Workflow

### Command 1: Planning

```bash
./sage plan "design a flight booking app with search, payment integration, and booking management"
```

**Routing Decision**:
- **Query**: "design a flight booking app with search, payment integration, and booking management"
- **Score**: 7
  - "design" keyword: +2
  - "integration" keyword: +2
  - "payment" keyword: +2
  - Multiple features: +1
- **Route**: HYBRID
- **Model**: google/gemini-1.5-pro ($1.25/$5)
- **Cost**: $0.00892

**Output**: 8-file implementation plan with detailed architecture

---

### Command 2: Build Execution

```bash
./sage build
```

## Detailed Per-File Routing

### Phase 1: Plan Parsing (FREE)

| Task | Score | Route | Model | Cost |
|------|-------|-------|-------|------|
| Extract files from plan | 2 | LOCAL | ollama/gemma3:12b | $0.00 |

**Why**: Simple JSON extraction, no complexity

---

### Phase 2: File Generation (Mix of FREE, Sonnet, Opus)

#### File 1: flight_app/models/flight.py (FREE)

**Context**: Simple data model for Flight
**Complexity Analysis**:
- Simple Pydantic/dataclass
- Basic fields (id, airline, origin, destination, etc.)
- No complex logic

**Routing**:
- **Score**: 2
- **Route**: LOCAL
- **Model**: ollama/gemma3:12b
- **Cost**: $0.00

---

#### File 2: flight_app/models/booking.py (Sonnet - $0.02)

**Context**: Booking model with state management
**Complexity Analysis**:
- State machine (pending → confirmed → cancelled)
- Payment tracking integration
- User associations

**Routing**:
- **Score**: 4
- **Route**: HYBRID
- **Model**: anthropic/claude-sonnet-4.5
- **Cost**: $0.02134

**Why Sonnet**: State machine logic requires careful design

---

#### File 3: flight_app/services/search.py (Sonnet - $0.04)

**Context**: Flight search with external API
**Complexity Analysis**:
- External API integration (Amadeus/Skyscanner)
- Complex filtering (date, price, airline)
- Async operations
- Error handling

**Routing**:
- **Score**: 6
- **Route**: HYBRID
- **Model**: anthropic/claude-sonnet-4.5
- **Cost**: $0.03891

**Why Sonnet**: API integration with multiple edge cases

---

#### File 4: flight_app/services/payment.py (Opus - $0.08)

**Context**: Stripe payment processing
**Complexity Analysis**:
- **SECURITY CRITICAL**
- Webhook signature verification
- Refund handling
- PCI compliance requirements

**Routing**:
- **Score**: 9 (security keywords trigger high score!)
- **Route**: CLOUD
- **Model**: anthropic/claude-opus-4.5
- **Cost**: $0.07621

**Why Opus**: Payment processing requires highest quality for security

---

#### File 5: flight_app/api/routes.py (Sonnet - $0.03)

**Context**: REST API endpoints
**Complexity Analysis**:
- REST API design
- Authentication middleware
- Request validation

**Routing**:
- **Score**: 5
- **Route**: HYBRID
- **Model**: anthropic/claude-sonnet-4.5
- **Cost**: $0.02567

**Why Sonnet**: API design needs good architecture

---

#### File 6: flight_app/database.py (Sonnet - $0.02)

**Context**: Database setup with async
**Complexity Analysis**:
- SQLAlchemy async configuration
- Connection pooling
- Migration setup

**Routing**:
- **Score**: 4
- **Route**: HYBRID
- **Model**: anthropic/claude-sonnet-4.5
- **Cost**: $0.01892

**Why Sonnet**: Async database patterns need expertise

---

#### File 7: flight_app/config.py (FREE)

**Context**: Configuration management
**Complexity Analysis**:
- Simple environment variable loading
- Basic validation

**Routing**:
- **Score**: 2
- **Route**: LOCAL
- **Model**: ollama/gemma3:12b
- **Cost**: $0.00

**Why FREE**: Standard configuration pattern

---

#### File 8: flight_app/main.py (FREE)

**Context**: FastAPI entry point
**Complexity Analysis**:
- Standard FastAPI boilerplate
- CORS, middleware mounting

**Routing**:
- **Score**: 3
- **Route**: LOCAL
- **Model**: ollama/gemma3:12b
- **Cost**: $0.00

**Why FREE**: Common FastAPI pattern

---

### Phase 3: Test Generation (ALL FREE)

**Task**: Generate pytest tests for all 8 files
**Routing**: All score < 4 (test generation is simpler)
**Model**: ollama/gemma3:12b for all
**Cost**: $0.00 (8 test files, all FREE)

---

### Phase 4: Test Execution & Self-Healing

#### Test Cycle 1: 3 Failures Detected

```
✓ test_flight_creation
✓ test_flight_validation
✗ test_booking_status          ← AttributeError
✓ test_payment_tracking
✗ test_flight_search           ← TypeError
✓ test_filters
✗ test_stripe_integration      ← Security vulnerability!
✓ test_refund
```

---

#### Bug Fix 1: booking.py (Sonnet - $0.02)

**Error**:
```python
AttributeError: 'Booking' object has no attribute 'transition_to'
```

**Error Analysis**:
- AttributeError (medium complexity)
- Missing state machine method
- Keyword "transition" suggests design pattern

**Routing**:
- **Score**: 5
- **Route**: HYBRID
- **Model**: anthropic/claude-sonnet-4.5
- **Cost**: $0.02341

**Fix Applied**: Added `transition_to()` method with state validation

---

#### Bug Fix 2: search.py (Sonnet - $0.02)

**Error**:
```python
TypeError: 'NoneType' object is not subscriptable
return response['data']  # response is None
```

**Error Analysis**:
- TypeError with None handling
- API response parsing
- Missing error handling

**Routing**:
- **Score**: 4
- **Route**: HYBRID
- **Model**: anthropic/claude-sonnet-4.5
- **Cost**: $0.02156

**Fix Applied**: Added null check and proper error handling

---

#### Bug Fix 3: payment.py (Opus - $0.08)

**Error**:
```python
AssertionError: Webhook signature verification failed
SecurityWarning: Payment webhook not properly secured!
```

**Error Analysis**:
- **SECURITY VULNERABILITY**
- Webhook signature missing
- Payment processing (critical domain)
- Keywords: "security", "webhook", "payment"

**Routing**:
- **Score**: 10 (security critical!)
- **Route**: CLOUD
- **Model**: anthropic/claude-opus-4.5
- **Cost**: $0.08234

**Fix Applied**:
- Implemented HMAC signature verification
- Added timestamp validation
- Prevented replay attacks

---

#### Test Cycle 2: All Tests Pass! ✅

```
✓ test_flight_creation
✓ test_flight_validation
✓ test_booking_status          ← Fixed!
✓ test_payment_tracking
✓ test_flight_search           ← Fixed!
✓ test_filters
✓ test_stripe_integration      ← Fixed!
✓ test_refund
```

---

## Cost Breakdown

### By Phase

| Phase | Operations | Cost |
|-------|-----------|------|
| Planning | 1 plan (Gemini) | $0.00892 |
| Parsing | 1 parse (Ollama) | $0.00000 |
| Generation | 3 FREE + 4 Sonnet + 1 Opus | $0.18105 |
| Testing | 8 tests (Ollama) | $0.00000 |
| Bug Fixes | 2 Sonnet + 1 Opus | $0.12731 |
| **TOTAL** | **31 LLM calls** | **$0.31728** |

### By Model

| Model | Calls | Input Tokens | Output Tokens | Cost | Percentage |
|-------|-------|--------------|---------------|------|------------|
| ollama/gemma3:12b | 11 | ~5,000 | ~6,000 | $0.00 | 0% |
| google/gemini-1.5-pro | 1 | 3,456 | 4,891 | $0.01 | 3% |
| anthropic/claude-sonnet-4.5 | 6 | ~7,500 | ~9,000 | $0.19 | 60% |
| anthropic/claude-opus-4.5 | 2 | ~4,400 | ~6,000 | $0.16 | 50% |

### Smart Routing Savings

```
Without Routing (All Opus):
  31 calls × $0.03/call avg = $0.93

With Smart Routing:
  11 calls FREE + 20 calls cloud = $0.32

Savings: $0.61 (66% reduction!)
```

---

## Key Routing Insights

### What Triggered Each Model?

#### FREE (Ollama) - 11 calls
- Simple models (flight.py, config.py, main.py)
- Plan parsing (JSON extraction)
- Test generation (all 8 tests)

**Why**: No complexity keywords, standard patterns, small scope

#### Gemini ($1.25/$5) - 1 call
- Initial planning (architecture design)

**Why**: Planning task with multiple integrations

#### Sonnet ($3/$15) - 6 calls
- State management (booking.py)
- API integration (search.py, database.py)
- REST API (routes.py)
- Medium bug fixes (2 fixes)

**Why**: Moderate complexity, requires design expertise

#### Opus ($5/$25) - 2 calls
- Payment processing (payment.py) - **Security critical**
- Security bug fix - **Webhook vulnerability**

**Why**: Security keywords, PCI compliance, critical domain

---

## Routing Decision Tree

```
For each file/task:
  ↓
1. Extract context and keywords
  ↓
2. Score complexity (0-15)
   ├─ Security keywords? +5
   ├─ Integration keywords? +2
   ├─ State machine? +2
   ├─ API external? +2
   └─ Simple CRUD? +0
  ↓
3. Determine route
   ├─ Score 0-3:  LOCAL  (Ollama, FREE)
   ├─ Score 4-7:  HYBRID (Sonnet, $3/$15)
   └─ Score 8+:   CLOUD  (Opus, $5/$25)
  ↓
4. Generate code with selected model
  ↓
5. If error → Route bug fix based on error complexity
```

---

## Monthly Projections

### If you build 10 similar apps/month:

```
Planning:    10 × $0.01  = $0.10
Generation:  10 × $0.18  = $1.80
Testing:     10 × $0.00  = $0.00
Bug fixes:   10 × $0.13  = $1.30
──────────────────────────────────
Total:       10 × $0.32  = $3.20/month
```

**Well within $120/month budget!**

---

## Real-World Observations

### 1. Security Gets Premium Treatment
- Payment processing automatically used Opus
- Security bug fix escalated to Opus
- This is exactly what you want!

### 2. Most Code is FREE
- 11/20 LLM calls used FREE Ollama (55%)
- Simple models, configs, tests → All FREE
- Cost only scales with complexity

### 3. Bug Fixes Cost Less Than Generation
- Initial generation: $0.18
- All 3 bug fixes: $0.13
- Self-healing is cost-effective!

### 4. Parallel Generation is Fast
- 8 files generated in parallel (3 workers)
- Total time: ~3-5 minutes
- No waiting for sequential processing

---

## Comparison: Manual vs Sage

### Manual Development (Traditional)

| Phase | Time | Cost (at $50/hr) |
|-------|------|------------------|
| Planning | 2 hours | $100 |
| Coding flight models | 1 hour | $50 |
| Coding booking system | 3 hours | $150 |
| API integration | 4 hours | $200 |
| Payment integration | 6 hours | $300 |
| Testing | 2 hours | $100 |
| Bug fixing | 3 hours | $150 |
| **TOTAL** | **21 hours** | **$1,050** |

### Sage Automated Development

| Phase | Time | Cost |
|-------|------|------|
| Planning | 30 seconds | $0.01 |
| Coding (all files) | 2 minutes | $0.18 |
| Testing | 30 seconds | $0.00 |
| Bug fixing | 1 minute | $0.13 |
| **TOTAL** | **4 minutes** | **$0.32** |

**Savings**: $1,049.68 and 20 hours 56 minutes!

---

## What This Demonstrates

1. ✅ **Intelligent per-file routing** - Each file gets optimal model
2. ✅ **Security-aware** - Payment code automatically uses premium model
3. ✅ **Cost-efficient** - 66% cheaper than using only premium models
4. ✅ **Self-healing** - Bugs fixed automatically with right model
5. ✅ **Parallel processing** - Fast generation with 3 workers
6. ✅ **Budget-conscious** - $0.32 for entire app (0.27% of $120 budget)

---

## Try It Yourself!

```bash
# Clone the example
./sage plan "design a flight booking app with search, payment integration, and booking management"

# Build it
./sage build

# Check the cost
./sage status

# Expected output:
# Monthly Budget: $0.32 / $120.00
```

---

## Related Documentation

- [BUILDER_ROUTING_FIX.md](BUILDER_ROUTING_FIX.md) - How routing works
- [ERROR_HANDLING_FLOW.md](ERROR_HANDLING_FLOW.md) - Self-healing details
- [SELF_UPDATING_ROUTING.md](SELF_UPDATING_ROUTING.md) - Dynamic model updates
- [SETUP_COMPLETE.md](../SETUP_COMPLETE.md) - System configuration

---

**Built with Sage** 🧠 - The AI architect that knows when to save money and when to spend it.
