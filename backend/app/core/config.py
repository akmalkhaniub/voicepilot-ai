import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    PROJECT_NAME: str = "VoicePilot AI"
    VERSION: str = "1.0.0"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    SAMPLE_RATE: int = 16000
    CHUNK_SIZE: int = 512  # 32ms window at 16kHz for Silero VAD
    VAD_THRESHOLD: float = 0.5
    SILENCE_TIMEOUT_MS: int = 400
    
    # Cloud Inference Keys
    GROQ_API_KEY: Optional[str] = None
    DEEPGRAM_API_KEY: Optional[str] = None
    CARTESIA_API_KEY: Optional[str] = None
    
    MOCK_MODE: bool = False
    DEFAULT_MODEL: str = "llama-3.3-70b-versatile"
    DEFAULT_VOICE: str = "sonic-english"


settings = Settings()

# Automatically fallback to mock mode if critical keys are missing
if not settings.GROQ_API_KEY:
    settings.MOCK_MODE = True
