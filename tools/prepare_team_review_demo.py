"""Clone the existing local synthetic demo into a NEW team-review database only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
SOURCE="acadmate_risk_csv_sprint2"
TARGET="acadmate_risk_team_review_sprint2"
BASE="postgresql+psycopg://acadmate_demo@127.0.0.1:55439/"
BIN=Path(r"C:\Program Files\PostgreSQL\18\bin")

def prepare(snapshot):
    snapshot=Path(snapshot).resolve()
    if not snapshot.is_relative_to(ROOT/"ml/outputs/main-integration"):
        raise ValueError("Isolated team snapshot required")
    provenance=json.loads((snapshot/"team-review-manifest.json").read_text(encoding="utf-8"))
    if provenance["main_commit"]!="9dba938da14df8607c81b6f92988e8210977bf24":
        raise ValueError("Reviewed source commit required")
    os.environ.update(DATABASE_URL=BASE+TARGET,ACADMATE_TODAY="2027-02-16")
    sys.path[:0]=[str(snapshot/"backend"),str(ROOT/"backend"),str(ROOT/"ml/src")]
    from sqlalchemy import create_engine,text
    from risk_mvp import main_data
    source=create_engine(BASE+SOURCE)
    original=main_data.fingerprint(main_data.snapshot(source))
    expected=dict(users=105,students=100,advisors=4,programs=1,courses=30,enrollments=800,advisor_student_assignments=100,program_requirements=3)
    with source.connect() as conn:
        conn.exec_driver_sql("SET TRANSACTION READ ONLY")
        assert {t:conn.scalar(text("SELECT count(*) FROM "+t)) for t in expected}==expected
    marker=snapshot/"team-demo-manifest.json"
    admin=create_engine(BASE+"postgres",isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists=conn.scalar(text("SELECT 1 FROM pg_database WHERE datname=:name"),{"name":TARGET})
        if exists and not marker.exists():raise ValueError("Existing target without provenance; refusing overwrite")
        if not exists:
            archive=snapshot/"team-demo-source.dump"
            if archive.exists():raise ValueError("Existing dump requires manual review")
            subprocess.run([str(BIN/"pg_dump.exe"),"-h","127.0.0.1","-p","55439","-U","acadmate_demo","-Fc","--no-owner","--no-acl","-f",str(archive),SOURCE],check=True)
            conn.exec_driver_sql("CREATE DATABASE "+TARGET)
            subprocess.run([str(BIN/"pg_restore.exe"),"-h","127.0.0.1","-p","55439","-U","acadmate_demo","--no-owner","--no-acl","--single-transaction","-d",TARGET,str(archive)],check=True)
            target=create_engine(BASE+TARGET)
            assert main_data.fingerprint(main_data.snapshot(target))==original
            marker.write_text(json.dumps({"state":"cloned","database":TARGET,"source_database":SOURCE,"academic_sha256":original,"counts":expected,"demo_day":"2027-02-16","main_commit":provenance["main_commit"],"dump_sha256":hashlib.sha256(archive.read_bytes()).hexdigest()},indent=2)+"\n",encoding="utf-8")
            target.dispose()
    target=create_engine(BASE+TARGET)
    saved=json.loads(marker.read_text(encoding="utf-8"))
    assert saved["database"]==TARGET and saved["source_database"]==SOURCE
    assert main_data.fingerprint(main_data.snapshot(target))==saved["academic_sha256"]
    if saved["state"]=="cloned":
        with target.begin() as db:
            db.exec_driver_sql("ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT false")
            db.exec_driver_sql("DELETE FROM sessions")
        saved["state"]="complete"
        marker.write_text(json.dumps(saved,indent=2)+"\n",encoding="utf-8")
    if saved["state"]!="complete":raise ValueError("Unexpected setup state")
    target.dispose()
    admin.dispose()
    # Reserved fictional emails remain permitted for login only on this one demo.
    auth=snapshot/"backend/schemas/auth.py"
    contents=auth.read_text(encoding="utf-8")
    if "TeamReviewLoginEmail" not in contents:
        alias=r'''from core.config import settings as _review_settings
from sqlalchemy.engine import make_url as _review_url
_rurl=_review_url(_review_settings.DATABASE_URL)
TeamReviewLoginEmail=EmailStr
if _rurl.host in ("127.0.0.1","localhost") and _rurl.port==55439 and _rurl.database=="acadmate_risk_team_review_sprint2":
    TeamReviewLoginEmail=EmailStr | Annotated[str,StringConstraints(pattern=r"^[a-zA-Z0-9._+-]+@example\.invalid$",max_length=100)]


'''
        old="class LoginIn(ApiModel):\n    email: EmailStr"
        if contents.count(old)!=1:raise ValueError("Login schema changed; manual review required")
        contents=contents.replace("class LoginIn(ApiModel):",alias+"class LoginIn(ApiModel):",1).replace(old,"class LoginIn(ApiModel):\n    email: TeamReviewLoginEmail",1)
        auth.write_text(contents,encoding="utf-8")
    target=create_engine(BASE+TARGET)
    saved=json.loads(marker.read_text(encoding="utf-8"))
    assert main_data.fingerprint(main_data.snapshot(target))==saved["academic_sha256"]
    assert main_data.fingerprint(main_data.snapshot(source))==original
    print(json.dumps(saved,indent=2))
    source.dispose();target.dispose()

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot",required=True)
    prepare(parser.parse_args().snapshot)
