# ✅ Sage PWA CLI - Implementation Complete!

## 🎉 What's New

You now have a **single command** that starts the entire Sage PWA stack!

```bash
./sage pwa
```

This one command launches:
- ✅ MQTT Broker (WebSocket + TCP)
- ✅ Brain Core (AI processing)
- ✅ Next.js PWA (modern web interface)

---

## 🚀 Quick Start

### 1. Start Everything

```bash
cd /home/kamicauze/sage
./sage pwa
```

**Expected output:**
```
🌐 Starting Sage PWA Stack...
============================================================

1️⃣ Starting MQTT Broker...
   ✅ Mosquitto running (ports 1883 + 9001)

2️⃣ Starting Brain Core...
   ✅ Brain started (logs: /tmp/sage_brain.log)

3️⃣ Starting PWA UI...
   Creating .env.local from example...
   Starting Next.js server...
   ✅ Next.js running (port 3000)

============================================================
🎉 Sage PWA is READY!
============================================================

📱 Access Points:
   Desktop:  http://localhost:3000/brain
   Network:  http://192.168.1.100:3000/brain

🔧 Services Running:
   • MQTT Broker:  ✅ (1883 + 9001)
   • Brain Core:   ✅ (see /tmp/sage_brain.log)
   • Next.js PWA:  ✅ (port 3000)

💡 Features:
   • Real-time brain monitoring
   • STT/TTS toggle controls
   • Live chat interface
   • Mobile-friendly (PWA)

🛑 To stop: Press Ctrl+C
============================================================
```

### 2. Access the UI

**Desktop:**
```
http://localhost:3000/brain
```

**Phone (same WiFi):**
```
http://YOUR_IP:3000/brain
```

**Phone (Tailscale):**
```
http://100.80.204.94:3000/brain
```

### 3. Use the Features

**Brain Monitor Page:**
- Toggle STT on/off (Power button)
- Toggle TTS on/off (Power button)
- View real-time status
- See audio levels
- Check latency metrics

**Live Chat Page:**
- Send text messages to Sage
- Get responses in real-time
- Works even with STT disabled

---

## 📋 Command Options

### Start with Brain
```bash
./sage pwa
```
**Default:** Starts everything

### Start without Brain
```bash
./sage pwa --no-brain
```
**Use case:** UI development, or brain running separately

### Stop Everything
```bash
./sage stop
```
**Stops:** All Sage services (MQTT, Brain, PWA, Voice, etc.)

---

## 🔧 What Happens Behind the Scenes

### 1. MQTT Broker (Mosquitto)
- Kills any existing mosquitto process
- Starts with `mosquitto.conf`:
  - Port 1883: MQTT protocol (for Python brain)
  - Port 9001: WebSocket protocol (for browser)
- Runs in background

### 2. Brain Core (Python)
- Starts `brain/main.py` in background
- Logs to `/tmp/sage_brain.log`
- Publishes status to MQTT topics
- Listens for control messages

### 3. PWA UI (Next.js)
- Creates `.env.local` if missing
- Runs `npm run dev:network` (binds to 0.0.0.0)
- Waits for port 3000 to be listening
- Connects to MQTT via WebSocket

### 4. Monitoring
- Watches all processes
- Detects crashes
- Handles Ctrl+C gracefully
- Cleans up on exit

---

## 🎯 Key Features

### Real-Time Connection
- Browser connects directly to MQTT broker
- WebSocket protocol (port 9001)
- Automatic reconnection
- Live status updates

### Optional STT/TTS
- Services warm up but don't auto-start
- Toggle on/off from UI
- Control messages published to MQTT
- Brain shows "STANDBY" when disabled

### Process Management
- All services run in background
- Coordinated startup
- Graceful shutdown
- Crash detection

### Network Access
- Binds to 0.0.0.0 (all interfaces)
- Accessible from local network
- Works with Tailscale
- Firewall-friendly

---

## 📱 Mobile Access Setup

### Update Environment
```bash
cd /home/kamicauze/sage/architect/ui
nano .env.local
```

Set your IP:
```env
NEXT_PUBLIC_MQTT_WS_URL=ws://YOUR_IP:9001
```

Or for Tailscale:
```env
NEXT_PUBLIC_MQTT_WS_URL=ws://100.80.204.94:9001
```

### Restart PWA
```bash
./sage stop
./sage pwa
```

### Open on Phone
```
http://YOUR_IP:3000/brain
```

### Install as App
- **iOS:** Safari → Share → Add to Home Screen
- **Android:** Chrome → Menu → Add to Home Screen

---

## 🐛 Troubleshooting

### "Mosquitto failed to start"

**Check if installed:**
```bash
which mosquitto
```

**Install if needed:**
```bash
sudo apt install mosquitto
```

**Check ports:**
```bash
netstat -tuln | grep -E "(1883|9001)"
```

### "Next.js failed to start"

**Check Node.js version:**
```bash
node --version
# Need v18.18+ or v20+
```

**Upgrade Node.js:**
```bash
# Install nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
source ~/.bashrc

# Install Node 20
nvm install 20
nvm use 20
nvm alias default 20
```

**Install dependencies:**
```bash
cd architect/ui
npm install
```

### "Brain stopped unexpectedly"

**Check logs:**
```bash
tail -50 /tmp/sage_brain.log
```

**Common issues:**
- MQTT broker not running
- Port 1883 already in use
- Missing Python dependencies

**Fix:**
```bash
# Reinstall dependencies
pip install -r requirements.txt

# Restart everything
./sage stop
./sage pwa
```

### "Not Connected to Brain" in UI

**This means WebSocket connection to MQTT failed.**

**Check MQTT is running:**
```bash
ps aux | grep mosquitto
```

**Check port 9001:**
```bash
netstat -tuln | grep 9001
```

**Test WebSocket:**
```bash
npm install -g wscat
wscat -c ws://localhost:9001
```

**Check firewall:**
```bash
sudo ufw allow 9001/tcp
sudo ufw reload
```

---

## 📊 Comparison

### Old Way
```bash
# Terminal 1
mosquitto -c mosquitto.conf -v

# Terminal 2
python brain/main.py

# Terminal 3
cd architect/ui
npm run dev:network

# Manual coordination, 3 terminals
```

### New Way
```bash
./sage pwa
# One command, everything coordinated
```

---

## 🔮 Implementation Details

### Added to `sage.py`

**New function: `cmd_pwa(args)`**
- Starts MQTT broker
- Optionally starts brain
- Starts Next.js PWA
- Monitors all processes
- Displays access information
- Handles cleanup

**New CLI argument:**
```python
parser_pwa = subparsers.add_parser("pwa", help="Start PWA Stack (MQTT + Brain + UI)")
parser_pwa.add_argument("--no-brain", action="store_true", help="Start only MQTT and UI")
parser_pwa.set_defaults(func=cmd_pwa)
```

**Updated `cmd_stop()`:**
- Now also kills mosquitto
- Kills Next.js process
- More robust cleanup

---

## 📖 Documentation

| File | Purpose |
|------|---------|
| **[CLI_COMMANDS.md](CLI_COMMANDS.md)** | Complete command reference |
| **[SAGE_PWA_SETUP.md](SAGE_PWA_SETUP.md)** | PWA installation guide |
| **[MQTT_WEBSOCKET_SETUP.md](MQTT_WEBSOCKET_SETUP.md)** | WebSocket setup |
| **[REALTIME_BRAIN_COMPLETE.md](REALTIME_BRAIN_COMPLETE.md)** | Integration details |
| **[README.md](README.md)** | Updated with PWA info |

---

## 🎓 What You Learned

1. **Process Management** - Starting/stopping coordinated services
2. **MQTT Brokers** - Dual protocol (MQTT + WebSocket) setup
3. **Next.js Deployment** - Network-accessible dev server
4. **CLI Design** - User-friendly command interface
5. **Error Handling** - Graceful degradation and cleanup

---

## ✨ Summary

### Before
- 3+ manual commands
- Multiple terminals
- Easy to forget a service
- No unified output

### After
- 1 command: `./sage pwa`
- Single terminal
- Coordinated startup
- Beautiful status display
- Easy to share with others

---

## 🚀 Next Steps

1. **Test it now:**
   ```bash
   ./sage pwa
   ```

2. **Access from phone:**
   - Update `.env.local` with your IP
   - Restart and visit on phone

3. **Install as PWA:**
   - Add to home screen
   - Use like a native app

4. **Share the command:**
   - Tell others: "Just run `./sage pwa`"
   - No complex setup needed

---

**Status:** ✅ Complete and ready to use!

**Try it:** `./sage pwa` → Visit http://localhost:3000/brain 🎉
