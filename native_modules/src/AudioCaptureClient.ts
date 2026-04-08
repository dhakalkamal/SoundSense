/**
 * AudioCaptureClient — TypeScript wrapper for the AudioCaptureModule native module.
 *
 * Handles the full lifecycle:
 *   1. Starts native microphone capture (iOS AVAudioEngine / Android AudioRecord).
 *   2. Waits for the AudioCaptureState event to get the device's actual sample rate.
 *   3. Opens a WebSocket to the SoundSense backend, sends the JSON header, then
 *      streams binary int16 PCM frames as the native module emits them.
 *   4. Reconnects automatically if the WebSocket drops while capture is active.
 *   5. stopCapture() stops native capture and tears down the WebSocket cleanly.
 *
 * Minimum requirements: React Native ≥ 0.63 (ArrayBuffer WebSocket send support),
 * global atob() available (polyfill with react-native-quick-base64 if on RN < 0.64).
 */

import { NativeEventEmitter, NativeModules } from 'react-native';

const { AudioCaptureModule: _native } = NativeModules;

if (!_native) {
  throw new Error(
    'AudioCaptureModule native module not found. ' +
    'Make sure you followed the integration steps in INTEGRATION.md.',
  );
}

const _emitter = new NativeEventEmitter(_native);

// ── Public types ──────────────────────────────────────────────────────────────

export type ConnectionState =
  | 'idle'
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'stopped';

/** Shape of the JSON messages pushed by the server after each detection event.
 *  Mirrors GET /api/v1/state/latest so you can reuse the same state-update logic. */
export interface DetectionPayload {
  event: {
    label: string;
    confidence: number;
    timestamp: number;
    elapsed_s: number;
  };
  situation: {
    flag: string;
    urgency: 'low' | 'medium' | 'high' | 'critical';
    explanation: string | null;
    flag_changed_at: number | null;
    previous_flag: string | null;
  };
  active_durations: Record<string, number>;
  counts_30s: Record<string, number>;
  timeline: Array<{ label: string; confidence: number; timestamp: number; elapsed_s: number }>;
}

export interface AudioCaptureCallbacks {
  onConnectionState?: (state: ConnectionState) => void;
  onDetection?: (payload: DetectionPayload) => void;
  onError?: (message: string) => void;
}

// ── AudioCaptureClient ────────────────────────────────────────────────────────

class AudioCaptureClient {
  private wsUrl = '';
  private ws: WebSocket | null = null;
  private sampleRate = 48_000;  // overridden by AudioCaptureState before WS header is sent
  private isStarted = false;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private nativeListeners: Array<{ remove(): void }> = [];
  private callbacks: AudioCaptureCallbacks = {};

  /** Register event callbacks. Call before startCapture(). Returns `this` for chaining. */
  on(callbacks: AudioCaptureCallbacks): this {
    Object.assign(this.callbacks, callbacks);
    return this;
  }

  /**
   * Start microphone capture and open a WebSocket to wsUrl.
   *
   * Order of operations (important for correct sample_rate in the header):
   *   1. Start native capture → native emits AudioCaptureState with actual sample rate.
   *   2. AudioCaptureState handler records sample_rate, then opens the WebSocket.
   *   3. WebSocket.onopen sends the JSON header with the correct sample_rate.
   *   4. AudioFrame events start flowing — frames before the socket is OPEN are dropped.
   */
  startCapture(wsUrl: string): void {
    if (this.isStarted) return;
    this.isStarted = true;
    this.wsUrl = wsUrl;

    this.nativeListeners.push(
      // Step 1 → 2: native tells us the actual sample rate, then we open the WebSocket.
      _emitter.addListener('AudioCaptureState', (state: Record<string, unknown>) => {
        if (state.state === 'started') {
          this.sampleRate = (state.sample_rate as number) ?? 48_000;
          this._connectWS();
        }
      }),

      // Step 4: stream binary frames to the server.
      _emitter.addListener('AudioFrame', (b64: string) => this._sendFrame(b64)),

      // Forward native errors to caller.
      _emitter.addListener('AudioCaptureError', (e: Record<string, unknown>) =>
        this.callbacks.onError?.(String(e.message ?? 'Native capture error')),
      ),
    );

    _native.startCapture();
  }

  /** Stop microphone capture and close the WebSocket. */
  stopCapture(): void {
    this.isStarted = false;
    _native.stopCapture();
    this._teardown();
    this.callbacks.onConnectionState?.('stopped');
  }

  // ── Private ─────────────────────────────────────────────────────────────────

  private _connectWS(): void {
    this.callbacks.onConnectionState?.('connecting');

    const ws = new WebSocket(this.wsUrl);
    this.ws = ws;

    ws.onopen = () => {
      // Protocol step 1: send JSON header so the server knows the phone's sample rate.
      // The server's ring buffer will resample to 32 kHz via torchaudio.
      ws.send(
        JSON.stringify({
          sample_rate: this.sampleRate,
          channels: 1,
          encoding: 'pcm_s16le',
        }),
      );
      this.callbacks.onConnectionState?.('connected');
    };

    ws.onmessage = ({ data }: MessageEvent) => {
      // Protocol step 3: server pushes JSON after each smoothed detection event.
      try {
        this.callbacks.onDetection?.(JSON.parse(data) as DetectionPayload);
      } catch {
        // Non-JSON message — ignore (future text control messages).
      }
    };

    ws.onerror = () => {
      this.callbacks.onError?.('WebSocket connection error');
    };

    ws.onclose = () => {
      this.ws = null;
      if (!this.isStarted) return;
      // Auto-reconnect while capture is active; native capture keeps running so we
      // don't lose the audio session on the phone side.
      this.callbacks.onConnectionState?.('reconnecting');
      this.reconnectTimer = setTimeout(() => {
        if (this.isStarted) this._connectWS();
      }, 2_000);
    };
  }

  private _sendFrame(b64: string): void {
    if (this.ws?.readyState !== WebSocket.OPEN) return;
    // Decode base64 → ArrayBuffer so WebSocket.send() sends a binary frame.
    // The server expects msg.get("bytes") — a binary WebSocket message.
    try {
      const binary = atob(b64);
      const buf = new ArrayBuffer(binary.length);
      const view = new Uint8Array(buf);
      for (let i = 0; i < binary.length; i++) view[i] = binary.charCodeAt(i);
      this.ws.send(buf);
    } catch {
      // Frame dropped — non-fatal; the 2-of-3 temporal smoother handles gaps.
    }
  }

  private _teardown(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.nativeListeners.forEach(l => l.remove());
    this.nativeListeners = [];
    this.ws?.close();
    this.ws = null;
  }
}

/** Singleton instance — import and use directly in components. */
export const audioCaptureClient = new AudioCaptureClient();
export default audioCaptureClient;
