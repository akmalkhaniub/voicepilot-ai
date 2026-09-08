import numpy as np
import pytest
from unittest.mock import MagicMock
from app.vad.silero_vad import SileroVAD


def test_vad_initialization():
    vad = SileroVAD(sample_rate=16000, threshold=0.5)
    assert vad.sample_rate == 16000
    assert vad.threshold == 0.5
    assert vad.is_speaking is False


def test_vad_process_silence():
    vad = SileroVAD()
    silent_chunk = np.zeros(512, dtype=np.int16).tobytes()
    res = vad.process_chunk(silent_chunk)
    
    assert "is_speech" in res
    assert "speech_prob" in res
    assert "barge_in" in res
    assert res["is_speech"] is False
    assert res["barge_in"] is False


def test_vad_speech_detection_and_bargein():
    vad = SileroVAD(threshold=0.5)
    
    # Mock the ONNX inference output to simulate active user speech
    mock_out = [np.array([[0.92]], dtype=np.float32)]
    mock_state = np.zeros((2, 1, 128), dtype=np.float32)
    vad.session = MagicMock()
    vad.session.run.return_value = (mock_out, mock_state)

    dummy_chunk = np.ones(512, dtype=np.int16).tobytes()
    
    # Frame 1: speech detected
    res1 = vad.process_chunk(dummy_chunk)
    assert res1["is_speech"] is True
    assert res1["speech_prob"] == pytest.approx(0.92, rel=1e-2)
    assert res1["consecutive_speech_frames"] == 1

    # Frame 2: consecutive speech -> triggers barge-in flag
    res2 = vad.process_chunk(dummy_chunk)
    assert res2["is_speech"] is True
    assert res2["barge_in"] is True
    assert res2["is_speaking"] is True


def test_vad_energy_fallback():
    vad = SileroVAD()
    vad.session = None  # Force energy-based fallback
    
    # Loud audio
    loud_data = np.ones(512, dtype=np.float32) * 0.5
    prob = vad._energy_vad(loud_data)
    assert prob > 0.5

    # Pure silence
    silent_data = np.zeros(512, dtype=np.float32)
    prob_silent = vad._energy_vad(silent_data)
    assert prob_silent == 0.0
