"""Demo data with fixed IDs (student 101, advisor 201, admin user 3, terms 1-7, courses 11-23, AI threads 701-704,
plan items 9001-9002, assignments 1101-1108 with Amara's submissions 1201-1208, conversations 1301-1305 with
messages 1401+). Users 6-8 are Amara's CS 675 teammates (students 102-104), user 9 Prof. Daniel Kim (advisor 203,
CS 608 instructor), user 10 the Graduate office (support admin) and user 11 career advisor Maya Brooks (advisor 204).
Meetings 1501-1507 (spec 18): Amara's check-in today 15:00 (confirmed), capstone topics today + 7 (requested), one past;
the rest fill Dr. Smith's next week. Dr. Smith, Maya Brooks and the Graduate office have booking hours.
Run on empty tables: python reset_db.py --yes && python seed_data.py
Every seeded user's password is DEMO_PASSWORD (demo only). Each feature adds its own seed_<area>(db).
Also seeded: a deactivated student (user 4) and a pending advisor invite (user 5) whose link is
http://localhost:5173/reset-password?token=demo-invite-token (fixed token, demo data only).
Admin overview (spec 30): users 12-13 (students 105-106) are Prof. Kim's advisees, which puts him over his capacity
of 2; past sign-ins 1601+ (revoked), AI threads 705-707 this week, approval requests 1701-1705 (decided ones for
Dr. Smith, pending ones for Prof. Kim, so Dr. Smith's approvals badge stays 0).
Integrations (spec 35): CSV import connected (last import today 06:00), the rest off, and one API key whose raw
value is random and never shown. Audit log (spec 36): events 1801-1812 over the last 10 days, every role."""
import secrets
import sys
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import Integer, text
from sqlalchemy.orm import Session

from core.security import hash_password, sha256_hex
from core.time import local_zone, now, short_date, today
from database import SessionLocal
from models import (
    AdvisorAvailability,
    Assignment,
    AssignmentSubmission,
    AuthToken,
    Base,
    User,
    Program,
    Student,
    Advisor,
    Course,
    ApiKey,
    CourseOffering,
    CourseSection,
    Integration,
    IntegrationEvent,
    Enrollment,
    PlanItem,
    GradeItem,
    StudySession,
    Term,
    AdvisorStudentAssignment,
    AiFlag,
    AuditEvent,
    AiMessage,
    AiThread,
    ApprovalRequest,
    CoursePrerequisite,
    Conversation,
    ConversationParticipant,
    Event,
    Meeting,
    Message,
    ProgramRequirement,
    UserPreference,
    UserSession,
)

DEMO_PASSWORD = "Acadmate!2026"
DEMO_INVITE_TOKEN = "demo-invite-token"


def seed_programs(db: Session) -> None:
    db.add(Program(program_id=1, program_name="M.S. Computer Science", total_required_credits=36,
                   catalog_year="2026–27"))
    db.flush()


def seed_terms(db: Session) -> None:
    """With ACADMATE_TODAY=2026-10-01 the current term is Fall 2026, week 6."""
    db.add_all([
        Term(id=1, name="Fall 2025", season="Fall", year=2025, start_date=date(2025, 8, 25), end_date=date(2025, 12, 19)),
        Term(id=2, name="Spring 2026", season="Spring", year=2026, start_date=date(2026, 1, 20), end_date=date(2026, 5, 15)),
        Term(id=3, name="Summer 2026", season="Summer", year=2026, start_date=date(2026, 5, 26), end_date=date(2026, 8, 14)),
        Term(id=4, name="Fall 2026", season="Fall", year=2026, start_date=date(2026, 8, 24), end_date=date(2026, 12, 18),
             registration_opens=date(2026, 4, 6), last_add=date(2026, 9, 4), last_drop=date(2026, 10, 30)),
        Term(id=5, name="Spring 2027", season="Spring", year=2027, start_date=date(2027, 1, 19), end_date=date(2027, 5, 14),
             registration_opens=date(2026, 11, 3), last_add=date(2027, 1, 29), last_drop=date(2027, 3, 12)),
        Term(id=6, name="Summer 2027", season="Summer", year=2027, start_date=date(2027, 5, 25), end_date=date(2027, 8, 13),
             registration_opens=date(2027, 3, 29)),
        Term(id=7, name="Fall 2027", season="Fall", year=2027, start_date=date(2027, 8, 23), end_date=date(2027, 12, 17),
             registration_opens=date(2027, 4, 5)),
    ])
    db.flush()


def seed_people(db: Session) -> None:
    password_hash = hash_password(DEMO_PASSWORD)
    db.add_all([
        User(user_id=1, name="Amara Okafor", first_name="Amara", last_name="Okafor", preferred_name="Amara", email="amara.okafor@pac.edu",
             password_hash=password_hash, role="student"),
        User(user_id=2, name="Dr. Sarah Smith", first_name="Sarah", last_name="Smith", email="sarah.smith@pac.edu",
             password_hash=password_hash, role="advisor", bookable=True, helps_with="Degree plan, capstone, course approvals"),
        User(user_id=3, name="Jordan Lee", first_name="Jordan", last_name="Lee", email="jordan.lee@pac.edu",
             password_hash=password_hash, role="admin"),
        # Deactivated account: signing in shows "This account is deactivated."
        User(user_id=4, name="Sam Rivera", first_name="Sam", last_name="Rivera", email="sam.rivera@pac.edu",
             password_hash=password_hash, role="student", is_active=False),
        # Invited advisor who hasn't set a password yet (activates through the invite link).
        User(user_id=5, name="Dr. Priya Natarajan", first_name="Priya", last_name="Natarajan", email="priya.natarajan@pac.edu",
             password_hash=None, role="advisor", is_active=False),
        # Amara's CS 675 project team (spec 16 messages).
        User(user_id=6, name="Kofi Mensah", first_name="Kofi", last_name="Mensah", email="kofi.mensah@pac.edu",
             password_hash=password_hash, role="student"),
        User(user_id=7, name="Lena Fischer", first_name="Lena", last_name="Fischer", email="lena.fischer@pac.edu",
             password_hash=password_hash, role="student"),
        User(user_id=8, name="Diego Alvarez", first_name="Diego", last_name="Alvarez", email="diego.alvarez@pac.edu",
             password_hash=password_hash, role="student"),
        # CS 608 instructor with an account, so students in the section can message him.
        User(user_id=9, name="Prof. Daniel Kim", first_name="Daniel", last_name="Kim", email="daniel.kim@pac.edu",
             password_hash=password_hash, role="advisor", title="Faculty"),
        # Support account students may message (is_support).
        User(user_id=10, name="Graduate office", first_name="Graduate", last_name="Office", email="grad.office@pac.edu",
             password_hash=password_hash, role="admin", title="Student services", is_support=True,
             bookable=True, helps_with="Graduation application, records"),
        # Career services advisor students can book (spec 18); no advisees.
        User(user_id=11, name="Maya Brooks", first_name="Maya", last_name="Brooks", email="maya.brooks@pac.edu",
             password_hash=password_hash, role="advisor", title="Career services", bookable=True,
             helps_with="Internships, CPT, résumé reviews"),
    ])
    db.flush()
    db.add(Student(student_id=101, user_id=1, name="Amara Okafor", email="amara.okafor@pac.edu", program_id=1,
                   student_number="S1002101", expected_graduation="May 2027", start_term_id=1))
    for student_id, user_id, name, email in [(102, 6, "Kofi Mensah", "kofi.mensah@pac.edu"),
                                             (103, 7, "Lena Fischer", "lena.fischer@pac.edu"),
                                             (104, 8, "Diego Alvarez", "diego.alvarez@pac.edu")]:
        db.add(Student(student_id=student_id, user_id=user_id, name=name, email=email, program_id=1, start_term_id=2,
                       student_number=f"S1002{student_id}"))
    db.add(Advisor(advisor_id=201, user_id=2, department="Computer Science"))
    db.add(Advisor(advisor_id=202, user_id=5, department="Data Science"))
    db.add(Advisor(advisor_id=203, user_id=9, department="Computer Science"))
    db.add(Advisor(advisor_id=204, user_id=11, department="Career Services"))
    db.add(AuthToken(user_id=5, token_hash=sha256_hex(DEMO_INVITE_TOKEN), purpose="invite", expires_at=now() + timedelta(days=7)))
    db.flush()


def seed_courses(db: Session) -> None:
    db.add_all([
        Course(course_id=11, course_code="CS 501", course_name="Programming Foundations with Java", credits=3,
               type="Foundation", description="Object-oriented programming in Java for students new to computer science."),
        Course(course_id=12, course_code="CS 510", course_name="Data Structures and Algorithms", credits=3,
               type="Foundation", description="Lists, trees, graphs, hashing and the analysis of algorithms."),
        Course(course_id=13, course_code="CS 620", course_name="Database Management Systems", credits=3,
               type="Core", description="Relational design, SQL, transactions and indexing."),
        Course(course_id=14, course_code="CS 600", course_name="Software Engineering", credits=3,
               type="Core", description="Requirements, design, testing and team delivery of software projects."),
        Course(course_id=15, course_code="CS 630", course_name="Operating Systems", credits=3,
               type="Core", description="Processes, memory, file systems and concurrency."),
        Course(course_id=16, course_code="CS 640", course_name="Computer Networks", credits=3,
               type="Core", description="Protocols, routing and network programming."),
        Course(course_id=17, course_code="CS 650", course_name="Cloud Computing", credits=3,
               type="Elective", description="Designing and running applications on cloud platforms."),
        Course(course_id=18, course_code="CS 608", course_name="Algorithms & Computing Theory", credits=3,
               type="Elective", description="Algorithm design techniques, complexity and computability."),
        Course(course_id=19, course_code="CS 661", course_name="Python Programming", credits=3,
               type="Elective", description="Python for data work, scripting and testing."),
        Course(course_id=20, course_code="CS 675", course_name="Data Science", credits=3,
               type="Elective", description="Data wrangling, statistics and visualisation with a team project."),
        Course(course_id=21, course_code="CS 691", course_name="Capstone Project", credits=3,
               type="Capstone", description="A semester-long project with a faculty supervisor; needs pre-approval."),
        Course(course_id=22, course_code="CS 680", course_name="Machine Learning", credits=3,
               type="Elective", description="Supervised and unsupervised learning, model evaluation and deployment."),
        Course(course_id=23, course_code="CS 665", course_name="Computer Vision", credits=3,
               type="Elective", description="Image processing, feature detection and deep learning for vision."),
    ])
    db.flush()


def seed_sections(db: Session) -> None:
    """Fall 2026 sections of the student's current courses."""
    db.add_all([
        CourseSection(id=501, course_id=18, term_id=4, instructor_name="Prof. Daniel Kim", instructor_user_id=9, meeting_days="Mon",
                      start_time=time(18, 10), end_time=time(20, 55), room="210",
                      site_url="https://lms.example.edu/cs608",
                      office_day="Mon", office_start=time(16, 0), office_end=time(17, 0)),
        CourseSection(id=502, course_id=19, term_id=4, instructor_name="Prof. Ravi Menon", meeting_days="Thu",
                      start_time=time(18, 10), end_time=time(20, 55), room="318",
                      site_url="https://lms.example.edu/cs661",
                      office_day="Thu", office_start=time(17, 0), office_end=time(18, 0)),
        CourseSection(id=503, course_id=20, term_id=4, instructor_name="Prof. Lina Ortiz", meeting_days="Thu",
                      start_time=time(10, 0), end_time=time(12, 45), room="1201",
                      site_url="https://lms.example.edu/cs675",
                      office_day="Wed", office_start=time(14, 0), office_end=time(15, 0)),
        # Spring 2027 sections (seed_offerings makes these courses offered in Spring 2027).
        CourseSection(id=504, course_id=21, term_id=5, instructor_name="Dr. Sarah Smith", meeting_days="Mon",
                      start_time=time(18, 10), end_time=time(20, 55), room="1204"),
        CourseSection(id=505, course_id=22, term_id=5, instructor_name="Prof. Lina Ortiz", meeting_days="Wed",
                      start_time=time(18, 10), end_time=time(20, 55), room="1201"),
        CourseSection(id=506, course_id=23, term_id=5, instructor_name="Prof. Daniel Kim", meeting_days="Tue",
                      start_time=time(10, 0), end_time=time(12, 45), room="210"),
        CourseSection(id=507, course_id=14, term_id=5, instructor_name="Prof. Ravi Menon", meeting_days="Thu",
                      start_time=time(18, 10), end_time=time(20, 55), room="318"),
    ])
    db.flush()


def seed_offerings(db: Session) -> None:
    """Spec 33: a course is offered in each term it has a section in. Other courses show "Not offered"."""
    pairs = {(section.course_id, section.term_id) for section in db.query(CourseSection)}
    db.add_all(CourseOffering(course_id=course_id, term_id=term_id) for course_id, term_id in sorted(pairs))
    db.flush()


def seed_prerequisites(db: Session) -> None:
    db.add_all([
        CoursePrerequisite(course_id=21, prerequisite_id=14),  # CS 691 needs CS 600
        CoursePrerequisite(course_id=21, prerequisite_id=13),  # and CS 620
        CoursePrerequisite(course_id=22, prerequisite_id=20),  # CS 680 needs CS 675
    ])
    db.flush()


def seed_preferences(db: Session) -> None:
    db.add(UserPreference(user_id=1, data={"classTime": "Evening", "targetGraduation": "May 2027"}))
    db.add(UserPreference(user_id=10, data={"bookings": {"autoConfirm": True}}))  # the Graduate office confirms bookings at once
    db.flush()


PLAN_SOURCES = ["Degree audit · updated today", "Course catalog 2026–27", "Spring 2027 schedule"]


def seed_ai(db: Session) -> None:
    """Amara's AI advisor history (the design conversation first) and one open flag for the admin review list."""
    current = now()
    threads = [
        (701, "Plan my Spring 2027 semester", current - timedelta(hours=2)),
        (702, "Can I take CS 608 and CS 675 together?", datetime(2026, 9, 14, 19, 5, tzinfo=timezone.utc)),
        (703, "Internship credit options", datetime(2026, 9, 2, 14, 30, tzinfo=timezone.utc)),
        (704, "Capstone topic ideas", datetime(2026, 8, 28, 16, 12, tzinfo=timezone.utc)),
    ]
    for thread_id, title, at in threads:
        db.add(AiThread(id=thread_id, student_id=101, title=title, created_at=at, updated_at=at))
    db.flush()

    first = current - timedelta(hours=2)
    plan = {
        "planTerm": "Spring 2027",
        "plan": [
            {"code": "CS 691", "name": "Capstone Project", "meta": "Mon 18:10–20:55", "fulfills": "Capstone", "why": None, "onPlan": False},
            {"code": "CS 680", "name": "Machine Learning", "meta": "Wed 18:10–20:55", "fulfills": "Elective 5 of 5", "why": None, "onPlan": False},
        ],
        "follow": "Before you can register, your advisor must sign your capstone pre-approval form. Spring registration opens Nov 3.",
        "actions": [{"label": "Add to degree plan", "to": "/student/degree-plan"}, {"label": "Send to advisor", "to": "/student/messages"}],
        "sources": PLAN_SOURCES,
    }
    messages = [
        AiMessage(id=801, thread_id=701, role="user", text="Plan my Spring 2027 semester. I prefer evening classes.", created_at=first),
        AiMessage(id=802, thread_id=701, role="assistant", engine="Rules", payload=plan, created_at=first + timedelta(seconds=4),
                  text="Here's a plan that finishes your degree in May 2027 with every class in the evening:"),
        AiMessage(id=803, thread_id=701, role="user", text="What happens if I take only one course in Spring?",
                  created_at=first + timedelta(minutes=3)),
        AiMessage(id=804, thread_id=701, role="assistant", engine="Rules", created_at=first + timedelta(minutes=3, seconds=4),
                  payload={"sources": ["Degree audit · updated today", "Course catalog 2026–27"]},
                  text="Taking only the capstone would move your last elective to Summer 2027, so you would graduate in August "
                       "instead of May. Summer electives run less often, so check what's offered before choosing this path."),
        AiMessage(id=805, thread_id=702, role="user", text="Can I take CS 608 and CS 675 together?", created_at=threads[1][2]),
        AiMessage(id=806, thread_id=702, role="assistant", engine="Rules", created_at=threads[1][2] + timedelta(seconds=3),
                  payload={"sources": ["Fall 2026 schedule"]},
                  text="Yes. CS 608 meets Mon 18:10–20:55 and CS 675 meets Thu 10:00–12:45, so they don't overlap."),
        AiMessage(id=807, thread_id=703, role="user", text="Can an internship count toward my degree?", created_at=threads[2][2]),
        AiMessage(id=808, thread_id=703, role="assistant", engine="Rules", created_at=threads[2][2] + timedelta(seconds=3),
                  payload={"sources": ["Degree audit · updated today"]},
                  text="Your program doesn't list internship credit as a requirement option. Ask your advisor whether an "
                       "internship can count as an elective."),
        AiMessage(id=809, thread_id=704, role="user", text="Give me some capstone topic ideas.", created_at=threads[3][2]),
        AiMessage(id=810, thread_id=704, role="assistant", engine="Rules", created_at=threads[3][2] + timedelta(seconds=3),
                  payload={"sources": ["Course catalog 2026–27"]},
                  text="Capstone topics usually build on your electives. With Data Science and Python Programming, a data "
                       "pipeline or a machine learning project would fit. Your capstone advisor approves the topic."),
    ]
    db.add_all(messages)
    db.flush()
    db.add(AiFlag(id=901, message_id=808, student_id=101, question=messages[6].text, answer=messages[7].text,
                  issue="My advisor said internships can count for 3 elective credits.", source="student", status="Open",
                  created_at=threads[2][2] + timedelta(minutes=5)))
    db.flush()


def seed_enrollments(db: Session) -> None:
    db.add_all([
        # Term GPAs 3.70 / 3.65 / 3.85 over 21 credits, cumulative 3.73.
        Enrollment(enrollment_id=301, student_id=101, course_id=11, term="Fall 2025", status="completed", grade="A-", grade_points=3.7),
        Enrollment(enrollment_id=302, student_id=101, course_id=12, term="Fall 2025", status="completed", grade="A-", grade_points=3.7),
        Enrollment(enrollment_id=303, student_id=101, course_id=13, term="Fall 2025", status="completed", grade="A-", grade_points=3.7),
        Enrollment(enrollment_id=304, student_id=101, course_id=14, term="Spring 2026", status="completed", grade="A", grade_points=4.0),
        Enrollment(enrollment_id=305, student_id=101, course_id=15, term="Spring 2026", status="completed", grade="B+", grade_points=3.3),
        Enrollment(enrollment_id=306, student_id=101, course_id=16, term="Summer 2026", status="completed", grade="A", grade_points=4.0),
        Enrollment(enrollment_id=307, student_id=101, course_id=17, term="Summer 2026", status="completed", grade="A-", grade_points=3.7),
        Enrollment(enrollment_id=308, student_id=101, course_id=18, term="Fall 2026", status="in_progress", section_id=501,
                   progress_pct=40, sessions_held=9, absences=0),
        Enrollment(enrollment_id=309, student_id=101, course_id=19, term="Fall 2026", status="in_progress", section_id=502,
                   progress_pct=50, sessions_held=8, absences=1),
        Enrollment(enrollment_id=310, student_id=101, course_id=20, term="Fall 2026", status="in_progress", section_id=503,
                   progress_pct=45, sessions_held=9, absences=0),
        # Amara's CS 675 project teammates.
        Enrollment(enrollment_id=311, student_id=102, course_id=20, term="Fall 2026", status="in_progress", section_id=503),
        Enrollment(enrollment_id=312, student_id=103, course_id=20, term="Fall 2026", status="in_progress", section_id=503),
        Enrollment(enrollment_id=313, student_id=104, course_id=20, term="Fall 2026", status="in_progress", section_id=503),
    ])
    db.flush()


def seed_grade_items(db: Session) -> None:
    """Graded work so far in Fall 2026 (spec 11 design): CS 608 87.8 B+, CS 661 95.8 A, CS 675 91.9 A-.
    CS 675 labs are 90, not the design's 92, which would make the course an A instead of the designed A-."""
    db.add_all([
        GradeItem(id=601, enrollment_id=308, label="Problem sets", weight=35, score=86, sort=1),
        GradeItem(id=602, enrollment_id=308, label="Midterm", weight=30, due_date=date(2026, 10, 19), sort=2),
        GradeItem(id=603, enrollment_id=308, label="Final", weight=30, due_date=date(2026, 12, 14), sort=3),
        GradeItem(id=604, enrollment_id=308, label="Participation", weight=5, score=100, sort=4),
        GradeItem(id=605, enrollment_id=309, label="Weekly tutorials", weight=40, score=96, sort=1),
        GradeItem(id=606, enrollment_id=309, label="Projects", weight=30, score=94, sort=2),
        GradeItem(id=607, enrollment_id=309, label="Final exam", weight=20, due_date=date(2026, 12, 10), sort=3),
        GradeItem(id=608, enrollment_id=309, label="Participation", weight=10, score=100, sort=4),
        GradeItem(id=609, enrollment_id=310, label="Team project", weight=40, due_date=date(2026, 12, 11), status_text="In progress", sort=1),
        GradeItem(id=610, enrollment_id=310, label="Labs", weight=25, score=90, sort=2),
        GradeItem(id=611, enrollment_id=310, label="Midterm", weight=20, due_date=date(2026, 10, 22), sort=3),
        GradeItem(id=612, enrollment_id=310, label="Participation", weight=15, score=95, sort=4),
        # Zero-weight checkpoints: deadlines on the schedule (spec 14) until assignments exist (spec 15).
        GradeItem(id=613, enrollment_id=308, label="Problem set 4", weight=0, due_date=date(2026, 10, 9), sort=5),
        GradeItem(id=614, enrollment_id=310, label="Project topic proposal", weight=0, due_date=date(2026, 10, 3), sort=5),
    ])
    db.flush()


def _due(month: int, day: int, hour: int = 23, minute: int = 59) -> datetime:
    """A 2026 local (New York) time as UTC."""
    return datetime(2026, month, day, hour, minute, tzinfo=local_zone()).astimezone(timezone.utc)


def seed_coursework(db: Session) -> None:
    """The spec 15 design's 8 assignments and Amara's progress on them (assignments are due at 23:59 local time)."""
    proposal_steps = ["Agree on the topic with the team", "Write the problem statement and dataset section",
                      "Outline supervised and unsupervised models", "Proofread and submit"]
    rows = [
        # id, section, program, title, short, type, due, weight, description, steps, grade item
        (1101, 503, None, "Project topic proposal", "proposal", "Team", _due(10, 3), "5%",
         "One-page team proposal: problem statement, chosen dataset, planned methods in R and Python, and each member's role.",
         proposal_steps, 614),
        (1102, 502, None, "Week 6 tutorial", None, "Individual", _due(10, 5), "4%",
         "Work through the week 6 notebook on file handling and submit it on the course site.", [], None),
        (1103, 501, None, "Problem set 4", None, "Individual", _due(10, 9), "7%",
         "Dynamic programming and greedy algorithms. Show recurrences and prove correctness where asked.", [], 613),
        (1104, 502, None, "Project 2 checkpoint", None, "Team", _due(10, 16), "10%",
         "Show a working prototype of project 2 and a short plan for the remaining features.", [], None),
        (1105, None, 1, "Capstone pre-approval form", "capstone form", "Form", _due(10, 20), "Required",
         "Your advisor must sign this form before you can register for the capstone in Spring 2027.", [], None),
        (1106, 503, None, "Lab 4: Exploratory analysis", None, "Individual", _due(9, 30), "6%",
         "Explore the course dataset and report three findings with plots.", [], None),
        (1107, 501, None, "Dynamic programming set", None, "Individual", _due(9, 28), "7%",
         "Practice problems on memoisation and tabulation.", [], None),
        (1108, 502, None, "Week 5 tutorial", None, "Individual", _due(9, 28), "4%",
         "Week 5 notebook on functions and modules.", [], None),
    ]
    sites = {section.id: section.site_url for section in db.query(CourseSection).all()}
    for id_, section, program, title, short, type_, due, weight, desc, steps, grade_item in rows:
        url = f"{sites[section]}/a/{id_}" if section and sites.get(section) else None
        db.add(Assignment(id=id_, section_id=section, program_id=program, title=title, short_title=short, type=type_,
                          due_at=due, weight_text=weight, description=desc, default_steps=steps, submission_url=url,
                          grade_item_id=grade_item))
    db.flush()
    db.add_all([
        AssignmentSubmission(id=1201, assignment_id=1101, student_id=101, status="in_progress", steps_done=[0]),
        AssignmentSubmission(id=1202, assignment_id=1102, student_id=101, status="in_progress"),
        AssignmentSubmission(id=1203, assignment_id=1103, student_id=101, status="todo"),
        AssignmentSubmission(id=1204, assignment_id=1104, student_id=101, status="todo"),
        AssignmentSubmission(id=1205, assignment_id=1105, student_id=101, status="todo"),
        AssignmentSubmission(id=1206, assignment_id=1106, student_id=101, status="submitted", submitted_at=_due(9, 29, 20, 0)),
        AssignmentSubmission(id=1207, assignment_id=1107, student_id=101, status="graded", score=84, submitted_at=_due(9, 27, 18, 0)),
        AssignmentSubmission(id=1208, assignment_id=1108, student_id=101, status="graded", score=98, submitted_at=_due(9, 27, 19, 0)),
    ])
    db.flush()


def seed_events(db: Session) -> None:
    """The design's week (Mon Sep 28 - Sun Oct 4, 2026); classes and office hours come from course_sections."""
    rows = [
        (1001, "Study · CS 675 labs", "Study", date(2026, 9, 28), time(13, 0), time(15, 0), "Library, 3rd floor",
         "Personal study block for lab work."),
        (1002, "Study · CS 661", "Study", date(2026, 9, 29), time(12, 0), time(13, 0), "Online", None),
        (1003, "Study · CS 608", "Study", date(2026, 9, 30), time(18, 0), time(20, 0), None, None),
        (1004, "Team project sync", "Team", date(2026, 10, 1), time(13, 30), time(14, 15), "Study room 3", None),
        # The design's Thursday advising check-in is meeting 1501 (seed_meetings).
        (1006, "CS 608 study group", "Team", date(2026, 10, 2), time(16, 0), time(17, 30), None, None),
        (1007, "Study · proposal edits", "Study", date(2026, 10, 3), time(10, 0), time(12, 0), None, None),
    ]
    db.add_all([Event(id=id_, student_id=101, title=title, type=type_, date=day, start_time=start, end_time=end,
                      location=location, note=note)
                for id_, title, type_, day, start, end, location, note in rows])
    db.flush()


def seed_assignments(db: Session) -> None:
    db.add(AdvisorStudentAssignment(student_id=101, advisor_id=201))
    db.flush()


def seed_requirements(db: Session) -> None:
    """Spec 12 design: Foundation 2, Core 4, Electives 5, Capstone 1 (12 courses, 36 credits). CS 608 counts as an elective."""
    db.add_all([
        ProgramRequirement(requirement_id=401, program_id=1, group_name="Foundation", required_courses=2, required_credits=6,
                           sort=1, eligible_courses_ids=[11, 12]),
        ProgramRequirement(requirement_id=402, program_id=1, group_name="Core courses", required_courses=4, required_credits=12,
                           sort=2, eligible_courses_ids=[13, 14, 15, 16]),
        ProgramRequirement(requirement_id=403, program_id=1, group_name="Electives", required_courses=5, required_credits=15,
                           sort=3, eligible_courses_ids=[17, 18, 19, 20, 22, 23]),
        ProgramRequirement(requirement_id=404, program_id=1, group_name="Capstone", required_courses=1, required_credits=3,
                           sort=4, eligible_courses_ids=[21], requires_approval=True),
    ])
    db.flush()


def seed_plan(db: Session) -> None:
    """Amara's Spring 2027 draft (spec 12). No capstone pre-approval form request, so the audit alert shows."""
    db.add_all([
        PlanItem(id=9001, student_id=101, course_id=21, term_id=5, status="needs_approval"),
        PlanItem(id=9002, student_id=101, course_id=22, term_id=5, status="planned"),
    ])
    db.flush()


def seed_study_sessions(db: Session) -> None:
    """This week's study log (Mon-Sun of today's week, so the chart is never empty)."""
    monday = today() - timedelta(days=today().weekday())
    for offset, hours in enumerate([3.5, 4, 2, 5, 2.5, 3, 1.5]):
        db.add(StudySession(student_id=101, day=monday + timedelta(days=offset), hours=hours))
    db.flush()


def _local_at(days_ago: int, hour: int, minute: int) -> datetime:
    """A time of day `days_ago` days before today, in the school time zone."""
    return datetime.combine(today() - timedelta(days=days_ago), time(hour, minute), local_zone())


def seed_messages(db: Session) -> None:
    """Amara's 5 design conversations (spec 16): 1 unread from her advisor, 2 unread in the team chat (badge 3)."""
    threads = [  # (id, kind, title, participant user ids, Amara's last_read_at, [(sender, days_ago, hh, mm, text)])
        (1301, "direct", None, [1, 2], _local_at(1, 16, 20), [
            (2, 1, 16, 5, "Hi Amara, I looked at the Spring plan Acadmate put together. Capstone plus one AI elective works for May 2027."),
            (1, 1, 16, 20, "Thank you! Could we go over capstone topics at our Oct 8 meeting?"),
            (2, 0, 9, 42, "Yes. Bring two or three ideas, and please send the capstone pre-approval form by Oct 20."),
        ]),
        (1302, "group", "CS 675 project team", [1, 6, 7, 8], _local_at(1, 21, 0), [
            (6, 1, 19, 30, "I pushed the cleaned dataset to our repo."),
            (1, 1, 20, 45, "Great, I'll start on the exploratory charts tonight."),
            (7, 0, 8, 15, "Can we meet Wednesday after class to split up the report?"),
            (8, 0, 8, 50, "Wednesday works for me. I'll book a study room."),
        ]),
        (1303, "direct", None, [1, 9], _local_at(1, 12, 0), [
            (9, 1, 11, 20, "Office hours move to Monday 4–5 pm this week. Bring questions on Problem set 4."),
        ]),
        (1304, "system", None, [1], _local_at(2, 18, 0), [
            (None, 3, 9, 0, "Reminder: capstone registration opens Nov 3."),
            (None, 2, 17, 30, "Acadmate drafted a Spring 2027 plan for you. Review it on your degree plan and send it to your advisor."),
        ]),
        (1305, "direct", None, [1, 10], _local_at(2, 12, 0), [
            (10, 2, 10, 0, "Students graduating in May 2027 should file a graduation application by Dec 1."),
        ]),
    ]
    message_id = 1401
    for conversation_id, kind, title, members, read_at, messages in threads:
        last_at = _local_at(*messages[-1][1:4])
        db.add(Conversation(id=conversation_id, kind=kind, title=title, created_by=None if kind == "system" else 1,
                            created_at=_local_at(*messages[0][1:4]), last_message_at=last_at))
        db.flush()
        for user_id in members:
            db.add(ConversationParticipant(conversation_id=conversation_id, user_id=user_id,
                                           last_read_at=read_at if user_id == 1 else last_at))
        for sender, days_ago, hour, minute, text_ in messages:
            db.add(Message(id=message_id, conversation_id=conversation_id, sender_id=sender, text=text_,
                           created_at=_local_at(days_ago, hour, minute)))
            message_id += 1
    db.flush()


def seed_meetings(db: Session) -> None:
    """Booking hours for the 3 bookable staff and the design's meetings (spec 18), relative to today's week."""
    windows = [  # (staff user id, weekdays, start, end, location)
        (2, range(5), time(9, 0), time(17, 0), "Room 4.12, Science Hall"),
        (11, (1, 3), time(10, 0), time(16, 0), "Career Center, Room 105"),
        (10, (0, 2, 4), time(10, 0), time(15, 0), "Graduate office, Room 2.03"),
    ]
    for staff, weekdays, start, end, location in windows:
        for weekday in weekdays:
            db.add(AdvisorAvailability(staff_user_id=staff, weekday=weekday, start_time=start, end_time=end,
                                       kind="booking", location=location))

    monday = today() - timedelta(days=today().weekday())
    next_monday = monday + timedelta(days=7)
    rows = [  # (id, student, day, hh, mm, format, topic, status, note)
        (1501, 101, today(), 15, 0, "online", "Advising check-in", "confirmed",
         "Review the Spring 2027 plan and the capstone pre-approval form."),
        (1502, 101, today() + timedelta(days=7), 15, 0, "in_person", "Capstone topics", "requested",
         "I'd like to compare two capstone ideas."),
        (1503, 101, today() - timedelta(days=21), 14, 0, "in_person", "Course planning", "completed", None),
        # Other students' bookings: the taken slots in Dr. Smith's week.
        (1504, 102, next_monday, 9, 0, "in_person", "Add or drop a course", "confirmed", None),
        (1505, 103, next_monday + timedelta(days=2), 10, 0, "online", "Capstone topics", "confirmed", None),
        (1506, 104, next_monday + timedelta(days=2), 10, 30, "in_person", "Spring 2027 plan", "confirmed", None),
        (1507, 102, next_monday + timedelta(days=4), 14, 0, "in_person", "Capstone topics", "requested", None),
    ]
    for id_, student, day, hour, minute, format_, topic, status, note in rows:
        starts = datetime.combine(day, time(hour, minute), local_zone()).astimezone(timezone.utc)
        db.add(Meeting(id=id_, student_id=student, advisor_id=201, staff_user_id=2, starts_at=starts,
                       ends_at=starts + timedelta(minutes=30), format=format_,
                       location="Room 4.12, Science Hall" if format_ == "in_person" else None,
                       video_url=f"https://meet.example.edu/{id_}" if format_ == "online" else None,
                       topic=topic, note=note, attach_plan=student == 101, status=status,
                       created_at=starts - timedelta(days=5)))
    db.flush()


def seed_overview(db: Session) -> None:
    """History for the admin overview (spec 30): capacities, sign-ins over 6 weeks, this week's AI use, decisions."""
    for advisor_id, capacity in ((201, 45), (202, 40), (203, 2), (204, 25)):
        db.get(Advisor, advisor_id).capacity = capacity

    password_hash = hash_password(DEMO_PASSWORD)
    for user_id, student_id, first, last in ((12, 105, "Hana", "Sato"), (13, 106, "Marcus", "Reed")):
        email = f"{first.lower()}.{last.lower()}@pac.edu"
        db.add(User(user_id=user_id, name=f"{first} {last}", first_name=first, last_name=last, email=email,
                    password_hash=password_hash, role="student"))
        db.flush()
        db.add(Student(student_id=student_id, user_id=user_id, name=f"{first} {last}", email=email, program_id=1,
                       student_number=f"S1002{student_id}", start_term_id=3))
        db.flush()  # no relationships to order the inserts by
        db.add(AdvisorStudentAssignment(student_id=student_id, advisor_id=203))
    db.add(AdvisorStudentAssignment(student_id=104, advisor_id=203))  # 3 of 2: Prof. Kim is over capacity (spec 32)
    db.flush()

    # Past sign-ins (revoked, never usable): who signed in each week, oldest first; the current week is the busiest.
    monday = today() - timedelta(days=today().weekday())
    weekly = [(1, 6), (1, 6, 7), (1, 7, 12), (1, 6, 8, 12), (1, 6, 7, 13), (1, 6, 7, 8, 12)]
    session_id = 1601
    for weeks_ago, users in zip(range(len(weekly) - 1, -1, -1), weekly):
        week = monday - timedelta(weeks=weeks_ago)
        for offset, user_id in enumerate(users):
            day = min(week + timedelta(days=offset % 5), today())
            created = datetime.combine(day, time(8, 30), local_zone()).astimezone(timezone.utc)
            db.add(UserSession(id=session_id, user_id=user_id, token_hash=sha256_hex(secrets.token_hex(32)),
                               created_at=created, expires_at=created + timedelta(hours=2),
                               revoked_at=created + timedelta(hours=1)))
            session_id += 1

    # This week's AI advisor use by Amara's classmates: ratings, one handoff and one automatic flag.
    start = datetime.combine(monday, time(7, 0), local_zone()).astimezone(timezone.utc)
    threads = [  # (thread id, student, title, [(question, answer, kind, rating)])
        (705, 102, "Spring electives", [
            ("Which electives fit an evening schedule in Spring 2027?",
             "CS 680 Machine Learning and CS 665 Cloud Computing both meet after 18:00 in Spring 2027.", "answer", 1),
            ("Does CS 665 need a prerequisite?", "Yes, CS 665 needs CS 608 first, which you're taking now.", "answer", 1),
        ]),
        (706, 103, "Graduation timeline", [
            ("Can I graduate in December 2026?",
             "You have 12 credits left, so December 2026 is possible only with an overload. Your advisor can approve "
             "an overload request.", "answer", -1),
            ("Can you approve my overload?", "I can't approve requests. I've passed your question to your advisor.",
             "handoff", None),
        ]),
        (707, 104, "Internship credit", [
            ("Does an internship count as an elective?",
             "Internships can count as an elective with a CPT approval.", "answer", 1),
        ]),
    ]
    message_id = 811
    for thread_id, student_id, title, pairs in threads:
        db.add(AiThread(id=thread_id, student_id=student_id, title=title, created_at=start, updated_at=start))
        db.flush()
        for question, answer, kind, rating in pairs:
            db.add(AiMessage(id=message_id, thread_id=thread_id, role="user", text=question, created_at=start))
            db.add(AiMessage(id=message_id + 1, thread_id=thread_id, role="assistant", engine="Rules", kind=kind,
                             text=answer, rating=rating, created_at=start + timedelta(seconds=4)))
            message_id += 2
            start += timedelta(minutes=7)
    db.flush()
    db.add(AiFlag(id=902, message_id=820, student_id=104, question="Does an internship count as an elective?",
                  answer="Internships can count as an elective with a CPT approval.",
                  issue="The program doesn't list internship credit as an elective option.", source="auto",
                  status="Open", created_at=start))

    # Approval history: Dr. Smith's decisions feed "Avg. reply"; Prof. Kim's queue is still waiting.
    requests = [  # (id, student, advisor, created days ago, decided after hours, status)
        (1701, 102, 201, 20, 24, "approved"),
        (1702, 103, 201, 12, 36, "approved"),
        (1703, 104, 201, 5, 48, "changes_requested"),
        (1704, 105, 203, 2, None, "pending"),
        (1705, 106, 203, 1, None, "pending"),
    ]
    for id_, student_id, advisor_id, days_ago, hours, status in requests:
        created = datetime.combine(today() - timedelta(days=days_ago), time(10), local_zone()).astimezone(timezone.utc)
        decided = created + timedelta(hours=hours) if hours else None
        db.add(ApprovalRequest(id=id_, student_id=student_id, advisor_id=advisor_id, type="plan", term_id=5,
                               title="Spring 2027 plan", status=status, created_at=created, decided_at=decided,
                               decided_by=db.get(Advisor, advisor_id).user_id if decided else None))
    db.flush()


def reset_sequences(db: Session) -> None:
    """The seed inserts fixed IDs, so move each table's id sequence past them (new rows would collide otherwise)."""
    for table in Base.metadata.sorted_tables:
        pk = list(table.primary_key.columns)
        if len(pk) != 1 or not isinstance(pk[0].type, Integer):  # BigInteger is an Integer subclass
            continue
        column = pk[0].name
        sequence = db.execute(text("SELECT pg_get_serial_sequence(:table, :column)"), {"table": table.name, "column": column}).scalar()
        if sequence:  # None for keys without a sequence, e.g. advisor_student_assignments.student_id
            db.execute(text(f"SELECT setval(:seq, COALESCE((SELECT MAX({column}) FROM {table.name}), 0) + 1, false)"), {"seq": sequence})


def seed_integrations(db: Session) -> None:
    """CSV data import connected with two past imports; Email and the calendars off (spec 35)."""
    six_am = datetime.combine(today(), time(6, 0), local_zone()).astimezone(timezone.utc)
    db.add_all([
        Integration(id="csv", enabled=True, config={}, last_sync_at=six_am),
        Integration(id="mail", enabled=False, config={}),
        Integration(id="gcal", enabled=False, config={}),
        Integration(id="outlook", enabled=False, config={}),
    ])
    db.flush()
    db.add_all([
        IntegrationEvent(integration_id="csv", text="Imported 13 courses", created_at=six_am - timedelta(days=7)),
        IntegrationEvent(integration_id="csv", text="Imported 1,284 grades", created_at=six_am),
    ])
    raw = "acm_" + secrets.token_urlsafe(24)  # never shown: the demo key only fills the API keys card
    db.add(ApiKey(name="Reporting export", key_hash=sha256_hex(raw), last4=raw[-4:], scope="reports:read", created_by=3,
                  created_at=datetime(2026, 8, 12, 14, 0, tzinfo=local_zone()).astimezone(timezone.utc)))
    db.flush()


def seed_audit(db: Session) -> None:
    """Audit log demo events (spec 36), one or more per role, newest last. System events have no IP."""
    meeting_day = short_date(today() + timedelta(days=7))
    rows = [
        # id, days ago, time, actor id, label, role, action, summary, target, changes, ip, result, error
        (1801, 9, (9, 12), 3, "Jordan Lee", "Admin", "user.import", "Invited 12 students from a CSV import", None,
         {"created": 12}, "10.0.4.20", "success", None),
        (1802, 8, (11, 40), 3, "Jordan Lee", "Admin", "catalog.course.draft", "Changed CS 650 to not offered in Spring 2027",
         ("course", "CS 650"), {"offered": [True, False]}, "10.0.4.20", "success", None),
        (1803, 8, (11, 45), 3, "Jordan Lee", "Admin", "catalog.publish", "Published the 2026–27 catalog",
         ("catalog", "2026–27"), {"courses": 1, "requirements": 0, "terms": 0}, "10.0.4.20", "success", None),
        (1804, 6, (16, 10), 2, "Dr. Sarah Smith", "Advisor", "approval.request_changes",
         "Requested changes on Marcus R.'s Spring plan", ("user", 13), {"status": ["pending", "changes_requested"]},
         "10.0.4.12", "success", None),
        (1805, 5, (10, 5), 3, "Jordan Lee", "Admin", "advisor.reassign", "Reassigned 1 advisee to Maya Brooks",
         ("advisor", 203), {"moved": 1}, "10.0.4.20", "success", None),
        (1806, 4, (8, 30), None, "Acadmate", "System", "ai.autoflag", "Flagged an answer about visa rules for human review",
         ("ai_flag", 902), None, None, "success", None),
        (1807, 3, (14, 2), 3, "Jordan Lee", "Admin", "ai.settings", "Turned on grade-based insights", ("settings", "ai"),
         {"features.gradeInsights": [False, True]}, "10.0.4.20", "success", None),
        (1808, 2, (9, 15), 2, "Dr. Sarah Smith", "Advisor", "approval.approve", "Approved Spring 2027 plan for Hana S.",
         ("user", 12), {"status": ["pending", "approved"]}, "10.0.4.12", "success", None),
        (1809, 1, (17, 20), 1, "Amara Okafor", "Student", "auth.login_failed", "Failed sign-in for amara.okafor@pac.edu",
         ("user", 1), None, "73.41.18.9", "failed", "Wrong email or password"),
        (1810, 1, (17, 21), 1, "Amara Okafor", "Student", "auth.login", "Signed in from a new device", ("user", 1), None,
         "73.41.18.9", "success", None),
        (1811, 1, (17, 25), 1, "Amara Okafor", "Student", "meeting.book", f"Booked a meeting with Dr. Smith for {meeting_day}",
         ("meeting", 1502), None, "73.41.18.9", "success", None),
        (1812, 0, (6, 0), None, "CSV import", "System", "import.run", "Imported 1,284 grades from a CSV file",
         ("import", "grades"), {"created": 0, "updated": 1284, "skipped": 0}, None, "success", None),
    ]
    for (id_, days, (hour, minute), actor, label, role, action, summary, target, changes, ip, result, error) in rows:
        db.add(AuditEvent(id=id_, at=_local_at(days, hour, minute), actor_id=actor, actor_label=label, actor_role=role,
                          action=action, summary=summary, target_type=target[0] if target else None,
                          target_id=str(target[1]) if target else None, changes=changes, ip=ip, result=result, error=error))
    db.flush()


def seed(db: Session) -> None:
    """Adds all demo data to the session; the caller commits."""
    seed_programs(db)
    seed_terms(db)
    seed_people(db)
    seed_courses(db)
    seed_sections(db)
    seed_offerings(db)
    seed_enrollments(db)
    seed_grade_items(db)
    seed_coursework(db)
    seed_assignments(db)
    seed_requirements(db)
    seed_prerequisites(db)
    seed_plan(db)
    seed_preferences(db)
    seed_study_sessions(db)
    seed_events(db)
    seed_ai(db)
    seed_messages(db)
    seed_meetings(db)
    seed_overview(db)
    seed_integrations(db)
    seed_audit(db)
    reset_sequences(db)


def main() -> int:
    db = SessionLocal()
    try:
        seed(db)
        db.commit()
    except Exception as exc:
        db.rollback()
        print("Failed to insert demo data (run `python reset_db.py --yes` first to start from empty tables):")
        print(exc)
        return 1
    finally:
        db.close()
    print(f"Demo data inserted. Sign-in password for every demo user: {DEMO_PASSWORD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
