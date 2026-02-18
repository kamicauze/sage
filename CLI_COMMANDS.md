# Sage CLI Command Reference

## 🌐 PWA Commands

### Start PWA Stack (Recommended)
```bash
./sage pwa
```
**Starts:** MQTT Broker + Brain + Next.js UI
**Access:** http://localhost:3000/brain
**Features:** Real-time monitoring, STT/TTS controls, live chat

### Start PWA without Brain
```bash
./sage pwa --no-brain
```
**Use case:** UI development or when brain is running separately

---

## 🧠 Runtime Commands

### Start Everything (Legacy)
```bash
./sage start
```
**Starts:** Brain + Voice (STT + TTS) + Gradio Dashboard
**Access:** http://localhost:7860
**Note:** Use `./sage pwa` for the modern PWA interface

### Start Brain Only
```bash
./sage brain
```
**Starts:** Brain core without voice services

### Start Voice Services
```bash
./sage voice
```
**Starts:** STT + TTS (requires brain running separately)

### Start Gradio Dashboard
```bash
./sage dashboard
# or
./sage ui
```
**Starts:** Legacy Gradio web interface
**Access:** http://localhost:7860

---

## 🏗️ Architect Commands

### Initialize Memory
```bash
./sage init
```
**Purpose:** Ingest codebase into memory system
**Run:** Once per project or after major changes

### Plan a Feature
```bash
./sage plan "Add user authentication"
```
**Output:** `architect/workspaces/sage_brain/plan.md`

**Interactive mode:**
```bash
./sage plan -i "Add dark mode"
```
Prompts for approval before proceeding.

### Build from Plan
```bash
./sage build
```
**Purpose:** Execute the current plan
**Features:** Auto-generates code, runs tests, self-heals

**Interactive mode:**
```bash
./sage build -i
```
Review each file change before writing.

### Update LLM Routing
```bash
./sage update
```
**Purpose:** Research latest models and update routing config
**Features:** Auto-discovers new models, optimizes cost/performance

### Check Status
```bash
./sage status
```
**Shows:** Monthly budget usage, memory size, manifest path

**Verbose mode:**
```bash
./sage status -v
```
Shows last 10 API calls with token counts and costs.

---

## 🎙️ Setup Commands

### Voice Enrollment
```bash
./sage enroll
```
**Purpose:** Record your voice for speaker verification
**Required:** Before using voice features

---

## 🛑 Control Commands

### Stop All Services
```bash
./sage stop
```
**Stops:** Brain, voice services, dashboards, MQTT, Next.js

**Manual alternative:**
```bash
Ctrl+C  # In the terminal running services
```

---

## 📁 File Locations

| Component | Path |
|-----------|------|
| Brain Logs | `/tmp/sage_brain.log` |
| STT Logs | `/tmp/sage_ears.log` |
| TTS Logs | `/tmp/sage_mouth.log` |
| Dashboard Logs | `/tmp/sage_dashboard.log` |
| Manifest | `architect/projects/sage.yaml` |
| Memory DB | `.sage_memory/` |
| Usage Tracking | `architect/usage.json` |
| PWA Env | `architect/ui/.env.local` |

---

## 🔥 Common Workflows

### Development (PWA)
```bash
# Terminal 1: Start PWA stack
./sage pwa

# Terminal 2: Watch logs
tail -f /tmp/sage_brain.log

# Access: http://localhost:3000/brain
```

### Architect Development
```bash
# Plan
./sage plan -i "Add feature X"

# Review plan
cat architect/workspaces/sage_brain/plan.md

# Build
./sage build -i

# Check status
./sage status -v
```

### Voice Testing
```bash
# Enroll voice (first time)
./sage enroll

# Start full stack
./sage start

# Or use PWA (recommended)
./sage pwa
# Then toggle STT/TTS in UI
```

### Mobile Access
```bash
# Start PWA
./sage pwa

# Get IP address
hostname -I | awk '{print $1}'

# On phone: http://YOUR_IP:3000/brain
```

---

## 🚨 Troubleshooting

### PWA won't start
```bash
# Check dependencies
cd architect/ui
npm install

# Check Node.js version (need 18+)
node --version

# Try manual start
npm run dev:network
```

### MQTT connection failed
```bash
# Check Mosquitto
ps aux | grep mosquitto
netstat -tuln | grep 9001

# Restart manually
pkill mosquitto
mosquitto -c mosquitto.conf -v
```

### Brain crashed
```bash
# Check logs
tail -50 /tmp/sage_brain.log

# Check if port is in use
netstat -tuln | grep 1883

# Restart
./sage stop
./sage pwa
```

### Can't access from phone
```bash
# Open firewall
sudo ufw allow 3000/tcp
sudo ufw allow 9001/tcp
sudo ufw reload

# Update .env.local
cd architect/ui
nano .env.local
# Set: NEXT_PUBLIC_MQTT_WS_URL=ws://YOUR_IP:9001

# Restart
./sage stop
./sage pwa
```

---

## 💡 Pro Tips

**1. Use PWA for daily use:**
```bash
./sage pwa  # Better than ./sage start
```

**2. Keep brain logs open:**
```bash
tail -f /tmp/sage_brain.log
```

**3. Monitor MQTT messages:**
```bash
mosquitto_sub -h localhost -t "sage/#" -v
```

**4. Check budget regularly:**
```bash
./sage status -v
```

**5. Use interactive mode for important changes:**
```bash
./sage plan -i "critical feature"
./sage build -i
```

**6. Install PWA on phone:**
- Visit http://YOUR_IP:3000/brain
- Safari → Share → Add to Home Screen
- Chrome → Menu → Add to Home Screen

---

## 📖 Related Documentation

- **[SAGE_PWA_SETUP.md](SAGE_PWA_SETUP.md)** - PWA installation guide
- **[MQTT_WEBSOCKET_SETUP.md](MQTT_WEBSOCKET_SETUP.md)** - Real-time connection setup
- **[REALTIME_BRAIN_COMPLETE.md](REALTIME_BRAIN_COMPLETE.md)** - Integration overview
- **[docs/symbiote.md](docs/symbiote.md)** - Architecture details

---

**Quick Reference:**
- Start PWA: `./sage pwa`
- Stop all: `./sage stop`
- Check status: `./sage status`
- Plan feature: `./sage plan -i "feature"`
- Build code: `./sage build -i`

