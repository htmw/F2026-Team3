"""Derive UI coursework completion from the shared fixed-date submission projection."""
from pathlib import Path
import argparse,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from prepare_csv_population_demo import bootstrap,hashes

def sync(snapshot):
    snapshot=bootstrap(snapshot)
    from database import SessionLocal,engine
    from sqlalchemy import select
    from models import Enrollment,AssignmentSubmission
    from risk_mvp import main_data
    marker=snapshot/'csv-population-manifest.json';manifest=json.loads(marker.read_text())
    assert manifest['state']=='complete' and hashes()==manifest['csv_sha256']
    counts={}
    with SessionLocal() as db:
        for sid,aid,status in db.execute(select(AssignmentSubmission.student_id,AssignmentSubmission.assignment_id,AssignmentSubmission.status)):
            counts[sid,aid]=status
        from models import Assignment
        tasks={}
        for aid,section in db.execute(select(Assignment.id,Assignment.section_id)):tasks.setdefault(section,[]).append(aid)
        checked=0
        for e in db.scalars(select(Enrollment)):
            ids=tasks.get(e.section_id,[])
            submitted=sum(counts.get((e.student_id,aid)) in ('submitted','graded') for aid in ids)
            e.progress_pct=round(100*submitted/len(ids)) if ids else 0
            checked+=1
        assert checked==800;db.commit()
    manifest['academic_sha256']=main_data.fingerprint(main_data.snapshot(engine))
    manifest['derived_progress']='Submitted coursework / all scheduled coursework in that course section, rounded to an integer percent. Snapshot-only; not a grade or probability.'
    marker.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    risk_marker=snapshot/'csv-risk-manifest.json';risk=json.loads(risk_marker.read_text());risk['academic_sha256']=manifest['academic_sha256'];risk_marker.write_text(json.dumps(risk,indent=2),encoding='utf-8')
    assert hashes()==manifest['csv_sha256']
    print('Verified derived coursework progress for all 800 enrollments; original CSV fields unchanged.')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);sync(p.parse_args().snapshot)
