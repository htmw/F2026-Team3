"""Exercise each CSV identity through the running frontend API proxy; no academic mutations."""
from pathlib import Path
import sys,json,urllib.request,urllib.error,http.cookiejar
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from prepare_csv_population_demo import bootstrap,source,hashes

def run():
    snap=bootstrap(ROOT/'ml/outputs/main-integration/8c4b0843368b')
    from seed_data import DEMO_PASSWORD
    data=source();before=hashes();base='http://127.0.0.1:5178/api/v1'
    calls=0;denials=0;failures=[];passed=[]
    def request(op,path,body=None):
        nonlocal calls
        calls+=1
        req=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
        with op.open(req,timeout=60) as response:
            raw=response.read()
            return json.loads(raw) if raw else None
    def denied(op,path,code):
        nonlocal denials
        try:request(op,path)
        except urllib.error.HTTPError as exc:
            assert exc.code==code,(path,exc.code,code)
            denials+=1;return
        raise AssertionError('Unexpected access: '+path)
    users={row['user_id']:row for row in data['users']}
    for role,rows in [('advisor',data['advisors']),('student',data['students'])]:
        for row in rows:
            user=users[row['user_id']]
            op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
            try:
                login=request(op,'/auth/login',{'email':user['email'],'password':DEMO_PASSWORD})
                assert login['user']['role']==role
                me=request(op,'/auth/me')['user']
                assert str(me['id'])==row['user_id'],(me['id'],row['user_id'])
                request(op,'/users/me');request(op,'/users/me/badges')
                if role=='student':
                    for endpoint in ('dashboard','courses','assignments','degree-audit','plan','meetings','ai/context','ai/threads'):
                        request(op,'/students/me/'+endpoint)
                    denied(op,'/advisor/advisees',403)
                    denied(op,'/advisor/research/students/'+row['student_id']+'/insights',403)
                else:
                    for endpoint in ('dashboard','advisees','reports','settings','meetings','approvals'):
                        request(op,'/advisor/'+endpoint)
                    assigned={x['student_id'] for x in data['advisor_student_assignments'] if x['advisor_id']==row['advisor_id']}
                    for student in data['students']:
                        if student['student_id'] not in assigned:
                            denied(op,'/advisor/advisees/'+student['student_id'],403)
                    denied(op,'/admin/overview',403)
                request(op,'/auth/logout',{})
                denied(op,'/auth/me',401)
                passed.append({'role':role,'user_id':int(row['user_id'])})
            except Exception as exc:
                failures.append({'role':role,'user_id':row['user_id'],'error':str(exc)})
            print(role,row['user_id'],'checked',flush=True)
    assert hashes()==before
    result={'passed':not failures,'identities_passed':len(passed),'advisors':sum(x['role']=='advisor' for x in passed),'students':sum(x['role']=='student' for x in passed),'http_requests':calls,'expected_denials':denials,'failures':failures,'csv_hashes_unchanged':True,'scope':'Read navigation APIs via frontend proxy, identity, role boundaries, all 300 foreign advisor records, logout. No approval/message/booking mutations.'}
    (snap/'all-session-validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
    if failures:raise SystemExit(1)
if __name__=='__main__':run()
