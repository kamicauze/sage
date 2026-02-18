# Sage PWA - First Time Setup Guide

## 🚨 Two Issues to Fix Before Starting

### Issue 1: Node.js Version (Required)

**Problem:** Node.js 16.20.2 is installed, but Next.js 15 requires v18.18+ or v20+

**Quick Fix:**

```bash
./install_node20.sh
```

**Then reload your terminal:**
```bash
source ~/.bashrc
# OR close and reopen your terminal
```

**Verify:**
```bash
node --version  # Should show v20.x.x
```

**Reinstall dependencies:**
```bash
cd architect/ui
npm install
cd ../..
```

---

### Issue 2: Mosquitto Port Conflict (Required)

**Problem:** System Mosquitto service is blocking port 1883

**Quick Fix:**

```bash
./fix_mosquitto.sh
```

This stops the system Mosquitto service and frees up the ports.

---

## ✅ Complete Setup Workflow

### Step 1: Fix Node.js
```bash
./install_node20.sh
source ~/.bashrc
```

### Step 2: Fix Mosquitto
```bash
./fix_mosquitto.sh
```

### Step 3: Install Dependencies
```bash
cd architect/ui
npm install
cd ../..
```

### Step 4: Start Sage PWA
```bash
./sage pwa
```

---

## 🎯 Expected Output

When everything works, you'll see:

```
🌐 Starting Sage PWA Stack...
============================================================

1️⃣ Starting MQTT Broker...
   ✅ Mosquitto running (ports 1883 + 9001)

2️⃣ Starting Brain Core...
   ✅ Brain started (logs: /tmp/sage_brain.log)

3️⃣ Starting PWA UI...
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

Then visit: **http://localhost:3000/brain**

---

## 🐛 Troubleshooting

### Still Getting Node.js Error?

**Check version:**
```bash
node --version
```

**If still showing v16.x.x:**
```bash
# Reload nvm
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

# Use Node 20
nvm use 20

# Verify
node --version
```

**Make it permanent:**
```bash
echo 'export NVM_DIR="$HOME/.nvm"' >> ~/.bashrc
echo '[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"' >> ~/.bashrc
source ~/.bashrc
```

### Still Getting Mosquitto Error?

**Check if port is in use:**
```bash
sudo netstat -tulnp | grep 1883
```

**If you see mosquitto:**
```bash
sudo pkill mosquitto
sudo systemctl stop mosquitto
sudo systemctl disable mosquitto
```

**Try again:**
```bash
./sage pwa
```

### Next.js Won't Start?

**Check Node.js version first:**
```bash
node --version  # Must be 18+ or 20+
```

**Clean install:**
```bash
cd architect/ui
rm -rf node_modules package-lock.json
npm install
cd ../..
```

**Try manual start:**
```bash
cd architect/ui
npm run dev:network
```

Look for specific error messages.

---

## 📱 Mobile Access Setup (Optional)

Once everything is running locally, set up mobile access:

### For Local WiFi

**Update environment:**
```bash
cd architect/ui
nano .env.local
```

Change:
```env
NEXT_PUBLIC_MQTT_WS_URL=ws://YOUR_LOCAL_IP:9001
```

Get your IP:
```bash
hostname -I | awk '{print $1}'
```

**Restart:**
```bash
./sage stop
./sage pwa
```

**Access from phone:**
```
http://YOUR_LOCAL_IP:3000/brain
```

### For Tailscale

**Update environment:**
```bash
cd architect/ui
nano .env.local
```

Change:
```env
NEXT_PUBLIC_MQTT_WS_URL=ws://100.80.204.94:9001
```

**Restart and access:**
```bash
./sage stop
./sage pwa

# On phone: http://100.80.204.94:3000/brain
```

---

## 📖 Quick Command Reference

```bash
# One-time setup
./install_node20.sh      # Install Node.js 20
./fix_mosquitto.sh       # Fix port conflict

# Daily use
./sage pwa               # Start everything
./sage stop              # Stop everything

# Troubleshooting
./sage status            # Check system status
tail -f /tmp/sage_brain.log  # View brain logs
mosquitto_sub -h localhost -t "sage/#" -v  # Monitor MQTT

# Development
cd architect/ui && npm run dev:network  # Start UI only
mosquitto -c mosquitto.conf -v  # Start MQTT only
python brain/main.py  # Start brain only
```

---

## 🎓 What Each Component Does

### MQTT Broker (Mosquitto)
- **Port 1883:** MQTT protocol (Python brain connects here)
- **Port 9001:** WebSocket protocol (Browser PWA connects here)
- **Purpose:** Real-time messaging between brain and UI

### Brain Core (Python)
- **Purpose:** AI processing, pattern recognition, conversation
- **Logs:** `/tmp/sage_brain.log`
- **MQTT:** Publishes status, listens for commands

### PWA UI (Next.js)
- **Port 3000:** Web interface
- **Purpose:** Monitor brain, control STT/TTS, chat interface
- **MQTT:** Connects via WebSocket for real-time updates

---

## ✨ Summary

**Before using Sage PWA for the first time:**

1. ✅ Install Node.js 20: `./install_node20.sh`
2. ✅ Fix Mosquitto: `./fix_mosquitto.sh`
3. ✅ Install dependencies: `cd architect/ui && npm install`
4. ✅ Start Sage: `./sage pwa`
5. ✅ Visit: http://localhost:3000/brain

**After initial setup:**

Just run `./sage pwa` every time!

---

**Need help?** Check these guides:
- **[MOSQUITTO_FIX.md](MOSQUITTO_FIX.md)** - Mosquitto troubleshooting
- **[CLI_COMMANDS.md](CLI_COMMANDS.md)** - All commands
- **[SAGE_PWA_SETUP.md](SAGE_PWA_SETUP.md)** - Mobile access setup
