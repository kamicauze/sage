#!/bin/bash

# Phase 3 Memory-Driven Personality Test Suite
# Tests that personality preferences are learned and persisted

echo "=========================================="
echo "  Phase 3: Memory-Driven Personality Test"
echo "=========================================="
echo ""

# Check if brain is running
BRAIN_PID=$(pgrep -f 'python.*brain/main.py')
if [ -z "$BRAIN_PID" ]; then
    echo "ERROR: Sage Brain is not running"
    echo "Start it with:"
    echo "  export DEFAULT_PERSONALITY=kenyan_babe"
    echo "  export SAGE_DISABLE_QUIET_HOURS=true"
    echo "  ./sage brain"
    exit 1
fi

echo "Brain PID: $BRAIN_PID"
echo ""

# Function to send test and wait for response
send_test() {
    local test_name=$1
    local message=$2
    local wait_time=${3:-6}

    echo "--- Test: $test_name ---"
    echo "Input: \"$message\""

    # Subscribe to responses
    timeout $((wait_time + 2)) mosquitto_sub -t "sage/voice/response" > /tmp/sage_phase3_resp.txt 2>&1 &
    SUBPID=$!
    sleep 0.5

    # Send message
    mosquitto_pub -t "sage/voice/transcript" -m "$message"
    echo "Waiting ${wait_time}s for response..."

    # Wait for response
    sleep $wait_time
    kill $SUBPID 2>/dev/null
    wait $SUBPID 2>/dev/null

    # Check response
    if [ -s /tmp/sage_phase3_resp.txt ]; then
        RESPONSE=$(cat /tmp/sage_phase3_resp.txt | jq -r '.text' 2>/dev/null || cat /tmp/sage_phase3_resp.txt)
        echo "Response: $RESPONSE"
    else
        echo "No response received"
    fi
    rm -f /tmp/sage_phase3_resp.txt
    echo ""
}

echo "=========================================="
echo "  Test 1: Establish Sheng Preference"
echo "=========================================="
echo "Sending multiple Sheng messages to train the model..."
echo ""

send_test "Sheng Greeting 1" "niaje fam, uko fiti?" 5
sleep 2
send_test "Sheng Follow-up" "poa sana, manze leo niko busy" 5
sleep 2
send_test "Sheng Emotional" "manze niko stressed, kazi ni mob" 5

echo "=========================================="
echo "  Test 2: Positive Feedback Signal"
echo "=========================================="
echo "Sending positive feedback to reinforce preferences..."
echo ""

send_test "Positive Feedback" "asante sana, you get me" 5
sleep 2

echo "=========================================="
echo "  Test 3: Tender Mode Training"
echo "=========================================="
echo "Testing emotional scenarios to train tender mode..."
echo ""

send_test "Sad Message" "am feeling really down today" 5
sleep 2
send_test "Follow-up" "thanks for listening" 5

echo "=========================================="
echo "  Test 4: Direct Mode Training"
echo "=========================================="
echo ""

send_test "Direct Request" "just tell me straight up, should I quit my job?" 6

echo "=========================================="
echo "  Test 5: Memory Persistence Check"
echo "=========================================="
echo ""
echo "To verify memory persistence:"
echo "1. Stop the brain (Ctrl+C in brain terminal)"
echo "2. Check for '[Brain] Personality preferences saved' message"
echo "3. Restart the brain"
echo "4. Check for '[PersonalityEngine] Loaded preferences from memory'"
echo "5. Send a message and see if preferences are applied"
echo ""

echo "=========================================="
echo "  Brain Log Indicators to Watch For"
echo "=========================================="
echo ""
echo "[PersonalityEngine] Loaded preferences from memory"
echo "[PersonalityEngine] Learning from interaction: signal=..."
echo "[Personality] emotion=..., cultural=full, depth=..."
echo ""

echo "=========================================="
echo "  Test Complete"
echo "=========================================="
echo ""
echo "Phase 3 Features Being Tested:"
echo "  - Sheng level preference learning"
echo "  - Positive/negative feedback detection"
echo "  - Tender mode training"
echo "  - Direct mode training"
echo "  - Preference persistence on shutdown"
echo ""
echo "Next Steps:"
echo "  1. Watch brain logs for learning signals"
echo "  2. Stop and restart brain to test persistence"
echo "  3. Verify preferences are loaded on restart"
echo ""
