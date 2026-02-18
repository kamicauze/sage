# Personality Switching in Sage PWA

## ✅ Feature Added: Personality Selection UI

You can now switch Sage's personality directly from the Brain UI!

## 🎭 Available Personalities

### 1. **HomeBuddy** (kenyan_babe)
- **Vibe:** Nairobi Gen Z home companion
- **Style:** Calm, grounded, minimal
- **Language:** Sheng + English code-switching
- **Best for:** Daily home automation, casual conversations
- **Emoji:** 🏠

### 2. **Sage** (sage)
- **Vibe:** Afro-Caribbean Gen Z therapist
- **Style:** Soulful, spicy, emotionally fluent, unfiltered
- **Language:** Caribbean energy with Gen Z slang
- **Best for:** Emotional support, life advice, deep talks
- **Emoji:** 🌺

### 3. **Martin** (martin)
- **Vibe:** Systems thinker and builder
- **Style:** Technical, strategic, focused
- **Language:** Professional, analytical
- **Best for:** Technical discussions, system design, planning
- **Emoji:** 🛠️

---

## 🚀 How to Use

### Access Settings

**Via Browser:**
1. Visit: http://localhost:3000/brain/settings
2. Or: Click "Settings" in the Brain sidebar

**Via Mobile:**
- Open Sage PWA
- Tap "Brain" tab
- Tap "Settings"

### Change Personality

1. **Select personality** by clicking on one of the three cards
2. **Adjust voice settings** (optional):
   - Choose voice (Bella, Sarah, Emma, Michael, Adam)
   - Adjust speech speed (0.5x - 1.5x)
3. **Adjust detection** (optional):
   - Pause detection duration (0.3s - 2.0s)
4. **Click "Save Changes"**

Changes take effect on the next response!

---

## 🎛️ Settings Available

### Personality
- **HomeBuddy** - Kenyan, Sheng, Chill, Home Assistant
- **Sage** - Therapist, Caribbean, Healing, Unfiltered
- **Martin** - Builder, Systems, Technical, Strategic

### Voice
- **af_bella** - Female, Warm
- **af_sarah** - Female, Clear
- **bf_emma** - Female, British
- **am_michael** - Male, Deep
- **am_adam** - Male, Friendly

### Speech Speed
- Range: 0.5x (slower) to 1.5x (faster)
- Default: 1.0x (normal)

### Pause Detection
- Range: 0.3s to 2.0s
- Default: 0.7s
- Controls how long to wait after you stop talking

---

## 📡 How It Works

### Frontend (PWA)
```typescript
// User selects personality
updateConfig({ personality: 'sage' })

// Published to MQTT
topic: sage/brain/config
payload: { personality: 'sage' }
```

### Backend (Brain)
The Python brain listens for `sage/brain/config` messages and updates the active personality prompt.

**Expected behavior:**
- Next conversation uses new personality
- Voice remains consistent
- All settings persist

---

## 🔧 Implementation Details

### Files Created
- [`architect/ui/src/app/brain/settings/page.tsx`](architect/ui/src/app/brain/settings/page.tsx) - Settings page UI

### Files Modified
- [`architect/ui/src/components/Sidebar.tsx`](architect/ui/src/components/Sidebar.tsx) - Added Settings link
- [`architect/ui/src/contexts/BrainContext.tsx`](architect/ui/src/contexts/BrainContext.tsx) - Already has `updateConfig()` method

### MQTT Topics Used
- **`sage/brain/config`** - Personality changes
- **`sage/voice/config`** - Voice and speed changes
- **`sage/config/performance`** - Detection settings

---

## 🎯 Testing

### Test Personality Switch

1. **Start Sage:**
   ```bash
   ./sage pwa
   ```

2. **Open Settings:**
   ```
   http://localhost:3000/brain/settings
   ```

3. **Switch to Sage personality:**
   - Click on "Sage" card
   - Click "Save Changes"

4. **Test in Live Chat:**
   - Go to "Live Activity"
   - Send: "How are you?"
   - Response should be in Sage's Caribbean therapist style

5. **Switch to Martin:**
   - Go back to Settings
   - Click on "Martin" card
   - Click "Save Changes"

6. **Test again:**
   - Send same message
   - Response should be more technical/analytical

---

## 🐛 Troubleshooting

### Changes Not Taking Effect

**Issue:** Personality stays the same after saving

**Check:**
1. **MQTT connected?** - Green indicator on Brain Monitor
2. **Brain running?** - Check `/tmp/sage_brain.log`
3. **MQTT messages sent?**
   ```bash
   mosquitto_sub -h localhost -t "sage/#" -v
   ```
   Change personality and you should see:
   ```
   sage/brain/config {"personality":"sage"}
   ```

### "Not Connected to MQTT" Warning

**Fix:** Make sure MQTT broker is running:
```bash
ps aux | grep mosquitto
netstat -tuln | grep 9001
```

Restart if needed:
```bash
./sage stop
./sage pwa
```

---

## 📱 Mobile Experience

The Settings page is fully responsive:
- Touch-friendly personality cards
- Large sliders for voice/speed
- Fixed save button at bottom
- Works in portrait and landscape

**Install as PWA for best experience:**
- iOS: Safari → Share → Add to Home Screen
- Android: Chrome → Menu → Add to Home Screen

---

## 🔮 Future Enhancements

Potential additions:
- [ ] Custom personality creation
- [ ] Personality previews (sample responses)
- [ ] Time-based personality switching
- [ ] Context-aware personality selection
- [ ] Voice samples for each personality
- [ ] Personality presets import/export

---

## ✨ Summary

You now have:
- ✅ 3 distinct personalities to choose from
- ✅ Voice customization (5 voices, speed control)
- ✅ Detection settings
- ✅ Real-time switching via UI
- ✅ Mobile-friendly interface
- ✅ MQTT-based configuration

**Try it now:**
```bash
./sage pwa
# Visit: http://localhost:3000/brain/settings
```

Choose your personality and start chatting! 🎭
