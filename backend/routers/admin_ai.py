"""/admin/ai/* (spec 34): AI settings, the test box and flagged answers (also the overview's card, spec 30)."""
from typing import Literal

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from core.deps import require_role
from database import get_db
from models import User
from schemas.ai import AiSettingsOut, AiSettingsPatch, AiTestIn, AiTestOut, FlagResultOut, FlagsOut, ResolveIn
from services import ai
from services.ai import flags
from services.ai import settings as ai_config
from services.audit import request_ip

router = APIRouter(prefix="/api/v1/admin/ai", tags=["Admin · AI"])

admin_only = require_role("admin")


@router.get("/settings", response_model=AiSettingsOut)
def get_settings(user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return ai_config.public(db)


@router.patch("/settings", response_model=AiSettingsOut)
def update_settings(body: AiSettingsPatch, request: Request, user: User = Depends(admin_only),
                    db: Session = Depends(get_db)):
    return ai_config.update(db, user, body.model_dump(exclude_unset=True, by_alias=True), ip=request_ip(request))


@router.post("/test", response_model=AiTestOut)
def test_question(body: AiTestIn, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    patch = body.settings.model_dump(exclude_unset=True, by_alias=True)
    return ai.test_answer(db, body.student_id, body.question, patch)


@router.get("/flags", response_model=FlagsOut)
def list_flags(status: Literal["Open", "Resolved", "Dismissed", "All"] = "Open", user: User = Depends(admin_only),
               db: Session = Depends(get_db)):
    return flags.list_flags(db, status)


@router.post("/flags/{flag_id}/resolve", response_model=FlagResultOut)
def resolve_flag(flag_id: int, body: ResolveIn, request: Request, user: User = Depends(admin_only),
                 db: Session = Depends(get_db)):
    return {"flag": flags.resolve(db, user, flag_id, body.resolution, body.note, ip=request_ip(request))}


@router.post("/flags/{flag_id}/reopen", response_model=FlagResultOut)
def reopen_flag(flag_id: int, request: Request, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return {"flag": flags.reopen(db, user, flag_id, ip=request_ip(request))}
