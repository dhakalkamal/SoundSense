import AVFoundation
import React

/// React Native native module — captures microphone audio using AVAudioEngine and emits
/// ~100 ms mono int16 PCM frames to JavaScript over the React Native event bridge.
///
/// AVAudioSession mode is set to .measurement (not .voiceChat) to bypass iOS voice-
/// processing DSP — AGC, noise suppression, echo cancellation — that would otherwise
/// attenuate or distort tonal sounds like smoke alarms and doorbells.
@objc(AudioCaptureModule)
final class AudioCaptureModule: RCTEventEmitter {

    private var engine: AVAudioEngine?
    private var isCapturing = false

    // MARK: - RCTEventEmitter

    override func supportedEvents() -> [String]! {
        ["AudioFrame", "AudioCaptureState", "AudioCaptureError"]
    }

    override static func requiresMainQueueSetup() -> Bool { false }

    // MARK: - JS-callable methods

    /// Start microphone capture.
    ///
    /// Emits `AudioCaptureState { state: "started", sample_rate, channels, encoding }`
    /// on success, or `AudioCaptureError { message }` on permission denial or engine error.
    @objc func startCapture() {
        guard !isCapturing else { return }
        AVAudioSession.sharedInstance().requestRecordPermission { [weak self] granted in
            guard let self else { return }
            if granted {
                self.startEngine()
            } else {
                self.sendEvent(withName: "AudioCaptureError",
                               body: ["message": "Microphone permission denied"])
            }
        }
    }

    /// Stop microphone capture.
    ///
    /// Emits `AudioCaptureState { state: "stopped" }`.
    @objc func stopCapture() {
        stopEngine()
    }

    // MARK: - Engine lifecycle

    private func startEngine() {
        do {
            let session = AVAudioSession.sharedInstance()
            // .measurement mode is critical — it disables iOS voice processing (AGC,
            // noise suppression, echo cancellation). Without this, iOS silently applies
            // aggressive filtering that kills stationary tonal sounds like alarms.
            try session.setCategory(.record, mode: .measurement, options: [])
            try session.setPreferredSampleRate(48_000)
            try session.setActive(true)

            let e = AVAudioEngine()
            let inputNode = e.inputNode
            // Read actual rate after session activation — device may not support 48 kHz
            // exactly and will use the nearest supported rate (44100 or 48000).
            let nativeFormat = inputNode.inputFormat(forBus: 0)
            let actualRate = nativeFormat.sampleRate
            guard actualRate > 0 else {
                sendEvent(withName: "AudioCaptureError",
                          body: ["message": "Could not determine input sample rate"])
                return
            }
            let bufferSize = AVAudioFrameCount(actualRate * 0.1)  // ~100 ms

            inputNode.installTap(onBus: 0, bufferSize: bufferSize, format: nativeFormat) {
                [weak self] buffer, _ in
                self?.handleBuffer(buffer)
            }

            try e.start()
            engine = e
            isCapturing = true

            // Report actual rate to JS so it can send the correct sample_rate in the
            // WebSocket JSON header (server uses torchaudio.functional.resample to 32 kHz).
            sendEvent(withName: "AudioCaptureState", body: [
                "state": "started",
                "sample_rate": Int(actualRate),
                "channels": 1,
                "encoding": "pcm_s16le",
            ])
        } catch {
            sendEvent(withName: "AudioCaptureError",
                      body: ["message": error.localizedDescription])
        }
    }

    private func stopEngine() {
        engine?.inputNode.removeTap(onBus: 0)
        engine?.stop()
        engine = nil
        isCapturing = false
        try? AVAudioSession.sharedInstance().setActive(false)
        sendEvent(withName: "AudioCaptureState", body: ["state": "stopped"])
    }

    // MARK: - Audio processing

    private func handleBuffer(_ buffer: AVAudioPCMBuffer) {
        guard let floatData = buffer.floatChannelData else { return }
        let frameCount = Int(buffer.frameLength)
        let channelCount = Int(buffer.format.channelCount)

        // Mix to mono and convert float32 → int16 little-endian.
        // Clamp to [-1, 1] before scaling to prevent int16 overflow on loud transients.
        var samples = [Int16](repeating: 0, count: frameCount)
        for i in 0..<frameCount {
            var sample: Float = 0
            for c in 0..<channelCount { sample += floatData[c][i] }
            if channelCount > 1 { sample /= Float(channelCount) }
            samples[i] = Int16((max(-1.0, min(1.0, sample)) * 32_767.0).rounded())
        }

        // Encode raw bytes as base64 for transport over the React Native JS bridge.
        // The JS wrapper decodes base64 → ArrayBuffer before sending over WebSocket.
        let data = samples.withUnsafeBytes { Data($0) }
        sendEvent(withName: "AudioFrame", body: data.base64EncodedString())
    }
}
