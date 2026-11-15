"""Host only the isolated, cloned full-population team review demo."""
import os
from datetime import datetime,time,timezone
from pathlib import Path
from sqlalchemy.engine import make_url
from core.config import settings

url=make_url(settings.DATABASE_URL)
if url.host not in ("127.0.0.1","localhost") or url.port!=55439 or url.database!="acadmate_risk_team_review_sprint2":
    raise RuntimeError("Named loopback team-review database required")
if os.environ.get("ACADMATE_RISK_MVP_ENABLED")!="true" or settings.ACADMATE_TODAY is None:
    raise RuntimeError("Explicit demo opt-in and fixed date required")
import core.time as clock
fixed=datetime.combine(settings.ACADMATE_TODAY,time.max,timezone.utc)
clock.now=lambda:fixed
os.environ.setdefault("ACADMATE_PROJECT_HELP_ENABLED", "true")
os.environ.setdefault("ACADMATE_ADVISOR_DEFAULT_HOURS", "true")
import services
services.__path__.append(str(Path(__file__).resolve().parents[1]/"services"))
from main import app
from .main_router import router
app.include_router(router)

@app.middleware("http")
async def no_risk_response_cache(request,call_next):
    response=await call_next(request)
    if request.url.path.startswith("/api/v1/advisor/research/"):
        response.headers["Cache-Control"]="no-store, private"
    return response
