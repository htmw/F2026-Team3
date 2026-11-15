"""Read-only model/source consistency across all 46 synthetic enrollments."""
import argparse
from pathlib import Path
from collections import Counter
import sys,json,hashlib
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from prepare_main_risk_demo import configure
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--snapshot',type=Path,required=True)
snapshot=parser.parse_args().snapshot.resolve();configure(snapshot)
from database import SessionLocal
from sqlalchemy import text,select
from models import Enrollment
from risk_mvp import service
from risk_mvp.generate import parse
from risk_mvp.main_explanations import attach
from risk_mvp.main_data import snapshot as academic_snapshot,fingerprint
bundle=json.loads((snapshot/'risk-main-bundle.json').read_text())
report=Counter()
with SessionLocal() as db:
    db.connection(execution_options={'isolation_level':'REPEATABLE READ'})
    db.execute(text('SET TRANSACTION READ ONLY'))
    before=fingerprint(academic_snapshot(db.get_bind()))
    with patch('sklearn.pipeline.Pipeline.fit',side_effect=AssertionError('No frozen model retraining')):
        for eid in db.scalars(select(Enrollment.enrollment_id)):
            for day in ('7','14','28'):
                cutoff=parse(bundle['manifest']['checkpoints'][str(eid)][day])
                row=service.assessment(db,eid,cutoff)
                assert row['status']=='scored_research_demo'
                assert 0<=row['research_risk_probability']<=1
                report['day_'+day+'_scored']+=1
                if day=='28':
                    explained=attach(row,db,eid,cutoff)
                    assert explained['explanation']['status']=='available'
                    assert abs(explained['explanation']['reconstructed_calibrated_probability']-row['research_risk_probability'])<1e-12
                    report['explanations_verified']+=1
            row=service.assessment(db,eid,parse('2026-10-01T23:59:59.999999Z'))
            report['current_'+row['status']]+=1
    assert before==fingerprint(academic_snapshot(db.get_bind()))
paths=['ml/outputs/baselines-v1/logistic_regression.joblib','ml/outputs/calibration-v1/calibration_maps.joblib']
expected=['93cab4b90d3fc755b087be6343673b47ec3b163f4d4a8d3aace93e356fcb0020','d9ef14cad9c5d0cc8731e68b02633bb831ebed7a8ba6bb255bef2513f7be88e7']
for path,digest in zip(paths,expected):assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest
print(json.dumps(dict(report),indent=2))
print('PASS: read-only, no refitting, academic records preserved, frozen artifact hashes unchanged')
