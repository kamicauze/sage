# Sage PWA Setup Guide

Your Sage ecosystem now includes a **unified Progressive Web App** that combines both the Brain monitor and Architect studio into a single, mobile-friendly interface!

## What's New

### 🎯 Unified Interface
- **Single UI** for both Brain monitoring and Architect development
- **Responsive design** optimized for mobile, tablet, and desktop
- **Quick switching** between Brain and Architect views

### 📱 Progressive Web App Features
- **Installable** - Add to home screen on iOS/Android
- **Offline support** - Works without internet (cached pages)
- **Native app feel** - Runs in standalone mode
- **Fast loading** - Service worker caching

### 🧠 Brain Monitor (React)
Replaced the Gradio dashboard with a modern React interface:
- Real-time status monitoring
- Live transcript feed
- Direct chat interface
- Mobile-optimized controls

## Quick Start

### 1. Start the Unified Interface

```bash
cd /home/kamicauze/sage/architect/ui

# Install dependencies (first time only)
npm install

# Start the development server
npm run dev
```

The interface will be available at: **http://localhost:3000**

### 2. Access from Other Devices

#### Option A: Local Network (Same WiFi)

1. Find your machine's IP address:
```bash
hostname -I | awk '{print $1}'
```

2. On your phone/tablet browser, navigate to:
```
http://YOUR_IP_ADDRESS:3000
```

Example: `http://192.168.1.100:3000`

3. **Install as App:**
   - **iOS Safari:** Tap Share → Add to Home Screen
   - **Android Chrome:** Tap Menu (⋮) → Add to Home Screen
   - **Desktop:** Look for install icon in address bar

#### Option B: Tailscale VPN (Recommended)

Access Sage from anywhere securely:

```bash
# Install Tailscale on your Sage machine
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up

# Install Tailscale app on your phone
# iOS: App Store
# Android: Play Store

# Access via Tailscale IP: http://100.x.x.x:3000
```

#### Option C: Cloudflare Tunnel (Custom Domain)

Get `https://sage.yourdomain.com`:

```bash
# Install cloudflared
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb

# Authenticate and create tunnel
cloudflared tunnel login
cloudflared tunnel create sage

# Configure tunnel (edit with your details)
cat > ~/.cloudflared/config.yml <<EOF
tunnel: <TUNNEL_ID>
credentials-file: ~/.cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: sage.yourdomain.com
    service: http://localhost:3000
  - service: http_status:404
EOF

# Start tunnel
cloudflared tunnel run sage

# Install as service for auto-start
sudo cloudflared service install
```

## Interface Features

### Navigation

The unified interface includes two main sections:

#### 🏗️ Architect (Development Studio)
- **Dashboard** - Project overview
- **Build** - Code generation and testing
- **Memory** - Cognitive zones and context
- **Stats** - Performance metrics
- **Settings** - Configuration

#### 🧠 Brain (Runtime Monitor)
- **Brain Monitor** - Live status dashboard
  - Real-time system status
  - Audio level visualization
  - STT/Brain/TTS status
  - Latency metrics
- **Live Activity** - Direct chat interface
  - Text-based conversation
  - Real-time responses
  - Chat history

### Switching Between Views

Use the toggle buttons at the top of the sidebar:
- **Architect** - Development tools
- **Brain** - Runtime monitoring

## Mobile Optimization

### Responsive Breakpoints
- **Mobile** (< 768px): Single column, compact navigation
- **Tablet** (768px - 1024px): Optimized grid layouts
- **Desktop** (> 1024px): Full sidebar and multi-column

### Touch Gestures
- Tap navigation items to switch views
- Scroll through activity logs
- Pull to refresh (coming soon)

## PWA Installation

### iOS (iPhone/iPad)

1. Open Safari (must use Safari, not Chrome)
2. Navigate to `http://YOUR_IP:3000`
3. Tap the **Share** button (square with arrow)
4. Scroll down and tap **Add to Home Screen**
5. Name it "Sage" and tap **Add**

**Note:** iOS Safari has limitations:
- No push notifications
- Limited background processing
- Must use Safari for installation

### Android

1. Open Chrome browser
2. Navigate to `http://YOUR_IP:3000`
3. Tap the **Menu** (⋮) button
4. Tap **Add to Home Screen** or **Install App**
5. Confirm installation

### Desktop (Chrome/Edge)

1. Navigate to `http://localhost:3000`
2. Look for install icon in address bar (⊕ or computer icon)
3. Click **Install Sage**
4. App will open in standalone window

## Current Status & Roadmap

### ✅ Implemented
- [x] PWA manifest and service worker
- [x] Unified navigation
- [x] Brain Monitor UI (React)
- [x] Live Chat interface
- [x] Responsive mobile design
- [x] Offline support (cached pages)
- [x] Install prompts

### 🚧 In Progress
- [ ] WebSocket-to-MQTT bridge
- [ ] Real-time data from brain
- [ ] MQTT message publishing from UI
- [ ] Push notifications (Android)

### 🔮 Future Enhancements
- [ ] Voice input from mobile
- [ ] Haptic feedback
- [ ] Background sync
- [ ] Pattern detection alerts
- [ ] Personality switching from mobile
- [ ] Voice settings adjustment

## Troubleshooting

### Can't Connect from Phone

1. **Check firewall:**
```bash
sudo ufw allow 3000/tcp
sudo ufw reload
```

2. **Verify server is listening on all interfaces:**
```bash
# Check if port 3000 is bound to 0.0.0.0 or ::
netstat -tuln | grep 3000
```

3. **Make sure both devices are on same network:**
```bash
# On Sage machine
ip addr show

# Ensure phone WiFi is connected to same router
```

### Service Worker Not Registering

1. **HTTPS Requirement:** PWAs require HTTPS (except localhost)
   - Use Cloudflare Tunnel for HTTPS
   - Or use Tailscale for secure local access

2. **Clear browser cache:**
   - Chrome: Settings → Privacy → Clear browsing data
   - Safari: Settings → Safari → Clear History and Website Data

3. **Check console for errors:**
   - Open browser dev tools (F12)
   - Look for service worker errors

### Brain Monitor Shows "Not Connected"

This is expected! The WebSocket-to-MQTT bridge is not yet implemented.

**Current workaround:**
- Access the Gradio dashboard at `http://YOUR_IP:7860` for real-time brain monitoring
- Use the React UI for chat and basic status (placeholder data)

**Coming soon:** Full WebSocket integration will connect the React UI directly to MQTT.

## Architecture Notes

### Old vs New

| Component | Old | New |
|-----------|-----|-----|
| Brain UI | Gradio (Python, port 7860) | React/Next.js (unified) |
| Architect UI | Next.js (port 3000) | React/Next.js (unified) |
| Mobile Access | Not optimized | PWA with offline support |
| Navigation | Separate apps | Unified with quick switch |

### File Structure

```
architect/ui/
├── public/
│   ├── manifest.json          # PWA configuration
│   ├── sw.js                  # Service worker
│   ├── icon-192.png          # App icon (192x192)
│   └── icon-512.png          # App icon (512x512)
├── src/
│   ├── app/
│   │   ├── brain/
│   │   │   ├── page.tsx      # Brain monitor dashboard
│   │   │   └── live/
│   │   │       └── page.tsx  # Live chat interface
│   │   ├── api/
│   │   │   └── brain/
│   │   │       └── route.ts  # WebSocket/MQTT bridge (TODO)
│   │   └── layout.tsx        # Root layout with PWA meta
│   └── components/
│       ├── Sidebar.tsx       # Unified navigation
│       └── PWAInstaller.tsx  # Install prompt
```

## Next Steps

1. **Try it on your phone:**
   ```bash
   # Find your IP
   hostname -I | awk '{print $1}'

   # Visit on phone: http://YOUR_IP:3000
   ```

2. **Install as PWA:**
   - Follow platform-specific instructions above

3. **Test offline mode:**
   - Install the PWA
   - Turn off WiFi
   - App should still load (cached version)

4. **Provide feedback:**
   - What features are most important?
   - Any UI/UX improvements?
   - Performance issues on mobile?

## Contributing

Want to help complete the WebSocket-to-MQTT bridge?

Check out:
- `architect/ui/src/app/api/brain/route.ts` - API endpoint
- `architect/ui/src/app/brain/page.tsx` - Frontend integration
- `brain/dashboard.py` - Reference Gradio implementation

## Resources

- **PWA Documentation:** https://web.dev/progressive-web-apps/
- **Next.js Docs:** https://nextjs.org/docs
- **Tailscale Setup:** https://tailscale.com/kb/1017/install/
- **Cloudflare Tunnels:** https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/

---

**Need help?** Check the troubleshooting section or open an issue.

Enjoy your unified Sage interface! 🧠🏗️
