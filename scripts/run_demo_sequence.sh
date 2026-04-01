#!/usr/bin/env bash

#BASE="http://10.250.30.121:8000/api/v1"
BASE="http://10.0.0.102:8000/api/v1"
AUDIO_DIR="/Users/kamal/Downloads"

echo "=== SoundSense Demo Loop — Press Ctrl+C to stop ==="

LOOP=1
while true; do
  echo ""
  echo "--- Loop $LOOP ---"

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
  sleep 5

  # Step 5: Glass break
  curl -s -X POST "$BASE/audio/classify" -F "file=@$AUDIO_DIR/breaking_glass.mp3" | tr -d '\n'; echo
  echo "Step 5: Glass break sent → watch UI go CRITICAL (purple)"
  sleep 5

  # Step 6: Door knock
  curl -s -X POST "$BASE/audio/classify" -F "file=@$AUDIO_DIR/knockdoor.mp3" | tr -d '\n'; echo
  echo "Step 6: Door knock sent → watch UI show MEDIUM (amber)"

  echo "=== Demo Complete — restarting in 3s ==="
  sleep 3

  LOOP=$((LOOP + 1))
done
