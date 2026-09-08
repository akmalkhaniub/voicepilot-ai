import os
import urllib.request
import logging
import numpy as np

logger = logging.getLogger(__name__)

SILERO_VAD_URL = "https://raw.githubusercontent.com/snakers4/silero-vad/master/src/silero_vad/data/silero_vad.onnx"
MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "silero_vad.onnx")


class SileroVAD:
    """
    Production-grade Voice Activity Detection (VAD) using Silero VAD v5 via ONNX Runtime.
    Optimized for ultra-low latency (<2ms per frame on CPU).
    Includes energy-based fallback if ONNX model is initializing or unavailable.
    """

    def __init__(self, sample_rate: int = 16000, threshold: float = 0.5):
        self.sample_rate = sample_rate
        self.threshold = threshold
        self.session = None
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._context = np.zeros((1, 64), dtype=np.float32)
        self.is_speaking = False
        self.consecutive_speech_frames = 0
        self.consecutive_silence_frames = 0
        
        self._init_model()

    def _init_model(self):
        try:
            import onnxruntime as ort
            os.makedirs(MODEL_DIR, exist_ok=True)
            if not os.path.exists(MODEL_PATH):
                logger.info(f"Downloading Silero VAD ONNX model to {MODEL_PATH}...")
                urllib.request.urlretrieve(SILERO_VAD_URL, MODEL_PATH)
                logger.info("Silero VAD model download complete.")

            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 1
            opts.inter_op_num_threads = 1
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self.session = ort.InferenceSession(MODEL_PATH, sess_options=opts, providers=["CPUExecutionProvider"])
            logger.info("Silero VAD ONNX session initialized successfully.")
        except Exception as e:
            logger.warning(f"Could not initialize ONNX Silero VAD ({e}). Falling back to energy-based VAD.")
            self.session = None

    def reset_states(self):
        """Reset internal recurrent state when a conversation turn completes."""
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._context = np.zeros((1, 64), dtype=np.float32)
        self.is_speaking = False
        self.consecutive_speech_frames = 0
        self.consecutive_silence_frames = 0

    def process_chunk(self, pcm_chunk: bytes) -> dict:
        """
        Process a 512-sample (32ms) 16kHz 16-bit mono PCM audio chunk.
        Returns:
            dict with:
                - is_speech (bool)
                - speech_prob (float)
                - barge_in (bool): True if speech detected for consecutive frames
        """
        # Convert raw PCM16 bytes to float32 in range [-1.0, 1.0]
        audio_data = np.frombuffer(pcm_chunk, dtype=np.int16).astype(np.float32) / 32768.0
        
        if len(audio_data) != 512:
            # Pad or truncate to exactly 512 samples
            if len(audio_data) < 512:
                audio_data = np.pad(audio_data, (0, 512 - len(audio_data)))
            else:
                audio_data = audio_data[:512]

        speech_prob = 0.0

        if self.session is not None:
            try:
                audio_input = np.expand_dims(audio_data, axis=0) # [1, 512]
                sr_input = np.array(self.sample_rate, dtype=np.int64)

                # Silero VAD v5 expects: input, state, sr
                inputs = {
                    "input": audio_input,
                    "state": self._state,
                    "sr": sr_input
                }
                out, new_state = self.session.run(None, inputs)
                self._state = new_state
                speech_prob = float(np.squeeze(out))
            except Exception as ex:
                logger.error(f"Error during ONNX VAD inference: {ex}")
                speech_prob = self._energy_vad(audio_data)
        else:
            speech_prob = self._energy_vad(audio_data)

        is_speech = speech_prob >= self.threshold

        if is_speech:
            self.consecutive_speech_frames += 1
            self.consecutive_silence_frames = 0
            if self.consecutive_speech_frames >= 2:
                self.is_speaking = True
        else:
            self.consecutive_silence_frames += 1
            if self.consecutive_silence_frames >= 10:  # ~320ms of silence
                self.is_speaking = False
                self.consecutive_speech_frames = 0

        # Barge-in triggers when speech is recognized continuously for >= 2 frames (~64ms)
        barge_in = self.consecutive_speech_frames >= 2

        return {
            "is_speech": is_speech,
            "speech_prob": speech_prob,
            "barge_in": barge_in,
            "is_speaking": self.is_speaking,
            "consecutive_speech_frames": self.consecutive_speech_frames,
            "consecutive_silence_frames": self.consecutive_silence_frames
        }

    def _energy_vad(self, audio_data: np.ndarray) -> float:
        """Root-mean-square energy VAD fallback for zero-dependency scenarios."""
        rms = np.sqrt(np.mean(np.square(audio_data)))
        # Normalize roughly between 0.0 and 1.0 (RMS > 0.02 is typical speech)
        prob = min(1.0, max(0.0, (rms - 0.01) * 20.0))
        return float(prob)
