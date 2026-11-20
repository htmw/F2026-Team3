"""Claude engine for the AI advisor (spec 13). Claude answers only from tool results; the instructions and tools are
shared with the Gemini engine (services.ai.tools). Returns None on a refusal or an empty answer; API errors propagate
and services.ai.ask() falls back to the rules engine."""
import logging

import anthropic
from anthropic import beta_tool
from sqlalchemy.orm import Session

from models import Student
from services.ai import tools as advisor_tools

log = logging.getLogger(__name__)

MODEL = "claude-opus-5-5"
MAX_TOOL_ROUNDS = 8

_client: anthropic.Anthropic | None = None


def client() -> anthropic.Anthropic:
    """Created once; reads ANTHROPIC_API_KEY. One retry, 60 s timeout per attempt."""
    global _client
    if _client is None:
        _client = anthropic.Anthropic(timeout=60, max_retries=1)
    return _client


def answer(db: Session, student: Student, text: str, ctx: dict, history: list) -> dict | None:
    box = advisor_tools.build(db, student, ctx)

    messages = [{"role": message.role, "content": message.text} for message in history]
    while messages and messages[0]["role"] != "user":
        messages.pop(0)
    messages.append({"role": "user", "content": advisor_tools.question(ctx, student, text)})

    runner = client().beta.messages.tool_runner(
        model=MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        output_config={"effort": "low"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        cache_control={"type": "ephemeral"},
        system=[{"type": "text", "text": part} for part in advisor_tools.instructions(ctx)],
        tools=[beta_tool(function) for function in box.functions],
        messages=messages,
        max_iterations=MAX_TOOL_ROUNDS,
    )
    final, input_tokens, output_tokens, cache_read = None, 0, 0, 0
    for message in runner:
        final = message
        usage = message.usage
        input_tokens += (usage.input_tokens or 0) + (usage.cache_creation_input_tokens or 0) + (usage.cache_read_input_tokens or 0)
        output_tokens += usage.output_tokens or 0
        cache_read += usage.cache_read_input_tokens or 0
    log.info("Claude answer: %s input tokens (%s from cache), %s output tokens", input_tokens, cache_read, output_tokens)

    if final is None or final.stop_reason == "refusal":
        return None
    reply_text = "".join(block.text for block in final.content if block.type == "text").strip()
    if not reply_text:
        return None
    return {"kind": "answer", "text": reply_text, "payload": box.payload(),
            "input_tokens": input_tokens, "output_tokens": output_tokens}
