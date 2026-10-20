from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from core.deps import get_current_user
from database import get_db
from models import User
from routers.auth import clear_session_cookie
from schemas.auth import BadgesOut, MeOut
from schemas.users import (DeleteMeIn, GoogleConnectOut, PreferencesPatch, PreferencesResponse, ProfilePatch,
                           SettingsMeOut)
from services import auth, preferences, users
from services.audit import request_ip
from services.badges import badges_for

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


@router.get("/me/badges", response_model=BadgesOut)
def my_badges(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"badges": badges_for(db, user)}


@router.get("/me", response_model=SettingsMeOut)
def get_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return users.me(db, user)


@router.patch("/me", response_model=MeOut)
def update_me(body: ProfilePatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    updated = users.update_profile(db, user, body.model_dump(exclude_unset=True))
    return {"user": auth.user_payload(updated)}


@router.patch("/me/preferences", response_model=PreferencesResponse)
def update_preferences(body: PreferencesPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    preferences.update(db, user, body.changes())
    return {"preferences": users.preferences_out(db, user)}


@router.post("/me/google/connect", response_model=GoogleConnectOut)
def connect_google(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"url": users.google_connect(db, user)}


@router.delete("/me/google", status_code=status.HTTP_204_NO_CONTENT)
def disconnect_google(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    users.google_disconnect(db, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/me/export")
def export_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return users.export(db, user)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(request: Request, body: DeleteMeIn | None = None, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    users.delete_self(db, user, body.password if body else None, request_ip(request))
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_session_cookie(response)
    return response
