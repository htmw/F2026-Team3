"""Read-only check of all team-demo advisor flags against the actual course evidence."""
import argparse,json,os,sys
from pathlib import Path
from datetime import datetime,time,timezone
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]

def verify(snapshot):
    snapshot=Path(snapshot).resolve()
    if not snapshot.is_relative_to(ROOT/"ml/outputs/main-integration"):raise ValueError("Isolated team export required")
    os.environ.update(DATABASE_URL="postgresql+psycopg://acadmate_demo@127.0.0.1:55439/acadmate_risk_team_review_sprint2",ACADMATE_TODAY="2027-02-16",ACADMATE_RISK_MVP_ENABLED="true")
    sys.path[:0]=[str(snapshot/"backend"),str(ROOT/"backend"),str(ROOT/"ml/src")]
    from risk_mvp.team_host import app
    from database import SessionLocal,engine
    from models import Advisor
    from services import advisees,advisor_dashboard
    from risk_mvp import service,main_data
    from risk_mvp.main_attention import overdue_counts
    from sqlalchemy import select,text
    before=main_data.fingerprint(main_data.snapshot(engine))
    results=[];students=active=0
    with SessionLocal() as db,patch.object(service.MODEL,"_load",side_effect=AssertionError("Advisor summaries must not load the prediction model")):
        db.connection(execution_options={"isolation_level":"REPEATABLE READ"});db.execute(text("SET TRANSACTION READ ONLY"))
        for advisor in db.scalars(select(Advisor).order_by(Advisor.advisor_id)):
            ctx,rated=advisees.levels(db,advisor)
            assert len(rated)==25
            students+=len(rated)
            e=service.T["enrollments"].c
            for student,level,_ in rated:
                ids=db.scalars(select(e.enrollment_id).where(e.student_id==student.student_id,e.status=="in_progress")).all()
                rows=[service.extract(db,eid,datetime(2027,2,16,23,59,59,999999,tzinfo=timezone.utc)) for eid in ids]
                active+=len(ids)
                assert ctx.missed.get(student.student_id)==overdue_counts(rows)
                outstanding=overdue_counts(rows,"overdue_assignments")
                assert ctx.course_overdue.get(student.student_id)==outstanding
                if outstanding is not None and outstanding>0:assert level!="Low",student.student_id
            summary=advisor_dashboard.build(db,advisor)
            count=int(next(s["value"] for s in summary["stats"] if s["key"]=="attention"))
            flagged=advisees.list_for(db,advisor,"Needs attention")
            assert len(flagged["rows"])==count==advisees.attention_count(db,advisor)
            assert next(t["count"] for t in flagged["tabs"] if t["label"]=="Needs attention")==count
            results.append({"advisor_id":advisor.advisor_id,"students":len(rated),"needs_attention":count})
    assert students==100 and active==179
    assert main_data.fingerprint(main_data.snapshot(engine))==before
    print(json.dumps({"passed":True,"students_checked":students,"active_enrollments_checked":active,"advisors":results,"academic_records_unchanged":True,"database_enforced_read_only":True,"model_loading_forbidden":True},indent=2))

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--snapshot",required=True)
    verify(parser.parse_args().snapshot)
