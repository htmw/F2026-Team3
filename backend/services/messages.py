"""Messages (spec 16): conversations between users plus each user's read-only Acadmate notifications.
Shared by students, advisors (spec 25) and admins. Other features post notices with notify()."""
from datetime import date, datetime, timedelta

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from core.errors import ApiError, forbidden, not_found
from core.time import iso_z, local_zone, now, short_date, today
from models import (Advisor, AdvisorStudentAssignment, Conversation, ConversationParticipant, Course, CourseSection,
                    Enrollment, Message, Student, User)
from services.auth import user_payload
from services.catalog import current_term

CONTACT_LIMIT = 20
PREVIEW_LENGTH = 120
SYSTEM_NAME = "Acadmate"
DEFAULT_GROUP_TITLE = "Group"
READ_ONLY_MESSAGE = "Automated notifications can't be replied to."


# --- time labels ------------------------------------------------------------------------------------------------

def _local(value: datetime) -> datetime:
    return value.astimezone(local_zone())


def format_time(value: datetime, day: date | None = None) -> str:
    """Conversation row time: "09:42" today, "Yesterday", else "Sep 29" (school time zone; day defaults to today())."""
    day = day or today()
    local = _local(value)
    if local.date() == day:
        return local.strftime("%H:%M")
    if local.date() == day - timedelta(days=1):
        return "Yesterday"
    return short_date(local.date())


def message_time(value: datetime, day: date | None = None) -> str:
    """Bubble time: "09:42", "Yesterday 16:05" or "Sep 29 10:00"."""
    label = format_time(value, day)
    clock = _local(value).strftime("%H:%M")
    return label if label == clock else f"{label} {clock}"


# --- who the viewer is to other people --------------------------------------------------------------------------

def _initials(user: User) -> str:
    return user_payload(user)["initials"]


def _student_of(db: Session, user: User) -> Student | None:
    if user.role != "student":
        return None
    return db.query(Student).filter(Student.user_id == user.user_id).one_or_none()


def _current_section_ids(db: Session, student: Student) -> list[int]:
    term = current_term(db)
    if term is None:
        return []
    rows = (db.query(Enrollment.section_id)
            .filter(Enrollment.student_id == student.student_id, Enrollment.status == "in_progress",
                    Enrollment.term == term.name, Enrollment.section_id.isnot(None))
            .all())
    return [section_id for section_id, in rows]


class _Viewer:
    """The relationships that decide a user's contacts and the role line shown for other people."""

    def __init__(self, db: Session, user: User):
        self.user = user
        self.advisors: set[int] = set()        # user ids of the student's assigned advisors
        self.instructors: dict[int, str] = {}  # instructor user id -> "CS 608 · Algorithms & Computing Theory"
        self.classmates: set[int] = set()      # user ids of students in the same current sections
        self.advisees: set[int] = set()        # user ids of an advisor's assigned students

        student = _student_of(db, user)
        if student is not None:
            self.advisors = {user_id for user_id, in (
                db.query(Advisor.user_id).join(AdvisorStudentAssignment, AdvisorStudentAssignment.advisor_id == Advisor.advisor_id)
                .filter(AdvisorStudentAssignment.student_id == student.student_id))}
            section_ids = _current_section_ids(db, student)
            if section_ids:
                for section, course in (db.query(CourseSection, Course).join(Course, CourseSection.course_id == Course.course_id)
                                        .filter(CourseSection.id.in_(section_ids), CourseSection.instructor_user_id.isnot(None))
                                        .order_by(Course.course_code)):
                    self.instructors.setdefault(section.instructor_user_id, f"{course.course_code} · {course.course_name}")
                self.classmates = {user_id for user_id, in (
                    db.query(Student.user_id).join(Enrollment, Enrollment.student_id == Student.student_id)
                    .filter(Enrollment.section_id.in_(section_ids), Enrollment.status == "in_progress",
                            Student.student_id != student.student_id))}
        elif user.role == "advisor":
            advisor = db.query(Advisor).filter(Advisor.user_id == user.user_id).one_or_none()
            if advisor is not None:
                self.advisees = {user_id for user_id, in (
                    db.query(Student.user_id).join(AdvisorStudentAssignment, AdvisorStudentAssignment.student_id == Student.student_id)
                    .filter(AdvisorStudentAssignment.advisor_id == advisor.advisor_id))}

    def label_for(self, other: User) -> str | None:
        """"Faculty advisor", "CS 608 · …", "Classmate", "Advisee", or the user's own title."""
        if other.user_id in self.advisors:
            return "Faculty advisor"
        if other.user_id in self.instructors:
            return self.instructors[other.user_id]
        if other.user_id in self.advisees:
            return "Advisee"
        if other.user_id in self.classmates:
            return "Classmate"
        return other.title

    def role_line(self, other: User) -> str:
        return self.label_for(other) or other.role.capitalize()


def _contact_query(db: Session, viewer: _Viewer):
    user = viewer.user
    query = db.query(User).filter(User.is_active.is_(True), User.user_id != user.user_id)
    if user.role == "student":
        known = viewer.advisors | set(viewer.instructors) | viewer.classmates
        return query.filter(or_(User.user_id.in_(known), and_(User.role == "admin", User.is_support.is_(True))))
    if user.role == "advisor":
        return query.filter(or_(User.user_id.in_(viewer.advisees), User.role.in_(("advisor", "admin"))))
    return query  # admins may message everyone


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def contacts(db: Session, user: User, q: str | None = None) -> list[dict]:
    viewer = _Viewer(db, user)
    query = _contact_query(db, viewer)
    if q:
        query = query.filter(User.name.ilike(f"%{_escape_like(q)}%", escape="\\"))
    return [{"id": other.user_id, "name": other.name, "initials": _initials(other), "role": other.role,
             "title": viewer.label_for(other)}
            for other in query.order_by(User.name, User.user_id).limit(CONTACT_LIMIT)]


# --- conversations ----------------------------------------------------------------------------------------------

def _unread_filter(user_id: int):
    """Messages of the joined participant row that the user hasn't read (their own messages never count)."""
    return and_(or_(Message.sender_id.is_(None), Message.sender_id != user_id),
                or_(ConversationParticipant.last_read_at.is_(None), Message.created_at > ConversationParticipant.last_read_at))


def _unread_by_conversation(db: Session, user: User, ids: list[int]) -> dict[int, int]:
    rows =(db.query(Message.conversation_id, func.count(Message.id))
            .join(ConversationParticipant, and_(ConversationParticipant.conversation_id == Message.conversation_id,
                                                ConversationParticipant.user_id == user.user_id))
            .filter(Message.conversation_id.in_(ids), _unread_filter(user.user_id))
            .group_by(Message.conversation_id))
    return dict(rows.all())


def unread_count(db: Session, user: User) -> int:
    """Unread messages across all the user's conversations (the sidebar badge)."""
    return (db.query(Message.id)
            .join(ConversationParticipant, and_(ConversationParticipant.conversation_id == Message.conversation_id,
                                                ConversationParticipant.user_id == user.user_id))
            .filter(_unread_filter(user.user_id))
            .count())


def _preview(message: Message | None, user: User) -> str | None:
    if message is None:
        return None
    text = " ".join(message.text.split())
    if len(text) > PREVIEW_LENGTH:
        text = text[:PREVIEW_LENGTH].rstrip() + "…"
    return f"You: {text}" if message.sender_id == user.user_id else text


def list_for(db: Session, user: User, q: str | None = None) -> list[dict]:
    """The user's conversations, newest activity first. q matches the conversation's name, title or any message."""
    conversations = (db.query(Conversation)
                     .join(ConversationParticipant, ConversationParticipant.conversation_id == Conversation.id)
                     .filter(ConversationParticipant.user_id == user.user_id)
                     .order_by(Conversation.last_message_at.desc(), Conversation.id.desc())
                     .all())
    if not conversations:
        return []
    ids = [conversation.id for conversation in conversations]

    rank = func.row_number().over(partition_by=Message.conversation_id,
                                  order_by=(Message.created_at.desc(), Message.id.desc())).label("rank")
    ranked = db.query(Message.id.label("id"), rank).filter(Message.conversation_id.in_(ids)).subquery()
    last = {message.conversation_id: message for message in (
        db.query(Message).join(ranked, ranked.c.id == Message.id).filter(ranked.c.rank == 1))}
    unread = _unread_by_conversation(db, user, ids)
    members: dict[int, list[User]] = {conversation_id: [] for conversation_id in ids}
    for participant, member in (db.query(ConversationParticipant, User).join(User, User.user_id == ConversationParticipant.user_id)
                                .filter(ConversationParticipant.conversation_id.in_(ids))
                                .order_by(User.name)):
        members[participant.conversation_id].append(member)

    text_matches: set[int] = set()
    if q:
        text_matches = {conversation_id for conversation_id, in (
            db.query(Message.conversation_id).filter(Message.conversation_id.in_(ids),
                                                     Message.text.ilike(f"%{_escape_like(q)}%", escape="\\"))
            .distinct())}

    viewer = _Viewer(db, user)
    rows = []
    for conversation in conversations:
        row = _row(conversation, members[conversation.id], last.get(conversation.id), unread.get(conversation.id, 0), viewer)
        if q and conversation.id not in text_matches and not _row_matches(row, q):
            continue
        rows.append(row)
    return rows


def _row_matches(row: dict, q: str) -> bool:
    needle = q.lower()
    return needle in row["name"].lower() or needle in row["role"].lower()


def _row(conversation: Conversation, members: list[User], last: Message | None, unread: int, viewer: _Viewer) -> dict:
    user = viewer.user
    others = [member for member in members if member.user_id != user.user_id]
    other = others[0] if conversation.kind == "direct" and others else None
    if conversation.kind == "system":
        name, initials, role = SYSTEM_NAME, "AI", "Notifications"
    elif conversation.kind == "group":
        name = conversation.title or DEFAULT_GROUP_TITLE
        initials = "".join(word[:1] for word in name.split()[:2]).upper() or "G"
        role = f"{len(members)} members"
    elif other is not None:
        name, initials, role = other.name, _initials(other), viewer.role_line(other)
    else:  # the other person's account is gone
        name, initials, role = "Former member", "?", ""
    return {
        "id": conversation.id,
        "kind": conversation.kind,
        "name": name,
        "initials": initials,
        "role": role,
        "preview": _preview(last, user),
        "time": format_time(last.created_at) if last else None,
        "last_at": iso_z(last.created_at) if last else None,
        "unread": unread,
        "can_reply": conversation.kind != "system",
        "bookable": bool(user.role == "student" and other is not None and other.is_active
                         and (other.bookable or other.user_id in viewer.advisors)),
        "other_user_id": other.user_id if other is not None else None,
        "members": len(members),
    }


def _membership(db: Session, user: User, conversation_id: int) -> tuple[Conversation, ConversationParticipant]:
    row = (db.query(Conversation, ConversationParticipant)
           .join(ConversationParticipant, ConversationParticipant.conversation_id == Conversation.id)
           .filter(Conversation.id == conversation_id, ConversationParticipant.user_id == user.user_id)
           .one_or_none())
    if row is None:
        raise not_found("Conversation")
    return row


def _message_out(message: Message, kind: str, user: User, names: dict[int, str]) -> dict:
    mine = message.sender_id == user.user_id
    sender = SYSTEM_NAME if message.sender_id is None else names.get(message.sender_id, "Former member")
    return {"id": message.id, "from": sender, "mine": mine, "show_name": kind == "group" and not mine,
            "text": message.text, "time": message_time(message.created_at), "sent_at": iso_z(message.created_at)}


def thread(db: Session, user: User, conversation_id: int) -> dict:
    """The conversation's messages, oldest first. Marks everything in it read for the caller."""
    conversation, participant = _membership(db, user, conversation_id)
    messages = (db.query(Message).filter(Message.conversation_id == conversation.id)
                .order_by(Message.created_at, Message.id).all())
    sender_ids = {message.sender_id for message in messages if message.sender_id is not None}
    names = dict(db.query(User.user_id, User.name).filter(User.user_id.in_(sender_ids)).all()) if sender_ids else {}
    # Seeded or clock-skewed messages can carry a later timestamp than now(); reading still covers them.
    participant.last_read_at = max([now()] + [message.created_at for message in messages[-1:]])
    db.commit()
    return {"can_reply": conversation.kind != "system",
            "messages": [_message_out(message, conversation.kind, user, names) for message in messages]}


def _append(db: Session, conversation: Conversation, sender_id: int | None, text: str) -> Message:
    # Never earlier than the conversation's last message (a pinned ACADMATE_TODAY can put seeded messages after now()).
    at = max(now(), conversation.last_message_at + timedelta(microseconds=1)) if conversation.last_message_at else now()
    message = Message(conversation_id=conversation.id, sender_id=sender_id, text=text, created_at=at)
    db.add(message)
    conversation.last_message_at = message.created_at
    db.flush()
    return message


def send(db: Session, user: User, conversation_id: int, text: str) -> dict:
    conversation, participant = _membership(db, user, conversation_id)
    if conversation.kind == "system":
        raise ApiError(403, "READ_ONLY", READ_ONLY_MESSAGE)
    message = _append(db, conversation, user.user_id, text.strip())
    participant.last_read_at = message.created_at
    db.commit()
    return _message_out(message, conversation.kind, user, {user.user_id: user.name})


def _existing_direct(db: Session, user_id: int, other_id: int) -> Conversation | None:
    mine = db.query(ConversationParticipant.conversation_id).filter(ConversationParticipant.user_id == user_id)
    theirs = db.query(ConversationParticipant.conversation_id).filter(ConversationParticipant.user_id == other_id)
    return (db.query(Conversation)
            .filter(Conversation.kind == "direct", Conversation.id.in_(mine), Conversation.id.in_(theirs))
            .order_by(Conversation.id).first())


def start(db: Session, user: User, recipient_ids: list[int], text: str | None = None, title: str | None = None) -> int:
    """Opens a conversation (reusing the direct one with a single recipient) and optionally sends the first message."""
    recipients = [recipient for recipient in dict.fromkeys(recipient_ids) if recipient != user.user_id]
    if not recipients:
        raise forbidden("You can't message yourself.")
    viewer = _Viewer(db, user)
    allowed = {user_id for user_id, in _contact_query(db, viewer).with_entities(User.user_id)
               .filter(User.user_id.in_(recipients))}
    if any(recipient not in allowed for recipient in recipients):
        raise forbidden("You can't message this person.")

    conversation = _existing_direct(db, user.user_id, recipients[0]) if len(recipients) == 1 else None
    if conversation is None:
        group = len(recipients) > 1
        conversation = Conversation(kind="group" if group else "direct", title=(title or DEFAULT_GROUP_TITLE) if group else None,
                                    created_by=user.user_id, created_at=now(), last_message_at=now())
        db.add(conversation)
        db.flush()
        db.add(ConversationParticipant(conversation_id=conversation.id, user_id=user.user_id, last_read_at=now()))
        for recipient in recipients:
            db.add(ConversationParticipant(conversation_id=conversation.id, user_id=recipient))
        db.flush()
    if text and text.strip():
        message = _append(db, conversation, user.user_id, text.strip())
        participant = db.get(ConversationParticipant, (conversation.id, user.user_id))
        participant.last_read_at = message.created_at
    db.commit()
    return conversation.id


def notify(db: Session, user_id: int, text: str) -> None:
    """Posts an Acadmate notice to the user's system conversation (created on first use). Runs in the caller's
    transaction, like audit.record(); the caller commits."""
    conversation = (db.query(Conversation)
                    .join(ConversationParticipant, ConversationParticipant.conversation_id == Conversation.id)
                    .filter(Conversation.kind == "system", ConversationParticipant.user_id == user_id)
                    .order_by(Conversation.id).first())
    if conversation is None:
        conversation = Conversation(kind="system", created_at=now(), last_message_at=now())
        db.add(conversation)
        db.flush()
        db.add(ConversationParticipant(conversation_id=conversation.id, user_id=user_id))
        db.flush()
    _append(db, conversation, None, text)
