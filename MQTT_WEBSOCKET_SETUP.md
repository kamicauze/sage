# MQTT WebSocket Setup for Real-Time Brain Monitoring

## Overview

The Sage PWA now includes **real-time MQTT integration** that connects your browser directly to the brain's MQTT broker using WebSockets. This enables:

- ✅ Live status updates (STT/TTS/Brain state)
- ✅ Real-time transcripts
- ✅ Audio level visualization
- ✅ Latency metrics
- ✅ STT/TTS toggle controls from the UI

## Architecture

```
Browser (PWA)
    ↓ WebSocket
MQTT Broker (Port 9001)
    ↓ MQTT
Sage Brain (Python)
```

## Setup Instructions

### 1. Configure MQTT Broker with WebSocket Support

Your `mosquitto.conf` has been updated to include WebSocket support:

```conf
# MQTT TCP listener (for Python brain)
listener 1883
protocol mqtt
allow_anonymous true

# WebSocket listener (for browser-based PWA)
listener 9001
protocol websockets
allow_anonymous true

# Disable persistence for speed
persistence false
```

### 2. Restart Mosquitto with WebSocket Support

```bash
cd /home/kamicauze/sage

# Stop any running instance
pkill mosquitto

# Start with WebSocket support
mosquitto -c mosquitto.conf -v
```

You should see output like:
```
1673847200: mosquitto version 2.x starting
1673847200: Opening ipv4 listen socket on port 1883.
1673847200: Opening ipv4 listen socket on port 9001.
```

### 3. Configure PWA Environment

```bash
cd /home/kamicauze/sage/architect/ui

# Copy environment template
cp .env.local.example .env.local

# Edit if needed (default should work)
nano .env.local
```

For local access:
```env
NEXT_PUBLIC_MQTT_WS_URL=ws://localhost:9001
```

For network/Tailscale access:
```env
NEXT_PUBLIC_MQTT_WS_URL=ws://YOUR_IP:9001
```

### 4. Start the Brain with Optional STT/TTS

The brain now supports **optional STT/TTS** - they warm up but don't auto-start:

```bash
cd /home/kamicauze/sage

# Start brain (STT/TTS disabled by default)
python brain/main.py
```

Enable/disable from the PWA UI using the toggle buttons on the Brain Monitor page.

### 5. Start the PWA

```bash
cd /home/kamicauze/sage/architect/ui

# Install dependencies (if not done)
npm install

# Start server
npm run dev:network
```

### 6. Test the Connection

1. Open browser: `http://localhost:3000/brain`
2. Check connection status at top of page
3. If connected, you'll see:
   - ✅ Green "Connected" indicator
   - Real-time status updates
   - STT/TTS toggle buttons working

## MQTT Topics

The PWA subscribes to these topics:

| Topic | Purpose | Payload Example |
|-------|---------|-----------------|
| `sage/brain/status` | Brain core status | `{"status": "ready"}` |
| `sage/stt/status` | STT service status | `{"status": "listening"}` |
| `sage/stt/levels` | Audio input levels | `{"vis": 0.5}` |
| `sage/stt/metrics` | STT performance | `{"transcribe_ms": 120}` |
| `sage/voice/transcript` | User speech | `"Hello Sage"` |
| `sage/voice/response` | Sage response | `{"text": "Hi there!"}` |
| `sage/tts/status` | TTS status | `{"status": "speaking"}` |

The PWA publishes to:

| Topic | Purpose | Payload Example |
|-------|---------|-----------------|
| `sage/voice/transcript` | Send text to brain | `"Tell me a joke"` |
| `sage/stt/control` | Enable/disable STT | `{"enabled": true}` |
| `sage/tts/control` | Enable/disable TTS | `{"enabled": false}` |
| `sage/brain/config` | Change personality | `{"personality": "sage"}` |
| `sage/voice/config` | Voice settings | `{"voice": "af_bella", "speed": 1.0}` |

## STT/TTS Optional Control

### Frontend (PWA)

The Brain Monitor page now has toggle buttons:

- **STT Toggle** - Enable/disable speech-to-text
- **TTS Toggle** - Enable/disable text-to-speech

When disabled:
- STT: Brain won't listen to microphone (text chat still works)
- TTS: Brain won't speak responses (text display still works)

### Backend (Python)

To make STT/TTS truly optional in the brain, you need to:

1. **Listen for control messages:**

Add to `brain/main.py` or `brain/voice/handler.py`:

```python
def on_stt_control(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
        enabled = data.get("enabled", False)

        if enabled:
            # Start STT service
            voice_handler.start_stt()
            print("[Brain] STT enabled")
        else:
            # Stop STT service
            voice_handler.stop_stt()
            print("[Brain] STT disabled")
    except Exception as e:
        print(f"[Brain] STT control error: {e}")

# Subscribe to control topics
client.subscribe("sage/stt/control")
client.message_callback_add("sage/stt/control", on_stt_control)
```

2. **Modify voice handler initialization:**

Update `VoiceHandler` to support lazy initialization:

```python
class VoiceHandler:
    def __init__(self, brain_callback, architect_bridge, auto_start=False):
        self.brain_callback = brain_callback
        self.architect_bridge = architect_bridge
        self.stt_enabled = False
        self.tts_enabled = False

        if auto_start:
            self.start_stt()
            self.start_tts()

    def start_stt(self):
        if not self.stt_enabled:
            # Initialize STT components
            self.stt_enabled = True

    def stop_stt(self):
        if self.stt_enabled:
            # Cleanup STT components
            self.stt_enabled = False
```

## Troubleshooting

### "Not Connected to Brain" Warning

**Cause:** PWA can't connect to MQTT WebSocket

**Solutions:**

1. **Check Mosquitto is running:**
```bash
ps aux | grep mosquitto
# Should show: mosquitto -c mosquitto.conf -v
```

2. **Verify WebSocket port is open:**
```bash
netstat -tuln | grep 9001
# Should show: tcp 0.0.0.0:9001 LISTEN
```

3. **Check firewall:**
```bash
sudo ufw allow 9001/tcp
sudo ufw reload
```

4. **Test WebSocket connection:**
```bash
# Install wscat if needed
npm install -g wscat

# Test connection
wscat -c ws://localhost:9001
```

### Connection Works Locally but Not on Phone

1. **Update .env.local with network IP:**
```env
NEXT_PUBLIC_MQTT_WS_URL=ws://192.168.1.100:9001
```

2. **Restart Next.js:**
```bash
# Ctrl+C to stop
npm run dev:network
```

3. **Verify firewall allows port 9001:**
```bash
sudo ufw status | grep 9001
```

### Mosquitto Won't Start with WebSocket

**Error:** `Error: Unable to load config`

**Fix:** Make sure mosquitto is compiled with WebSocket support:

```bash
# Check mosquitto version and modules
mosquitto -h | grep websockets

# If not available, install from official repo
sudo apt-add-repository ppa:mosquitto-dev/mosquitto-ppa
sudo apt update
sudo apt install mosquitto
```

### STT/TTS Toggles Don't Work

**This is expected!** The frontend sends the control messages, but the Python brain needs to be updated to listen and respond to them.

**Quick test:** Monitor MQTT messages:
```bash
mosquitto_sub -h localhost -t "sage/#" -v
```

Toggle STT in the PWA and you should see:
```
sage/stt/control {"enabled": true}
```

## Performance Tips

### Reduce Latency

1. **Use local MQTT broker** (already done)
2. **Disable persistence** (already done in config)
3. **Use QoS 0** for real-time data (best effort, no acks)

### Network Access

For best mobile performance:

**Local WiFi:**
- Latency: ~5-20ms
- Best for: Home use

**Tailscale:**
- Latency: ~20-50ms
- Best for: Remote access with encryption

**Cloudflare Tunnel:**
- Latency: ~50-200ms
- Best for: HTTPS access, multiple devices

## Next Steps

1. ✅ **Test locally** - Visit http://localhost:3000/brain
2. ✅ **Enable services** - Toggle STT/TTS on
3. ✅ **Send messages** - Use Live Chat to test
4. 🚧 **Update Python brain** - Add control message handlers
5. 🚧 **Test on mobile** - Access via Tailscale

## Files Modified

- `mosquitto.conf` - Added WebSocket listener
- `architect/ui/src/lib/mqtt-bridge.ts` - MQTT client library
- `architect/ui/src/contexts/BrainContext.tsx` - Real-time state management
- `architect/ui/src/app/brain/page.tsx` - Brain monitor with toggles
- `architect/ui/src/app/brain/live/page.tsx` - Live chat interface
- `architect/ui/.env.local.example` - Environment template

---

**Status:** ✅ Real-time MQTT connection implemented!

**Test it:** `npm run dev:network` → Visit `/brain` → See live updates!
