from sqlalchemy import (JSON, BigInteger, Boolean, Column, Date, DateTime, Enum, ForeignKey, Index, Integer, Numeric,
                        SmallInteger, String, Text, Time, UniqueConstraint, text)
from sqlalchemy.orm import declarative_base
from sqlalchemy.dialects.postgresql import ARRAY

from core.time import now

Base = declarative_base()   
class Program(Base):
    __tablename__ = "programs"

    program_id = Column(Integer, primary_key=True)
    program_name = Column(String(100), nullable=False)
    total_required_credits = Column(Numeric, nullable=False)  # Σ program_requirements.required_credits, set on publish (spec 33)
    catalog_year = Column(String(9), nullable=False, default="2026–27")

class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)  # full name as displayed
    first_name = Column(String(60), nullable=False)
    last_name = Column(String(60), nullable=False, default="")
    preferred_name = Column(String(60), nullable=True)  # used in greetings (spec 17)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=True)  # null for invited (not yet activated) accounts
    role= Column(Enum("student", "advisor", "admin", name="user_role"), nullable=False)  # e.g., 'student', 'advisor', 'admin'
    is_active = Column(Boolean, default=True,nullable=False)
    totp_secret = Column(String(64), nullable=True)  # two-step sign-in, spec 02 Phase B
    mfa_enabled = Column(Boolean, default=False, nullable=False)
    google_sub = Column(String(64), unique=True, nullable=True)  # Google sign-in, spec 02 Phase B
    title = Column(String(60), nullable=True)  # display role, e.g. "Student services" (spec 16)
    is_support = Column(Boolean, default=False, nullable=False)  # admins students may message, e.g. the graduate office
    bookable = Column(Boolean, default=False, nullable=False)  # students can book meetings with them (spec 18)
    helps_with = Column(String(120), nullable=True)  # "Degree plan, capstone, course approvals"
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)
    last_login_at = Column(DateTime(timezone=True), nullable=True)

class Student(Base):
    __tablename__ = "students"

    student_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), unique=True, nullable=False)  # Foreign key to User
    name = Column(String(100), nullable=False)
    email = Column(String(200), unique=True, nullable=False)
    student_number = Column(String(20), unique=True, nullable=True)  # school-issued ID, e.g. "S1002101"
    program_id = Column(Integer, ForeignKey("programs.program_id"), nullable=False)  # Foreign key to Program
    expected_graduation = Column(String(20), nullable=True)  # display text, e.g. "May 2027"
    start_term_id = Column(Integer, ForeignKey("terms.id"), nullable=True)
    goal = Column(String(200), nullable=True)
    study_goal_hours = Column(Numeric, nullable=False, default=20)  # weekly goal on the dashboard

class Term(Base):
    """Academic terms (spec 33 owns the admin screen). Enrollment.term holds the term name as text."""
    __tablename__ = "terms"

    id = Column(Integer, primary_key=True)
    name = Column(String(30), unique=True, nullable=False)  # e.g. "Spring 2027"
    season = Column(Enum("Spring", "Summer", "Fall", name="term_season"), nullable=False)
    year = Column(Integer, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    registration_opens = Column(Date, nullable=True)
    last_add = Column(Date, nullable=True)
    last_drop = Column(Date, nullable=True)

class Course(Base):
    __tablename__ = "courses"

    course_id = Column(Integer, primary_key=True)
    course_code = Column(String(100), unique=True, nullable=False)
    course_name = Column(String(200), nullable=False)
    credits = Column(Numeric, nullable=False)
    type = Column(Enum("Foundation", "Core", "Elective", "Capstone", name="course_type"), nullable=False, default="Elective")
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)


class CourseOffering(Base):
    """A course is offered in a term (spec 33). The single source of "offered"; sections only add schedule detail."""
    __tablename__ = "course_offerings"

    course_id = Column(Integer, ForeignKey("courses.course_id", ondelete="CASCADE"), primary_key=True)
    term_id = Column(Integer, ForeignKey("terms.id", ondelete="CASCADE"), primary_key=True)

class Enrollment(Base):
    __tablename__ = "enrollments"

    enrollment_id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.student_id"), nullable=False)  # Foreign key to Student
    course_id = Column(Integer, ForeignKey("courses.course_id"), nullable=False)  # Foreign key to Course
    term = Column(String(50), nullable=False)  # e.g., 'Fall 2026', 'Spring 2026'
    status = Column(Enum("in_progress", "completed", "failed","withdrawn", name="enrollment_status"), nullable=False)  # e.g., 'in_progress', 'completed', 'failed', 'withdrawn'
    grade = Column(String(5), nullable=True)  # e.g., 'A', 'B+', 'C-', etc. (nullable for in-progress courses)
    grade_points = Column(Numeric, nullable=True)  # e.g., 4.0, 3.5, etc. (nullable for in-progress courses)
    section_id = Column(Integer, ForeignKey("course_sections.id"), nullable=True)  # null for history rows
    progress_pct = Column(Integer, nullable=False, default=0)
    absences = Column(Integer, nullable=False, default=0)
    sessions_held = Column(Integer, nullable=False, default=0)

class CourseSection(Base):
    """One offering of a course in a term (spec 11)."""
    __tablename__ = "course_sections"

    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.course_id"), nullable=False)
    term_id = Column(Integer, ForeignKey("terms.id"), nullable=False)
    instructor_name = Column(String(100), nullable=True)
    instructor_user_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)  # set when the instructor has an account
    meeting_days = Column(String(20), nullable=True)  # e.g. "Thu" or "Mon,Wed"
    start_time = Column(Time, nullable=True)
    end_time = Column(Time, nullable=True)
    room = Column(String(50), nullable=True)
    site_url = Column(String(255), nullable=True)
    office_hours = Column(String(60), nullable=True)  # display text
    office_day = Column(String(3), nullable=True)
    office_start = Column(Time, nullable=True)
    office_end = Column(Time, nullable=True)
    capacity = Column(Integer, nullable=True)

class GradeItem(Base):
    """A weighted grade component of an enrollment (spec 11)."""
    __tablename__ = "grade_items"

    id = Column(Integer, primary_key=True)
    enrollment_id = Column(Integer, ForeignKey("enrollments.enrollment_id", ondelete="CASCADE"), nullable=False, index=True)
    label = Column(String(80), nullable=False)
    weight = Column(Numeric(5, 2), nullable=False)  # percent
    score = Column(Numeric(5, 2), nullable=True)
    due_date = Column(Date, nullable=True)
    status_text = Column(String(40), nullable=True)  # e.g. "In progress"
    sort = Column(Integer, nullable=False, default=0)

class StudySession(Base):
    """Study hours a student logged on a day (dashboard chart)."""
    __tablename__ = "study_sessions"

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.student_id", ondelete="CASCADE"), nullable=False, index=True)
    day = Column(Date, nullable=False)
    hours = Column(Numeric(4, 1), nullable=False)

class Event(Base):
    """A student's own calendar event (spec 14). Classes and office hours come from course_sections instead."""
    __tablename__ = "events"

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.student_id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(80), nullable=False)
    type = Column(Enum("Study", "Team", "Office hours", "Advising", "Class", name="event_type"), nullable=False)
    date = Column(Date, nullable=False, index=True)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    location = Column(String(80), nullable=True)
    note = Column(String(500), nullable=True)
    reminder_minutes = Column(Integer, nullable=True)  # stored only; delivery is out of scope
    source = Column(Enum("student", "ai", name="event_source"), nullable=False, default="student")
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)

class CalendarFeed(Base):
    """A student's private .ics feed. The token is HMAC(SECRET_KEY, "{student_id}:{version}"); only its hash is stored."""
    __tablename__ = "calendar_feeds"

    student_id = Column(Integer, ForeignKey("students.student_id", ondelete="CASCADE"), primary_key=True)
    token_hash = Column(String(64), unique=True, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)

class Advisor(Base):
    __tablename__ = "advisors"

    advisor_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), unique=True, nullable=False)  # Foreign key to User
    capacity = Column(Integer, nullable=False, default=40, server_default="40")  # advisee capacity (specs 30, 32)
    department = Column(String(80), nullable=True)  # e.g. "Computer Science" (spec 32)
    office = Column(String(120), nullable=True)  # e.g. "Science Hall, Room 4.12" (spec 27)

class AdvisorStudentAssignment(Base):
    __tablename__ = "advisor_student_assignments"

    student_id = Column(Integer, ForeignKey("students.student_id"),primary_key=True, nullable=False)  # Foreign key to Student
    advisor_id = Column(Integer, ForeignKey("advisors.advisor_id"), nullable=False)  # Foreign key to Advisor
    updated_at = Column(DateTime(timezone=True), nullable=False,default=now)  # Timestamp of the last update

class ProgramRequirement(Base):
    __tablename__ = "program_requirements"

    requirement_id = Column(Integer, primary_key=True)
    program_id = Column(Integer, ForeignKey("programs.program_id"), nullable=False)  # Foreign key to Program
    group_name = Column(String(100), nullable=False)  # Name of the requirement group (e.g., "Core Courses", "Electives")
    required_credits = Column(Numeric, nullable=False)  # required_courses × credits_per_course, set on publish (spec 33)
    required_courses = Column(Integer, nullable=False)
    credits_per_course = Column(Integer, nullable=False, default=3)
    sort = Column(Integer, nullable=False, default=0)
    eligible_courses_ids = Column(ARRAY(Integer), nullable=False)  # List of eligible course IDs for this requirement
    requires_approval = Column(Boolean, nullable=False, default=False)  # e.g. capstone pre-approval (spec 12)


class CoursePrerequisite(Base):
    """course_id requires prerequisite_id to be completed first (spec 33 owns the admin screen)."""
    __tablename__ = "course_prerequisites"

    course_id = Column(Integer, ForeignKey("courses.course_id", ondelete="CASCADE"), primary_key=True)
    prerequisite_id = Column(Integer, ForeignKey("courses.course_id", ondelete="CASCADE"), primary_key=True)


class CatalogDraft(Base):
    """An unpublished catalog edit (spec 33). A later save of the same entity overwrites it; publish applies them all."""
    __tablename__ = "catalog_drafts"
    __table_args__ = (UniqueConstraint("entity", "entity_key", name="uq_catalog_drafts_entity"),)

    id = Column(Integer, primary_key=True)
    entity = Column(Enum("course", "requirements", "term", name="catalog_entity"), nullable=False)
    entity_key = Column(String(40), nullable=False)  # course code, program id or term id
    data = Column(JSON, nullable=False)
    created_by = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=now, onupdate=now)


class PlanItem(Base):
    """A course a student plans to take in a future term (spec 12). id is the planned row's enrollmentId in the API."""
    __tablename__ = "plan_items"
    __table_args__ = (UniqueConstraint("student_id", "course_id", name="uq_plan_items_student_course"),)

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.student_id", ondelete="CASCADE"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.course_id"), nullable=False)
    term_id = Column(Integer, ForeignKey("terms.id"), nullable=False)
    status = Column(Enum("planned", "recommended", "needs_approval", "pending_approval", "approved", "changes_requested",
                         name="plan_item_status"), nullable=False, default="planned")
    note = Column(String(500), nullable=True)
    source = Column(Enum("student", "ai", "advisor", name="plan_item_source"), nullable=False, default="student")
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)


class Assignment(Base):
    """Coursework or an advising item (spec 15). section_id null + program_id set = an advising item for everyone in a program."""
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True)
    section_id = Column(Integer, ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=True, index=True)
    program_id = Column(Integer, ForeignKey("programs.program_id"), nullable=True)
    title = Column(String(120), nullable=False)
    short_title = Column(String(40), nullable=True)  # for stat notes ("Next: proposal on Oct 3"); else the title before ":"
    type = Column(Enum("Individual", "Team", "Form", name="assignment_type"), nullable=False)
    due_at = Column(DateTime(timezone=True), nullable=False)
    weight_text = Column(String(20), nullable=False)  # "5%" or "Required"
    description = Column(Text, nullable=True)
    default_steps = Column(JSON, nullable=False, default=list)  # list of step texts
    submission_url = Column(String(255), nullable=True)
    grade_item_id = Column(Integer, ForeignKey("grade_items.id", ondelete="SET NULL"), nullable=True)


class AssignmentSubmission(Base):
    """A student's progress on an assignment. Created lazily the first time the student's list is read."""
    __tablename__ = "assignment_submissions"
    __table_args__ = (UniqueConstraint("assignment_id", "student_id", name="uq_submissions_assignment_student"),)

    id = Column(Integer, primary_key=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.student_id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(Enum("todo", "in_progress", "submitted", "graded", name="submission_status"), nullable=False, default="todo")
    steps_done = Column(JSON, nullable=False, default=list)  # indexes into Assignment.default_steps
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    score = Column(Numeric(5, 2), nullable=True)
    score_text = Column(String(20), nullable=True)  # e.g. "Approved" for forms
    form_fields = Column(JSON, nullable=True)
    feedback = Column(Text, nullable=True)


class ApprovalRequest(Base):
    """The advisor approval queue. Spec 12 creates plan requests; spec 23 adds the advisor side (behaviour, not columns)."""
    __tablename__ = "approval_requests"

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.student_id", ondelete="CASCADE"), nullable=False, index=True)
    advisor_id = Column(Integer, ForeignKey("advisors.advisor_id", ondelete="SET NULL"), nullable=True, index=True)
    type = Column(Enum("plan", "form", "overload", "swap", "other", name="approval_type"), nullable=False)
    title = Column(String(200), nullable=False)  # e.g. "Spring 2027 plan · Capstone Project + Machine Learning"
    term_id = Column(Integer, ForeignKey("terms.id"), nullable=True)
    payload = Column(JSON, nullable=True)  # plan item ids, form fields
    precheck = Column(JSON, nullable=True)
    status = Column(Enum("pending", "approved", "changes_requested", "withdrawn", name="approval_status"),
                    nullable=False, default="pending", index=True)
    comment = Column(Text, nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    decided_by = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)


class AdvisorNote(Base):
    """A private note on a student, visible to advisors only (spec 22). Never returned by a student endpoint."""
    __tablename__ = "advisor_notes"

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.student_id", ondelete="CASCADE"), nullable=False, index=True)
    author_id = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    text = Column(String(1000), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)


class UserPreference(Base):
    """A user's preferences as JSON; services/preferences.py applies the defaults (spec 17 owns the screen)."""
    __tablename__ = "user_preferences"

    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True)
    data = Column(JSON, nullable=False, default=dict)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=now, onupdate=now)


class AiThread(Base):
    """An AI advisor conversation (spec 13)."""
    __tablename__ = "ai_threads"

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.student_id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(80), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=now)


class AiMessage(Base):
    """One question or answer. payload holds planTerm, plan, follow, actions and sources."""
    __tablename__ = "ai_messages"

    id = Column(Integer, primary_key=True)
    thread_id = Column(Integer, ForeignKey("ai_threads.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(Enum("user", "assistant", name="ai_message_role"), nullable=False)
    kind = Column(Enum("answer", "handoff", "limit", name="ai_message_kind"), nullable=False, default="answer")
    text = Column(Text, nullable=False)
    payload = Column(JSON, nullable=True)
    engine = Column(String(10), nullable=True)  # "Claude" or "Rules" on assistant messages
    rating = Column(SmallInteger, nullable=True)  # 1 helpful, -1 not helpful
    created_at = Column(DateTime(timezone=True), nullable=False, default=now, index=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)


class AiFlag(Base):
    """A reported AI answer, reviewed in admin AI settings (specs 30, 34). Keeps text snapshots if the thread is deleted."""
    __tablename__ = "ai_flags"

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("ai_messages.id", ondelete="SET NULL"), nullable=True)
    student_id = Column(Integer, ForeignKey("students.student_id", ondelete="CASCADE"), nullable=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    issue = Column(Text, nullable=False)
    source = Column(Enum("student", "advisor", "auto", name="ai_flag_source"), nullable=False, default="student")
    status = Column(Enum("Open", "Resolved", "Dismissed", name="ai_flag_status"), nullable=False, default="Open")
    resolved_by = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)


class Conversation(Base):
    """A message thread (spec 16): direct (two people), group, or a user's Acadmate system notifications."""
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True)
    kind = Column(Enum("direct", "group", "system", name="conversation_kind"), nullable=False)
    title = Column(String(80), nullable=True)  # groups only
    team_key = Column(String(60), unique=True, nullable=True)  # spec 25: "advising:{department}" team groups
    created_by = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)
    last_message_at = Column(DateTime(timezone=True), nullable=False, default=now, index=True)


class ConversationParticipant(Base):
    __tablename__ = "conversation_participants"

    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True, index=True)
    last_read_at = Column(DateTime(timezone=True), nullable=True)  # messages after this (not sent by the user) are unread
    joined_at = Column(DateTime(timezone=True), nullable=False, default=now)


class Message(Base):
    """A conversation message. sender_id null = sent by Acadmate (system notifications)."""
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_conversation_created", "conversation_id", "created_at"),)

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)


MEETING_ACTIVE = ("requested", "confirmed", "proposed")


class Meeting(Base):
    """A booked meeting between a student and a bookable staff member (spec 18; the advisor side is spec 24)."""
    __tablename__ = "meetings"
    __table_args__ = (
        # One active booking per staff member and start time; the service also locks the staff row while booking.
        Index("uq_meetings_staff_start", "staff_user_id", "starts_at", unique=True,
              postgresql_where=text("status IN ('requested', 'confirmed', 'proposed')")),
    )

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.student_id", ondelete="CASCADE"), nullable=False, index=True)
    advisor_id = Column(Integer, ForeignKey("advisors.advisor_id", ondelete="SET NULL"), nullable=True)  # when the staff member is an advisor
    staff_user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    starts_at = Column(DateTime(timezone=True), nullable=False)
    ends_at = Column(DateTime(timezone=True), nullable=False)
    format = Column(Enum("in_person", "online", name="meeting_format"), nullable=False)
    location = Column(String(120), nullable=True)
    video_url = Column(String(255), nullable=True)
    topic = Column(String(80), nullable=False)
    note = Column(String(500), nullable=True)
    attach_plan = Column(Boolean, nullable=False, default=False)
    status = Column(Enum("requested", "confirmed", "proposed", "cancelled", "completed", "no_show", name="meeting_status"),
                    nullable=False, default="requested", index=True)
    proposed_starts_at = Column(DateTime(timezone=True), nullable=True)
    advisor_notes = Column(Text, nullable=True)  # spec 24
    reminded_at = Column(DateTime(timezone=True), nullable=True)  # day-before reminder sent
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=now, onupdate=now)


class AdvisorAvailability(Base):
    """Weekly hours of a staff member: booking windows (cut into meeting slots) and office hours (specs 24/27 edit them)."""
    __tablename__ = "advisor_availability"

    id = Column(Integer, primary_key=True)
    staff_user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    weekday = Column(SmallInteger, nullable=False)  # 0 = Monday
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    kind = Column(Enum("booking", "office_hours", name="availability_kind"), nullable=False, default="booking")
    location = Column(String(120), nullable=True)


class UserSession(Base):
    """A signed-in browser (table `sessions`; named UserSession to avoid clashing with sqlalchemy.orm.Session). The cookie holds the raw token; only its SHA-256 is stored."""
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    remember = Column(Boolean, nullable=False, default=False)
    ip = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)


class AuthToken(Base):
    """Password reset and invite links (hashed, single use)."""
    __tablename__ = "auth_tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, nullable=False)
    purpose = Column(Enum("reset", "invite", name="auth_tokens_purpose"), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)


class LoginAttempt(Base):
    """Sign-in attempts and reset requests, for rate limiting."""
    __tablename__ = "login_attempts"

    id = Column(Integer, primary_key=True)
    email = Column(String(100), nullable=False, index=True)
    ip = Column(String(45), nullable=True)
    kind = Column(Enum("login", "reset", name="login_attempts_kind"), nullable=False)
    success = Column(Boolean, nullable=False)
    at = Column(DateTime(timezone=True), nullable=False, default=now, index=True)


class SystemSetting(Base):
    """Institution-wide settings as key -> JSON (spec 37 owns the table; spec 34 stores "ai" here)."""
    __tablename__ = "system_settings"

    key = Column(String(40), primary_key=True)  # institution, security, retention, branding, ai
    value = Column(JSON, nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=now, onupdate=now)
    updated_by = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)


class Integration(Base):
    """An external connection (spec 35): csv, mail, gcal, outlook. Secrets in `config` are encrypted
    (core.security.encrypt). Status is derived in services/integrations.py, not stored."""
    __tablename__ = "integrations"

    id = Column(String(20), primary_key=True)
    enabled = Column(Boolean, nullable=False, default=False)
    config = Column(JSON, nullable=False, default=dict)
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=now, onupdate=now)


class IntegrationEvent(Base):
    """The Recent activity rows of an integration (spec 35)."""
    __tablename__ = "integration_events"
    __table_args__ = (Index("ix_integration_events_integration_at", "integration_id", "created_at"),)

    id = Column(Integer, primary_key=True)
    integration_id = Column(String(20), ForeignKey("integrations.id", ondelete="CASCADE"), nullable=False)
    text = Column(String(200), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)


class ImportJob(Base):
    """One CSV import (spec 35). `body` is kept so Sync now can re-run the latest import."""
    __tablename__ = "import_jobs"

    id = Column(Integer, primary_key=True)
    type = Column(Enum("courses", "enrollments", "grades", name="import_type"), nullable=False)
    filename = Column(String(200), nullable=True)
    body = Column(Text, nullable=False)
    created = Column(Integer, nullable=False, default=0)
    updated = Column(Integer, nullable=False, default=0)
    skipped = Column(JSON, nullable=False, default=list)
    actor_id = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)


class ApiKey(Base):
    """An API key for the reporting endpoints (spec 35). Only the SHA-256 of the key is stored."""
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True)
    name = Column(String(60), nullable=False)
    key_hash = Column(String(64), unique=True, nullable=False)
    last4 = Column(String(4), nullable=False)
    scope = Column(String(30), nullable=False)
    created_by = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)


class AuditEvent(Base):
    """Append-only audit trail (spec 36). Written through services/audit.record()."""
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_events_at_role", "at", "actor_role"),)

    id = Column(BigInteger, primary_key=True)
    at = Column(DateTime(timezone=True), nullable=False, default=now, index=True)
    actor_id = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    actor_label = Column(String(100), nullable=False)
    actor_role = Column(Enum("Admin", "Advisor", "Student", "System", name="audit_events_actor_role"), nullable=False)
    action = Column(String(60), nullable=False)
    summary = Column(String(300), nullable=False)
    target_type = Column(String(30), nullable=True)
    target_id = Column(String(40), nullable=True)
    changes = Column(JSON, nullable=True)
    ip = Column(String(45), nullable=True)
    result = Column(Enum("success", "failed", name="audit_events_result"), nullable=False, default="success")
    error = Column(String(300), nullable=True)
