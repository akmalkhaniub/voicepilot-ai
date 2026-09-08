import asyncio
import json
import logging
import re
import time
from typing import AsyncGenerator, Dict, List, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are VoicePilot, an ultra-fast, professional AI Voice Assistant for CloudPSO Enterprise.
Keep responses direct, natural, conversational, and concise (1 to 2 sentences per turn), as they will be spoken aloud via TTS.
Avoid bullet points, special markdown symbols, or long lists. Speak warmly and efficiently.
You have access to tools for customer account lookup and appointment scheduling."""

# Sentence boundary regex for streaming TTS chunking
SENTENCE_SPLIT_REGEX = re.compile(r'([.!?]+[\s]+|[\n]+)')


class LLMService:
    """
    Streaming NLU and Reasoning Engine.
    Powered by Groq API (Llama 3.3 70B / 3.1 8B) with sentence-by-sentence streaming for TTS.
    """

    def __init__(self):
        self.client = None
        self._init_client()

    def _init_client(self):
        if settings.GROQ_API_KEY and not settings.MOCK_MODE:
            try:
                from groq import AsyncGroq
                self.client = AsyncGroq(api_key=settings.GROQ_API_KEY)
                logger.info("Groq Async client initialized.")
            except Exception as e:
                logger.warning(f"Failed to initialize Groq client: {e}")
                self.client = None

    async def stream_response(
        self,
        messages: List[Dict[str, str]],
        cancellation_token: Optional[asyncio.Event] = None
    ) -> AsyncGenerator[str, None]:
        """
        Yields complete sentences/clauses as soon as generated for immediate TTS streaming.
        Stops immediately if cancellation_token is set (barge-in).
        """
        buffer = ""

        if self.client and not settings.MOCK_MODE:
            try:
                chat_completion = await self.client.chat.completions.create(
                    model=settings.DEFAULT_MODEL,
                    messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
                    temperature=0.6,
                    max_tokens=200,
                    stream=True,
                )

                async for chunk in chat_completion:
                    if cancellation_token and cancellation_token.is_set():
                        logger.info("LLM generation cancelled by barge-in.")
                        break

                    delta = chunk.choices[0].delta.content or ""
                    if not delta:
                        continue

                    buffer += delta

                    # Check if buffer contains a completed sentence
                    splits = SENTENCE_SPLIT_REGEX.split(buffer)
                    if len(splits) > 1:
                        # Yield the completed sentence with its delimiter
                        sentence = splits[0] + splits[1]
                        buffer = "".join(splits[2:])
                        if sentence.strip():
                            yield sentence.strip()

                if buffer.strip() and not (cancellation_token and cancellation_token.is_set()):
                    yield buffer.strip()
                return
            except Exception as e:
                logger.error(f"Error calling Groq API: {e}. Falling back to simulation.")

        # High-Fidelity Mock Streaming Engine (Simulates sub-100ms TTFT)
        user_query = messages[-1]["content"] if messages else ""
        mock_reply = self._generate_mock_reply(user_query)

        # Split mock reply into words and stream realistically
        words = mock_reply.split(" ")
        current_sentence = []

        for word in words:
            if cancellation_token and cancellation_token.is_set():
                logger.info("Mock LLM generation cancelled by barge-in.")
                break

            await asyncio.sleep(0.035)  # ~35ms per token simulation
            current_sentence.append(word)

            if word.endswith((".", "!", "?")):
                yield " ".join(current_sentence)
                current_sentence = []

        if current_sentence and not (cancellation_token and cancellation_token.is_set()):
            yield " ".join(current_sentence)

    def _generate_mock_reply(self, user_query: str) -> str:
        q = user_query.lower()
        if "account" in q or "status" in q:
            return "I've checked your CloudPSO enterprise account. Your tier is Active with 99.99% SLA uptime."
        elif "schedule" in q or "demo" in q or "appointment" in q:
            return "Certainly! I've reserved a technical demonstration slot for your team for next Tuesday at 2 PM EST."
        elif "latency" in q or "barge-in" in q or "speech" in q:
            return "Our platform runs Silero VAD on ONNX and streams audio in 32ms frames to guarantee sub-300 millisecond response times."
        elif "human" in q or "support" in q:
            return "I am initiating a live transfer to our Tier-2 engineering support desk right now."
        else:
            return "I understand completely. Our real-time voice pipeline is listening and ready to assist you with any questions."

    def execute_tool(self, tool_name: str, arguments: dict) -> dict:
        """Simulated enterprise CRM / Support tool execution."""
        if tool_name == "lookup_customer_account":
            return {
                "account_id": arguments.get("account_id", "ENT-9842"),
                "status": "Active Platinum",
                "open_tickets": 0,
                "assigned_csm": "Sarah Jenkins"
            }
        elif tool_name == "schedule_appointment":
            return {
                "status": "confirmed",
                "slot": arguments.get("slot", "Tuesday 2:00 PM EST"),
                "confirmation_code": "VP-58291"
            }
        return {"status": "success"}
