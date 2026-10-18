"""AI conversations: listing, reading, deleting, ratings and flags. Questions go through services.ai.ask()."""
from sqlalchemy.orm import Session

from core.errors import bad_request, conflict, not_found
from core.time import iso_z
from models import AiFlag, AiMessage, AiThread, Student

TITLE_LENGTH = 60
HISTORY_LENGTH = 10


def title_for(text: str) -> str:
    """The question's first 60 characters, cut at a word boundary."""
    text = " ".join(text.split())
    if len(text) <= TITLE_LENGTH:
        return text
    cut = text[:TITLE_LENGTH]
    if " " in cut and text[TITLE_LENGTH] != " ":
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(" ,.;:-")


def thread_out(thread: AiThread) -> dict:
    return {"id": thread.id, "title": thread.title, "updated_at": iso_z(thread.updated_at)}


def message_out(message: AiMessage) -> dict:
    payload = message.payload or {}
    return {
        "id": message.id,
        "role": message.role,
        "kind": message.kind,
        "text": message.text,
        "created_at": iso_z(message.created_at),
        "plan_term": payload.get("planTerm"),
        "plan": payload.get("plan") or [],
        "follow": payload.get("follow"),
        "actions": payload.get("actions") or [],
        "sources": payload.get("sources") or [],
        "rating": message.rating,
    }


def list_threads(db: Session, student: Student) -> list[dict]:
    rows = (db.query(AiThread).filter(AiThread.student_id == student.student_id)
            .order_by(AiThread.updated_at.desc(), AiThread.id.desc()).all())
    return [thread_out(thread) for thread in rows]


def get_thread(db: Session, student: Student, thread_id: int) -> AiThread:
    thread = db.query(AiThread).filter(AiThread.id == thread_id, AiThread.student_id == student.student_id).one_or_none()
    if thread is None:
        raise not_found("Conversation")
    return thread


def messages_of(db: Session, thread: AiThread) -> list[AiMessage]:
    return (db.query(AiMessage).filter(AiMessage.thread_id == thread.id)
            .order_by(AiMessage.created_at, AiMessage.id).all())


def history(db: Session, thread: AiThread) -> list[AiMessage]:
    """The thread's last messages, oldest first (context for the Claude engine)."""
    return messages_of(db, thread)[-HISTORY_LENGTH:]


def thread_detail(db: Session, student: Student, thread_id: int) -> dict:
    thread = get_thread(db, student, thread_id)
    return {"thread": thread_out(thread), "messages": [message_out(message) for message in messages_of(db, thread)]}


def new_thread(db: Session, student: Student, text: str) -> AiThread:
    thread = AiThread(student_id=student.student_id, title=title_for(text))
    db.add(thread)
    db.flush()
    return thread


def delete_thread(db: Session, student: Student, thread_id: int) -> None:
    """Messages go with the thread (FK cascade); flags keep their text snapshots (message_id becomes null)."""
    db.delete(get_thread(db, student, thread_id))
    db.commit()


def delete_all(db: Session, student: Student) -> None:
    db.query(AiThread).filter(AiThread.student_id == student.student_id).delete(synchronize_session=False)
    db.commit()


def _own_message(db: Session, student: Student, message_id: int) -> AiMessage:
    message = (db.query(AiMessage).join(AiThread, AiMessage.thread_id == AiThread.id)
               .filter(AiMessage.id == message_id, AiThread.student_id == student.student_id).one_or_none())
    if message is None:
        raise not_found("Message")
    return message


def rate(db: Session, student: Student, message_id: int, helpful: bool | None) -> None:
    message = _own_message(db, student, message_id)
    if message.role != "assistant":
        raise bad_request("Only answers can be rated.")
    message.rating = None if helpful is None else (1 if helpful else -1)
    db.commit()


def flag(db: Session, student: Student, message_id: int, issue: str) -> int:
    message = _own_message(db, student, message_id)
    if message.role != "assistant":
        raise bad_request("Only answers can be reported.")
    existing = db.query(AiFlag).filter(AiFlag.message_id == message.id, AiFlag.student_id == student.student_id).first()
    if existing is not None:
        raise conflict("You've already reported this answer.")
    question = (db.query(AiMessage).filter(AiMessage.thread_id == message.thread_id, AiMessage.role == "user",
                                           AiMessage.id < message.id)
                .order_by(AiMessage.id.desc()).first())
    row = AiFlag(message_id=message.id, student_id=student.student_id, question=question.text if question else "",
                 answer=message.text, issue=issue, source="student", status="Open")
    db.add(row)
    db.commit()
    return row.id
