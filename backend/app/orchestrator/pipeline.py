import asyncio
import json
import logging
import time
from typing import Callable, Optional
from app.core.config import settings
from app.vad.silero_vad import SileroVAD
from app.services.stt_service import STTService
from app.services.llm_service import LLMService
from app.services.tts_service import TTSService

logger = logging.getLogger(__name__)


class VoiceSessionPipeline:
    """
    Full-Duplex Conversational Pipeline Coordinator.
    Manages state, VAD, STT, LLM streaming, TTS audio output, and Barge-In cancellation.
    """

    def __init__(self, send_json_fn: Callable, send_bytes_fn: Callable):
        self.send_json = send_json_fn
        self.send_bytes = send_bytes_fn
        
        self.vad = SileroVAD(sample_rate=settings.SAMPLE_RATE, threshold=settings.VAD_THRESHOLD)
        self.stt = STTService()
        self.llm = LLMService()
        self.tts = TTSService(sample_rate=settings.SAMPLE_RATE)

        self.state = "IDLE"  # IDLE, LISTENING, THINKING, SPEAKING, INTERRUPTED
        self.cancellation_token = asyncio.Event()
        self.history = []
        
        # Audio accumulator for STT
        self.audio_buffer = bytearray()
        self.user_speech_start_time = 0.0
        self.user_speech_end_time = 0.0

        # Latency metrics tracking
        self.metrics = {
            "vad_ms": 0.0,
            "stt_ms": 0.0,
            "llm_ttft_ms": 0.0,
            "tts_ttfb_ms": 0.0,
            "total_e2e_ms": 0.0
        }

    async def start(self):
        """Initialize connection to STT engine."""
        await self.stt.connect()
        self.state = "LISTENING"
        await self.send_state_update()

    async def handle_audio_frame(self, pcm_chunk: bytes):
        """Processes an incoming 16kHz 16-bit PCM chunk from client microphone."""
        # 1. Run low-latency VAD
        t0 = time.perf_counter()
        vad_res = self.vad.process_chunk(pcm_chunk)
        self.metrics["vad_ms"] = round((time.perf_counter() - t0) * 1000, 2)

        is_speech = vad_res["is_speech"]
        barge_in = vad_res["barge_in"]

        # 2. Check for Barge-in Interruption while bot is speaking
        if self.state == "SPEAKING" and barge_in:
            logger.info(">>> BARGE-IN DETECTED: User interrupted agent speech! <<<")
            self.cancellation_token.set()
            self.state = "INTERRUPTED"
            await self.send_json({"type": "INTERRUPT", "reason": "user_barge_in"})
            # Transition back to listening
            self.state = "LISTENING"
            self.audio_buffer.clear()
            self.user_speech_start_time = time.time()
            self.vad.reset_states()
            await self.send_state_update()
            return

        # 3. Speech Turn Tracking
        if is_speech:
            if not self.audio_buffer:
                self.user_speech_start_time = time.time()
                self.state = "LISTENING"
                await self.send_state_update()

            self.audio_buffer.extend(pcm_chunk)
            await self.stt.send_audio_chunk(pcm_chunk)

        # 4. Silence detected after speech (turn completion)
        elif len(self.audio_buffer) > (settings.SAMPLE_RATE * 0.5 * 2):  # At least 0.5s speech accumulated
            if vad_res["consecutive_silence_frames"] >= (settings.SILENCE_TIMEOUT_MS // 32):
                # User has finished speaking!
                self.user_speech_end_time = time.time()
                speech_bytes = bytes(self.audio_buffer)
                self.audio_buffer.clear()
                self.vad.reset_states()

                # Launch response pipeline asynchronously
                asyncio.create_task(self._process_turn(speech_bytes))

    async def _process_turn(self, speech_bytes: bytes):
        """Executes STT -> LLM -> Streaming TTS with latency telemetry."""
        turn_start_time = time.perf_counter()
        self.state = "THINKING"
        self.cancellation_token.clear()
        await self.send_state_update()

        # Step A: STT Finalization
        stt_start = time.perf_counter()
        transcript = await self.stt.finalize_mock_speech()
        self.metrics["stt_ms"] = round((time.perf_counter() - stt_start) * 1000, 1)

        await self.send_json({
            "type": "TRANSCRIPT",
            "role": "user",
            "text": transcript,
            "stt_ms": self.metrics["stt_ms"]
        })

        self.history.append({"role": "user", "content": transcript})

        # Step B: LLM Generation & Streaming TTS
        self.state = "SPEAKING"
        await self.send_state_update()

        llm_start = time.perf_counter()
        first_token_received = False
        first_audio_sent = False
        agent_full_text = []

        try:
            async for sentence in self.llm.stream_response(self.history, self.cancellation_token):
                if self.cancellation_token.is_set():
                    logger.info("Pipeline cancelled mid-turn.")
                    break

                if not first_token_received:
                    first_token_received = True
                    self.metrics["llm_ttft_ms"] = round((time.perf_counter() - llm_start) * 1000, 1)

                agent_full_text.append(sentence)
                await self.send_json({
                    "type": "AGENT_PARTIAL_TEXT",
                    "text": sentence
                })

                # Stream synthesized audio for this sentence immediately
                tts_start = time.perf_counter()
                async for audio_chunk in self.tts.stream_audio(sentence, self.cancellation_token):
                    if self.cancellation_token.is_set():
                        break

                    if not first_audio_sent:
                        first_audio_sent = True
                        self.metrics["tts_ttfb_ms"] = round((time.perf_counter() - tts_start) * 1000, 1)
                        self.metrics["total_e2e_ms"] = round((time.perf_counter() - turn_start_time) * 1000, 1)
                        # Broadcast latency metrics
                        await self.send_json({
                            "type": "LATENCY_TELEMETRY",
                            "metrics": self.metrics
                        })

                    await self.send_bytes(audio_chunk)

        except Exception as e:
            logger.error(f"Error in turn pipeline: {e}")

        # Finalize turn
        if agent_full_text:
            complete_reply = " ".join(agent_full_text)
            self.history.append({"role": "assistant", "content": complete_reply})
            await self.send_json({
                "type": "TRANSCRIPT",
                "role": "assistant",
                "text": complete_reply
            })

        if not self.cancellation_token.is_set():
            self.state = "LISTENING"
            await self.send_state_update()

    async def send_state_update(self):
        """Notify frontend of agent state changes."""
        await self.send_json({
            "type": "STATE_CHANGE",
            "state": self.state
        })

    async def close(self):
        """Tear down session."""
        self.cancellation_token.set()
        await self.stt.close()
