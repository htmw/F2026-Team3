"""The CSV reserved-domain allowance must never apply to normal databases or signup."""
import os,subprocess,sys
from pathlib import Path

def test_csv_login_allowance_is_local_and_scoped():
    code="""
from schemas.auth import LoginIn,SignupIn,ResetRequestIn
from pydantic import ValidationError
import os
expected=os.environ['EXPECTED']=='yes'
try:
    LoginIn(email='advisor.2@example.invalid',password='test-password')
    accepted=True
except ValidationError:accepted=False
assert accepted==expected
for cls in (SignupIn,ResetRequestIn):
    try:cls(email='advisor.2@example.invalid',name='Demo',password='test-password')
    except ValidationError:pass
    else:raise AssertionError('Reserved domain accepted outside login')
try:LoginIn(email='not-an-email',password='test-password')
except ValidationError:pass
else:raise AssertionError('Malformed address accepted')
"""
    import schemas.auth as active_auth
    schema_root=str(Path(active_auth.__file__).resolve().parents[1])
    for host,db,expected in [('127.0.0.1','acadmate_risk_csv_sprint2','yes'),('127.0.0.1','acadmate_risk_demo_main_sprint2_test','no'),('example.com','acadmate_risk_csv_sprint2','no')]:
        env=dict(os.environ,DATABASE_URL=f'postgresql+psycopg://demo@{host}/{db}',EXPECTED=expected)
        env['PYTHONPATH']=schema_root+os.pathsep+env.get('PYTHONPATH','')
        result=subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,text=True)
        assert result.returncode==0,result.stderr
