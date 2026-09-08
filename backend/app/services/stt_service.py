import asyncio
import json
import logging
import time
from typing import AsyncGenerator, Callable, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)


class STTService:
    """
    Real-Time Streaming Speech-to-Text Service.
    Supports Deepgram Nova-3 over WebSocket with automatic fallback to mock/local simulation.
    """

    def __init__(self, on_transcript_callback: Optional[Callable[[str, bool, float], None]] = None):
        self.on_transcript_callback = on_transcript_callback
        self.is_connected = False
        self._ws = None
        self._mock_responses = [
            "Hello, I am calling to check the status of my enterprise account.",
            "Can you help me schedule a technical demo for next Tuesday at 2 PM?",
            "What are your platform's features for speech-to-text and barge-in latency?",
            "I want to speak to human support regarding a billing question.",
            "That sounds great, thank you for your help!"
        ]
        self._mock_index = 0

    async def connect(self):
        """Establish connection to Deepgram Nova-3 streaming WebSocket if key available."""
        if settings.DEEPGRAM_API_KEY and not settings.MOCK_MODE:
            try:
                import websockets
                url = (
                    "wss://api.deepgram.com/v1/listen?"
                    "model=nova-3&encoding=linear16&sample_rate=16000&channels=1"
                    "&interim_results=true&smart_format=true&endpointing=300"
                )
                headers = {"Authorization": f"Token {settings.DEEPGRAM_API_KEY}"}
                self._ws = await websockets.connect(url, extra_headers=headers)
                self.is_connected = True
                logger.info("Connected to Deepgram Nova-3 streaming STT.")
                asyncio.create_task(self._listen_deepgram_responses())
                return
            except Exception as e:
                logger.warning(f"Failed to connect to Deepgram ({e}). Using mock/fallback STT.")
        
        self.is_connected = True
        logger.info("Using simulated low-latency STT engine.")

    async def _listen_deepgram_responses(self):
        """Receive and forward real-time transcripts from Deepgram."""
        try:
            async for message in self._ws:
                data = json.loads(message)
                channel = data.get("channel", {})
                alternatives = channel.get("alternatives", [{}])
                if alternatives:
                    transcript = alternatives[0].get("transcript", "")
                    is_final = data.get("is_final", False)
                    if transcript and self.on_transcript_callback:
                        self.on_transcript_callback(transcript, is_final, time.time())
        except Exception as e:
            logger.error(f"Error reading from Deepgram WebSocket: {e}")
            self.is_connected = False

    async def send_audio_chunk(self, chunk: bytes):
        """Send 16kHz PCM audio chunk to the STT provider."""
        if self._ws and not self._ws.closed:
            try:
                await self._ws.send(chunk)
            except Exception as e:
                logger.error(f"Error sending audio to Deepgram: {e}")

    async def finalize_mock_speech(self) -> str:
        """Simulate realistic STT transcription latency and output for mock mode."""
        # Realistic STT delay: 120ms - 180ms
        await asyncio.sleep(0.14)
        transcript = self._mock_responses[self._mock_index % len(self._mock_responses)]
        self._mock_index += 1
        return transcript

    async def close(self):
        """Close connection cleanly."""
        if self._ws and not self._ws.closed:
            await self._ws.close()
        self.is_connected = False
