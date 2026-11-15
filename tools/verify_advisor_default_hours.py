"""Verify all four advisor defaults and 100 next-day booking contexts; no bookings or academic writes."""
import argparse,csv,hashlib,http.cookiejar,json,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE="http://127.0.0.1:5179/api/v1"

def verify(output):
    output=Path(output).resolve()
    if not output.is_relative_to(ROOT/"ml/outputs") or output.exists():raise ValueError("New ignored output required")
    def rows(name):
        with (ROOT/"data/synthetic"/(name+".csv")).open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/"data/synthetic").glob("*.csv")}
    users={u["user_id"]:u for u in rows("users")};assignments=rows("advisor_student_assignments")
    results=[]
    for advisor in rows("advisors"):
        op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        def call(path,body=None):
            req=urllib.request.Request(BASE+path,data=json.dumps(body).encode() if body is not None else None,headers={"Content-Type":"application/json"})
            with op.open(req,timeout=60) as response:
                raw=response.read();return json.loads(raw) if raw else None
        call("/auth/login",{"email":users[advisor["user_id"]]["email"],"password":"Acadmate!2026"})
        page=call("/advisor/meetings");hours=page["officeHours"]
        assert hours["days"]==["Mon","Tue","Wed","Thu","Fri"] and hours["start"]=="08:00" and hours["end"]=="17:00",hours
        contexts=[]
        for a in assignments:
            if a["advisor_id"]!=advisor["advisor_id"]:continue
            sid=int(a["student_id"])
            slots=call(f"/advisor/meetings/free-slots?date=2027-02-17&studentId={sid}")["slots"]
            assert slots,(advisor["advisor_id"],sid,"No next-day slots")
            assert all("08:00"<=s["time"]<"17:00" for s in slots)
            assert call(f"/advisor/meetings/free-slots?date=2027-02-20&studentId={sid}")["slots"]==[]
            contexts.append({"student_id":sid,"next_day_open_slots":len(slots)})
        assert len(contexts)==25
        results.append({"advisor_id":int(advisor["advisor_id"]),"hours":hours,"contexts":contexts})
        call("/auth/logout",{})
    students={int(s["student_id"]):s for s in rows("students")}
    advisor_users={int(a["advisor_id"]):int(a["user_id"]) for a in rows("advisors")}
    student_checks=0
    for result in results:
        staff_id=advisor_users[result["advisor_id"]]
        for ctx in result["contexts"]:
            student=students[ctx["student_id"]]
            op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
            call("/auth/login",{"email":users[student["user_id"]]["email"],"password":"Acadmate!2026"})
            assert staff_id in {s["id"] for s in call("/staff?bookable=true")["staff"]}
            availability=call(f"/staff/{staff_id}/availability?week=2027-02-15")
            day=next(d for d in availability["days"] if d["date"]=="2027-02-17")
            open_slots=[slot for slot in day["slots"] if not slot["taken"]]
            assert len(open_slots)==ctx["next_day_open_slots"]
            assert all("08:00"<=slot["time"]<"17:00" for slot in open_slots)
            call("/auth/logout",{})
            student_checks+=1
    assert student_checks==100
    assert hashes=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/"data/synthetic").glob("*.csv")}
    report={"passed":True,"advisors":4,"student_contexts":100,"student_booking_views":student_checks,"date":"2027-02-17","weekend_empty":True,"csv_unchanged":True,"bookings_created":0,"results":results}
    output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("PASS: 4 advisors, 100 advisor/student next-day contexts, weekday bounds and empty weekends; no bookings created")

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--output",required=True);verify(p.parse_args().output)
