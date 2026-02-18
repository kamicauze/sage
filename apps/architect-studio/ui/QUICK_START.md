# Sage PWA - Quick Start

## 🚀 Launch on Desktop

```bash
cd /home/kamicauze/sage/architect/ui

# Start (network accessible)
npm run dev:network

# Visit: http://localhost:3000
```

## 📱 Access from Phone

### Step 1: Get Your IP Address
```bash
hostname -I | awk '{print $1}'
# Example output: 192.168.1.100
```

### Step 2: Open on Phone
- Open browser (Safari on iOS, Chrome on Android)
- Visit: `http://YOUR_IP:3000`
- Example: `http://192.168.1.100:3000`
- Prefer `/brain` for runtime controls:
  - `http://YOUR_IP:3000/brain`

### Step 3: Install as App

**iOS:**
1. Tap Share button (□↑)
2. Scroll down → "Add to Home Screen"
3. Tap "Add"

**Android:**
1. Tap Menu (⋮)
2. Tap "Add to Home Screen" or "Install App"
3. Confirm

## 🧭 Navigation

### Architect Mode (Development)
- Dashboard - Project overview
- Build - Code generation
- Memory - Context zones
- Stats - Performance
- Settings - Configuration

### Brain Mode (Monitoring)
- Brain Monitor - Live status
- Live Activity - Chat interface

**Switch modes:** Use toggle buttons at top of sidebar

## 🔥 Common Commands

```bash
# Start with network access
npm run dev:network

# Build for production
npm run build

# Start production server
npm start

# Run setup (create icons)
npm run setup

# Check what's running
netstat -tuln | grep 3000
```

## 🌐 Network Access Options

### Option 1: Local WiFi (Easiest)
- Both devices on same WiFi
- Access via `http://YOUR_IP:3000`
- Fast, no extra setup

### Option 2: Tailscale VPN (Best for mobile)
```bash
# On Sage machine
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up

# Install Tailscale app on phone
# Access via: http://100.x.x.x:3000
```

### Option 3: Cloudflare Tunnel (Custom domain)
- Get HTTPS access anywhere
- Custom domain: `sage.yourdomain.com`
- See full setup in SAGE_PWA_SETUP.md

## 🐛 Troubleshooting

### Can't connect from phone?
```bash
# Open firewall
sudo ufw allow 3000/tcp

# Verify server is listening
netstat -tuln | grep 3000
# Should show: :::3000 or 0.0.0.0:3000
```

### Need HTTPS for full PWA features?
- Use Tailscale (encrypted automatically)
- Or Cloudflare Tunnel (free HTTPS)

### Fast path from Sage CLI
```bash
./sage pwa --brain-logs
```
This starts MQTT + Brain + UI and prints both localhost and network URLs.

### Service worker not loading?
- Clear browser cache
- Try incognito/private mode
- Check browser console (F12) for errors

## 📊 What Works Right Now

✅ PWA installation
✅ Offline support (cached pages)
✅ Unified navigation
✅ Brain Monitor UI
✅ Live Chat UI
✅ Responsive mobile design
✅ Architect features (existing)

🚧 Coming Soon
- Real-time MQTT data in Brain Monitor
- WebSocket connection to brain
- Push notifications
- Voice input from mobile

## 🔗 Resources

- Full Setup Guide: `/home/kamicauze/sage/SAGE_PWA_SETUP.md`
- Main README: `/home/kamicauze/sage/README.md`

## 💡 Pro Tips

1. **Bookmark on desktop:** Install as PWA for app-like experience
2. **Use Tailscale for phone:** Access Sage from anywhere securely
3. **Pin to home screen:** Feels like a native app
4. **Portrait mode on phone:** Optimized for vertical scrolling
5. **Clear old Gradio:** Brain UI now integrated, can keep Gradio as backup

---

**Ready to go?** Run `npm run dev:network` and visit on your phone!
