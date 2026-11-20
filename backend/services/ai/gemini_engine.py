"""Gemini engine for the AI advisor. It uses the same instructions and tools as the Claude engine
(services.ai.tools); the google-genai SDK calls the tools itself (automatic function calling) and returns the final
answer. Returns None on a blocked or empty answer; API errors propagate and services.ai.ask() falls back to the
rules engine."""
import logging

from google import genai
from google.genai import types
from sqlalchemy.orm import Session

from core.config import settings as env
from models import Student
from services.ai import tools as advisor_tools

log = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 8
TIMEOUT_MS = 60_000  # google-genai takes the timeout in milliseconds

_client: genai.Client | None = None


def client() -> genai.Client:
    """Created once; reads GEMINI_API_KEY."""
    global _client
    if _client is None:
        _client = genai.Client(api_key=env.GEMINI_API_KEY, http_options=types.HttpOptions(timeout=TIMEOUT_MS))
    return _client


def _content(role: str, text: str) -> types.Content:
    return types.Content(role=role, parts=[types.Part.from_text(text=text)])


def answer(db: Session, student: Student, text: str, ctx: dict, history: list) -> dict | None:
    box = advisor_tools.build(db, student, ctx)

    # Earlier messages in the thread. Gemini calls the assistant role "model".
    past = [_content("model" if message.role == "assistant" else "user", message.text) for message in history]
    while past and past[0].role != "user":
        past.pop(0)

    chat = client().chats.create(
        model=env.GEMINI_MODEL,
        history=past,
        config=types.GenerateContentConfig(
            system_instruction="\n\n".join(advisor_tools.instructions(ctx)),
            tools=box.functions,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(maximum_remote_calls=MAX_TOOL_ROUNDS),
        ),
    )
    response = chat.send_message(advisor_tools.question(ctx, student, text))
    usage = response.usage_metadata
    input_tokens = (usage.prompt_token_count or 0) if usage else 0
    output_tokens = (usage.candidates_token_count or 0) if usage else 0
    log.info("Gemini answer (%s): %s input tokens, %s output tokens", env.GEMINI_MODEL, input_tokens, output_tokens)

    reply_text = (response.text or "").strip()
    if not reply_text:  # blocked by a safety filter, or still calling tools after MAX_TOOL_ROUNDS
        return None
    return {"kind": "answer", "text": reply_text, "payload": box.payload(),
            "input_tokens": input_tokens, "output_tokens": output_tokens}
