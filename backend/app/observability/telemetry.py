from collections import deque
from dataclasses import asdict, dataclass
import math
import re
import secrets
import threading
import time
from typing import Deque, Dict, Optional, Tuple


TRACEPARENT_RE = re.compile(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$", re.IGNORECASE)


def parse_or_create_traceparent(traceparent: Optional[str] = None) -> Tuple[str, Optional[str], str, str]:
    """
    Parse incoming W3C traceparent or mint a fresh trace_id.
    Always mints a new child span_id for local execution.
    Returns (trace_id, parent_span_id, span_id, child_traceparent).
    """
    span_id = secrets.token_hex(8)
    if traceparent:
        match = TRACEPARENT_RE.match(traceparent.strip())
        if match:
            trace_id, parent_span_id, flags = match.groups()
            if trace_id != "0" * 32 and parent_span_id != "0" * 16:
                t_id = trace_id.lower()
                p_id = parent_span_id.lower()
                f_hex = flags.lower()
                return t_id, p_id, span_id, f"00-{t_id}-{span_id}-{f_hex}"

    trace_id = secrets.token_hex(16)
    return trace_id, None, span_id, f"00-{trace_id}-{span_id}-01"


@dataclass
class VoiceTurnSpan:
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    vad_ms: float
    stt_ms: float
    llm_ttft_ms: float
    tts_ttfb_ms: float
    total_e2e_ms: float
    barge_in_cutoff_ms: Optional[float]
    sla_budget_ms: float
    sla_budget_met: bool
    cancelled_by_barge_in: bool
    guardrail_verdict: str
    recorded_at: float

    def to_otel_dict(self) -> Dict[str, object]:
        return {
            "name": "voicepilot.voice_turn",
            "attributes": {
                "gen_ai.operation.name": "voice_turn",
                "voice.sla.budget_ms": self.sla_budget_ms,
                "voice.sla.budget_met": self.sla_budget_met,
                "voice.barge_in.cancelled": self.cancelled_by_barge_in,
                "voice.guardrail.verdict": self.guardrail_verdict,
                **asdict(self),
            },
        }


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return round(sorted_values[0], 2)
    idx = math.ceil((pct / 100.0) * len(sorted_values)) - 1
    idx = max(0, min(idx, len(sorted_values) - 1))
    return round(sorted_values[idx], 2)


class VoiceTelemetryRegistry:
    """Thread-safe rolling telemetry & SLO aggregator for real-time voice sessions."""

    def __init__(self, max_spans: int = 500, sla_budget_ms: float = 300.0):
        self._spans: Deque[VoiceTurnSpan] = deque(maxlen=max_spans)
        self._barge_in_cutoffs_ms: Deque[float] = deque(maxlen=max_spans)
        self._lock = threading.Lock()
        self.sla_budget_ms = sla_budget_ms
        self._total_barge_ins = 0
        self._guardrail_blocks = 0

    def record_turn(self, span: VoiceTurnSpan) -> None:
        with self._lock:
            self._spans.append(span)
            if span.guardrail_verdict != "ALLOW":
                self._guardrail_blocks += 1

    def record_barge_in(self, cutoff_ms: float) -> None:
        with self._lock:
            self._total_barge_ins += 1
            self._barge_in_cutoffs_ms.append(round(cutoff_ms, 2))

    def snapshot(self) -> Dict[str, object]:
        with self._lock:
            spans = list(self._spans)
            cutoffs = sorted(self._barge_in_cutoffs_ms)
            total_barge_ins = self._total_barge_ins
            guardrail_blocks = self._guardrail_blocks

        e2e_values = sorted(s.total_e2e_ms for s in spans if s.total_e2e_ms > 0)
        sla_evaluated = [s for s in spans if s.total_e2e_ms > 0]
        sla_passed = sum(1 for s in sla_evaluated if s.sla_budget_met)
        sla_pass_rate = round((sla_passed / len(sla_evaluated)) * 100.0, 2) if sla_evaluated else 100.0

        return {
            "service": "voicepilot-ai",
            "sla_budget_ms": self.sla_budget_ms,
            "total_turns": len(spans),
            "total_barge_ins": total_barge_ins,
            "guardrail_interventions": guardrail_blocks,
            "sla_pass_rate_pct": sla_pass_rate,
            "latency_ms": {
                "p50_e2e_ms": _percentile(e2e_values, 50),
                "p95_e2e_ms": _percentile(e2e_values, 95),
                "p95_barge_in_cutoff_ms": _percentile(cutoffs, 95),
            },
            "recent_traces": [
                {
                    "trace_id": s.trace_id,
                    "span_id": s.span_id,
                    "total_e2e_ms": s.total_e2e_ms,
                    "sla_budget_met": s.sla_budget_met,
                    "guardrail_verdict": s.guardrail_verdict,
                    "recorded_at": s.recorded_at,
                }
                for s in spans[-10:]
            ],
        }


global_telemetry_registry = VoiceTelemetryRegistry()
