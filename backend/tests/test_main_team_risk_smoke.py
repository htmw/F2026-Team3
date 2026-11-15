"""Opt-in real frozen-model HTTP checks on the dedicated disposable pytest database."""
import os
from datetime import datetime
from unittest.mock import patch
import pytest

pytestmark=pytest.mark.skipif(os.getenv("RUN_TEAM_RISK_SMOKE")!="true", reason="Opt-in frozen-artifact local PostgreSQL smoke test")

def test_authenticated_latest_schema_real_inference(client, monkeypatch):
    from sqlalchemy import DateTime, delete, insert, inspect, select
    from database import engine, SessionLocal
    from main import app
    from models import AdvisorStudentAssignment, User, Advisor
    from risk_mvp.models import Base, RISK_TABLES, Coverage
    # Same service namespace extension as the isolated main_host, without its demo-only clock/DB guard.
    import services, risk_mvp
    from pathlib import Path
    monkeypatch.setattr(services,"__path__",[*services.__path__,str(Path(risk_mvp.__file__).resolve().parent.parent/"services")])
    from risk_mvp import main_data, service
    from risk_mvp.main_router import router
    from risk_mvp.main_assessment_cache import CACHE
    from conftest import login
    from acadmate_ml import predict
    from sklearn.pipeline import Pipeline

    # Never permit this fixture's DDL/data writes on a working demo or remote database.
    assert engine.url.host in ("127.0.0.1", "localhost")
    assert engine.url.database=="acadmate_risk_demo_main_sprint2_test"
    existing=set(inspect(engine).get_table_names())
    assert not existing.intersection(t.name for t in RISK_TABLES), "Refuse existing risk tables"
    records=main_data.snapshot(engine)
    before=main_data.fingerprint(records)
    seed_ids=set(range(101,114))
    seed_records=dict(records,students=[s for s in records["students"] if s["student_id"] in seed_ids],enrollments=[e for e in records["enrollments"] if e["student_id"] in seed_ids])
    bundle=main_data.generate(seed_records)  # Test-only simulated sidecars, never academic CSVs.
    monkeypatch.setattr(app.router,"routes",list(app.router.routes))
    monkeypatch.setattr(app,"openapi_schema",None)
    app.include_router(router)
    prefix="/api/v1/advisor/research"
    def sign_in(email):
        client.cookies.clear()  # Never carry the preceding advisor session through a password-change response.
        response=login(client,email)
        assert response.status_code==200,response.text
        assert response.json()["user"]["email"]==email

    CACHE.entries.clear()
    try:
        for table in RISK_TABLES:table.create(engine,checkfirst=True)
        with engine.begin() as conn:
            for table in RISK_TABLES:
                rows=[]
                for raw in bundle["tables"][table.name]:
                    row=dict(raw)
                    for column in table.columns:
                        if isinstance(column.type,DateTime) and isinstance(row.get(column.name),str):
                            row[column.name]=datetime.fromisoformat(row[column.name])
                    rows.append(row)
                if rows:conn.execute(insert(table),rows)
        assert client.get(prefix+"/students").status_code==401
        with SessionLocal() as db:
            owners=dict(db.execute(select(AdvisorStudentAssignment.student_id,AdvisorStudentAssignment.advisor_id).where(AdvisorStudentAssignment.student_id.in_(seed_ids))).all())
            people=dict(db.execute(select(Advisor.advisor_id,User.email).join(User,User.user_id==Advisor.user_id)).all())
        scored=[]
        with patch.object(Pipeline,"fit",side_effect=AssertionError("Frozen model must never refit")), patch.object(predict,"predict",wraps=predict.predict) as real_predict:
            for advisor_id,email in people.items():
                if not any(owner==advisor_id for owner in owners.values()):continue
                sign_in(email)
                assert client.get(prefix+"/students").status_code==200
                for enrollment in seed_records["enrollments"]:
                    if owners.get(enrollment["student_id"])!=advisor_id:continue
                    eid=enrollment["enrollment_id"]
                    cutoff=bundle["manifest"]["checkpoints"][str(eid)]["28"]
                    url=prefix+f"/enrollments/{eid}/risk-assessment"
                    response=client.get(url,params={"cutoff":cutoff,"force_refresh":True})
                    assert response.status_code==200,response.text
                    row=response.json()
                    assert row["status"]=="scored_research_demo",row
                    assert row["student_id"]==enrollment["student_id"]
                    assert row["enrollment_id"]==eid
                    assert 0<=row["research_risk_probability"]<=1
                    scored.append((advisor_id,eid,cutoff))
            assert len(scored)==sum(e["student_id"] in owners for e in seed_records["enrollments"])
            assert real_predict.call_count==len(scored)>0
        owner,eid,cutoff=scored[0]
        sign_in(people[owner])
        url=prefix+f"/enrollments/{eid}/risk-assessment"
        assert client.get(url,params={"cutoff":"invalid"}).status_code==422
        assert client.get(prefix+"/enrollments/999999/risk-assessment",params={"cutoff":cutoff}).status_code==404
        with patch.object(service.MODEL,"_artifacts",None), patch.object(service.MODEL,"_load",side_effect=FileNotFoundError("Test missing artifacts")):
            assert client.get(url,params={"cutoff":cutoff,"force_refresh":True}).status_code==503
        # A source gap must invalidate the previously scored entry, never substitute zero activity.
        with engine.begin() as conn:
            conn.execute(delete(Coverage).where(Coverage.enrollment_id==eid,Coverage.source=="activity"))
        result=client.get(url,params={"cutoff":cutoff})
        assert result.status_code==200
        assert result.json()["status"]=="unavailable"
        assert result.json()["research_risk_probability"] is None
        foreign=next(a for a in people if a!=owner and a in owners.values())
        sign_in(people[foreign])
        assert client.get(url,params={"cutoff":cutoff}).status_code==403
        for email in ("amara.okafor@pac.edu","jordan.lee@pac.edu"):
            sign_in(email)
            assert client.get(prefix+"/students").status_code==403
        assert main_data.fingerprint(main_data.snapshot(engine))==before
        print(f"Real frozen inference: {len(scored)} assigned enrollments; auth, 422/404/503, source-gap/cache and unchanged academic snapshot passed")
    finally:
        CACHE.entries.clear()
        # Per-table DDL avoids metadata-level DROP TYPE events for copied academic enums.
        for table in reversed(RISK_TABLES):table.drop(engine,checkfirst=True)
