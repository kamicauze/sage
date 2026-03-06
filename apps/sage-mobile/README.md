# Sage Mobile Companion

Dedicated mobile app for human-in-the-middle control of Sage.

## SDK Baseline

- Expo SDK: `54.x`
- React Native: `0.81.5`

## Current MVP

- Configure Architect API URL and token
- Optional Tailscale API URL with automatic fallback between Tailnet and LAN
- Chat with Sage through Architect API (`POST /chat`, provider=`brain`)
- Streaming chat support via `POST /chat/stream` with fallback to non-stream
- AI News tab powered by `GET /news/ai` (RSS + optional X/Nitter sources)
- List pending approval proposals (`GET /approvals/pending`)
- Open proposal detail (title, summary, actions, metadata)
- Approve/deny actions (`POST /approvals/{id}/decision`)
- Persist chat sessions locally for testing continuity
- Save API token in secure device storage when supported

## Run

```bash
cd apps/sage-mobile
npm install
npm run start
```

Then open in Expo Go, Android emulator, or iOS simulator.

## API Requirements

- Architect API reachable from mobile device (LAN IP, Tailscale, or public HTTPS)
- MQTT broker + Brain runtime running (`sage brain`) for live Brain chat
- If API auth is enabled:
  - set `SAGE_ARCHITECT_API_TOKEN` on server
  - enter the same token in mobile app settings

## Notes

- `localhost` works only on emulators/simulators; physical phones need a reachable host IP.
- This app is intentionally scoped to approvals first so it can serve as a safe control plane before adding broader Sage controls.
