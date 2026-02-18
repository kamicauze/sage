# Architect Hardening Sprint Board

Timeline: February 9, 2026 -> February 27, 2026
Goal: Production-grade reliability for Sage Architect.

## HS-01 Path and Config Unification (P0)
Status: In Progress
Owner: Codex + Maintainer
Scope:
- Add centralized path module (`architect.paths`)
- Remove hardcoded `architect/...`/`workspaces/...` strings in core runtime and API paths
- Keep compatibility with legacy root symlinks
Tasks:
- [x] Add `apps/architect-studio/paths.py`
- [x] Migrate `builder.py` path usage
- [x] Migrate `router.py` path usage
- [x] Migrate `llm.py`, `llm_updater.py` path usage
- [x] Migrate API models/routes (`builds`, `builds_git`, `projects`, `stats`)
- [x] Migrate CLI architect path touchpoints in `sage.py`
- [ ] Migrate remaining route/filesystem path literals in MCP/stats helpers
- [ ] Add CI rule to reject new hardcoded Architect path literals
DoD:
- One module defines Architect paths/config defaults.
- Core Architect flows no longer depend on scattered literals.

## HS-02 Build Pipeline Determinism (P0)
Status: In Progress
Scope:
- Deterministic incremental caching
- Explicit skip/rebuild reasons
Tasks:
- [x] Replace output-hash cache bug with input-signature cache
- [x] Add regression tests: unchanged skip, source-change rebuild
- [ ] Emit structured build telemetry for skip/rebuild decisions
DoD:
- Stable skip behavior across repeated runs with unchanged inputs.

## HS-03 Memory and Dependency Resilience (P0)
Status: In Progress
Scope:
- Graceful behavior when optional deps unavailable
- Ingestion guardrails
Tasks:
- [x] Make memory import dependency-safe
- [x] Fallback when memory unavailable during planning
- [x] Restrict ingestion scope (zones + size/type ignores)
- [ ] Add memory health status endpoint fields for degraded mode reason
DoD:
- Planning/build still operate in degraded mode without memory backend.

## HS-04 API Contract Hardening (P0)
Status: In Progress
Scope:
- Rich, stable response schema for plan/build
Tasks:
- [x] Include files built/skipped/failed with reason
- [x] Include test run summary and failing tests in `BuildResponse`
- [x] Include timing metadata (`started_at`, `duration_ms`) in plan/build responses
- [x] Add backward-compatible API version marker

## HS-05 Security Baseline (P0)
Status: Completed
Scope:
- Basic access and input hardening
Tasks:
- [x] Token auth middleware for API routes
- [x] Restrict CORS by configured origins
- [x] Validate and sanitize manifest/file path inputs (block traversal)
- [x] Redact internal stack traces from default API errors
- [x] Add API security tests (auth + traversal) with optional dependency skip in lean envs

## HS-06 Test and CI Gates (P0)
Status: Completed
Scope:
- Reliable quality gates
Tasks:
- [x] Expand unit test suite for router/builder/api error modes
- [x] Add integration smoke tests for `plan -> build`
- [x] Add CI pipeline for lint + tests + py_compile
- [x] Add failure triage output artifacts in CI

## HS-07 Observability and Ops (P1)
Status: Completed
Scope:
- Structured logs and traceability
Tasks:
- [x] Add structured JSON logging in API/router/builder
- [x] Propagate request/build correlation IDs
- [x] Add ops runbook for degraded modes (memory/cloud unavailable)

## HS-08 Performance and Budget Guardrails (P1)
Status: Pending
Scope:
- Latency and budget control
Tasks:
- [ ] Add route-level timeout/retry policy matrix
- [ ] Benchmark plan/build median/p95 with baseline report
- [ ] Enforce budget-stop behavior with explicit API/CLI message contracts

## Week-by-Week Plan
- Week 1 (Feb 9-13): HS-01, HS-02, HS-03
- Week 2 (Feb 16-20): HS-04, HS-05
- Week 3 (Feb 23-27): HS-06, HS-07, HS-08 + release stabilization
