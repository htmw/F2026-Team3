"""Local proxy verification through the existing non-persisting admin AI test box."""
import argparse
import http.cookiejar
import json
from pathlib import Path
import urllib.request
import urllib.error
ROOT=Path(__file__).resolve().parents[1]
BASE="http://127.0.0.1:5179/api/v1"


def verify(output):
    output=Path(output).resolve()
    if not output.is_relative_to(ROOT/"ml/outputs") or output.exists():raise ValueError("New ignored output required")
    op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def call(path,body=None,plain=False):
        req=urllib.request.Request(BASE+path,data=json.dumps(body).encode() if body is not None else None,headers={"Content-Type":"application/json"})
        with op.open(req,timeout=60) as response:
            raw=response.read().decode();return raw if plain else json.loads(raw) if raw else None
    try:call("/help/documents/project-help-plan",plain=True)
    except urllib.error.HTTPError as error:assert error.code==401
    else:raise AssertionError("Source must require authentication")
    call("/auth/login",{"email":"santos.shel@pac.edu","password":"Acadmate!2026"})
    before=call("/students/me/ai/threads")
    call("/auth/logout",{})
    call("/auth/login",{"email":"admin@example.invalid","password":"Acadmate!2026"})
    original_settings=call("/admin/ai/settings")
    checks=[]
    for question,identity in [("How do I submit my degree plan in AcadMate?","project-help-plan"),("What does a course risk estimate mean?","project-help-assessment"),("How do I message a student in AcadMate?","project-help-followup"),("How do I book an advising meeting?","project-help-followup")]:
        out=call("/admin/ai/test",{"studentId":1,"question":question,"settings":{"engine":"Rules"}})
        assert out["engine"]=="Rules"
        reply=out["reply"];citation=reply["citations"][0]
        assert citation["documentId"]==identity and reply["text"].startswith("Project help")
        if "book an advising meeting" in question:
            assert "as a student, open Book a meeting" in reply["text"]
        source=call(citation["path"],plain=True)
        assert "not university academic policy" in source
        # Citation lines point to the exact returned passage, not a generated source name.
        numbered={int(line.split(": ",1)[0]):line.split(": ",1)[1] for line in source.splitlines() if ": " in line and line.split(": ",1)[0].isdigit()}
        quote="\n".join(numbered[i] for i in range(citation["startLine"],citation["endLine"]+1))
        assert reply["text"]=="Project help\n\n"+quote
        checks.append(identity)
    policy=call("/admin/ai/test",{"studentId":1,"question":"What is the minimum GPA required by university policy?","settings":{"engine":"Rules"}})["reply"]
    assert policy["citations"]==[] and "official catalog" in policy["text"]
    blocked=call("/admin/ai/test",{"studentId":1,"question":"How do I submit a grade appeal in AcadMate?","settings":{"engine":"Rules"}})["reply"]
    assert blocked["kind"]=="handoff" and blocked["citations"]==[]
    assert call("/admin/ai/settings")==original_settings
    call("/auth/logout",{})
    call("/auth/login",{"email":"santos.shel@pac.edu","password":"Acadmate!2026"})
    assert call("/students/me/ai/threads")==before
    source=call("/help/documents/project-help-plan",plain=True)
    assert "Send for approval" in source
    call("/auth/logout",{})
    result={"passed":True,"verified_guides":checks,"policy_abstention":True,"topic_guard":True,"authenticated_sources":True,"settings_unchanged":True,"student_thread_list_unchanged":True,"scope":"non-persisting admin preview through frontend proxy; persisted student chat separately tested on disposable pytest DB"}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("x",encoding="utf-8") as stream:json.dump(result,stream,indent=2)
    print(json.dumps(result,indent=2))


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--output",required=True);verify(p.parse_args().output)
