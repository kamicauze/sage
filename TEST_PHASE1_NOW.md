# Testing Phase 1 Personality Improvements - Quick Start

## ⚠️ IMPORTANT: Current Issue Found

Your Sage Brain is currently running with:
- **Personality:** `sage` (Afro-Caribbean) instead of `kenyan_babe` (Nairobi)
- **Quiet Hours:** ACTIVE (it's 04:36 AM, quiet hours are 23:00-07:00)

This is why you're getting generic responses instead of Sheng-rich Kenyan responses!

---

## Quick Fix: Restart with Kenyan Babe Personality

### Option 1: Restart Brain Now (Recommended)

In the terminal where `./sage brain` is running:
1. Press `Ctrl+C` to stop the brain
2. Run these commands:
```bash
export DEFAULT_PERSONALITY=kenyan_babe
export SAGE_DISABLE_QUIET_HOURS=true
export SAGE_INCLUDE_EXAMPLES=true
./sage brain
```

### Option 2: Wait Until 7:00 AM
After 7 AM, quiet hours will end and responses will show (but still with "sage" personality, not kenyan_babe)

---

## Testing After Restart

### 1. Start Response Monitor (Terminal 1)
```bash
mosquitto_sub -t "sage/voice/response" -v
```

### 2. Send Test Messages (Terminal 2)

#### Test 1: Emotional (Tender Tone)
```bash
mosquitto_pub -t "sage/voice/transcript" -m "am sad"
```
**Expected:** Sheng-infused empathy like:
> "Aii, babes. Pole sana. Sometimes we just need to sit with what we're feeling, si ndio? You don't have to be okay right now. What's weighing on you?"

**Look for:**
- ✅ "pole sana" (Kenyan sympathy)
- ✅ "si ndio?" (Sheng tag question)
- ✅ "babes" (Kenyan endearment)
- ✅ Emojis: ❤️, ✨

---

#### Test 2: Casual Sheng Smalltalk
```bash
mosquitto_pub -t "sage/voice/transcript" -m "niaje bro"
```
**Expected:** Natural Sheng response:
> "Niaje? Just vibing here, watching things flow. Uko fiti? Anything I can help with?"

**Look for:**
- ✅ "Uko fiti" (How are you/are you good)
- ✅ Natural code-switching
- ✅ Casual energy

---

#### Test 3: Complex Emotional Scenario
```bash
mosquitto_pub -t "sage/voice/transcript" -m "life sucks and am turning 30 tomorrow with no plans"
```
**Expected:** Deep empathy with cultural warmth:
> "Babes, 30 isn't the enemy—life just threw you some heavy punches getting there. But listen, you made it. You survived all that, na bado uko hapa. That's something. Even if you don't feel like celebrating, do something small for yourself tomorrow. Order your favorite food, watch something that makes you smile, ama just rest. You've earned it. Happy early 30th, babe. ❤️✨"

**Look for:**
- ✅ "na bado uko hapa" (and you're still here)
- ✅ "ama just rest" (or just rest)
- ✅ Acknowledgment of struggle
- ✅ Practical, grounded advice
- ✅ Emojis: ❤️✨

---

#### Test 4: Grief Disclosure
```bash
mosquitto_pub -t "sage/voice/transcript" -m "my sister died last year and my ex is asking for lunch money after cheating"
```
**Expected:** Tender but real response:
> "Mdogo... That's a lot. Losing your sister like that—pole sana, seriously. And now this clown wants lunch money after cheating? Block him. You don't owe him anything, especially not while you're still carrying all that pain. Focus on healing, not on people who disrespected you. You deserve peace. ❤️"

**Look for:**
- ✅ "Mdogo" (little one - endearment)
- ✅ "pole sana, seriously" (deep sympathy)
- ✅ Direct advice (block him)
- ✅ Validates pain while being real

---

#### Test 5: Overwhelmed
```bash
mosquitto_pub -t "sage/voice/transcript" -m "feeling overwhelmed with work and life"
```
**Expected:** Grounded support:
> "Mahn, I feel you. When everything hits at once, it's like you can't breathe, si ndio? But you don't have to solve it all today. Pick one thing—just one—and focus on that. The rest can wait. What's the most urgent thing stressing you right now?"

**Look for:**
- ✅ "Mahn" (exclamation)
- ✅ "si ndio?" (isn't it?)
- ✅ Breaking down the problem
- ✅ Asking clarifying question

---

## What to Monitor in Brain Logs

Watch the terminal where `./sage brain` is running for these indicators:

### Before Phase 1 (Old Behavior):
```
[AI] Mode selected: quiet, tone=casual, core_variant=light
[Router] Suggestion filtered: confidence 0.55 < 0.65
[Voice] Suppressed response; skipping publish
```

### After Phase 1 (New Behavior):
```
[AI] Mode selected: supportive, tone=tender, core_variant=light, minimal_prompt=False
[AI] Input size: core=150w, mode=66w, system_sent=250w, context=12w
[Router] Suggestion received: text="Aii, babes. Pole sana...", confidence=0.75
[Router] Personality markers detected: True
[Router] min_confidence: 0.40 (has personality markers)
[Router] (gemma3:12b) suggestion: ... (conf=0.75)
[Voice] Response published in 3500ms: Aii, babes. Pole sana...
```

**Key indicators Phase 1 is working:**
1. ✅ Mode = "supportive" (not "quiet")
2. ✅ system_sent > 200 words (examples included)
3. ✅ Confidence threshold = 0.40 or 0.45 (not 0.65)
4. ✅ "Personality markers detected" appears
5. ✅ Responses not suppressed
6. ✅ Sheng phrases in output

---

## Phase 1 Success Metrics

### Response Quality:
- **Sheng density:** 2-4 phrases per response
- **Emojis:** 1-2 per emotional response
- **Cultural authenticity:** Natural code-switching
- **Emotional depth:** Validates + offers grounded support

### Technical Metrics:
| Metric | Before | Target After |
|--------|--------|--------------|
| Suppression rate | 35% | < 15% |
| Avg response length | 45 tokens | 75+ tokens |
| Sheng phrases per 100 words | 0.5 | 3-5 |
| Min confidence threshold | 0.65 | 0.40-0.45 |

---

## Troubleshooting

### Issue: Still getting generic responses

**Check 1: Is personality correct?**
```bash
ps eww $(pgrep -f 'python.*brain/main.py') | tr ' ' '\n' | grep DEFAULT_PERSONALITY
```
Should show: `DEFAULT_PERSONALITY=kenyan_babe`

**Check 2: Are examples enabled?**
Look for this in brain logs when processing:
```
[AI] Input size: core=XXXw, mode=66w, system_sent=250w+
```
If `system_sent` < 150w, examples aren't loading.

**Check 3: Are responses being suppressed?**
Look for:
```
[Router] Suggestion filtered: confidence X < Y
```
If Y = 0.65, Phase 1 changes didn't take effect (old code running).

---

### Issue: No responses at all

**Check 1: Quiet hours active?**
```bash
date +%H
```
If hour is 23-06, you're in quiet hours. Either:
- Set `SAGE_DISABLE_QUIET_HOURS=true` before starting
- Wait until 7:00 AM
- Send message with critical flag (not implemented yet)

**Check 2: MQTT broker running?**
```bash
systemctl status mosquitto
```

**Check 3: Brain subscribed to topics?**
Look for this in brain startup logs:
```
[MQTT] Subscribed to: sage/sensors/+/presence, sage/voice/transcript, sage/brain/config
```

---

## Quick Validation Commands

### Check Current Settings:
```bash
echo "Brain PID: $(pgrep -f 'python.*brain/main.py')"
echo "Personality: $(ps eww $(pgrep -f 'python.*brain/main.py') | tr ' ' '\n' | grep DEFAULT_PERSONALITY | cut -d= -f2)"
echo "Current Hour: $(date +%H) (Quiet hours: 23-06)"
```

### Force Restart with Correct Config:
```bash
# Stop brain
pkill -f 'python.*brain/main.py'

# In the terminal where you want to run brain:
cd /home/kamicauze/sage
export DEFAULT_PERSONALITY=kenyan_babe
export SAGE_DISABLE_QUIET_HOURS=true
export SAGE_INCLUDE_EXAMPLES=true
./sage brain
```

---

## Expected Timeline

- **Restart brain:** 30 seconds
- **Test 5 scenarios:** 3 minutes
- **Validate improvements:** 5 minutes
- **Total testing time:** < 10 minutes

---

## Next Steps After Phase 1

If Phase 1 delivers 60%+ improvement:
1. ✅ Document results
2. ✅ Collect sample responses
3. ✅ Measure metrics (suppression rate, Sheng density)
4. → Proceed to **Phase 2: Deep Personality System**

If Phase 1 needs tuning:
1. Adjust confidence thresholds (currently 0.40/0.45)
2. Add more personality markers to detection
3. Increase token predictions further
4. Add more examples for edge cases

---

## Contact

Issues? Check:
- [PHASE1_PERSONALITY_IMPROVEMENTS.md](PHASE1_PERSONALITY_IMPROVEMENTS.md) - Full implementation details
- Brain logs in terminal where `./sage brain` is running
- MQTT traffic: `mosquitto_sub -t "sage/#" -v`

**Status: READY TO TEST** 🚀

Restart with `DEFAULT_PERSONALITY=kenyan_babe` and test!
