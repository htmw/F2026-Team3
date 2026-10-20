"""Public calendar feed (spec 14): no session cookie; the token in the URL is the credential."""
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from database import get_db
from services import calendar

router = APIRouter(prefix="/api/v1/calendar", tags=["Calendar feed"])


@router.get("/{token}.ics")
def calendar_feed(token: str, db: Session = Depends(get_db)):
    student = calendar.student_for_token(db, token)
    return Response(calendar.ics(db, student), media_type="text/calendar; charset=utf-8",
                    headers={"Cache-Control": "private, max-age=900"})
