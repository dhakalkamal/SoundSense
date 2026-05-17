/**
 * AudioWebSocket — manages the WebSocket connection to /ws/audio.
 *
 * Protocol (backend contract):
 *   1. Client opens ws://<host>/ws/audio
 *   2. Client sends a JSON text frame as the stream header:
 *        {"sample_rate": 48000, "channels": 1, "encoding": "pcm_s16le"}
 *   3. Client streams binary frames of int16 LE mono PCM (~9600 bytes / ~100ms).
 *   4. Server pushes JSON text frames with state snapshots in the same shape
 *      as GET /api/v1/state/latest:
 *        { scenario_running, timeline: [{timestamp, label, elapsed_s}], situation }
 *
 * Reconnect policy: 3 attempts with exponential backoff (1s / 2s / 4s), then
 * calls onFallback() so the caller can resume REST polling. Mirrors the silent
 * failure behaviour of the existing pollState() — no errors are surfaced to the
 * user beyond the status indicator.
 *
 * Error handling philosophy: matches pollState()'s catch(_){} pattern — all
 * failures are caught and handled internally; callers receive status callbacks,
 * not thrown errors.
 */

import { WS_URL } from '../config';

const STREAM_HEADER = JSON.stringify({
  sample_rate: 48000,
  channels: 1,
  encoding: 'pcm_s16le',
});

const RECONNECT_DELAYS_MS = [1000, 2000, 4000]; // 3 attempts

/**
 * @typedef {'connecting' | 'open' | 'closed'} WsState
 */

let _ws        = null;
let _attempt   = 0;
let _reconnectTimer = null;
let _destroyed = false;

// Callbacks — set by open(), cleared by close().
let _onSnapshot  = null; // (snapshotJson: object) => void
let _onStatus    = null; // (status: string) => void — 'connecting'|'open'|'disconnected'|'error'
let _onFallback  = null; // () => void — called when all reconnect attempts exhausted

/**
 * Open the WebSocket and begin streaming.
 *
 * @param {object} opts
 * @param {function(object): void} opts.onSnapshot  Called with each parsed state snapshot.
 * @param {function(string): void} opts.onStatus    Called on connection state changes.
 * @param {function(): void}       opts.onFallback  Called when reconnect attempts exhausted.
 */
export function openConnection({ onSnapshot, onStatus, onFallback }) {
  _onSnapshot = onSnapshot;
  _onStatus   = onStatus;
  _onFallback = onFallback;
  _destroyed  = false;
  _attempt    = 0;
  _connect();
}

/**
 * Send a binary PCM chunk. No-ops if the socket is not open.
 * @param {Buffer} chunk  Raw int16 LE PCM buffer from MicrophoneStream.
 */
export function sendChunk(chunk) {
  if (_ws && _ws.readyState === WebSocket.OPEN) {
    // React Native's WebSocket accepts ArrayBuffer / typed arrays as binary.
    // Buffer (Uint8Array subclass) works directly.
    _ws.send(chunk);
  }
}

/**
 * Close the WebSocket permanently — no reconnect will be attempted.
 * Call this when the component unmounts or capture is intentionally stopped.
 */
export function closeConnection() {
  _destroyed = true;
  _clearReconnectTimer();
  _closeSocket();
  _onSnapshot  = null;
  _onStatus    = null;
  _onFallback  = null;
}

// ─── Internal ─────────────────────────────────────────────────────────────────

function _connect() {
  if (_destroyed) return;

  _onStatus?.('connecting');

  try {
    _ws = new WebSocket(WS_URL);
  } catch (_) {
    // Synchronous construction error (invalid URL, etc.) — treat as failure.
    _handleFailure();
    return;
  }

  _ws.onopen = () => {
    _attempt = 0; // Reset backoff on successful connection.
    // Send stream header as the first text frame before any binary data.
    _ws.send(STREAM_HEADER);
    _onStatus?.('open');
  };

  _ws.onmessage = (event) => {
    // The server sends text frames only (JSON state snapshots).
    // Binary echo or other non-string messages are silently ignored.
    if (typeof event.data !== 'string') return;
    try {
      const snapshot = JSON.parse(event.data);
      _onSnapshot?.(snapshot);
    } catch (_) {
      // Malformed JSON from server — ignore, same as pollState's !res.ok return.
    }
  };

  _ws.onerror = () => {
    // onerror always fires before onclose — suppress here, handle in onclose.
  };

  _ws.onclose = () => {
    _ws = null;
    if (!_destroyed) {
      _handleFailure();
    }
  };
}

function _handleFailure() {
  if (_destroyed) return;

  _onStatus?.('disconnected');

  if (_attempt < RECONNECT_DELAYS_MS.length) {
    const delay = RECONNECT_DELAYS_MS[_attempt];
    _attempt += 1;
    _reconnectTimer = setTimeout(_connect, delay);
  } else {
    // All attempts exhausted — hand off to REST polling fallback.
    _onFallback?.();
  }
}

function _clearReconnectTimer() {
  if (_reconnectTimer !== null) {
    clearTimeout(_reconnectTimer);
    _reconnectTimer = null;
  }
}

function _closeSocket() {
  if (_ws) {
    const ws = _ws;
    _ws = null;
    try {
      ws.onopen    = null;
      ws.onmessage = null;
      ws.onerror   = null;
      ws.onclose   = null;
      ws.close();
    } catch (_) {}
  }
}
