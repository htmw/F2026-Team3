"""AI advisor (spec 13). ask() runs one question: settings and daily limit, the blocked-topic guard, then the
Claude engine (when configured) with the rules engine as fallback, plan validation, and saving both messages.
test_answer() is the admin test box (spec 34): the same answer path with unsaved settings, storing nothing."""
import logging

import anthropic
from sqlalchemy.orm import Session

from core.errors import ApiError, not_found
from core.time import now
from models import AiMessage, AiThread, Student, User
from services.ai import claude_engine, context, guard, plans, quota, rules_engine, threads
from services.ai import settings as ai_config

log = logging.getLogger(__name__)

SLOW_NOTE = "(Answered from your records — the AI service was slow.)"


def _engine_answer(db: Session, student: Student, label: str, text: str, ctx: dict, history: list) -> dict:
    if ctx["engine"] == "Claude":
        try:
            result = claude_engine.answer(db, student, text, ctx, history)
            if result is not None:
                return {**result, "engine": "Claude"}
            log.warning("Claude declined or gave no answer for %s; using the rules engine", label)
        except anthropic.APITimeoutError:
            log.warning("Claude timed out for %s; using the rules engine", label)
            result = rules_engine.answer(db, student, text, ctx)
            return {**result, "text": f"{result['text']}\n\n{SLOW_NOTE}", "engine": "Rules"}
        except Exception:
            log.exception("Claude engine failed for %s; using the rules engine", label)
    return {**rules_engine.answer(db, student, text, ctx), "engine": "Rules"}


def _clean_payload(db: Session, payload: dict | None) -> dict:
    payload = dict(payload or {})
    if payload.get("plan"):
        payload["plan"] = plans.validate(db, payload["plan"], payload.get("planTerm"))
    if not payload.get("plan"):
        payload.pop("plan", None)
        payload.pop("planTerm", None)
    return payload


def _answer(db: Session, student: Student, text: str, ctx: dict, history: list, label: str) -> dict:
    """Guard, then an engine; the result has a validated payload and the engine that answered."""
    result = guard.check(text, ctx["settings"]["blockedTopics"])
    if result is not None:
        result["engine"] = "Rules"  # no model call for blocked topics
    else:
        result = _engine_answer(db, student, label, text, ctx, history)
    return {**result, "payload": _clean_payload(db, result.get("payload"))}


def ask(db: Session, student: Student, text: str, thread_id: int | None = None) -> tuple[AiThread, AiMessage, AiMessage]:
    ctx = context.build(db, student)
    cfg = ctx["settings"]
    if not cfg["features"]["advisor"]:
        raise ApiError(403, "AI_DISABLED", "The AI advisor is turned off for your school.")
    limit = cfg["dailyLimit"]
    if quota.remaining_today(db, student, limit) <= 0:
        raise ApiError(429, "DAILY_LIMIT", f"You've used today's {limit} questions. They reset at midnight.")

    thread = threads.get_thread(db, student, thread_id) if thread_id else threads.new_thread(db, student, text)
    past = threads.history(db, thread)
    question = AiMessage(thread_id=thread.id, role="user", text=text, created_at=now())
    db.add(question)
    db.flush()

    result = _answer(db, student, text, ctx, past, f"thread {thread.id}")
    reply = AiMessage(thread_id=thread.id, role="assistant", kind=result.get("kind", "answer"), text=result["text"],
                      payload=result["payload"], engine=result["engine"],
                      input_tokens=result.get("input_tokens"), output_tokens=result.get("output_tokens"),
                      created_at=now())
    db.add(reply)
    thread.updated_at = reply.created_at
    db.commit()
    return thread, question, reply


def test_answer(db: Session, user_id: int, text: str, patch: dict | None) -> dict:
    """Answers `text` as the student with this user id, using the stored settings with `patch` laid over them.
    No thread, no quota, nothing saved; a turned-off advisor still answers and reports advisorOn false."""
    user = db.get(User, user_id)
    student = db.query(Student).filter(Student.user_id == user_id).one_or_none() if user and user.role == "student" else None
    if student is None:
        raise not_found("Student")
    cfg = ai_config.merge(ai_config.ai_settings(db), patch)
    result = _answer(db, student, text, context.build(db, student, cfg), [], "the admin test")
    db.rollback()  # the engines only read; this guarantees a test never leaves anything behind
    reply = AiMessage(id=0, role="assistant", kind=result.get("kind", "answer"), text=result["text"],
                      payload=result["payload"], engine=result["engine"], created_at=now())
    return {"engine": result["engine"], "advisorOn": cfg["features"]["advisor"], "reply": threads.message_out(reply)}
