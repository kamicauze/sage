# Sage Mobile Companion MVP

Date: 2026-02-12

## Why Native Mobile App

The Architect PWA now has improved bundle size, but a dedicated app is still useful for:

- Always-available approval controls with push notifications.
- Stable device auth/session handling.
- Better background behavior (health sync, location/presence hooks).
- Cleaner "man in the middle" UX than a general-purpose web console.

## MVP Goal

Ship a safe control plane first:

1. Receive and review pending approval requests.
2. Approve/deny with reviewer identity and reason.
3. Keep audit trail on backend.

## Delivered in This Iteration

New app scaffold: `apps/sage-mobile`

- Expo + React Native TypeScript setup.
- Config screen:
  - Architect API base URL
  - API token
  - reviewer identity
  - connection test
- Pending queue screen:
  - reads `GET /approvals/pending`
- Decision flow:
  - submits `POST /approvals/{id}/decision`
- Local settings persistence via AsyncStorage.

## Backend Control Plane Delivered

- New router: `apps/architect-studio/api/routes/approvals.py`
- Wired in `apps/architect-studio/api/server.py`
- Endpoints:
  - `POST /approvals/proposals`
  - `GET /approvals/pending`
  - `GET /approvals/{id}`
  - `POST /approvals/{id}/decision`

## Next Mobile Phases

1. Push notifications for new high-risk proposals.
2. Signed action preview (hash) to prevent payload tampering.
3. Biometric unlock before approving `high`/`critical` risk actions.
4. Expanded controls:
  - active tasks
  - model canary status
  - home/health summary dashboards.
