"""/admin/integrations, /admin/imports, /admin/api-keys and /admin/reports/* (spec 35)."""
from typing import Literal

from fastapi import APIRouter, Body, Depends, Header, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from core.config import settings
from core.deps import ReportCaller, reports_access, require_role
from core.errors import bad_request
from database import get_db
from models import User
from schemas.integrations import (ApiKeyCreated, ApiKeyIn, ApiKeysOut, ImportOut, IntegrationOut, IntegrationsOut,
                                  OAuthUrlOut, SmtpIn)
from services import admin_overview, api_keys, imports, integrations
from services.audit import request_ip

router = APIRouter(prefix="/api/v1/admin", tags=["Admin · Integrations"])

admin_only = require_role("admin")


@router.get("/integrations", response_model=IntegrationsOut)
def list_integrations(user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return integrations.list_all(db)


@router.post("/integrations/{integration_id}/connect", response_model=IntegrationOut | OAuthUrlOut)
def connect(integration_id: str, request: Request, body: SmtpIn | None = None, user: User = Depends(admin_only),
            db: Session = Depends(get_db)):
    """SMTP takes the server settings and sends a test email first; a calendar returns the provider's sign-in URL."""
    smtp = body.model_dump(by_alias=True) if body else None
    return integrations.connect(db, user, integration_id, smtp, str(request.base_url), ip=request_ip(request))


@router.get("/integrations/{integration_id}/callback", include_in_schema=False)
def oauth_callback(integration_id: str, request: Request, code: str | None = None, state: str | None = None,
                   user: User = Depends(admin_only), db: Session = Depends(get_db)):
    integrations.oauth_callback(db, user, integration_id, code, state, str(request.base_url), ip=request_ip(request))
    return RedirectResponse(f"{settings.FRONTEND_ORIGIN}/admin/integrations?id={integration_id}", status_code=303)


@router.post("/integrations/{integration_id}/disconnect", response_model=IntegrationOut)
def disconnect(integration_id: str, request: Request, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return integrations.disconnect(db, user, integration_id, ip=request_ip(request))


@router.post("/integrations/{integration_id}/sync", response_model=IntegrationOut)
def sync(integration_id: str, request: Request, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return integrations.sync(db, user, integration_id, ip=request_ip(request))


@router.post("/imports", response_model=ImportOut)
def run_import(request: Request, type: Literal["courses", "enrollments", "grades"] = Query(...),
               body: bytes = Body(..., media_type="text/csv"), x_filename: str | None = Header(None, max_length=200),
               user: User = Depends(admin_only), db: Session = Depends(get_db)):
    if len(body) > imports.MAX_IMPORT_BYTES:
        raise bad_request("The file is larger than 1 MB.")
    try:
        text = body.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise bad_request("Save the file as a UTF-8 CSV.") from None
    return imports.run(db, user, type, text, x_filename, ip=request_ip(request))


@router.get("/api-keys", response_model=ApiKeysOut)
def list_keys(user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return api_keys.list_keys(db)


@router.post("/api-keys", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
def create_key(body: ApiKeyIn, request: Request, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return api_keys.create(db, user, body.name, body.scope, ip=request_ip(request))


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_key(key_id: int, request: Request, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    api_keys.revoke(db, user, key_id, ip=request_ip(request))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/reports/overview.csv")
def overview_report(request: Request, caller: ReportCaller = Depends(reports_access), db: Session = Depends(get_db)):
    """The platform overview CSV for reporting tools (`Authorization: Bearer acm_…`) or a signed-in admin."""
    body = admin_overview.export_csv(db, caller.user, ip=request_ip(request), key_name=caller.key.name if caller.key else None)
    return Response(body, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{admin_overview.csv_filename()}"'})
