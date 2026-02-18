# Functional Sage Roadmap

This roadmap turns Sage into a reliable personal assistant with safe autonomy, measurable quality, and real-world integrations.

## Success Criteria

- Voice in -> useful action out reliably (`STT -> intent -> brain/architect/home -> TTS`)
- Safe autonomy for risky operations (explicit approvals + rollback)
- Continuous model improvement (trigger -> evaluate -> canary -> promote/rollback)
- Persistent context (subconscious summaries + active task memory + handoff)
- Real-world awareness (SmartThings + health summaries + presence-aware output)

## Current Baseline

- [x] Hybrid intent classifier exists (`packages/shared/intent.py`)
- [x] n8n trigger/list/create/execute/status API endpoints exist (`apps/architect-studio/api/routes/mcp.py`)
- [x] Canary routing controls exist (`packages/shared/routing.py`)
- [x] Canary routing tests exist (`tests/test_routing_canary.py`)
- [x] Approval queue API exists (`apps/architect-studio/api/routes/approvals.py`)
- [x] Mobile approval companion scaffold exists (`apps/sage-mobile`)

## Phase 1: Runtime Reliability (Week 1)

- [x] Fix voice->Architect task mapping (`code/fix/test` should execute full plan+build flow)
- [x] Add strict response contract for `voice.handler` <-> `main.py` <-> `action.router`
- [x] Add startup preflight checks (MQTT, Ollama, STT/TTS model paths, cloud keys)
- [ ] Add e2e smoke test for one full voice turn path

## Phase 2: Decision Broker (Week 1-2)

- [ ] Implement action proposal queue with policy: `auto | ask | deny`
- [ ] Require confirmation for risky operations (model switch, workflow creation, repo write, device automation)
- [ ] Add approval timeout + cancellation behavior
- [ ] Add immutable audit log for proposed/executed/blocked actions

## Phase 3: Intent System (Week 2-3)

- [ ] Keep Tier 1 regex reflex path (<1ms) as default fast path
- [ ] Add Tier 2 embedding classifier service (4070 Ti) for ambiguous but non-reasoning intents
- [ ] Keep Tier 3 LLM fallback for long-tail ambiguity
- [ ] Add intents: `self_modify`, `self_diagnose`, `task_continue`
- [ ] Add active task mode biasing for multi-turn technical sessions

## Phase 4: Subconscious / Working Memory (Week 3)

- [ ] Add async summarizer service (fire-and-forget per turn)
- [ ] Persist rolling summary + last raw turns + active task context
- [ ] Add tool handoff payload for Codex/Claude continuation
- [ ] Add fallback path when summary is stale/unavailable

## Phase 5: Device + Health Integrations (Week 3-4)

- [ ] Add SmartThings OAuth bridge and event subscriptions -> MQTT normalization
- [ ] Add Android companion for Health Connect summaries -> MQTT
- [ ] Normalize telemetry schema for brain context ingestion
- [ ] Add privacy policy controls (retention windows, redaction, consent revocation)

## Phase 6: Model Autopilot (Week 4)

- [ ] Trigger model research nightly and on latency/quality regressions
- [ ] Discover local Ollama candidates + allowlisted remote candidates
- [ ] Evaluate candidates on quality, p95 latency, VRAM fit, stability
- [ ] Run staged canary rollout and auto-rollback on degradation
- [ ] Promote winning model by updating routing registry/config

## Phase 7: Safe Self-Modification (Week 5)

- [ ] Pipeline: request -> design -> plan -> build -> tests -> approval -> apply
- [ ] Add explicit "promote sandbox to repo" step with rollback handle
- [ ] Auto re-index memory/RAG after accepted code changes
- [ ] Add post-change guardrails (error budget + revert policy)

## Phase 8: Cluster Hardening (Week 5-6)

- [ ] Assign stable service roles across Pi / Jetson / 3090 / 4070
- [ ] Add MQTT health heartbeats and failure detection
- [ ] Add supervisor/autorestart and degraded-mode routing
- [ ] Run failure drills (node down, model unavailable, broker restart)

## Tracking Notes

- Keep this file updated with dates and owners as tasks start/finish.
- Every completed phase should add/expand automated tests.
- 2026-02-12: Added approval queue endpoints and initial mobile approval client.
