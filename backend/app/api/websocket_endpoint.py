import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.orchestrator.pipeline import VoiceSessionPipeline

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/voice-agent")
async def websocket_voice_agent_endpoint(websocket: WebSocket):
    """
    Bi-directional full-duplex WebSocket endpoint for real-time voice streaming.
    Receives:
      - Binary frames: Raw 16kHz 16-bit mono PCM chunks from AudioWorklet.
      - Text frames: Control JSON (e.g. {"action": "ping"}, {"action": "reset"}).
    Sends:
      - Binary frames: Synthesized 16kHz audio chunks.
      - Text frames: JSON telemetry (transcripts, latency, barge-in events).
    """
    await websocket.accept()
    logger.info("Client connected to voice-agent WebSocket.")

    pipeline = VoiceSessionPipeline(
        send_json_fn=lambda data: websocket.send_text(json.dumps(data)),
        send_bytes_fn=lambda chunk: websocket.send_bytes(chunk)
    )

    await pipeline.start()

    try:
        while True:
            message = await websocket.receive()
            if "bytes" in message and message["bytes"]:
                # Audio frame received
                await pipeline.handle_audio_frame(message["bytes"])
            elif "text" in message and message["text"]:
                # Control frame received
                try:
                    payload = json.loads(message["text"])
                    action = payload.get("action")
                    if action == "reset":
                        pipeline.vad.reset_states()
                    elif action == "ping":
                        await websocket.send_text(json.dumps({"type": "pong"}))
                except json.JSONDecodeError:
                    pass

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected normally.")
    except Exception as e:
        logger.error(f"WebSocket session error: {e}")
    finally:
        await pipeline.close()
