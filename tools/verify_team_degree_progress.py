"""Read-only comparison of Datta degree progress against every preserved synthetic CSV student."""
import argparse
import csv
from decimal import Decimal
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
URL="postgresql+psycopg://acadmate_demo@127.0.0.1:55439/acadmate_risk_csv_sprint2"

def verify(snapshot):
    snapshot=Path(snapshot).resolve()
    if not snapshot.is_relative_to(ROOT/"ml/outputs/main-integration"):
        raise ValueError("Isolated team export required")
    os.environ.update(DATABASE_URL=URL,ACADMATE_TODAY="2027-02-16")
    sys.path[:0]=[str(snapshot/"backend"),str(ROOT/"backend"),str(ROOT/"ml/src")]
    from sqlalchemy import create_engine,select,text
    from sqlalchemy.orm import Session
    from models import Student
    from services.degree_progress import degree_progress
    from schemas.degree_progress import DegreeProgressResponse
    def read(name):
        with (ROOT/"data/synthetic"/f"{name}.csv").open(encoding="utf-8-sig",newline="") as stream:
            return list(csv.DictReader(stream))
    students=read("students")
    courses={r["course_id"]:Decimal(r["credits"]) for r in read("courses")}
    programs={r["program_id"]:Decimal(r["total_required_credits"]) for r in read("programs")}
    requirements=read("program_requirements")
    enrollments=read("enrollments")
    engine=create_engine(URL)
    with Session(engine) as db:
        db.connection(execution_options={"isolation_level":"REPEATABLE READ"})
        db.execute(text("SET TRANSACTION READ ONLY"))
        assert set(db.scalars(select(Student.student_id)))=={int(s["student_id"]) for s in students}
        for student in students:
            done={r["course_id"] for r in enrollments if r["student_id"]==student["student_id"] and r["status"]=="completed" and r["grade"].upper()!="F"}
            expected={}
            for requirement in requirements:
                if requirement["program_id"]!=student["program_id"]:continue
                eligible={str(i) for i in json.loads(requirement["eligible_course_ids"])}
                required=Decimal(requirement["required_credits"])
                earned=min(required,sum((courses[cid] for cid in done&eligible),Decimal(0)))
                expected[int(requirement["requirement_id"])]=(required,earned,required-earned)
            result=degree_progress(db,int(student["student_id"]))
            public=DegreeProgressResponse.model_validate(result).model_dump(by_alias=True)
            earned=min(programs[student["program_id"]],sum((v[1] for v in expected.values()),Decimal(0)))
            assert public["requiredCredits"]==float(programs[student["program_id"]])
            assert public["earnedCredits"]==float(earned),(student["student_id"],public)
            assert public["remainingCredits"]==float(programs[student["program_id"]]-earned)
            assert abs(public["completionRate"]-float(earned/programs[student["program_id"]]))<1e-12
            assert len(result["requirements"])==len(expected)
            for group in result["requirements"]:
                assert (group["required_credits"],group["earned_credits"],group["remaining_credits"])==tuple(float(v) for v in expected[group["requirement_id"]])
    engine.dispose()
    print(json.dumps({"passed":True,"students_checked":len(students),"enrollment_source_rows":len(enrollments),"mode":"database-enforced read-only","scope":"degree-progress service and serialized response; not latest-auth HTTP migration"},indent=2))

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot",required=True)
    verify(parser.parse_args().snapshot)
