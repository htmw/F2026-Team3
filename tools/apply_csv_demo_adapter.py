"""Apply CSV-only compatibility to the isolated exported app, never shared source."""
from pathlib import Path
import argparse
from apply_main_dashboard_review import ROOT,replace

def apply(snapshot):
    snap=Path(snapshot).resolve()
    if not snap.is_relative_to(ROOT/'ml/outputs/main-integration'):raise ValueError('Isolated export required')
    p=snap/'backend/schemas/auth.py';s=p.read_text(encoding='utf-8')
    alias=r"""# Reserved synthetic addresses are accepted for login only in the named local CSV demo.
from core.config import settings as _demo_settings
from sqlalchemy.engine import make_url as _make_url
_demo_url = _make_url(_demo_settings.DATABASE_URL)
DemoLoginEmail = EmailStr
if _demo_url.host in ('127.0.0.1', 'localhost') and _demo_url.database == 'acadmate_risk_csv_sprint2':
    DemoLoginEmail = EmailStr | Annotated[str, StringConstraints(pattern=r"^[a-zA-Z0-9._+-]+@example\.invalid$", max_length=100)]


"""
    if 'DemoLoginEmail = EmailStr' not in s:s=s.replace('class LoginIn(ApiModel):',alias+'class LoginIn(ApiModel):',1)
    s=replace(s,'class LoginIn(ApiModel):\n    email: EmailStr','class LoginIn(ApiModel):\n    email: DemoLoginEmail')
    p.write_text(s,encoding='utf-8')
    print('CSV-only reserved-domain login compatibility applied; signup and reset validators unchanged.')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);apply(p.parse_args().snapshot)
