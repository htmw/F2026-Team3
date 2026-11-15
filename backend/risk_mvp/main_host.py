"""Run only against the prepared disposable main integration database.

PYTHONPATH must place the isolated main backend first, then this branch backend.
"""
import os
from sqlalchemy.engine import make_url
from core.config import settings
url=make_url(settings.DATABASE_URL)
if url.host not in ('127.0.0.1','localhost') or url.database not in ('acadmate_risk_demo_main_sprint2', 'acadmate_risk_csv_sprint2'):
    raise RuntimeError('Dedicated disposable main integration database required')
if os.environ.get('ACADMATE_RISK_MVP_ENABLED')!='true':
    raise RuntimeError('Explicit research opt-in required')
# The full-population demo is one reproducible end-of-day snapshot across all roles.
if url.database == 'acadmate_risk_csv_sprint2':
    from datetime import datetime, time, timezone
    import core.time as _csv_clock
    if settings.ACADMATE_TODAY is None: raise RuntimeError('CSV demo requires an explicit date')
    _csv_now = datetime.combine(settings.ACADMATE_TODAY, time.max, timezone.utc)
    _csv_clock.now = lambda: _csv_now

from pathlib import Path
import services
services.__path__.append(str(Path(__file__).resolve().parents[1]/'services'))
from main import app
from .main_router import router
app.include_router(router)


@app.middleware('http')
async def prevent_assessment_caching(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith('/api/v1/advisor/research/'):
        response.headers['Cache-Control'] = 'no-store, private'
    return response
