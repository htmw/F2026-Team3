"""Create one labelled plan through the student API in the isolated CSV demo."""
from pathlib import Path
import sys,json,urllib.request,http.cookiejar
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from prepare_csv_population_demo import bootstrap,hashes

def run():
    snap=bootstrap(ROOT/'ml/outputs/main-integration/8c4b0843368b')
    from database import SessionLocal
    from services.integrations import smtp_config
    from seed_data import DEMO_PASSWORD
    with SessionLocal() as db:assert smtp_config(db) is None,'Log-only mail required'
    before=hashes();base='http://127.0.0.1:5178/api/v1'
    def session(email):
        op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        def request(path,body=None):
            req=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
            with op.open(req,timeout=60) as response:
                raw=response.read();return json.loads(raw) if raw else None
        request('/auth/login',{'email':email,'password':DEMO_PASSWORD});return request
    student=session('santos.shel@pac.edu')
    plan=student('/students/me/plan');term=next(t for t in plan['futureTerms'] if t['name']=='Fall 2027')
    note='[Sprint 2 demo] Review the remaining elective and capstone; confirm future course availability.'
    advisor=session('sarah.smith@pac.edu')
    queue=advisor('/advisor/approvals')
    existing=[row for row in queue['rows'] if row['studentId']==101 and row['item'].startswith('Fall 2027 plan')]
    if existing:
        result=existing[0];print('Existing pending demo request preserved',result['id']);return
    available={c['code'] for c in plan['available']}
    intended=('CS706','CS799')
    planned=next(t for t in plan['terms'] if t['name']=='Fall 2027')['courses']
    assert not planned,'Review existing plan before adding demonstration courses'
    assert set(intended)<=available,'Expected remaining courses are unavailable'
    added=[]
    for code in intended:
        added.append(student('/students/me/plan',{'courseCode':code,'termId':term['id'],'note':note}))
    submitted=student('/students/me/plan/submit',{'termId':term['id']})
    request_id=submitted['requestId'];detail=advisor('/advisor/approvals/'+str(request_id))
    assert detail['studentId']==101 and detail['status']=='Pending'
    assert hashes()==before
    result={'student_id':101,'student':'Santos Shel','advisor_id':201,'request_id':request_id,'term':'Fall 2027','courses':list(intended),'credits':6,'status':detail['status'],'precheck':submitted['precheck'],'csv_hashes_unchanged':True,'external_email':'disabled/log-only','decision_submitted':False,'plan_items':added}
    (snap/'approval-demo-manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
    student('/auth/logout',{});advisor('/auth/logout',{})
if __name__=='__main__':run()
