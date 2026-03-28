#!/usr/bin/env bash

BASE="http://10.250.30.121:8000/api/v1"
AUDIO_DIR="/Users/kamal/Downloads"

# Reset state
curl -s -X POST "$BASE/scenario/stop" | tr -d '\n'; echo

echo "=== SoundSense Demo Starting ==="

# Step 1: Baby crying
curl -s -X POST "$BASE/audio/classify" -F "file=@$AUDIO_DIR/baby-crying-high-pitch.mp3" | tr -d '\n'; echo
echo "Step 1: Baby crying sent → watch UI go CRITICAL (purple)"
sleep 5

# Step 2: Alarm 1/3
curl -s -X POST "$BASE/audio/classify" -F "file=@$AUDIO_DIR/smoke-alarm.mp3" | tr -d '\n'; echo
echo "Step 2: Alarm 1/3 sent"
sleep 3

# Step 3: Alarm 2/3
curl -s -X POST "$BASE/audio/classify" -F "file=@$AUDIO_DIR/smoke-alarm.mp3" | tr -d '\n'; echo
echo "Step 3: Alarm 2/3 sent"
sleep 3

# Step 4: Alarm 3/3
curl -s -X POST "$BASE/audio/classify" -F "file=@$AUDIO_DIR/smoke-alarm.mp3" | tr -d '\n'; echo
echo "Step 4: Alarm 3/3 sent → watch UI escalate to HIGH (red)"

echo "=== Demo Complete ==="
