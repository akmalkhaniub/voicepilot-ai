import asyncio
import numpy as np
import pytest
from unittest.mock import MagicMock
from app.orchestrator.pipeline import VoiceSessionPipeline


@pytest.mark.asyncio
async def test_pipeline_barge_in_cancellation():
    sent_json_messages = []
    sent_bytes_chunks = []

    async def mock_send_json(data):
        sent_json_messages.append(data)

    async def mock_send_bytes(chunk):
        sent_bytes_chunks.append(chunk)

    pipeline = VoiceSessionPipeline(mock_send_json, mock_send_bytes)
    await pipeline.start()

    assert pipeline.state == "LISTENING"

    # Simulate agent currently in SPEAKING state
    pipeline.state = "SPEAKING"
    assert not pipeline.cancellation_token.is_set()

    # Mock VAD to simulate user speech triggering barge-in
    pipeline.vad.process_chunk = MagicMock(return_value={
        "is_speech": True,
        "speech_prob": 0.95,
        "barge_in": True,
        "is_speaking": True,
        "consecutive_speech_frames": 2,
        "consecutive_silence_frames": 0
    })

    dummy_chunk = np.zeros(512, dtype=np.int16).tobytes()
    await pipeline.handle_audio_frame(dummy_chunk)

    # Verify cancellation token was tripped and interrupt message sent
    assert pipeline.cancellation_token.is_set()
    interrupt_events = [m for m in sent_json_messages if m.get("type") == "INTERRUPT"]
    assert len(interrupt_events) == 1
    assert interrupt_events[0]["reason"] == "user_barge_in"
    assert pipeline.state == "LISTENING"

    await pipeline.close()
