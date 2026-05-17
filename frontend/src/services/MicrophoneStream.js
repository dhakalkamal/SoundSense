/**
 * MicrophoneStream — wraps @dr.pogodin/react-native-audio InputAudioStream.
 *
 * Configuration:
 *   Android: AudioSource.UNPROCESSED (source=9, API 24+) — bypasses OS AGC,
 *            noise suppression, and echo cancellation. Critical for detecting
 *            tonal stationary sounds (fire alarms, etc.) that voice-mode capture
 *            specifically attenuates.
 *   iOS:     AUDIO_SOURCES.RAW maps to UNPROCESSED on Android; on iOS the
 *            audioSource parameter is ignored by the library and the default
 *            AVAudioSession configuration applies (AGC gap accepted for v1).
 *
 * Output: raw int16 little-endian mono PCM at 48kHz, ~100ms chunks (~9600 bytes).
 * The chunk listener receives a Node Buffer (Uint8Array-compatible) ready to send
 * as a binary WebSocket frame — no further encoding needed.
 */

import {
  InputAudioStream,
  AUDIO_SOURCES,
  AUDIO_FORMATS,
  CHANNEL_CONFIGS,
} from '@dr.pogodin/react-native-audio';

// 48 kHz mono int16 LE — matches the backend's expected wire format.
const SAMPLE_RATE    = 48000;
const CHANNEL_CONFIG = CHANNEL_CONFIGS.MONO;
const AUDIO_FORMAT   = AUDIO_FORMATS.PCM_16BIT;

// ~100ms per chunk: 48000 samples/s × 0.1s = 4800 samples → 9600 bytes
const SAMPLES_PER_CHUNK = 4800;

// AUDIO_SOURCES.RAW is the library's name for MediaRecorder.AudioSource.UNPROCESSED.
// The compiled JS maps: AUDIO_SOURCES["RAW"] = AUDIO_SOURCE_UNPROCESSED (= 9 on Android).
// Verified in ReactNativeAudioModule.kt:
//   constants["AUDIO_SOURCE_UNPROCESSED"] = MediaRecorder.AudioSource.UNPROCESSED
const ANDROID_AUDIO_SOURCE = AUDIO_SOURCES.RAW;

// Stop capture when the app leaves the foreground (battery / background policy).
const STOP_IN_BACKGROUND = true;

let _stream = null;

/**
 * Start microphone capture. Calls onChunk for each ~100ms PCM frame.
 *
 * The library's start() calls getAudioRecordingPermission() internally:
 *   - First launch: triggers the OS permission dialog.
 *   - Permission already granted: proceeds immediately.
 *   - Permission blocked: shows an Alert (library behaviour) and returns false.
 *
 * @param {function(Buffer): void} onChunk  Called with each raw PCM Buffer.
 * @param {function(Error): void}  onError  Called on any capture error.
 * @returns {Promise<boolean>}  true if capture started successfully.
 */
export async function startCapture(onChunk, onError) {
  if (_stream) {
    await stopCapture();
  }

  _stream = new InputAudioStream(
    ANDROID_AUDIO_SOURCE,
    SAMPLE_RATE,
    CHANNEL_CONFIG,
    AUDIO_FORMAT,
    SAMPLES_PER_CHUNK,
    STOP_IN_BACKGROUND,
  );

  _stream.addChunkListener(onChunk);
  _stream.addErrorListener(onError);

  const started = await _stream.start();
  if (!started) {
    // Permission denied or unavailable — clean up so the caller can inspect
    // status and show the in-screen explainer.
    await _destroyStream();
  }
  return started;
}

/**
 * Stop microphone capture and release native resources.
 */
export async function stopCapture() {
  await _destroyStream();
}

async function _destroyStream() {
  if (_stream) {
    const s = _stream;
    _stream = null;
    await s.destroy();
  }
}
