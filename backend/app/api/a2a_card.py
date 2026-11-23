import base64
import hashlib
import hmac
import json
import os
from typing import Any, Dict


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _canonical_json(payload: Dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def build_agent_card_payload(base_url: str = "http://localhost:8000", version: str = "1.0.0") -> Dict[str, Any]:
    return {
        "protocolVersion": "1.0.0",
        "name": "VoicePilot AI",
        "description": "Full-duplex real-time enterprise voice assistant with sub-300ms latency, Silero VAD v5 barge-in cancellation, deterministic safety guardrails, and OTel SLO telemetry.",
        "url": f"{base_url.rstrip('/')}/ws/voice-agent",
        "version": version,
        "provider": {
            "organization": "VoicePilot Enterprise AI",
            "url": base_url.rstrip("/"),
        },
        "capabilities": {
            "streaming": True,
            "pushNotifications": False,
            "stateTransitionHistory": True,
        },
        "defaultInputModes": ["audio/pcm;rate=16000", "text/plain"],
        "defaultOutputModes": ["audio/pcm;rate=16000", "application/json"],
        "securitySchemes": {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
        },
        "skills": [
            {
                "id": "enterprise-voice-support",
                "name": "Enterprise Voice Support",
                "description": "Sub-300ms full-duplex conversational support with deterministic PII scrubbing and Tier-2 restraint escalation.",
                "tags": ["voice-ai", "full-duplex", "barge-in", "support"],
                "examples": [
                    "Check my enterprise account SLA status.",
                    "Schedule a technical product demonstration for Tuesday."
                ],
            },
            {
                "id": "realtime-barge-in-session",
                "name": "Instant Barge-In Voice Session",
                "description": "32ms PCM frame Silero VAD v5 interruption detection with <20ms audio queue flush.",
                "tags": ["silero-vad", "audioworklet", "low-latency"],
            },
        ],
    }


def sign_agent_card(card: Dict[str, Any], secret: str) -> Dict[str, Any]:
    """Attach an HS256 JWS signature block per A2A v1.0.0 Agent Card integrity signing."""
    unsigned = {k: v for k, v in card.items() if k != "signatures"}
    protected_header = _b64url(_canonical_json({"alg": "HS256", "typ": "JOSE+JSON"}))
    payload_b64 = _b64url(_canonical_json(unsigned))
    signing_input = f"{protected_header}.{payload_b64}".encode("ascii")
    sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()

    signed_card = dict(unsigned)
    signed_card["signatures"] = [
        {
            "protected": protected_header,
            "signature": _b64url(sig),
        }
    ]
    return signed_card


def verify_agent_card_signature(card: Dict[str, Any], secret: str) -> bool:
    signatures = card.get("signatures")
    if not isinstance(signatures, list) or not signatures:
        return False
    first = signatures[0]
    protected = first.get("protected")
    provided_sig = first.get("signature")
    if not isinstance(protected, str) or not isinstance(provided_sig, str):
        return False

    unsigned = {k: v for k, v in card.items() if k != "signatures"}
    payload_b64 = _b64url(_canonical_json(unsigned))
    signing_input = f"{protected}.{payload_b64}".encode("ascii")
    expected_sig = _b64url(hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest())
    return hmac.compare_digest(provided_sig, expected_sig)


def get_signed_agent_card(base_url: str = "http://localhost:8000", version: str = "1.0.0") -> Dict[str, Any]:
    secret = os.getenv("VOICEPILOT_A2A_SIGNING_KEY", "voicepilot-dev-a2a-signing-key")
    return sign_agent_card(build_agent_card_payload(base_url=base_url, version=version), secret=secret)
