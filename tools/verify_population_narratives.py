"""Recreate all four local team-demo audit inputs then run actual narrative assertions."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]


def run(snapshot,output):
    snapshot=Path(snapshot).resolve();output=Path(output).resolve()
    if not output.is_relative_to(ROOT/"ml/outputs") or output.exists():
        raise ValueError("New ignored output directory required")
    if not snapshot.is_relative_to(ROOT/"ml/outputs/main-integration"):
        raise ValueError("Isolated snapshot required")
    output.mkdir(parents=True)
    for advisor in (201,10200,10201,10202):
        subprocess.run([sys.executable,str(ROOT/"tools/audit_csv_advisor.py"),"--snapshot",str(snapshot),"--advisor-id",str(advisor),"--team-review","--output",str(output/f"advisor-{advisor}-audit.json")],check=True,cwd=ROOT)
    env=dict(os.environ,ACADMATE_MAIN_SNAPSHOT=str(snapshot),ACADMATE_ADVISOR_AUDIT_DIR=str(output))
    subprocess.run(["node","--test","frontend/tests/csv-advisor-narratives.test.js"],env=env,check=True,cwd=ROOT)
    print("Recreated and checked 100 students / 179 active enrollments. This is consistency, not predictive accuracy.")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot",required=True);parser.add_argument("--output",required=True)
    args=parser.parse_args();run(args.snapshot,args.output)
