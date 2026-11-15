"""Authenticated main integration. Loaded only by an isolated main-based host."""
from datetime import datetime
from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from core.deps import get_current_advisor, advisor_can_see
from core.errors import ApiError, not_found
from database import SessionLocal
from models import Advisor, Student, Enrollment, AdvisorStudentAssignment, Course
from . import service
from .models import Link, Offering

def read_research_db():
    # Keep assignment checks, academic inputs and temporal sources in one snapshot.
    with SessionLocal() as db:
        db.connection(execution_options={'isolation_level':'REPEATABLE READ'})
        db.execute(__import__('sqlalchemy').text('SET TRANSACTION READ ONLY'))
        yield db


router = APIRouter(prefix='/api/v1/advisor/research',tags=['Advisor research risk'])


def authorize(db, advisor, student_id):
    if db.get(Student,student_id) is None: raise not_found('Student')
    advisor_can_see(db,advisor.advisor_id,student_id)


@router.get('/students')
def students(advisor:Advisor=Depends(get_current_advisor),db:Session=Depends(read_research_db)):
    rows = db.execute(select(Student.student_id,Student.name).join(
        AdvisorStudentAssignment, Student.student_id==AdvisorStudentAssignment.student_id
    ).where(AdvisorStudentAssignment.advisor_id==advisor.advisor_id).order_by(Student.student_id)).mappings()
    return {'students':[dict(row) for row in rows]}


@router.get('/students/{student_id}/insights')
def insights(student_id:int=Path(gt=0),advisor:Advisor=Depends(get_current_advisor),db:Session=Depends(read_research_db)):
    authorize(db,advisor,student_id)
    result = service.insights(db,student_id)
    # Expose all enrollments, including historical ones, with explicit timing.
    e=service.T['enrollments'].c
    rows=db.execute(select(e.enrollment_id,e.course_id,e.term,e.status,
                           Offering.starts_at,Offering.ends_at,Course.course_code).join(Course,e.course_id==Course.course_id).outerjoin(Link,e.enrollment_id==Link.enrollment_id)
                    .outerjoin(Offering,Link.offering_id==Offering.id).where(e.student_id==student_id)
                    .order_by(e.enrollment_id)).mappings()
    result['enrollments']=[dict(row) for row in rows]
    from core.time import today
    result['demo_cutoff']=today().isoformat()+'T23:59:59.999999Z'
    result['simulation_notice']='Synthetic activity and historical trajectories; not observed LMS records.'
    return result


@router.get('/enrollments/{enrollment_id}/risk-assessment')
def assessment(enrollment_id:int=Path(gt=0),cutoff:datetime=Query(...),include_explanation:bool=Query(False),force_refresh:bool=Query(False),
               advisor:Advisor=Depends(get_current_advisor),db:Session=Depends(read_research_db)):
    student_id=db.scalar(select(Enrollment.student_id).where(Enrollment.enrollment_id==enrollment_id))
    if student_id is None:raise not_found('Enrollment')
    authorize(db,advisor,student_id)
    try:
        from .main_assessment_cache import assessment as cached_assessment
        result=cached_assessment(db,enrollment_id,cutoff,include_explanation,force_refresh)
    except service.InvalidCutoff as exc:raise ApiError(422,'INVALID_CUTOFF',str(exc)) from None
    except service.MissingEnrollment:raise not_found('Enrollment') from None
    except Exception:
        import logging
        logging.getLogger(__name__).exception('Main research inference failed')
        raise ApiError(503,'RESEARCH_DEMO_UNAVAILABLE','Research inference unavailable.') from None
    result['simulation_notice']='Synthetic activity and historical trajectories; not observed LMS records.'
    return result
