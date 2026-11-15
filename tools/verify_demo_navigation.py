"""Supplemental GET-only schedule/messaging checks through the local frontend proxy."""
from pathlib import Path
import sys,json,urllib.request,http.cookiejar
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from prepare_csv_population_demo import bootstrap,source

def run():
    snap=bootstrap(ROOT/'ml/outputs/main-integration/8c4b0843368b')
    from seed_data import DEMO_PASSWORD
    data=source();users={r['user_id']:r for r in data['users']}
    def check(pair):
        role,row=pair;op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        base='http://127.0.0.1:5178/api/v1'
        def call(path,body=None):
            request=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
            with op.open(request,timeout=60) as response:return response.read()
        count=0
        try:
            call('/auth/login',{'email':users[row['user_id']]['email'],'password':DEMO_PASSWORD})
            for path in ['/conversations','/conversations/contacts']+(['/students/me/events','/staff?bookable=true'] if role=='student' else []):
                json.loads(call(path));count+=1
            call('/auth/logout',{})
            return {'role':role,'user_id':row['user_id'],'passed':True,'navigation_responses':count}
        except Exception as exc:return {'role':role,'user_id':row['user_id'],'passed':False,'error':str(exc)}
    pairs=[('advisor',r) for r in data['advisors']]+[('student',r) for r in data['students']]
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(check,pairs))
    failures=[x for x in results if not x['passed']]
    report={'passed':not failures,'accounts':len(results),'navigation_responses':sum(x.get('navigation_responses',0) for x in results),'failures':failures}
    (snap/'navigation-validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
    if failures:raise SystemExit(1)
if __name__=='__main__':run()
