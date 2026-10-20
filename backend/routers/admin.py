"""/admin/* (spec 30 overview, spec 31 users, spec 32 advisors, spec 36 audit log, spec 37 settings). Later admin specs add routes here or in sibling
admin_*.py routers."""
from typing import Literal

from fastapi import APIRouter, Body, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from core.config import settings as env
from core.deps import require_role
from core.errors import bad_request
from database import get_db
from models import User
from schemas.admin import (AddAdvisorIn, AdminAdvisorRow, AdminUserRow, AdminUsersOut, AdvisorPatch, AdvisorsOut,
                           AuditListOut, ImportOut, InviteIn, InviteOut, OverviewOut, ReassignIn, ReassignOut, UserPatch)
from schemas.settings import DemoResetOut, SettingsOut, SettingsPatch
from services import admin_advisors, admin_overview, admin_users, audit, demo, settings
from services.audit import request_ip

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])

admin_only = require_role("admin")


@router.get("/overview", response_model=OverviewOut)
def get_overview(user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return admin_overview.overview(db)


@router.get("/overview.csv")
def export_overview(request: Request, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    body = admin_overview.export_csv(db, user, ip=request_ip(request))
    return Response(body, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{admin_overview.csv_filename()}"'})


# --- users (spec 31) ----------------------------------------------------------------------------------------------

@router.get("/users", response_model=AdminUsersOut)
def list_users(role: str = "all", q: str = "", status_: Literal["Active", "Invited", "Deactivated"] | None =
               Query(None, alias="status"), page: int = Query(1, ge=1),
               page_size: int = Query(50, ge=1, le=200, alias="pageSize"),
               user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return admin_users.list_users(db, role, q, status_, page, page_size)


@router.post("/users/invite", response_model=InviteOut)
def invite_users(body: InviteIn, request: Request, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return admin_users.invite(db, user, body.emails, body.role, ip=request_ip(request))


@router.post("/users/import", response_model=ImportOut)
def import_users(request: Request, body: bytes = Body(..., media_type="text/csv"), user: User = Depends(admin_only),
                 db: Session = Depends(get_db)):
    if len(body) > admin_users.MAX_IMPORT_BYTES:
        raise bad_request("The file is larger than 1 MB.")
    try:
        text = body.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise bad_request("Save the file as a UTF-8 CSV.") from None
    return admin_users.import_csv(db, user, text, ip=request_ip(request))


@router.patch("/users/{user_id}", response_model=AdminUserRow)
def update_user(user_id: int, body: UserPatch, request: Request, user: User = Depends(admin_only),
                db: Session = Depends(get_db)):
    patch = body.model_dump(by_alias=True, exclude_unset=True)
    return admin_users.update(db, user, user_id, patch, ip=request_ip(request))


@router.post("/users/{user_id}/reset", status_code=status.HTTP_202_ACCEPTED)
def reset_user(user_id: int, request: Request, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    admin_users.send_reset(db, user, user_id, ip=request_ip(request))
    return {"ok": True}


# --- advisors (spec 32) -------------------------------------------------------------------------------------------

@router.get("/advisors", response_model=AdvisorsOut)
def list_advisors(user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return {"advisors": admin_advisors.list_advisors(db)}


@router.post("/advisors", response_model=AdminAdvisorRow, status_code=status.HTTP_201_CREATED)
def add_advisor(body: AddAdvisorIn, request: Request, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return admin_advisors.add(db, user, body.model_dump(), ip=request_ip(request))


@router.patch("/advisors/{advisor_id}", response_model=AdminAdvisorRow)
def update_advisor(advisor_id: int, body: AdvisorPatch, request: Request, user: User = Depends(admin_only),
                   db: Session = Depends(get_db)):
    return admin_advisors.update(db, user, advisor_id, body.model_dump(exclude_unset=True), ip=request_ip(request))


@router.post("/advisors/{advisor_id}/reassign", response_model=ReassignOut)
def reassign_advisees(advisor_id: int, body: ReassignIn, request: Request, user: User = Depends(admin_only),
                      db: Session = Depends(get_db)):
    return admin_advisors.reassign(db, user, advisor_id, body.to_advisor_id, count=body.count,
                                   student_ids=body.student_ids, ip=request_ip(request))


# --- audit log (spec 36) ------------------------------------------------------------------------------------------

AuditRole = Literal["All", "Admin", "Advisor", "Student", "System"]
AuditRange = Literal["today", "7d", "30d"]


@router.get("/audit", response_model=AuditListOut)
def list_audit(role: AuditRole = "All", range_: AuditRange = Query("30d", alias="range"),
               q: str | None = Query(None, max_length=100), cursor: str | None = Query(None, max_length=20),
               user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return audit.list_events(db, role, range_, q, cursor)


@router.get("/audit.csv")
def export_audit(request: Request, role: AuditRole = "All", range_: AuditRange = Query("30d", alias="range"),
                 q: str | None = Query(None, max_length=100), user: User = Depends(admin_only),
                 db: Session = Depends(get_db)):
    body = audit.export_csv(db, user, role, range_, q, ip=request_ip(request))
    return Response(body, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{audit.csv_filename()}"'})


# --- settings (spec 37) -------------------------------------------------------------------------------------------

@router.get("/settings", response_model=SettingsOut)
def get_settings(user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return settings.get_all(db)


@router.patch("/settings", response_model=SettingsOut)
def update_settings(body: SettingsPatch, request: Request, user: User = Depends(admin_only),
                    db: Session = Depends(get_db)):
    patch = body.model_dump(by_alias=True, exclude_unset=True)
    return settings.update(db, user, patch, ip=request_ip(request))


@router.post("/demo/reset", response_model=DemoResetOut, status_code=status.HTTP_202_ACCEPTED)
def reset_demo(request: Request, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return demo.reset(db, user, request.cookies.get(env.SESSION_COOKIE), ip=request_ip(request))
