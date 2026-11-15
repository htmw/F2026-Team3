"""Real main-app authentication and all-enrollment API verification (local demo only)."""
import argparse
from collections import Counter
import json
from pathlib import Path
from prepare_main_risk_demo import configure, ROOT


def verify(snapshot,with_explanations=False):
    configure(snapshot)
    from sqlalchemy import select
    from fastapi.testclient import TestClient
    from database import SessionLocal, engine
    from models import User, Advisor, AdvisorStudentAssignment, Enrollment
    from seed_data import DEMO_PASSWORD
    from risk_mvp import main_data
    from risk_mvp.main_host import app
    import logging
    logging.getLogger('httpx2').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    from risk_mvp.models import Coverage
    before=main_data.fingerprint(main_data.snapshot(engine))
    bundle=json.loads((snapshot/'risk-main-bundle.json').read_text())
    with SessionLocal() as db:
        people=[dict(id=u.user_id,email=u.email,role=u.role) for u in db.scalars(select(User).where(User.is_active==True))]
        advisors={a.user_id:a.advisor_id for a in db.scalars(select(Advisor))}
        assignments={a.student_id:a.advisor_id for a in db.scalars(select(AdvisorStudentAssignment))}
        enrollments=[dict(id=e.enrollment_id,student=e.student_id) for e in db.scalars(select(Enrollment))]
    assert len(enrollments)==bundle['manifest']['enrollment_count']
    report=Counter()
    prefix='/api/v1/advisor/research'
    with TestClient(app) as client:
        assert client.get(prefix+'/students').status_code==401
    for person in people:
        if person['role'] not in ('advisor','student','admin'):continue
        if person['role']!='advisor' and report[person['role']+'_denied']:continue
        with TestClient(app) as client:
            login=client.post('/api/v1/auth/login',json={'email':person['email'],'password':DEMO_PASSWORD})
            assert login.status_code==200,(person['id'],login.status_code)
            if person['role']!='advisor':
                assert client.get(prefix+'/students').status_code==403
                report[person['role']+'_denied']+=1;continue
            aid=advisors[person['id']]
            listed=client.get(prefix+'/students');assert listed.status_code==200,listed.text
            expected={sid for sid,owner in assignments.items() if owner==aid}
            assert {s['student_id'] for s in listed.json()['students']}==expected
            for sid in expected:
                response=client.get(prefix+f'/students/{sid}/insights');assert response.status_code==200,response.text
                values=response.json()
                assert {e['enrollment_id'] for e in values['enrollments']}=={e['id'] for e in enrollments if e['student']==sid}
                if sid==101:assert values['name']=='Amara Okafor'
            for e in enrollments:
                cutoff=bundle['manifest']['checkpoints'][str(e['id'])]['28']
                response=client.get(prefix+f"/enrollments/{e['id']}/risk-assessment",params={'cutoff':cutoff, 'include_explanation':str(with_explanations).lower()})
                if assignments.get(e['student'])==aid:
                    assert response.status_code==200,response.text
                    assert response.json()['status']=='scored_research_demo'
                    report['authorized_enrollments_scored']+=1
                    if with_explanations:
                        detail=response.json()['explanation']
                        assert detail['status']=='available',detail
                        assert detail['background_reference']['reference_day']==28
                        assert abs(detail['reconstructed_calibrated_probability']-response.json()['research_risk_probability'])<1e-12
                        baseline=client.get(prefix+f"/enrollments/{e['id']}/risk-assessment",params={'cutoff':cutoff}).json()
                        assert 'explanation' not in baseline
                        assert baseline['research_risk_probability']==response.json()['research_risk_probability']
                        report['optional_explanations_verified']+=1
                else:
                    assert response.status_code==403,response.text
                    report['cross_assignment_denied']+=1
            if aid==201 and with_explanations:
                from unittest.mock import patch
                from risk_mvp import service
                from risk_mvp.generate import parse
                from risk_mvp.main_explanations import training_background
                with SessionLocal() as db:
                    current=next(e for e in enrollments if assignments.get(e['student'])==aid and service.extract(db,e['id'],parse('2026-10-01T23:59:59.999999Z'))['status']=='ready')
                path=prefix+f"/enrollments/{current['id']}/risk-assessment"
                params={'cutoff':'2026-10-01T23:59:59.999999Z','include_explanation':'true'}
                response=client.get(path,params=params);assert response.status_code==200,response.text
                detail=response.json()['explanation'];assert detail['status']=='available',detail
                assert detail['background_reference']['prediction_day']==38
                assert detail['background_reference']['reference_day']==35
                probability=response.json()['research_risk_probability']
                with patch('risk_mvp.main_explanations.training_background',side_effect=FileNotFoundError('private-path')):
                    failed=client.get(path,params={**params,'force_refresh':'true'})
                assert failed.status_code==200 and failed.json()['research_risk_probability']==probability
                assert failed.json()['explanation']['status']=='unavailable'
                assert 'private-path' not in str(failed.json())
                report['day38_reference35_verified']=True
                report['explanation_failure_preserves_prediction']=True
            if aid==201:
                from unittest.mock import patch
                from risk_mvp import service
                saved=service.MODEL._artifacts
                try:
                    service.MODEL._artifacts=None
                    owned=next(e for e in enrollments if assignments.get(e['student'])==aid)
                    with patch.object(service.MODEL,'_load',side_effect=FileNotFoundError('private artifact path')):
                        failed=client.get(prefix+f"/enrollments/{owned['id']}/risk-assessment",params={'cutoff':bundle['manifest']['checkpoints'][str(owned['id'])]['28'],'force_refresh':'true'})
                    assert failed.status_code==503
                    assert failed.json()['error']['code']=='RESEARCH_DEMO_UNAVAILABLE'
                    assert 'private artifact path' not in failed.text
                    report['missing_artifacts_safe_503']=True
                finally:service.MODEL._artifacts=saved
            assert client.get(prefix+'/enrollments/0/risk-assessment',params={'cutoff':'bad'}).status_code==422
            assert client.get(prefix+'/enrollments/99999999/risk-assessment',params={'cutoff':'2026-10-01T23:59:59.999999Z'}).status_code==404
    active_advisors={advisors[p['id']] for p in people if p['id'] in advisors}
    eligible=[e for e in enrollments if assignments.get(e['student']) in active_advisors]
    assert report['authorized_enrollments_scored']==len(eligible)
    report['enrollments_without_active_assigned_advisor']=len(enrollments)-len(eligible)
    # Test incomplete coverage without changing persistent records.
    from risk_mvp import service
    from risk_mvp.generate import parse
    eid=enrollments[0]['id'];cutoff=parse(bundle['manifest']['checkpoints'][str(eid)]['28'])
    with SessionLocal() as db:
        coverage=db.scalar(select(Coverage).where(Coverage.enrollment_id==eid,Coverage.source=='activity',Coverage.known_at==cutoff))
        coverage.complete=False;db.flush()
        result=service.assessment(db,eid,cutoff)
        assert result['status']=='unavailable' and result['research_risk_probability'] is None
        assert result['evidence']['clicks_7d'] is None
        db.rollback()
    from risk_mvp.models import Link
    from risk_mvp.main_router import insights as main_insights
    with SessionLocal() as db:
        owned=next(e for e in enrollments if assignments.get(e['student'])==201)
        link=db.get(Link,owned['id']);db.delete(link);db.flush()
        rows=main_insights(student_id=owned['student'],advisor=db.get(Advisor,201),db=db)['enrollments']
        assert owned['id'] in {e['enrollment_id'] for e in rows}
        no_link=service.assessment(db,owned['id'],parse(bundle['manifest']['checkpoints'][str(owned['id'])]['28']))
        assert no_link['status']=='unavailable' and no_link['research_risk_probability'] is None
        db.rollback()
    report['missing_sidecar_enrollment_stays_visible']=True
    assert before==main_data.fingerprint(main_data.snapshot(engine))
    report['academic_records_unchanged']=True
    report['incomplete_feed_unscored']=True
    # Main's existing route registrations are preserved; adapter adds exactly three.
    import importlib
    from fastapi import FastAPI
    import main
    source=(snapshot/'backend/main.py').read_text(encoding='utf-8')
    isolated={};exec(compile(source,'verified_main.py','exec'),isolated)
    original_paths=set(isolated['app'].openapi()['paths'])
    combined_paths=set(app.openapi()['paths'])
    assert original_paths<=combined_paths
    assert len(combined_paths-original_paths)==3
    report['existing_paths_preserved']=len(original_paths)
    report['added_paths']=3
    (snapshot/'risk-main-api-verification.json').write_text(json.dumps(dict(report),indent=2)+'\n')
    print(json.dumps(dict(report),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot',required=True,type=Path)
    parser.add_argument('--with-explanations',action='store_true')
    args=parser.parse_args();verify(args.snapshot.resolve(),args.with_explanations)
