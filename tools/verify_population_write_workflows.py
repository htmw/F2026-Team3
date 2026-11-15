"""Exercise synthetic write workflows only on a new, disposable full-population clone."""
import argparse,hashlib,json,logging,os,subprocess,sys
from datetime import datetime,time,timezone
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
BASE="postgresql+psycopg://acadmate_demo@127.0.0.1:55439/"
SOURCE="acadmate_risk_team_review_sprint2"
TARGET="acadmate_risk_population_acceptance_"+datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")+"_test"
BIN=Path(r"C:\Program Files\PostgreSQL\18\bin")

def run(snapshot,output):
    snapshot=Path(snapshot).resolve();output=Path(output).resolve()
    if not snapshot.is_relative_to(ROOT/"ml/outputs/main-integration") or not output.is_relative_to(ROOT/"ml/outputs") or output.exists():
        raise ValueError("Reviewed export and new ignored output required")
    marker=json.loads((snapshot/"team-demo-manifest.json").read_text())
    assert marker["database"]==SOURCE and marker["state"]=="complete"
    output.mkdir(parents=True)
    os.environ.update(DATABASE_URL=BASE+TARGET,ACADMATE_TODAY="2027-02-16",ACADMATE_ADVISOR_DEFAULT_HOURS="true",ACADMATE_PROJECT_HELP_ENABLED="true")
    sys.path[:0]=[str(snapshot/"backend"),str(ROOT/"backend"),str(ROOT/"ml/src")]
    from sqlalchemy import create_engine,text
    from risk_mvp.main_data import snapshot as academic_snapshot,fingerprint
    original=create_engine(BASE+SOURCE)
    before=fingerprint(academic_snapshot(original))
    csv_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/"data/synthetic").glob("*.csv")}
    admin=create_engine(BASE+"postgres",isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        if conn.scalar(text("SELECT 1 FROM pg_database WHERE datname=:db"),{"db":TARGET}):raise ValueError("Existing acceptance clone preserved; choose a reviewed new target in source")
        archive=output/"private-clone.dump"
        subprocess.run([str(BIN/"pg_dump.exe"),"-h","127.0.0.1","-p","55439","-U","acadmate_demo","-Fc","--no-owner","--no-acl","-f",str(archive),SOURCE],check=True)
        conn.exec_driver_sql("CREATE DATABASE "+TARGET)
        subprocess.run([str(BIN/"pg_restore.exe"),"-h","127.0.0.1","-p","55439","-U","acadmate_demo","--no-owner","--no-acl","--single-transaction","-d",TARGET,str(archive)],check=True)
    from database import SessionLocal,engine
    assert engine.url.database==TARGET and engine.url.host=="127.0.0.1" and engine.url.port==55439
    import core.time as clock
    clock.now=lambda:datetime.combine(clock.today(),time.max,timezone.utc)
    from main import app
    from core.deps import get_current_user
    from models import Advisor,AdvisorStudentAssignment,Student,User
    from services import mailer
    from fastapi.testclient import TestClient
    for name in ("httpx2","httpx","acadmate.mail"):logging.getLogger(name).setLevel(logging.WARNING)
    def identity(user_id):
        with SessionLocal() as db:
            user=db.get(User,user_id);db.expunge(user)
        app.dependency_overrides[get_current_user]=lambda:user
    checks=0;records=[]
    with SessionLocal() as db:
        population=[(s.student_id,s.user_id,a.user_id) for s,assignment,a in db.query(Student,AdvisorStudentAssignment,Advisor).join(AdvisorStudentAssignment,AdvisorStudentAssignment.student_id==Student.student_id).join(Advisor,Advisor.advisor_id==AdvisorStudentAssignment.advisor_id).order_by(Student.student_id)]
    assert len(population)==100
    def call(method,path,body=None,status=200):
        nonlocal checks
        response=client.request(method,"/api/v1"+path,json=body) if body is not None else client.request(method,"/api/v1"+path)
        checks+=1
        assert response.status_code==status,(method,path,response.status_code,response.text[:500])
        return response.json() if response.content else None
    with patch.object(mailer,"send",return_value=None),patch.object(mailer,"_smtp_send",side_effect=AssertionError("No external mail")),TestClient(app,raise_server_exceptions=False) as client:
        for sid,student_user,advisor_user in population:
            record={"student_id":sid,"advisor_user_id":advisor_user}
            identity(advisor_user)
            slots=call("GET",f"/advisor/meetings/free-slots?date=2027-02-17&studentId={sid}")["slots"]
            assert slots
            booking={"studentId":sid,"startsAt":slots[0]["startsAt"],"format":"In person","topic":"Isolated acceptance check"}
            meeting=call("POST","/advisor/meetings",booking,status=201)
            assert meeting["studentId"]==sid and meeting["status"]=="confirmed"
            call("POST","/advisor/meetings",booking,status=409)
            identity(student_user)
            assert any(m["id"]==meeting["id"] and m["status"]=="confirmed" for m in call("GET","/students/me/meetings")["meetings"])
            call("POST",f"/meetings/{meeting['id']}/cancel",{})
            record["booking_confirm_visibility_conflict_cancel"]=True
            conversation=call("POST","/conversations",{"recipientIds":[advisor_user],"text":f"Synthetic acceptance question {sid}"},status=201)["id"]
            identity(advisor_user)
            assert any(m["text"]==f"Synthetic acceptance question {sid}" for m in call("GET",f"/conversations/{conversation}/messages")["messages"])
            call("POST",f"/conversations/{conversation}/messages",{"text":f"Synthetic acceptance reply {sid}"},status=201)
            identity(student_user)
            assert any(m["text"]==f"Synthetic acceptance reply {sid}" for m in call("GET",f"/conversations/{conversation}/messages")["messages"])
            record["message_round_trip"]=True
            plan=call("GET","/students/me/plan")
            assert plan["futureTerms"]
            term=plan["futureTerms"][-1]
            added=None
            for course in plan["available"]:
                response=client.post("/api/v1/students/me/plan",json={"courseCode":course["code"],"termId":term["id"],"note":"Isolated acceptance fixture"})
                checks+=1
                if response.status_code==201:
                    added=response.json();break
                assert response.status_code==400,(sid,response.status_code,response.text[:300])
            if added is None:
                record["plan_round_trip"]="no eligible new course; existing plan read succeeded"
            else:
                call("POST","/students/me/plan",{"courseCode":added["code"],"termId":term["id"]},status=409)
                submitted=call("POST","/students/me/plan/submit",{"termId":term["id"]})
                rid=submitted["requestId"]
                call("POST","/students/me/plan/submit",{"termId":term["id"]},status=409)
                identity(advisor_user)
                request=call("GET",f"/advisor/approvals/{rid}")
                assert request["studentId"]==sid and request["status"]=="Pending"
                comment="Please review the selected course before resubmitting."
                assert call("POST",f"/advisor/approvals/{rid}/request-changes",{"comment":comment})["status"]=="Changes requested"
                identity(student_user)
                term_data=next(t for t in call("GET","/students/me/plan")["terms"] if t["name"]==term["name"])
                assert term_data["advisorFeedback"]==comment
                rid=call("POST","/students/me/plan/submit",{"termId":term["id"]})["requestId"]
                identity(advisor_user)
                assert call("POST",f"/advisor/approvals/{rid}/approve",{"comment":"Synthetic course-choice approval only; offering checks still apply."})["status"]=="Approved"
                identity(student_user)
                term_data=next(t for t in call("GET","/students/me/plan")["terms"] if t["name"]==term["name"])
                assert term_data["advisorFeedback"] is None
                assert next(c for c in term_data["courses"] if c["code"]==added["code"])["planStatus"]=="Approved"
                record["plan_round_trip"]="changes requested, resubmitted, approved, feedback cleared"
            records.append(record)
            if len(records)%10==0:print(f"Verified {len(records)}/100 students",flush=True)
    app.dependency_overrides.clear()
    assert before==fingerprint(academic_snapshot(original))
    assert csv_hashes=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/"data/synthetic").glob("*.csv")}
    report={"passed":True,"students":len(records),"checks":checks,"write_target":TARGET,"source_academic_unchanged":True,"csv_unchanged":True,"external_delivery":False,"authentication":"dependency override in in-process test client; actual all-account login verified separately","records":records}
    (output/"results.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k!="records"},indent=2))

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--snapshot",required=True);p.add_argument("--output",required=True);a=p.parse_args();run(a.snapshot,a.output)
