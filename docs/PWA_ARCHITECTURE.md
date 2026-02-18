# Sage PWA Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     SAGE ECOSYSTEM                          │
└─────────────────────────────────────────────────────────────┘

         📱 Mobile              💻 Desktop           🌐 Remote
         ┌────────┐            ┌────────┐          ┌────────┐
         │ iPhone │            │ Laptop │          │ Tablet │
         │ Android│            │ Desktop│          │  iPad  │
         └───┬────┘            └───┬────┘          └───┬────┘
             │                     │                   │
             └─────────────────────┼───────────────────┘
                                   │
                          PWA (Port 3000)
                    http://YOUR_IP:3000
                                   │
        ┌──────────────────────────┴──────────────────────────┐
        │                                                      │
        │         UNIFIED SAGE CONTROL CENTER                 │
        │              (Next.js PWA)                          │
        │                                                      │
        ├──────────────────┬───────────────────────────────────┤
        │                  │                                   │
        │  🏗️ ARCHITECT    │         🧠 BRAIN                 │
        │   (Dev Studio)   │        (Runtime Monitor)         │
        │                  │                                   │
        │  • Dashboard     │    • Live Status                 │
        │  • Build         │    • Audio Levels                │
        │  • Memory        │    • Transcripts                 │
        │  • Stats         │    • Chat Interface              │
        │  • Settings      │    • Latency Metrics             │
        │                  │                                   │
        └──────────────────┴───────────────────────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │                             │
               Architect API                 MQTT Broker
                 (SQLite)                  (Port 1883)
                    │                             │
                    │                             │
              Project Data                   sage/# topics
              Memory Zones                   ├─ sage/brain/status
              Build Logs                     ├─ sage/stt/status
                                            ├─ sage/voice/transcript
                                            └─ sage/voice/response
                                                   │
                                            ┌──────┴──────┐
                                            │             │
                                        Brain Core    Gradio UI
                                        (Python)     (Port 7860)
                                            │         [Backup]
                                            │
                                        IoT Sensors
```

## Component Breakdown

### 1. Client Layer (Multi-Device)

```
📱 Phone/Tablet              💻 Desktop
├─ iOS Safari               ├─ Chrome
├─ Android Chrome           ├─ Firefox
├─ Installed PWA            ├─ Edge
└─ Standalone Mode          └─ Installed PWA

Common Features:
✓ Responsive UI
✓ Offline caching
✓ Touch/click optimized
✓ Install to home screen
```

### 2. PWA Application (Port 3000)

```
Next.js 15 Application
│
├─ /app
│  ├─ /                     → Architect Dashboard
│  ├─ /build                → Build Interface
│  ├─ /memory               → Memory Zones
│  ├─ /stats                → Performance Stats
│  ├─ /settings             → Configuration
│  ├─ /brain                → Brain Monitor
│  └─ /brain/live           → Live Chat
│
├─ /api
│  ├─ /projects/*           → Project management
│  ├─ /memory/*             → Memory operations
│  └─ /brain/*              → MQTT bridge (TODO)
│
├─ /components
│  ├─ Sidebar               → Unified navigation
│  ├─ ProjectSelector       → Project switcher
│  └─ PWAInstaller          → Install prompt
│
└─ /public
   ├─ manifest.json         → PWA config
   ├─ sw.js                 → Service worker
   └─ icons/                → App icons
```

### 3. Service Worker Flow

```
Browser Request
      │
      ↓
Service Worker Intercepts
      │
      ├─→ Check Cache
      │   │
      │   ├─→ Cache Hit → Return cached response
      │   │
      │   └─→ Cache Miss
      │           │
      │           ↓
      └─→ Network Request
              │
              ├─→ Success → Cache response + Return
              │
              └─→ Failure → Return offline page
```

### 4. Data Flow

#### Architect Operations
```
UI Component
    ↓
API Route (/api/*)
    ↓
Backend Logic
    ↓
SQLite Database
    ↓
Response → UI
```

#### Brain Monitoring (Future)
```
Brain Core (Python)
    ↓
MQTT Publish (sage/*)
    ↓
MQTT Broker
    ↓
WebSocket Bridge (TODO)
    ↓
Next.js API Route
    ↓
WebSocket to Client
    ↓
React Component Update
```

## Network Access Methods

### Method 1: Local Network (WiFi)

```
Phone (WiFi)
    │
    └─→ Router (192.168.1.x)
            │
            └─→ Sage Machine (192.168.1.100:3000)
                    │
                    └─→ Next.js Server

URL: http://192.168.1.100:3000
Speed: Fast (local)
Security: Network dependent
```

### Method 2: Tailscale VPN

```
Phone (Cellular/WiFi)
    │
    └─→ Tailscale Network (encrypted)
            │
            └─→ Sage Machine (100.x.x.x:3000)
                    │
                    └─→ Next.js Server

URL: http://100.x.x.x:3000
Speed: Good (VPN overhead)
Security: Encrypted end-to-end
Works: Anywhere with internet
```

### Method 3: Cloudflare Tunnel

```
Phone (Any network)
    │
    └─→ Internet
            │
            └─→ Cloudflare Edge
                    │
                    └─→ Cloudflare Tunnel
                            │
                            └─→ Sage Machine (localhost:3000)

URL: https://sage.yourdomain.com
Speed: Good (CDN cached)
Security: HTTPS encrypted
Works: Anywhere
```

## PWA Installation Flow

```
First Visit
    │
    ↓
Browser detects manifest.json
    │
    ↓
beforeinstallprompt event fires
    │
    ↓
PWAInstaller component shows banner
    │
    ├─→ User dismisses
    │   └─→ Save preference in localStorage
    │
    └─→ User clicks "Install"
            │
            ↓
        Browser install prompt
            │
            ├─→ User cancels → Hide banner
            │
            └─→ User confirms
                    │
                    ↓
                App installed
                    │
                    ├─→ Icon on home screen
                    ├─→ Standalone window
                    └─→ Offline caching active
```

## Offline Support Strategy

```
User visits page
    │
    ↓
Service Worker registers
    │
    ↓
Cache Strategy: Network First
    │
    ├─→ Online
    │   │
    │   ├─→ Fetch from network
    │   ├─→ Cache response
    │   └─→ Display to user
    │
    └─→ Offline
        │
        ├─→ Check cache
        │
        ├─→ Cache hit → Display cached version
        │
        └─→ Cache miss → Show offline page
```

## State Management

```
┌─────────────────────────────────────┐
│        React Context API            │
├─────────────────────────────────────┤
│                                     │
│  ProjectContext                     │
│  ├─ currentProject                  │
│  ├─ projects list                   │
│  └─ selectProject()                 │
│                                     │
│  Future: BrainContext               │
│  ├─ systemStatus                    │
│  ├─ transcripts                     │
│  ├─ mqttConnection                  │
│  └─ sendMessage()                   │
│                                     │
└─────────────────────────────────────┘
```

## Security Layers

```
┌─────────────────────────────────────┐
│         Security Stack              │
├─────────────────────────────────────┤
│                                     │
│  Layer 1: Network                   │
│  ├─ Firewall rules (ufw)           │
│  ├─ Port restrictions              │
│  └─ IP filtering                   │
│                                     │
│  Layer 2: Transport                 │
│  ├─ HTTPS (Cloudflare)             │
│  ├─ VPN (Tailscale)                │
│  └─ WebSocket encryption           │
│                                     │
│  Layer 3: Application               │
│  ├─ API route validation           │
│  ├─ Input sanitization             │
│  └─ CSRF protection (Next.js)      │
│                                     │
│  Layer 4: Data (Future)             │
│  ├─ Authentication                  │
│  ├─ Session management             │
│  └─ Role-based access              │
│                                     │
└─────────────────────────────────────┘
```

## Performance Optimization

```
Initial Load
    │
    ├─→ Static files (cached by CDN)
    ├─→ JavaScript (code splitting)
    ├─→ CSS (Tailwind purged)
    └─→ Images (optimized)
        │
        ↓
    First Paint < 1s
        │
        ↓
    Lazy Load
    ├─→ Heavy components (charts)
    ├─→ Non-critical routes
    └─→ Images (below fold)
        │
        ↓
    Interactive < 2s
        │
        ↓
    Background Tasks
    ├─→ Service worker update
    ├─→ Cache refresh
    └─→ Prefetch next routes
```

## Browser Compatibility

```
✅ Full Support
├─ Chrome 90+ (Desktop/Mobile)
├─ Edge 90+
├─ Firefox 88+
└─ Safari 14+ (iOS/macOS)

⚠️  Partial Support
├─ Safari iOS (no push notifications)
├─ Chrome iOS (uses Safari engine)
└─ Firefox Android (limited)

❌ Not Supported
├─ IE 11 and below
├─ Old Android browsers
└─ Pre-2020 mobile browsers
```

## Development vs Production

### Development Mode
```
npm run dev:network
    │
    ↓
Next.js Dev Server
├─ Hot module reload
├─ Source maps
├─ Verbose logging
└─ Port 3000 (--host 0.0.0.0)
```

### Production Mode
```
npm run build
    │
    ↓
Optimized build
├─ Minified JS/CSS
├─ Tree shaking
├─ Image optimization
└─ Static generation
    │
    ↓
npm start
└─ Production server (Port 3000)
```

## Monitoring & Debugging

```
Client Side
├─ Browser DevTools (F12)
├─ React DevTools
├─ Network tab
└─ Service Worker inspector

Server Side
├─ Next.js logs
├─ API route errors
└─ Build output

Mobile Debugging
├─ Chrome Remote Debugging (Android)
├─ Safari Web Inspector (iOS)
└─ Weinre (remote inspector)
```

---

## Quick Reference

| Component | Port | Protocol | Access |
|-----------|------|----------|--------|
| PWA UI | 3000 | HTTP(S) | All devices |
| Gradio (backup) | 7860 | HTTP | Local/Network |
| MQTT Broker | 1883 | MQTT | Internal |
| Architect API | 3000/api/* | HTTP | Same as UI |

| Storage | Type | Purpose |
|---------|------|---------|
| SQLite | Database | Projects, memory, builds |
| localStorage | Browser | PWA preferences, cache |
| IndexedDB | Browser | Offline queue (future) |
| Cache API | Browser | Static assets, pages |

---

**Architecture Status:** ✅ Complete | 🚧 WebSocket bridge pending

This architecture provides a solid foundation for unified, mobile-accessible control of the entire Sage ecosystem.
