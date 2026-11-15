"""All-account GET acceptance through the team frontend proxy; no academic writes."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from decimal import Decimal
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import sys
import urllib.request
import urllib.error
import urllib.parse
ROOT=Path(__file__).resolve().parents[1]
BASE="http://127.0.0.1:5179/api/v1"


def verify(snapshot,output):
    snapshot=Path(snapshot).resolve();output=Path(output).resolve()
    if not snapshot.is_relative_to(ROOT/"ml/outputs/main-integration") or not output.is_relative_to(ROOT/"ml/outputs") or output.exists():
        raise ValueError("Verified isolated snapshot and new ignored output file required")
    marker=json.loads((snapshot/"team-demo-manifest.json").read_text())
    assert marker["state"]=="complete" and marker["database"]=="acadmate_risk_team_review_sprint2"
    os.environ.update(DATABASE_URL="postgresql+psycopg://acadmate_demo@127.0.0.1:55439/acadmate_risk_team_review_sprint2",ACADMATE_TODAY="2027-02-16")
    sys.path[:0]=[str(snapshot/"backend"),str(ROOT/"backend"),str(ROOT/"ml/src")]
    from seed_data import DEMO_PASSWORD
    from database import engine
    from risk_mvp.main_data import snapshot as academic_snapshot,fingerprint
    before=fingerprint(academic_snapshot(engine))
    def read(name):
        with (ROOT/"data/synthetic"/f"{name}.csv").open(encoding="utf-8-sig",newline="") as stream:return list(csv.DictReader(stream))
    data={name:read(name) for name in ("users","students","advisors","enrollments","courses","program_requirements","programs","advisor_student_assignments")}
    hashes={name:hashlib.sha256((ROOT/"data/synthetic"/f"{name}.csv").read_bytes()).hexdigest() for name in data}
    assert len(data["users"])==105 and len(data["students"])==100 and len(data["enrollments"])==800
    students={int(s["user_id"]):s for s in data["students"]}
    advisors={int(a["user_id"]):a for a in data["advisors"]}
    courses={c["course_id"]:Decimal(c["credits"]) for c in data["courses"]}
    programs={p["program_id"]:Decimal(p["total_required_credits"]) for p in data["programs"]}
    owners={int(a["student_id"]):int(a["advisor_id"]) for a in data["advisor_student_assignments"]}
    def check(user):
        op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        calls=0;denials=0;followups=0
        def call(path,body=None):
            nonlocal calls
            calls+=1
            request=urllib.request.Request(BASE+path,data=json.dumps(body).encode() if body is not None else None,headers={"Content-Type":"application/json"})
            with op.open(request,timeout=60) as response:
                raw=response.read();return json.loads(raw) if raw else None
        def deny(path,status):
            nonlocal denials
            try:call(path)
            except urllib.error.HTTPError as error:
                assert error.code==status,(path,error.code,status)
                denials+=1;return
            raise AssertionError("Unexpected role/assignment access: "+path)
        result={"user_id":int(user["user_id"]),"role":user["role"]}
        try:
            login=call("/auth/login",{"email":user["email"],"password":DEMO_PASSWORD})
            assert login["user"]["role"]==user["role"]
            assert int(call("/auth/me")["user"]["id"])==int(user["user_id"])
            call("/users/me");call("/users/me/badges");call("/conversations")
            contacts=call("/conversations/contacts")["contacts"]
            if user["role"]=="student":
                student=students[int(user["user_id"])];sid=int(student["student_id"])
                for suffix in ("dashboard","courses","assignments","events","degree-audit","plan","meetings","ai/context","ai/threads"):
                    call("/students/me/"+suffix)
                progress=call("/students/me/degree-progress")
                assert progress["studentId"]==sid
                done={e["course_id"] for e in data["enrollments"] if e["student_id"]==str(sid) and e["status"]=="completed" and e["grade"].upper()!="F"}
                expected=sum((min(Decimal(g["required_credits"]),sum((courses[c] for c in done & {str(v) for v in json.loads(g["eligible_course_ids"])}),Decimal(0))) for g in data["program_requirements"] if g["program_id"]==student["program_id"]),Decimal(0))
                required=programs[student["program_id"]];expected=min(expected,required)
                assert progress["earnedCredits"]==float(expected) and progress["remainingCredits"]==float(required-expected)
                staff=call("/staff?bookable=true")
                owner=next(a for a in data["advisors"] if int(a["advisor_id"])==owners[sid])
                assert int(owner["user_id"]) in {c["id"] for c in contacts}
                deny("/advisor/advisees",403);deny("/admin/overview",403)
            elif user["role"]=="advisor":
                advisor=advisors[int(user["user_id"])];aid=int(advisor["advisor_id"])
                listing=call("/advisor/advisees")
                expected={sid for sid,owner in owners.items() if owner==aid}
                assert len(expected)==25 and {x["studentId"] for x in listing["rows"]}==expected
                # Contacts are search-limited to 20; query the exact selected person.
                contact_ids={c["id"] for c in contacts}
                for suffix in ("dashboard","reports","meetings","approvals"):
                    call("/advisor/"+suffix)
                for row in listing["rows"]:
                    sid=row["studentId"];record=call(f"/advisor/advisees/{sid}")
                    student=next(s for s in data["students"] if int(s["student_id"])==sid)
                    assert record["student"]["id"]==sid and record["student"]["userId"]==int(student["user_id"])
                    assert row["userId"]==record["student"]["userId"], (sid,"Recipient identity mismatch")
                    selected_contacts=call("/conversations/contacts?q="+urllib.parse.quote(student["name"]))["contacts"]
                    assert row["userId"] in {c["id"] for c in selected_contacts}, (sid,"Assigned recipient absent from exact-name search")
                    slots=call(f"/advisor/meetings/free-slots?date=2027-02-17&studentId={sid}")
                    assert isinstance(slots["slots"],list)
                    followups+=1
                for sid in owners:
                    if sid not in expected:deny(f"/advisor/advisees/{sid}",403)
                deny("/admin/overview",403)
            else:
                for suffix in ("overview","advisors","catalog/summary","catalog/courses","catalog/requirements","catalog/terms","ai/settings","ai/flags","integrations","audit","settings"):
                    call("/admin/"+suffix)
                users=call("/admin/users?pageSize=200")
                assert users["total"]==105 and len(users["rows"])==105
                deny("/advisor/research/students",403)
            call("/auth/logout",{})
            deny("/auth/me",401)
            result.update(passed=True,responses=calls,denials=denials,followup_contexts=followups)
        except Exception as error:
            result.update(passed=False,error=repr(error),responses=calls,denials=denials,followup_contexts=followups)
        return result
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(check,data["users"]))
    after=fingerprint(academic_snapshot(engine));assert before==after
    assert hashes=={name:hashlib.sha256((ROOT/"data/synthetic"/f"{name}.csv").read_bytes()).hexdigest() for name in data}
    failures=[row for row in results if not row["passed"]]
    report={"passed":not failures,"accounts":len(results),"responses":sum(x["responses"] for x in results),"denials":sum(x["denials"] for x in results),"followup_contexts":sum(x.get("followup_contexts",0) for x in results),"academic_sha256":before,"csv_unchanged":True,"failures":failures,"scope":"Authenticated GET workflows through frontend proxy; login/logout only mutations; not browser visual QA or external provider delivery","records":results}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("x",encoding="utf-8") as stream:json.dump(report,stream,indent=2)
    print(json.dumps({k:v for k,v in report.items() if k!="records"},indent=2))
    if failures:raise SystemExit(1)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--snapshot",required=True);p.add_argument("--output",required=True);a=p.parse_args();verify(a.snapshot,a.output)
