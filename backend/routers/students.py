from datetime import date

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from core.deps import get_current_student, get_current_user, require_role
from database import get_db
from models import Student, User
from schemas.assignments import AssignmentsOut
from schemas.calendar import EventIn, EventOut, EventPatch, FeedOut, WeekOut
from schemas.courses import MyCoursesOut
from schemas.dashboard import DashboardOut
from schemas.meetings import MeetingListOut
from schemas.plan import AuditOut, PlanAddIn, PlanAddOut, PlanOut, PlanSubmitIn, SubmitOut
from schemas.students import AcademicProfileResponse
from services import assignments, calendar, meetings, plan
from services.courses import my_courses
from services.dashboard import build_dashboard
from services.degree_audit import degree_audit
from services.students import ensure_can_view, get_student_profile


router = APIRouter(
    prefix="/api/v1/students",
    tags=["Students"]
)


# /me/* routes come before /{student_id}/* so "me" is never parsed as an id.
@router.get("/me/dashboard", response_model=DashboardOut)
def get_my_dashboard(student: Student = Depends(get_current_student), db: Session = Depends(get_db)):
    return build_dashboard(db, student)


@router.get("/me/courses", response_model=MyCoursesOut)
def get_my_courses(student: Student = Depends(get_current_student), db: Session = Depends(get_db)):
    return my_courses(db, student)


@router.get("/me/degree-audit", response_model=AuditOut)
def get_my_degree_audit(student: Student = Depends(get_current_student), db: Session = Depends(get_db)):
    return degree_audit(db, student)


@router.get("/me/plan", response_model=PlanOut)
def get_my_plan(student: Student = Depends(get_current_student), db: Session = Depends(get_db)):
    return plan.get_plan(db, student)


@router.post("/me/plan", response_model=PlanAddOut, status_code=status.HTTP_201_CREATED)
def add_to_my_plan(body: PlanAddIn, student: Student = Depends(get_current_student),
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return plan.add_item(db, student, user, body.course_code, body.term_id, body.note)


@router.post("/me/plan/submit", response_model=SubmitOut)
def submit_my_plan(body: PlanSubmitIn, student: Student = Depends(get_current_student),
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return plan.submit_term(db, student, user, body.term_id)


@router.delete("/me/plan/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_from_my_plan(item_id: int, student: Student = Depends(get_current_student),
                        user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plan.remove_item(db, student, user, item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me/assignments", response_model=AssignmentsOut)
def get_my_assignments(student: Student = Depends(get_current_student), db: Session = Depends(get_db)):
    return assignments.payload(db, student)


@router.get("/me/events", response_model=WeekOut)
def get_my_events(from_: date | None = Query(None, alias="from"), to: date | None = Query(None),
                  student: Student = Depends(get_current_student), db: Session = Depends(get_db)):
    return calendar.week(db, student, from_, to)


@router.post("/me/events", response_model=EventOut, status_code=status.HTTP_201_CREATED)
def create_my_event(body: EventIn, student: Student = Depends(get_current_student), db: Session = Depends(get_db)):
    return calendar.create_event(db, student, body.model_dump())


@router.patch("/me/events/{event_id}", response_model=EventOut)
def update_my_event(event_id: str, body: EventPatch, student: Student = Depends(get_current_student),
                    db: Session = Depends(get_db)):
    return calendar.update_event(db, student, event_id, body.model_dump(exclude_unset=True))


@router.delete("/me/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_event(event_id: str, student: Student = Depends(get_current_student), db: Session = Depends(get_db)):
    calendar.delete_event(db, student, event_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me/calendar", response_model=FeedOut)
def get_my_calendar_feed(request: Request, student: Student = Depends(get_current_student), db: Session = Depends(get_db)):
    return {"url": calendar.feed_url(db, student, str(request.base_url))}


@router.post("/me/calendar/rotate", response_model=FeedOut)
def rotate_my_calendar_feed(request: Request, student: Student = Depends(get_current_student),
                            db: Session = Depends(get_db)):
    return {"url": calendar.feed_url(db, student, str(request.base_url), rotate=True)}


@router.get("/me/calendar.ics")
def download_my_calendar(student: Student = Depends(get_current_student), db: Session = Depends(get_db)):
    return Response(calendar.ics(db, student), media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="acadmate.ics"'})


@router.get("/me/meetings", response_model=MeetingListOut)
def get_my_meetings(student: Student = Depends(get_current_student), db: Session = Depends(get_db)):
    return {"meetings": meetings.upcoming_for_student(db, student)}


@router.get(
    "/{student_id}/academic-profile",
    response_model=AcademicProfileResponse
)
def get_academic_profile(student_id: int, user: User = Depends(require_role("advisor", "admin")), db: Session = Depends(get_db)):
    ensure_can_view(db, user, student_id)
    return get_student_profile(db, student_id)
