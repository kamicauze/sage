# Architect Degraded Mode Runbook

Last updated: February 11, 2026
Scope: `apps/architect-studio` API + router/build pipeline.

## Purpose

Define operational response when Architect dependencies degrade while keeping core plan/build flows available where possible.

## Observability Signals

- Structured JSON logs (component/event/correlation):
  - API: `component=api`
  - Router: `component=router`
  - Builder: `component=builder`
- Correlation header on responses: `X-Architect-Correlation-Id`
- Request/version headers:
  - `X-Architect-Api-Version`
  - `X-Architect-Api-Compat`

## Quick Triage Checklist

1. Capture `X-Architect-Correlation-Id` from failing response.
2. Filter logs by that correlation ID.
3. Identify failure domain:
   - memory backend
   - cloud provider
   - MCP integrations
4. Apply domain-specific mitigation below.
5. Re-run smoke checks:
   - `python -m unittest discover -s tests -p "test_architect_*.py" -v`

## Scenario A: Memory Backend Unavailable

Symptoms:
- Plan requests still run, but context retrieval logs warnings:
  - `event=memory_context_unavailable`
  - `event=plan_memory_unavailable`

Expected behavior:
- Router degrades to planning without memory context.
- Build flow remains operational.

Actions:
1. Verify memory dependencies:
   - `chromadb`
   - `sentence-transformers`
   - `langchain-text-splitters`
2. Validate persist path permissions (`.sage_memory`).
3. Rebuild/repair memory index:
   - run architect ingest for target manifest.
4. Confirm warnings stop after successful query path.

Escalation:
- If memory fails for all projects for >30 minutes, mark service degraded and pause memory-dependent tuning work.

## Scenario B: Cloud LLM Unavailable / Timeout

Symptoms:
- Router decisions still produced.
- LLM calls fail or route fallbacks increase.
- Build/plan latency spikes; repeated provider errors in logs.

Expected behavior:
- Local route (`ollama`) remains available where policy allows.
- Some high-complexity requests may degrade in quality.

Actions:
1. Check provider key/config presence in `brain/.env`.
2. Validate outbound connectivity to provider endpoint.
3. Confirm policy model mapping still points to valid models.
4. Temporarily lower cloud reliance in manifest policy if needed.
5. Track recovery with correlation IDs across repeated requests.

Escalation:
- If cloud route failure >50% for 15 minutes, switch to temporary local-first policy and notify maintainers.

## Scenario C: MCP Integrations Unavailable

Symptoms:
- API startup previously failed due MCP import errors.
- Now route availability is logged:
  - `mcp_enabled` in startup event.

Expected behavior:
- Core plan/build API should remain online.
- MCP-specific endpoints may degrade if underlying dependency is missing.

Actions:
1. Check startup log event for disabled reason.
2. Install missing optional packages (`watchdog`, `aiomqtt`, etc).
3. Validate `shared/mcp` imports cleanly.
4. Restart API and confirm `mcp_enabled=true`.

Escalation:
- If MCP features are required for current release workflow, block release until route health is restored.

## Recovery Verification

After remediation, verify:

1. API security + observability tests:
   - `python -m unittest discover -s tests -p "test_architect_api_security.py" -v`
2. Architect improvements + smoke:
   - `python -m unittest discover -s tests -p "test_architect_improvements.py" -v`
   - `python -m unittest discover -s tests -p "test_architect_plan_build_smoke.py" -v`
3. CI gate script:
   - `PYTHON_BIN=.venv/bin/python bash scripts/ci/run_architect_checks.sh`

## Incident Record Template

- Start time (UTC):
- Correlation IDs affected:
- Scenario (A/B/C):
- User impact:
- Root cause:
- Mitigation:
- Permanent fix follow-up:
