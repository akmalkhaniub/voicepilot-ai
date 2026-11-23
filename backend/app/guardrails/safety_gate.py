from dataclasses import dataclass
import re
from typing import List


@dataclass
class SafetyEvaluation:
    verdict: str  # ALLOW | BLOCK_INJECTION | RESTRAINT_ESCALATION
    sanitized_text: str
    reasons: List[str]
    spoken_fallback: str = ""
    pii_redacted: bool = False


INJECTION_PATTERNS = [
    (re.compile(r"\bignore\s+(all\s+)?(previous|prior|system)\s+instructions?\b", re.IGNORECASE), "PROMPT_INJECTION_OVERRIDE"),
    (re.compile(r"\breveal\s+(your\s+)?(system\s+prompt|hidden\s+instructions?|api\s+keys?)\b", re.IGNORECASE), "SYSTEM_PROMPT_EXFILTRATION"),
    (re.compile(r"\b(jailbreak|developer\s+mode|bypass\s+safety)\b", re.IGNORECASE), "SAFETY_BYPASS_ATTEMPT"),
]

RESTRAINT_PATTERNS = [
    (re.compile(r"\b(wire\s+transfer|send\s+\$?\d+.*without\s+verification|override\s+fraud)\b", re.IGNORECASE), "HIGH_RISK_FINANCIAL_ACTION"),
    (re.compile(r"\b(drop\s+(production\s+)?database|delete\s+all\s+(customer|user)\s+accounts)\b", re.IGNORECASE), "DESTRUCTIVE_ADMIN_COMMAND"),
    (re.compile(r"\b(export|dump)\s+all\s+(ssn|social\s+security|credit\s+cards?)\b", re.IGNORECASE), "BULK_PII_EXFILTRATION"),
]

PII_SCRUB_PATTERNS = [
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[REDACTED_SSN]"),
    (re.compile(r"\b(?:\d[ -]*?){13,16}\b"), "[REDACTED_PAN]"),
    (re.compile(r"\bBearer\s+[A-Za-z0-9._-]{12,}\b", re.IGNORECASE), "Bearer [REDACTED_TOKEN]"),
    (re.compile(r"\b(sk|gsk|dg)_[A-Za-z0-9_-]{12,}\b"), "[REDACTED_API_KEY]"),
]


class VoiceSafetyGate:
    """
    Deterministic control-plane safety & restraint gate executed prior to LLM streaming.
    Detects prompt injection, enforces restraint on high-risk commands, and scrubs PII.
    """

    def evaluate(self, transcript: str) -> SafetyEvaluation:
        cleaned = transcript.strip()
        pii_redacted = False

        for pattern, replacement in PII_SCRUB_PATTERNS:
            updated = pattern.sub(replacement, cleaned)
            if updated != cleaned:
                pii_redacted = True
                cleaned = updated

        reasons: List[str] = []
        for pattern, code in INJECTION_PATTERNS:
            if pattern.search(cleaned):
                reasons.append(code)

        if reasons:
            return SafetyEvaluation(
                verdict="BLOCK_INJECTION",
                sanitized_text=cleaned,
                reasons=reasons,
                spoken_fallback="I cannot follow instructions that alter my security rules. How can I assist with your account today?",
                pii_redacted=pii_redacted,
            )

        for pattern, code in RESTRAINT_PATTERNS:
            if pattern.search(cleaned):
                reasons.append(code)

        if reasons:
            return SafetyEvaluation(
                verdict="RESTRAINT_ESCALATION",
                sanitized_text=cleaned,
                reasons=reasons,
                spoken_fallback="That action requires verified human authorization. I am routing your request to a Tier-2 specialist now.",
                pii_redacted=pii_redacted,
            )

        return SafetyEvaluation(
            verdict="ALLOW",
            sanitized_text=cleaned,
            reasons=[],
            pii_redacted=pii_redacted,
        )
