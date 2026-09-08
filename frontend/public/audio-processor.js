/**
 * AudioWorkletProcessor for VoicePilot AI.
 * Runs in a dedicated audio thread to capture microphone PCM audio
 * and play back streaming voice chunks with zero main-thread UI jitter.
 */

class VoicePilotAudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.bufferSize = 512; // 32ms window at 16kHz
    this.inputBuffer = new Float32Array(this.bufferSize);
    this.inputBufferIndex = 0;

    // Output playback queue (incoming PCM chunks from server)
    this.playbackQueue = [];
    this.currentPlaybackChunk = null;
    this.playbackIndex = 0;

    this.port.onmessage = (event) => {
      const { type, data } = event.data;
      if (type === "AUDIO_PLAYBACK") {
        // Enqueue Float32Array audio chunk for playback
        this.playbackQueue.push(new Float32Array(data));
      } else if (type === "CLEAR_PLAYBACK") {
        // Instant Barge-In cancellation: flush playback queue immediately
        this.playbackQueue = [];
        this.currentPlaybackChunk = null;
        this.playbackIndex = 0;
      }
    };
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    const output = outputs[0];

    // 1. Microphone Capture Processing
    if (input && input.length > 0) {
      const channelData = input[0];
      for (let i = 0; i < channelData.length; i++) {
        this.inputBuffer[this.inputBufferIndex++] = channelData[i];
        if (this.inputBufferIndex >= this.bufferSize) {
          // Convert Float32 [-1.0, 1.0] to 16-bit PCM Int16
          const pcm16 = new Int16Array(this.bufferSize);
          for (let j = 0; j < this.bufferSize; j++) {
            const s = Math.max(-1, Math.min(1, this.inputBuffer[j]));
            pcm16[j] = s < 0 ? s * 0x8000 : s * 0x7FFF;
          }

          // Emit PCM buffer to main thread for WebSocket transmission
          this.port.postMessage({
            type: "MIC_PCM",
            buffer: pcm16.buffer
          }, [pcm16.buffer]);

          this.inputBufferIndex = 0;
        }
      }
    }

    // 2. Audio Playback Processing (Streaming incoming bot speech)
    if (output && output.length > 0) {
      const outChannel = output[0];
      for (let i = 0; i < outChannel.length; i++) {
        if (!this.currentPlaybackChunk && this.playbackQueue.length > 0) {
          this.currentPlaybackChunk = this.playbackQueue.shift();
          this.playbackIndex = 0;
        }

        if (this.currentPlaybackChunk) {
          outChannel[i] = this.currentPlaybackChunk[this.playbackIndex++];
          if (this.playbackIndex >= this.currentPlaybackChunk.length) {
            this.currentPlaybackChunk = null;
          }
        } else {
          outChannel[i] = 0; // Silence
        }
      }
    }

    return true;
  }
}

registerProcessor("voicepilot-audio-processor", VoicePilotAudioProcessor);
