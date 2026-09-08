import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.websocket_endpoint import router as ws_router

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
