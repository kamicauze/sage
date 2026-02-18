#!/bin/bash

# Phase 1 Personality Test Suite
# Run after restarting brain with DEFAULT_PERSONALITY=kenyan_babe

echo "╔════════════════════════════════════════════════════════════╗"
echo "║       Phase 1 Personality Test Suite                      ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Check if brain is running
BRAIN_PID=$(pgrep -f 'python.*brain/main.py')
if [ -z "$BRAIN_PID" ]; then
    echo "❌ ERROR: Sage Brain is not running"
    echo "   Start it with:"
    echo "   export DEFAULT_PERSONALITY=kenyan_babe"
    echo "   export SAGE_DISABLE_QUIET_HOURS=true"
    echo "   ./sage brain"
    exit 1
fi

# Check personality setting
PERSONALITY=$(ps eww $BRAIN_PID | tr ' ' '\n' | grep DEFAULT_PERSONALITY | cut -d= -f2)
if [ -z "$PERSONALITY" ]; then
    PERSONALITY="sage (default)"
fi

echo "📊 Current Configuration:"
echo "   Brain PID: $BRAIN_PID"
echo "   Personality: $PERSONALITY"
echo "   Current Time: $(date '+%H:%M')"
echo ""

if [ "$PERSONALITY" != "kenyan_babe" ]; then
    echo "⚠️  WARNING: Personality is '$PERSONALITY', not 'kenyan_babe'"
    echo "   You may not see Sheng responses!"
    echo "   Restart brain with: DEFAULT_PERSONALITY=kenyan_babe"
    echo ""
fi

# Check quiet hours
HOUR=$(date +%H)
if [ $HOUR -ge 23 ] || [ $HOUR -lt 7 ]; then
    echo "⚠️  WARNING: Quiet hours active (23:00-07:00)"
    echo "   Responses may be suppressed"
    echo "   Set SAGE_DISABLE_QUIET_HOURS=true to test"
    echo ""
fi

# Function to send test and wait for response
run_test() {
    local test_num=$1
    local test_name=$2
    local message=$3
    local expected=$4

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🧪 Test $test_num: $test_name"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📝 Input: \"$message\""
    echo ""

    # Subscribe to responses
    timeout 8 mosquitto_sub -t "sage/voice/response" > /tmp/sage_test_resp_$test_num.txt 2>&1 &
    SUBPID=$!
    sleep 0.5

    # Send message
    mosquitto_pub -t "sage/voice/transcript" -m "$message"
    echo "⏳ Waiting for response..."

    # Wait for response
    sleep 6
    kill $SUBPID 2>/dev/null
    wait $SUBPID 2>/dev/null

    # Check response
    if [ -s /tmp/sage_test_resp_$test_num.txt ]; then
        RESPONSE=$(cat /tmp/sage_test_resp_$test_num.txt | jq -r '.text' 2>/dev/null || cat /tmp/sage_test_resp_$test_num.txt)
        echo "✅ Response received:"
        echo ""
        echo "$RESPONSE" | fold -s -w 70 | sed 's/^/   /'
        echo ""
        echo "🔍 Looking for: $expected"

        # Check for personality markers
        MARKERS_FOUND=""
        for marker in "pole sana" "manze" "babes" "si ndio" "uko fiti" "tutapanga" "aii" "mahn" "❤️" "✨"; do
            if echo "$RESPONSE" | grep -qi "$marker"; then
                MARKERS_FOUND="$MARKERS_FOUND $marker,"
            fi
        done

        if [ -n "$MARKERS_FOUND" ]; then
            echo "🎯 Personality markers found:${MARKERS_FOUND%,}"
        else
            echo "⚠️  No personality markers detected (generic response)"
        fi
    else
        echo "❌ No response received (suppressed or error)"
    fi

    rm -f /tmp/sage_test_resp_$test_num.txt
    echo ""
}

# Run tests
echo "Starting test sequence..."
echo ""

run_test 1 "Emotional (Tender)" \
    "am sad" \
    "pole sana, babes, emotional validation"

sleep 2

run_test 2 "Sheng Smalltalk" \
    "niaje bro" \
    "niaje, uko fiti, casual Sheng response"

sleep 2

run_test 3 "Complex Emotion" \
    "life sucks and turning 30 tomorrow" \
    "babes, empathy, na bado uko hapa, encouragement"

sleep 2

run_test 4 "Casual Check-in" \
    "niko fiti na wewe" \
    "niko poa, reciprocal Sheng"

sleep 2

run_test 5 "Overwhelmed" \
    "feeling overwhelmed with work" \
    "mahn, si ndio, grounded advice"

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Test sequence complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 Check brain logs for:"
echo "   - [AI] Mode selected: supportive"
echo "   - [Router] Personality markers detected"
echo "   - [Router] min_confidence: 0.40 or 0.45"
echo ""
echo "🎯 Phase 1 Success Indicators:"
echo "   ✓ Sheng phrases in responses"
echo "   ✓ Emojis in emotional contexts"
echo "   ✓ Lower suppression rate"
echo "   ✓ Richer, longer responses"
echo ""
echo "📖 See TEST_PHASE1_NOW.md for detailed analysis"
echo ""
