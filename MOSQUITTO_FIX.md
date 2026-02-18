# Mosquitto Port Conflict Fix

## Problem

When running `./sage pwa`, you see:

```
❌ Mosquitto failed to start!
💡 Try: mosquitto -c mosquitto.conf -v
```

**Cause:** Ubuntu's system Mosquitto service is already running on port 1883, conflicting with Sage's custom configuration.

---

## Quick Fix

### Option 1: Automated Fix (Recommended)

```bash
./fix_mosquitto.sh
```

This script will:
1. Stop the system Mosquitto service
2. Disable it from auto-starting
3. Verify ports are free
4. Guide you to start Sage

### Option 2: Manual Fix

**Step 1: Stop system Mosquitto**
```bash
sudo systemctl stop mosquitto
sudo systemctl disable mosquitto
```

**Step 2: Verify ports are free**
```bash
netstat -tuln | grep -E "(1883|9001)"
# Should return nothing
```

**Step 3: Start Sage**
```bash
./sage pwa
```

---

## Verify the Fix

After running the fix, test Mosquitto manually:

```bash
mosquitto -c mosquitto.conf -v
```

**Expected output:**
```
1768324165: mosquitto version 2.0.18 starting
1768324165: Config loaded from mosquitto.conf.
1768324165: Opening ipv4 listen socket on port 1883.
1768324165: Opening ipv4 listen socket on port 9001.  ← WebSocket
```

Press Ctrl+C to stop, then run:
```bash
./sage pwa
```

---

## Why This Happens

Ubuntu installs Mosquitto as a system service that auto-starts with:
- Default config: `/etc/mosquitto/mosquitto.conf`
- Default port: 1883 (MQTT only, no WebSocket)

Sage needs:
- Custom config: `mosquitto.conf` (in Sage directory)
- Ports: 1883 (MQTT) + 9001 (WebSocket for PWA)

The system service blocks Sage's custom config from binding to port 1883.

---

## Alternative: Use Different Ports

If you want to keep the system Mosquitto running, edit Sage's config:

**Edit `mosquitto.conf`:**
```conf
# MQTT TCP listener (for Python brain)
listener 11883
protocol mqtt
allow_anonymous true

# WebSocket listener (for browser-based PWA)
listener 19001
protocol websockets
allow_anonymous true

persistence false
```

**Update brain to use new port:**
Edit `.env` or wherever `MQTT_PORT` is set:
```env
MQTT_PORT=11883
```

**Update PWA to use new WebSocket port:**
Edit `architect/ui/.env.local`:
```env
NEXT_PUBLIC_MQTT_WS_URL=ws://localhost:19001
```

**Note:** This is more complex. We recommend stopping the system Mosquitto.

---

## Permanent Solution

To prevent the system Mosquitto from starting on boot:

```bash
sudo systemctl disable mosquitto
sudo systemctl mask mosquitto
```

This ensures Sage's custom Mosquitto always starts correctly.

---

## Troubleshooting

### Still getting "Address already in use"?

**Check what's using port 1883:**
```bash
sudo netstat -tulnp | grep 1883
```

**Kill the process:**
```bash
# If it shows mosquitto with PID (e.g., 12345)
sudo kill 12345

# Or kill all mosquitto processes
sudo pkill mosquitto
```

### Can't start Mosquitto at all?

**Check if it's installed:**
```bash
which mosquitto
mosquitto -h
```

**Install if missing:**
```bash
sudo apt update
sudo apt install mosquitto
```

**Check config syntax:**
```bash
mosquitto -c mosquitto.conf -t
```

### WebSocket port (9001) blocked?

**Check firewall:**
```bash
sudo ufw status
sudo ufw allow 9001/tcp
sudo ufw reload
```

---

## After Fixing

Once Mosquitto starts successfully, you'll see:

```
🌐 Starting Sage PWA Stack...
============================================================

1️⃣ Starting MQTT Broker...
   ✅ Mosquitto running (ports 1883 + 9001)

2️⃣ Starting Brain Core...
   ✅ Brain started (logs: /tmp/sage_brain.log)

3️⃣ Starting PWA UI...
   ✅ Next.js running (port 3000)

============================================================
🎉 Sage PWA is READY!
============================================================
```

Visit: http://localhost:3000/brain

---

**Quick Commands:**

```bash
# Fix the port conflict
./fix_mosquitto.sh

# Start Sage
./sage pwa

# If issues persist, check logs
mosquitto -c mosquitto.conf -v
```
