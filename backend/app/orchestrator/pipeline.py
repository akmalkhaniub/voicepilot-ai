import asyncio
import logging
import time
from typing import Callable, Optional
from app.core.config import settings
from app.guardrails.safety_gate import VoiceSafetyGate
from app.observability.telemetry import (
    VoiceTelemetryRegistry,
    VoiceTurnSpan,
    global_telemetry_registry,
    parse_or_create_traceparent,
)
from app.vad.silero_vad import SileroVAD
from app.services.stt_service import STTService
from app.services.llm_service import LLMService
from app.services.tts_service import TTSService

logger = logging.getLogger(__name__)


class VoiceSessionPipeline:
    """
    Full-Duplex Conversational Pipeline Coordinator.
    Manages state, VAD, STT, deterministic safety guardrails, LLM streaming,
    TTS audio output, OTel GenAI turn telemetry, and Barge-In cancellation.
    """

    def __init__(
        self,
        send_json_fn: Callable,
        send_bytes_fn: Callable,
        traceparent: Optional[str] = None,
        telemetry_registry: Optional[VoiceTelemetryRegistry] = None,
    ):
        self.send_json = send_json_fn
        self.send_bytes = send_bytes_fn

        self.vad = SileroVAD(sample_rate=settings.SAMPLE_RATE, threshold=settings.VAD_THRESHOLD)
        self.stt = STTService()
        self.llm = LLMService()
        self.tts = TTSService(sample_rate=settings.SAMPLE_RATE)
        self.safety_gate = VoiceSafetyGate()
        self.telemetry = telemetry_registry or global_telemetry_registry
        self.session_traceparent = traceparent

        self.state = "IDLE"  # IDLE, LISTENING, THINKING, SPEAKING, INTERRUPTED
        self.cancellation_token = asyncio.Event()
        self.history = []
        self._active_turn_task: Optional[asyncio.Task] = None

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
            "total_e2e_ms": 0.0,
            "barge_in_cutoff_ms": 0.0,
        }

    async def start(self):
        """Initialize connection to STT engine."""
        await self.stt.connect()
        self.state = "LISTENING"
        await self.send_state_update()

    async def handle_audio_frame(self, pcm_chunk: bytes):
        """Processes an incoming 16kHz 16-bit PCM chunk from client microphone."""
        t0 = time.perf_counter()
        vad_res = self.vad.process_chunk(pcm_chunk)
        self.metrics["vad_ms"] = round((time.perf_counter() - t0) * 1000, 2)

        is_speech = vad_res["is_speech"]
        barge_in = vad_res["barge_in"]

        # Check for Barge-in Interruption while bot is speaking
        if self.state == "SPEAKING" and barge_in:
            cutoff_start = time.perf_counter()
            logger.info(">>> BARGE-IN DETECTED: User interrupted agent speech! <<<")
            self.cancellation_token.set()
            self.state = "INTERRUPTED"
            await self.send_json({"type": "INTERRUPT", "reason": "user_barge_in"})
            cutoff_ms = round((time.perf_counter() - cutoff_start) * 1000, 2)
            self.metrics["barge_in_cutoff_ms"] = cutoff_ms
            self.telemetry.record_barge_in(cutoff_ms)

            # Transition back to listening
            self.state = "LISTENING"
            self.audio_buffer.clear()
            self.user_speech_start_time = time.time()
            self.vad.reset_states()
            await self.send_state_update()
            return

        # Speech Turn Tracking
        if is_speech:
            if not self.audio_buffer:
                self.user_speech_start_time = time.time()
                self.state = "LISTENING"
                await self.send_state_update()

            self.audio_buffer.extend(pcm_chunk)
            await self.stt.send_audio_chunk(pcm_chunk)

        # Silence detected after speech (turn completion)
        elif len(self.audio_buffer) > (settings.SAMPLE_RATE * 0.5 * 2):
            if vad_res["consecutive_silence_frames"] >= (settings.SILENCE_TIMEOUT_MS // 32):
                self.user_speech_end_time = time.time()
                speech_bytes = bytes(self.audio_buffer)
                self.audio_buffer.clear()
                self.vad.reset_states()

                if self._active_turn_task and not self._active_turn_task.done():
                    self.cancellation_token.set()
                    self._active_turn_task.cancel()

                self._active_turn_task = asyncio.create_task(self._process_turn(speech_bytes))

    async def _stream_tts_sentence(
        self,
        sentence: str,
        turn_start_time: float,
        trace_id: str,
        span_id: str,
        child_traceparent: str,
        first_audio_sent: bool,
    ) -> bool:
        tts_start = time.perf_counter()
        async for audio_chunk in self.tts.stream_audio(sentence, self.cancellation_token):
            if self.cancellation_token.is_set():
                break

            if not first_audio_sent:
                first_audio_sent = True
                self.metrics["tts_ttfb_ms"] = round((time.perf_counter() - tts_start) * 1000, 1)
                self.metrics["total_e2e_ms"] = round((time.perf_counter() - turn_start_time) * 1000, 1)
                await self.send_json({
                    "type": "LATENCY_TELEMETRY",
                    "metrics": dict(self.metrics),
                    "otel": {
                        "traceparent": child_traceparent,
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "sla_budget_met": self.metrics["total_e2e_ms"] <= self.telemetry.sla_budget_ms,
                    },
                })

            await self.send_bytes(audio_chunk)
        return first_audio_sent

    async def _process_turn(self, speech_bytes: bytes):
        """Executes STT -> Safety Gate -> LLM -> Streaming TTS with OTel telemetry."""
        turn_start_time = time.perf_counter()
        trace_id, parent_span_id, span_id, child_traceparent = parse_or_create_traceparent(self.session_traceparent)
        self.state = "THINKING"
        self.cancellation_token.clear()
        await self.send_state_update()

        # Step A: STT Finalization
        stt_start = time.perf_counter()
        transcript = await self.stt.finalize_mock_speech()
        self.metrics["stt_ms"] = round((time.perf_counter() - stt_start) * 1000, 1)

        # Step B: Deterministic Control-Plane Safety & PII Gate
        safety = self.safety_gate.evaluate(transcript)

        await self.send_json({
            "type": "TRANSCRIPT",
            "role": "user",
            "text": safety.sanitized_text,
            "stt_ms": self.metrics["stt_ms"],
            "pii_redacted": safety.pii_redacted,
        })

        self.history.append({"role": "user", "content": safety.sanitized_text})

        self.state = "SPEAKING"
        await self.send_state_update()

        llm_start = time.perf_counter()
        first_token_received = False
        first_audio_sent = False
        agent_full_text = []

        try:
            if safety.verdict != "ALLOW":
                await self.send_json({
                    "type": "GUARDRAIL_EVENT",
                    "verdict": safety.verdict,
                    "reasons": safety.reasons,
                    "pii_redacted": safety.pii_redacted,
                    "trace_id": trace_id,
                })
                self.metrics["llm_ttft_ms"] = 0.0
                agent_full_text.append(safety.spoken_fallback)
                await self.send_json({"type": "AGENT_PARTIAL_TEXT", "text": safety.spoken_fallback})
                first_audio_sent = await self._stream_tts_sentence(
                    safety.spoken_fallback, turn_start_time, trace_id, span_id, child_traceparent, first_audio_sent
                )
            else:
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
                        "text": sentence,
                    })

                    first_audio_sent = await self._stream_tts_sentence(
                        sentence, turn_start_time, trace_id, span_id, child_traceparent, first_audio_sent
                    )

        except asyncio.CancelledError:
            logger.info("Active voice turn task cancelled cleanly.")
        except Exception as e:
            logger.error(f"Error in turn pipeline: {e}")

        if agent_full_text:
            complete_reply = " ".join(agent_full_text)
            self.history.append({"role": "assistant", "content": complete_reply})
            await self.send_json({
                "type": "TRANSCRIPT",
                "role": "assistant",
                "text": complete_reply,
            })

        total_e2e = self.metrics["total_e2e_ms"] or round((time.perf_counter() - turn_start_time) * 1000, 1)
        self.telemetry.record_turn(
            VoiceTurnSpan(
                trace_id=trace_id,
                span_id=span_id,
                parent_span_id=parent_span_id,
                vad_ms=self.metrics["vad_ms"],
                stt_ms=self.metrics["stt_ms"],
                llm_ttft_ms=self.metrics["llm_ttft_ms"],
                tts_ttfb_ms=self.metrics["tts_ttfb_ms"],
                total_e2e_ms=total_e2e,
                barge_in_cutoff_ms=self.metrics["barge_in_cutoff_ms"] or None,
                sla_budget_ms=self.telemetry.sla_budget_ms,
                sla_budget_met=total_e2e <= self.telemetry.sla_budget_ms,
                cancelled_by_barge_in=self.cancellation_token.is_set(),
                guardrail_verdict=safety.verdict,
                recorded_at=time.time(),
            )
        )

        if not self.cancellation_token.is_set():
            self.state = "LISTENING"
            await self.send_state_update()

    async def send_state_update(self):
        """Notify frontend of agent state changes."""
        await self.send_json({
            "type": "STATE_CHANGE",
            "state": self.state,
        })

    async def close(self):
        """Tear down session cleanly, cancelling any in-flight turn."""
        self.cancellation_token.set()
        if self._active_turn_task and not self._active_turn_task.done():
            self._active_turn_task.cancel()
            try:
                await self._active_turn_task
            except asyncio.CancelledError:
                pass
        await self.stt.close()
