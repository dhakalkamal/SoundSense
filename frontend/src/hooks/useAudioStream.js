/**
 * useAudioStream — integrates MicrophoneStream + AudioWebSocket for HomeScreen.
 *
 * Behaviour:
 *   - Auto-starts on mount (demo mode: continuous listening, no toggle).
 *   - Checks for permanently blocked permission before attempting capture;
 *     if blocked, sets status to 'denied' without calling start() (avoids the
 *     library's Alert.alert for blocked permissions).
 *   - For first-launch (DENIED status), allows the library to trigger the OS
 *     permission dialog via MicrophoneStream.startCapture().
 *   - WebSocket opens first so it's ready when the user grants permission and
 *     mic capture starts flowing chunks.
 *   - Exposes `streamStatus` for the listening indicator and `isWsActive` so
 *     HomeScreen knows when to pause/resume REST polling.
 *
 * Status values:
 *   'requesting'   — connecting to WS or checking permission (transient)
 *   'listening'    — WS open, mic active, chunks flowing
 *   'disconnected' — WS dropped; reconnect in progress or fallback to REST
 *   'denied'       — mic permission denied/blocked; show in-screen explainer
 *
 * Error handling: mirrors pollState()'s catch(_){} pattern — all failures are
 * caught internally and surfaced only through streamStatus, never thrown.
 */

import { useEffect, useRef, useState } from 'react';
import { Platform } from 'react-native';
import { check, PERMISSIONS, RESULTS } from 'react-native-permissions';
import * as MicrophoneStream from '../services/MicrophoneStream';
import * as AudioWebSocket from '../services/AudioWebSocket';

/**
 * @param {object}   opts
 * @param {function} opts.onSnapshot  Called with each parsed state snapshot from the
 *                                    WebSocket (same shape as /api/v1/state/latest).
 * @param {function} opts.onFallback  Called when WebSocket reconnect attempts are
 *                                    exhausted — HomeScreen should resume REST polling.
 * @returns {{ streamStatus: string, isWsActive: boolean }}
 */
export function useAudioStream({ onSnapshot, onFallback }) {
  const [streamStatus, setStreamStatus] = useState('requesting');
  const [isWsActive,   setIsWsActive]   = useState(false);

  // Keep callback refs stable so the effect closure sees the latest versions
  // without re-running the effect on every render.
  const onSnapshotRef = useRef(onSnapshot);
  const onFallbackRef = useRef(onFallback);

  useEffect(() => { onSnapshotRef.current = onSnapshot; }, [onSnapshot]);
  useEffect(() => { onFallbackRef.current = onFallback; }, [onFallback]);

  useEffect(() => {
    let cancelled = false;

    async function start() {
      // ── Step 1: Pre-check permission to avoid the library's Alert ────────────
      // Only BLOCKED / UNAVAILABLE are handled early. DENIED (never asked) and
      // GRANTED are both handled by MicrophoneStream.startCapture() below,
      // which triggers the OS dialog for DENIED.
      const permission = Platform.OS === 'android'
        ? PERMISSIONS.ANDROID.RECORD_AUDIO
        : PERMISSIONS.IOS.MICROPHONE;

      let permStatus;
      try {
        permStatus = await check(permission);
      } catch (_) {
        // check() failed (e.g., simulator without mic) — fall through and let
        // startCapture() handle it.
        permStatus = RESULTS.DENIED;
      }

      if (cancelled) return;

      if (permStatus === RESULTS.BLOCKED || permStatus === RESULTS.UNAVAILABLE) {
        setStreamStatus('denied');
        return;
      }

      // ── Step 2: Open WebSocket ────────────────────────────────────────────────
      // Connects and sends the stream header on open. Opens before mic starts
      // so the connection is established while the user responds to the
      // permission dialog (first launch only).
      AudioWebSocket.openConnection({
        onSnapshot: (data) => {
          if (!cancelled) onSnapshotRef.current?.(data);
        },
        onStatus: (wsStatus) => {
          if (cancelled) return;
          if (wsStatus === 'open') {
            setIsWsActive(true);
            setStreamStatus('listening');
          } else if (wsStatus === 'connecting') {
            setIsWsActive(false);
            // Stay on 'requesting' only if we haven't been listening yet;
            // otherwise show 'disconnected' (we're in a reconnect cycle).
            setStreamStatus((prev) =>
              prev === 'listening' ? 'disconnected' : 'requesting'
            );
          } else {
            // 'disconnected' — reconnect cycle in progress
            setIsWsActive(false);
            setStreamStatus('disconnected');
          }
        },
        onFallback: () => {
          if (cancelled) return;
          setIsWsActive(false);
          setStreamStatus('disconnected');
          // Signal HomeScreen to resume REST polling.
          onFallbackRef.current?.();
        },
      });

      // ── Step 3: Start mic capture ─────────────────────────────────────────────
      // For DENIED (first launch), startCapture() triggers the OS dialog.
      // For GRANTED, it starts immediately.
      // Chunks are piped directly into AudioWebSocket.sendChunk().
      const started = await MicrophoneStream.startCapture(
        (chunk) => AudioWebSocket.sendChunk(chunk),
        (_err) => {
          // Mic capture error (device disconnected, etc.) — same silent treatment
          // as pollState()'s catch(_){}.
          if (!cancelled) setStreamStatus('disconnected');
        },
      );

      if (cancelled) return;

      if (!started) {
        // Permission was denied during the OS dialog.
        setStreamStatus('denied');
        AudioWebSocket.closeConnection();
      }
    }

    start().catch(() => {
      // Top-level safety net — mirrors catch(_){} in pollState().
      if (!cancelled) setStreamStatus('disconnected');
    });

    return () => {
      cancelled = true;
      MicrophoneStream.stopCapture();
      AudioWebSocket.closeConnection();
      setIsWsActive(false);
    };
  }, []); // Empty deps: runs once on mount, cleans up on unmount.

  return { streamStatus, isWsActive };
}
