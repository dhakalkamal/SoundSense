package com.soundsense.app  // ← replace with your actual application package name

import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.media.audiofx.AcousticEchoCanceler
import android.media.audiofx.AudioEffect
import android.media.audiofx.AutomaticGainControl
import android.media.audiofx.NoiseSuppressor
import android.os.Build
import android.util.Base64
import com.facebook.react.bridge.ReactApplicationContext
import com.facebook.react.bridge.ReactContextBaseJavaModule
import com.facebook.react.bridge.ReactMethod
import com.facebook.react.modules.core.DeviceEventManagerModule.RCTDeviceEventEmitter
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.concurrent.atomic.AtomicBoolean

/**
 * React Native native module — captures microphone audio using AudioRecord and emits
 * ~100 ms mono int16 PCM frames to JavaScript over the React Native event bridge.
 *
 * Audio source selection:
 *   API ≥ 24: MediaRecorder.AudioSource.UNPROCESSED — requests raw audio with no
 *             Android voice-processing pipeline applied.
 *   API < 24: MediaRecorder.AudioSource.VOICE_RECOGNITION — best available raw-ish
 *             source; AGC/NS/AEC are then disabled explicitly below.
 *
 * After AudioRecord creation, NoiseSuppressor, AcousticEchoCanceler, and
 * AutomaticGainControl are explicitly disabled via the AudioEffect API. This is
 * redundant when UNPROCESSED is honored by the hardware, but is essential for the
 * VOICE_RECOGNITION fallback path and for devices that silently ignore UNPROCESSED.
 */
class AudioCaptureModule(reactContext: ReactApplicationContext) :
    ReactContextBaseJavaModule(reactContext) {

    override fun getName() = "AudioCaptureModule"

    private var audioRecord: AudioRecord? = null
    private val isCapturing = AtomicBoolean(false)
    private var captureThread: Thread? = null
    // Keep disabled effects alive for the recording session so they are not GC'd
    // and silently re-enabled by the system.
    private val activeEffects = mutableListOf<AudioEffect>()

    companion object {
        private const val SAMPLE_RATE = 48_000
        private const val FRAME_SAMPLES = SAMPLE_RATE / 10  // 4 800 samples ≈ 100 ms
    }

    @ReactMethod
    fun startCapture() {
        if (isCapturing.get()) return

        // Request the least-processed audio source available on this API level.
        val audioSource =
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N)
                MediaRecorder.AudioSource.UNPROCESSED
            else
                MediaRecorder.AudioSource.VOICE_RECOGNITION

        val minBuf = AudioRecord.getMinBufferSize(
            SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
        )
        if (minBuf <= 0) {
            emit("AudioCaptureError",
                mapOf("message" to "48 kHz mono PCM not supported on this device"))
            return
        }
        // Buffer at least 4 frames so read() never starves the capture thread.
        val bufBytes = maxOf(minBuf, FRAME_SAMPLES * Short.SIZE_BYTES * 4)

        val record = AudioRecord(
            audioSource,
            SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
            bufBytes,
        )

        if (record.state != AudioRecord.STATE_INITIALIZED) {
            record.release()
            emit("AudioCaptureError",
                mapOf("message" to "AudioRecord failed to initialize (source=$audioSource)"))
            return
        }

        // Disable audio processing effects.
        // isAvailable() is checked before create() — some devices report available
        // but throw on create(), so the try-catch inside disableEffect handles that.
        val sessionId = record.audioSessionId
        disableEffect(NoiseSuppressor.isAvailable()) { NoiseSuppressor.create(sessionId) }
        disableEffect(AcousticEchoCanceler.isAvailable()) { AcousticEchoCanceler.create(sessionId) }
        disableEffect(AutomaticGainControl.isAvailable()) { AutomaticGainControl.create(sessionId) }

        audioRecord = record
        isCapturing.set(true)
        record.startRecording()

        emit("AudioCaptureState", mapOf(
            "state" to "started",
            "sample_rate" to SAMPLE_RATE,
            "channels" to 1,
            "encoding" to "pcm_s16le",
        ))

        captureThread = Thread {
            val buf = ShortArray(FRAME_SAMPLES)
            while (isCapturing.get()) {
                val read = record.read(buf, 0, FRAME_SAMPLES)
                if (read > 0) {
                    // Pack shorts as little-endian bytes (matches the server's
                    // np.frombuffer(..., dtype="<i2") decode in ws_routes.py).
                    val bytes = ByteBuffer
                        .allocate(read * Short.SIZE_BYTES)
                        .order(ByteOrder.LITTLE_ENDIAN)
                        .apply { for (i in 0 until read) putShort(buf[i]) }
                        .array()
                    emit("AudioFrame", Base64.encodeToString(bytes, Base64.NO_WRAP))
                }
            }
        }.also { it.start() }
    }

    @ReactMethod
    fun stopCapture() {
        isCapturing.set(false)
        captureThread?.join(500)   // wait up to 500 ms for the read loop to exit
        captureThread = null
        activeEffects.forEach { it.release() }
        activeEffects.clear()
        audioRecord?.apply { stop(); release() }
        audioRecord = null
        emit("AudioCaptureState", mapOf("state" to "stopped"))
    }

    // Required stubs — RN event emitter housekeeping (no-op on the native side).
    @ReactMethod fun addListener(eventName: String) {}
    @ReactMethod fun removeListeners(count: Int) {}

    // ── Helpers ─────────────────────────────────────────────────────────────

    private fun disableEffect(available: Boolean, create: () -> AudioEffect?) {
        if (!available) return
        try {
            create()?.let { effect ->
                effect.enabled = false
                activeEffects.add(effect)  // keep reference to prevent GC re-enablement
            }
        } catch (e: Exception) {
            // isAvailable() returned true but create() threw — safe to ignore.
            // The effect simply won't be disabled, which is acceptable.
        }
    }

    private fun emit(name: String, data: Any) {
        try {
            reactApplicationContext
                .getJSModule(RCTDeviceEventEmitter::class.java)
                .emit(name, data)
        } catch (e: Exception) {
            // React context not yet ready or already torn down — drop event silently.
        }
    }
}
