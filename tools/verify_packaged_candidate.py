"""Verify a checksum-reviewed packaged backend against the existing local synthetic DB, read-only academically."""
import argparse,csv,hashlib,json,logging,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def verify(source,output):
    source=Path(source).resolve();output=Path(output).resolve()
    if not (source==ROOT or source.is_relative_to(ROOT/"ml/outputs")) or not output.is_relative_to(ROOT/"ml/outputs") or output.exists():
        raise ValueError("Reviewed source and NEW ignored output required")
    manifest=json.loads((source/"MANIFEST.json").read_text())
    assert manifest["kind"]=="source_review_snapshot"
    for name,digest in manifest["files"].items():
        path=(source/name).resolve();assert path.is_relative_to(source)
        assert hashlib.sha256(path.read_bytes()).hexdigest()==digest,name
    os.environ.update(DATABASE_URL="postgresql+psycopg://acadmate_demo@127.0.0.1:55439/acadmate_risk_team_review_sprint2",ACADMATE_TODAY="2027-02-16",ACADMATE_RISK_MVP_ENABLED="true",ACADMATE_ADVISOR_DEFAULT_HOURS="true",SESSION_COOKIE="acadmate_team_review_session")
    sys.path[:0]=[str(source/"backend"),str(source/"ml/src")]
    from risk_mvp.team_host import app
    import risk_mvp.team_host as host
    import services.research_predictions as inference
    import acadmate_ml.features as features
    from risk_mvp.main_data import snapshot,fingerprint
    from database import engine
    assert all(Path(module.__file__).resolve().is_relative_to(source) for module in (host,inference,features))
    before=fingerprint(snapshot(engine))
    def rows(name):
        with (source/"data/synthetic"/(name+".csv")).open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
    students={int(s["user_id"]):int(s["student_id"]) for s in rows("students")}
    assignments={int(a["student_id"]):int(a["advisor_id"]) for a in rows("advisor_student_assignments")}
    advisors={int(a["user_id"]):int(a["advisor_id"]) for a in rows("advisors")}
    enrollments=rows("enrollments")
    from fastapi.testclient import TestClient
    for name in ("httpx2","httpx"):logging.getLogger(name).setLevel(logging.WARNING)
    calls=0;scored=0;accounts=0
    with TestClient(app,raise_server_exceptions=False) as client:
        def call(method,path,body=None):
            nonlocal calls
            response=client.request(method,"/api/v1"+path,json=body) if body is not None else client.request(method,"/api/v1"+path)
            calls+=1
            assert response.status_code in (200,204),(path,response.status_code,response.text[:350])
            return response.json() if response.content else None
        for user in rows("users"):
            uid=int(user["user_id"])
            identity=call("POST","/auth/login",{"email":user["email"],"password":"Acadmate!2026"})["user"]
            assert int(identity["id"])==uid and identity["role"]==user["role"]
            if user["role"]=="student":
                sid=students[uid]
                progress=call("GET",f"/students/{sid}/degree-progress")
                assert progress["studentId"]==sid
                call("GET","/students/me/plan")
                call("GET","/staff?bookable=true")
            elif user["role"]=="advisor":
                aid=advisors[uid];listing=call("GET","/advisor/advisees")
                ids={sid for sid,owner in assignments.items() if owner==aid}
                assert {r["studentId"] for r in listing["rows"]}==ids and len(ids)==25
                for row in enrollments:
                    if int(row["student_id"]) not in ids or row["status"]!="in_progress":continue
                    eid=int(row["enrollment_id"])
                    result=call("GET",f"/advisor/research/enrollments/{eid}/risk-assessment?cutoff=2027-02-16T23:59:59.999999Z&include_explanation=true&force_refresh=true")
                    assert result["status"]=="scored_research_demo" and result["student_id"]==int(row["student_id"])
                    assert result["explanation"]["status"]=="available"
                    scored+=1
            else:
                call("GET","/admin/overview")
            call("POST","/auth/logout",{})
            accounts+=1
    assert accounts==105 and scored==179 and before==fingerprint(snapshot(engine))
    report={"passed":True,"accounts":accounts,"active_scored_and_explained":scored,"http_checks":calls,"source_manifest_verified":True,"imports_from_package":True,"source_academic_unchanged":True,"scope":"In-process packaged app with real synthetic logins and actual frozen inference; not a fresh-machine DB install or browser UI review"}
    output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8");print(json.dumps(report,indent=2))

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--source",required=True);p.add_argument("--output",required=True);a=p.parse_args();verify(a.source,a.output)
