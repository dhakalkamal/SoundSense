"""Quick smoke-test for YAMNetClassifier — hint fallback and optional real audio."""

import os
import sys

sys.path.insert(0, ".")

from app.inference.yamnet_classifier import YAMNetClassifier

print("Loading YAMNet...")
clf = YAMNetClassifier()
print("YAMNet loaded.")

# Test with hint fallback
event = clf.classify(hint="door_knock", confidence=0.91)
print(f"Hint fallback: {event.label} @ {event.confidence:.2f}")

# Test with real audio if provided
audio_path = sys.argv[1] if len(sys.argv) > 1 else None
if audio_path and os.path.exists(audio_path):
    print(f"Testing: {audio_path}")
    event = clf.classify(audio_path=audio_path)
    print(f"YAMNet classified: {event.label} @ {event.confidence:.2f}")
else:
    print("No audio file provided. Pass path as argument to test real audio.")
    print("Example: python scripts/test_yamnet.py ~/Downloads/knockdoor.mp3")
