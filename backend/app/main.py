import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.a2a_card import get_signed_agent_card
from app.api.websocket_endpoint import router as ws_router
from app.observability.telemetry import global_telemetry_registry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Full-Duplex Real-Time Voice Assistant API for Enterprise Platforms"
)

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ws_router)


@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "sample_rate": settings.SAMPLE_RATE,
        "vad_engine": "Silero VAD v5 (ONNX)",
        "mock_mode": settings.MOCK_MODE
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "mock_mode": settings.MOCK_MODE,
        "default_model": settings.DEFAULT_MODEL,
        "default_voice": settings.DEFAULT_VOICE
    }


@app.get("/metrics/slo")
def get_slo_metrics():
    return global_telemetry_registry.snapshot()


@app.get("/.well-known/agent-card.json")
def get_a2a_agent_card(request: Request):
    base_url = str(request.base_url).rstrip("/")
    return get_signed_agent_card(base_url=base_url, version=settings.VERSION)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
