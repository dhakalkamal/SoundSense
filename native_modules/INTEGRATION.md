# Audio Capture Native Module — Integration Guide

Five files to drop into your React Native project:

```
native_modules/
  ios/
    AudioCaptureModule.swift   → ios/<AppName>/
    AudioCaptureModule.m       → ios/<AppName>/
  android/
    AudioCaptureModule.kt      → android/app/src/main/java/<your/package>/
    AudioCapturePackage.kt     → android/app/src/main/java/<your/package>/
  src/
    AudioCaptureClient.ts      → src/  (or wherever your TS modules live)
```

---

## iOS Setup

### 1. Add files to Xcode

Open `ios/<AppName>.xcworkspace` in Xcode. Drag both `.swift` and `.m` files into
the `<AppName>` group (not `Pods`). When prompted, choose **"Create bridging header"**
if Xcode asks — accept it. If a bridging header already exists, nothing extra is needed.

### 2. Microphone permission

Add to `ios/<AppName>/Info.plist`:

```xml
<key>NSMicrophoneUsageDescription</key>
<string>SoundSense needs microphone access to detect sounds for you.</string>
```

### 3. Background audio (optional — skip for demo)

The module keeps capture running as long as the app is in the foreground. If you need
background capture, add `audio` to `UIBackgroundModes` in Info.plist. This is out of
scope for the current demo.

---

## Android Setup

### 1. Replace the package name

Open `AudioCaptureModule.kt` and `AudioCapturePackage.kt`. Replace:

```kotlin
package com.soundsense.app
```

with your actual application package (e.g., `com.yourcompany.soundsense`).

### 2. Register the package

In `android/app/src/main/java/<your/package>/MainApplication.kt` (or `.java`),
add `AudioCapturePackage()` to the packages list:

```kotlin
// MainApplication.kt
override fun getPackages(): List<ReactPackage> =
    PackageList(this).packages.apply {
        add(AudioCapturePackage())   // ← add this line
    }
```

### 3. Microphone permission

Add to `android/app/src/main/AndroidManifest.xml` (inside `<manifest>`):

```xml
<uses-permission android:name="android.permission.RECORD_AUDIO" />
```

Then request the permission at runtime before calling `startCapture()`. The module
does NOT request it internally on Android:

```typescript
import { PermissionsAndroid, Platform } from 'react-native';

async function requestMicPermission(): Promise<boolean> {
  if (Platform.OS !== 'android') return true;
  const result = await PermissionsAndroid.request(
    PermissionsAndroid.PERMISSIONS.RECORD_AUDIO,
    {
      title: 'Microphone Permission',
      message: 'SoundSense needs mic access to detect sounds.',
      buttonPositive: 'Allow',
    },
  );
  return result === PermissionsAndroid.RESULTS.GRANTED;
}
```

---

## Usage from a React Component

```typescript
import React, { useEffect, useState } from 'react';
import { Button, Platform, Text, View } from 'react-native';
import { PermissionsAndroid } from 'react-native';
import audioCaptureClient, { ConnectionState, DetectionPayload } from './AudioCaptureClient';

const WS_URL = 'ws://192.168.1.100:8000/ws/audio';  // ← your server's LAN IP

export default function SoundSenseScreen() {
  const [connState, setConnState] = useState<ConnectionState>('idle');
  const [lastDetection, setLastDetection] = useState<DetectionPayload | null>(null);

  useEffect(() => {
    audioCaptureClient.on({
      onConnectionState: setConnState,
      onDetection: setLastDetection,
      onError: (msg) => console.warn('[AudioCapture]', msg),
    });
    return () => audioCaptureClient.stopCapture();
  }, []);

  const handleStart = async () => {
    if (Platform.OS === 'android') {
      const granted = await PermissionsAndroid.request(
        PermissionsAndroid.PERMISSIONS.RECORD_AUDIO,
      );
      if (granted !== PermissionsAndroid.RESULTS.GRANTED) return;
    }
    audioCaptureClient.startCapture(WS_URL);
  };

  const handleStop = () => audioCaptureClient.stopCapture();

  return (
    <View style={{ flex: 1, padding: 24 }}>
      <Text>Connection: {connState}</Text>
      {lastDetection && (
        <>
          <Text>Sound: {lastDetection.event.label} ({lastDetection.event.confidence.toFixed(2)})</Text>
          <Text>Flag: {lastDetection.situation.flag}</Text>
          <Text>Urgency: {lastDetection.situation.urgency}</Text>
          <Text>{lastDetection.situation.explanation}</Text>
        </>
      )}
      <Button title="Start" onPress={handleStart} disabled={connState === 'connected'} />
      <Button title="Stop"  onPress={handleStop}  disabled={connState === 'idle' || connState === 'stopped'} />
    </View>
  );
}
```

**Replace `WS_URL`** with your server's LAN IP address (not `localhost` — the phone
is a separate device). Find it with `ifconfig | grep "inet "` on macOS.

---

## Simulator Caveat

**Real device testing is required to validate the capture path fix.**

iOS Simulator and Android Emulator do not have a physical microphone. More importantly:

- **iOS Simulator**: `AVAudioSession.setCategory(.record, mode: .measurement)` is
  silently accepted but may not actually route audio through the measurement path.
  The sim mic input is a routed audio source, not a real hardware device. You will
  get audio data (from your Mac's mic via the sim), but you cannot confirm that
  AGC and noise suppression are actually disabled.

- **Android Emulator**: `AudioSource.UNPROCESSED` is not supported in the emulator.
  The emulator falls back to a processed source regardless of what you request.
  `NoiseSuppressor.isAvailable()` returns false in the emulator, so the disable
  calls are no-ops.

**Until you test on a real device, you cannot confirm the capture-path fix works.**
The smoke alarm test (`test_audio/smoke-alarm.mp3` played through a physical speaker
near the phone) is the validation step.

---

## Troubleshooting

### "WebSocket connects but no audio arrives"

This is almost always a permission issue. Check:

1. **iOS**: Did you add `NSMicrophoneUsageDescription` to Info.plist? On first launch,
   the OS shows a permission dialog. If the user previously denied it, they must go to
   Settings → Privacy → Microphone to re-enable.

2. **Android**: Is `RECORD_AUDIO` granted at runtime? The module does not request it
   internally. Check `PermissionsAndroid.check(PermissionsAndroid.PERMISSIONS.RECORD_AUDIO)`.

3. **AudioCaptureState event**: Add a temporary `console.log` listener for
   `AudioCaptureState`. If you see `state: "started"`, the native module is running.
   If you never see it, the issue is in the native setup (Xcode/Gradle configuration).

### "I see AudioFrame events but the server returns no detections"

1. The 2-of-3 temporal smoother requires 3 consecutive windows (~1.4 s) before firing.
   Wait a few seconds after a sound starts.

2. Check the server log for `[WS] Client connected` and `[WS] Session started`. If
   the server never logs these, the WebSocket isn't reaching the backend. Verify the
   IP address and that the server is running with `CLASSIFIER_MODE=panns`.

3. The energy gate silently drops windows with RMS < 0.001. If the phone is very far
   from the sound source, try moving closer or lowering `WS_ENERGY_RMS_THRESHOLD` in
   the server's `.env`.

### "AudioRecord init failed (source=UNPROCESSED)"

Some devices report `UNPROCESSED` as available but fail to initialize `AudioRecord`
with it. The current code does not auto-retry with `VOICE_RECOGNITION` in this case.
As a temporary fix, change the `audioSource` in `AudioCaptureModule.kt` to always
use `MediaRecorder.AudioSource.VOICE_RECOGNITION` and re-run with the effects disabled
explicitly — that path is fully functional.

### "Module not found / null native module"

- **iOS**: Make sure both `.swift` and `.m` files are added to the Xcode target
  (check target membership in the File Inspector on the right). Clean build folder
  (Cmd+Shift+K) and rebuild.
- **Android**: Verify `AudioCapturePackage()` is in the `getPackages()` list in
  `MainApplication.kt`. Run `./gradlew clean` and rebuild.
