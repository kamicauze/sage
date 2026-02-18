#!/bin/bash
# Script to simulate a presence message
# Usage: ./test-presence.sh [room] [motion]
# Example: ./test-presence.sh livingroom true

ROOM=${1:-livingroom}
MOTION=${2:-true}
TS=$(date +%s)

echo "Publishing presence message:"
echo "  Topic: sage/sensors/$ROOM/presence"
echo "  Payload: {\"motion\": $MOTION, \"ts\": $TS}"

# Use docker exec to run mosquitto_pub from the MQTT container
docker exec infra-mqtt-1 mosquitto_pub -h localhost -p 1883 -t "sage/sensors/$ROOM/presence" -m "{\"motion\": $MOTION, \"ts\": $TS}"

