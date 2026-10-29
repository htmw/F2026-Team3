"""/advisor/* (spec 20 dashboard, spec 21 advisees, spec 22 student record, spec 26 reports, spec 27 settings). The approvals queue and its decisions
(spec 23) are in advisor_approvals.py; later advisor specs add routes here or in sibling advisor_*.py routers."""
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from core.deps import get_current_advisor
from database import get_db
from models import Advisor
from schemas.advisor import (AdviseesOut, AdvisorDashboardOut, AdvisorSettingsOut, AdvisorSettingsPatch, NoteIn, NoteOut,
                             RecordOut, ReportOut, SharedThreadsOut)
from services import advisees, advisor_dashboard, advisor_reports, advisor_settings, student_record

router = APIRouter(prefix="/api/v1/advisor", tags=["Advisor"])


@router.get("/dashboard", response_model=AdvisorDashboardOut)
def get_dashboard(advisor: Advisor = Depends(get_current_advisor), db: Session = Depends(get_db)):
    return advisor_dashboard.build(db, advisor)


@router.get("/advisees", response_model=AdviseesOut)
def list_advisees(status: Literal["All", "Needs attention", "On track", "Graduating", "At risk"] = "All",
                  q: str | None = Query(None, max_length=100), advisor: Advisor = Depends(get_current_advisor),
                  db: Session = Depends(get_db)):
    return advisees.list_for(db, advisor, status, q)


@router.get("/settings", response_model=AdvisorSettingsOut)
def get_settings(advisor: Advisor = Depends(get_current_advisor), db: Session = Depends(get_db)):
    return advisor_settings.get(db, advisor)


@router.patch("/settings", response_model=AdvisorSettingsOut)
def update_settings(body: AdvisorSettingsPatch, advisor: Advisor = Depends(get_current_advisor),
                    db: Session = Depends(get_db)):
    data = body.model_dump(by_alias=True, exclude_unset=True)
    return advisor_settings.update(db, advisor, data)


@router.get("/reports", response_model=ReportOut)
def get_report(term: int | None = None, advisor: Advisor = Depends(get_current_advisor), db: Session = Depends(get_db)):
    return advisor_reports.report(db, advisor, term)


@router.get("/reports.csv")
def export_report(term: int | None = None, advisor: Advisor = Depends(get_current_advisor), db: Session = Depends(get_db)):
    body, filename = advisor_reports.export_csv(db, advisor, term)
    db.commit()
    return Response(body, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/advisees/{student_id}", response_model=RecordOut)
def get_record(student_id: int, advisor: Advisor = Depends(get_current_advisor), db: Session = Depends(get_db)):
    return student_record.record(db, advisor, student_id)


@router.post("/advisees/{student_id}/notes", response_model=NoteOut, status_code=201)
def add_note(student_id: int, body: NoteIn, advisor: Advisor = Depends(get_current_advisor),
             db: Session = Depends(get_db)):
    note = student_record.add_note(db, advisor, student_id, body.text)
    db.commit()
    return note


@router.delete("/notes/{note_id}", status_code=204)
def delete_note(note_id: int, advisor: Advisor = Depends(get_current_advisor), db: Session = Depends(get_db)):
    student_record.delete_note(db, advisor, note_id)
    db.commit()


@router.get("/advisees/{student_id}/ai-threads", response_model=SharedThreadsOut)
def shared_ai_threads(student_id: int, advisor: Advisor = Depends(get_current_advisor), db: Session = Depends(get_db)):
    return student_record.ai_threads(db, advisor, student_id)

