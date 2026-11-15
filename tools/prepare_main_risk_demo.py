"""Prepare or audit only the dedicated local main/risk integration database.

Run with the isolated main environment and --snapshot pointing to the ignored,
commit-pinned main export. No source checkout or shared database is altered.
"""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
URL = 'postgresql+psycopg://acadmate_demo@127.0.0.1:55439/acadmate_risk_demo_main_sprint2'


def export(snapshot, source_ref='origin/main'):
    import subprocess, io, zipfile
    snapshot=snapshot.resolve()
    if not snapshot.is_relative_to(ROOT/'ml/outputs/main-integration') or snapshot.exists():
        raise ValueError('NEW directory inside ignored main-integration outputs required')
    git=['git','-c','safe.directory='+str(ROOT),'-C',str(ROOT)]
    commit=subprocess.check_output(git+['rev-parse',source_ref]).decode().strip()
    data=subprocess.check_output(git+['archive','--format=zip',commit,'backend','frontend'])
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for name in archive.namelist():
            if not (snapshot/name).resolve().is_relative_to(snapshot):raise ValueError('Invalid archive path')
        archive.extractall(snapshot)
    (snapshot/'source.json').write_text(json.dumps({'commit':commit,'source':source_ref,'academic_source':'unmodified main seed records'},indent=2))
    print('Exported main commit '+commit+' to '+str(snapshot))


def configure(snapshot):
    snapshot = snapshot.resolve()
    if not snapshot.is_relative_to(ROOT/'ml/outputs/main-integration'):
        raise ValueError('Snapshot must be inside ignored ml/outputs/main-integration')
    provenance = json.loads((snapshot/'source.json').read_text())
    if len(provenance['commit']) != 40: raise ValueError('Commit-pinned snapshot required')
    os.environ.update(DATABASE_URL=URL, ACADMATE_RISK_DATABASE_URL=URL,
                      ACADMATE_TODAY='2026-10-01', ACADMATE_RISK_MVP_ENABLED='true',
                      ACADMATE_RESEARCH_DEMO_ENABLED='true', OMP_NUM_THREADS='2')
    os.chdir(snapshot/'backend')
    sys.path[:0] = [str(snapshot/'backend'),str(ROOT/'backend'),str(ROOT/'ml/src')]
    # Extend the existing package; do not overwrite main service implementations.
    import services
    services.__path__.append(str(ROOT/'backend/services'))
    return provenance


def prepare(snapshot):
    provenance = configure(snapshot)
    from sqlalchemy import create_engine, text, inspect, select, func
    from models import Base
    from seed_data import seed
    from risk_mvp import main_data
    admin = create_engine(URL.rsplit('/',1)[0]+'/postgres', isolation_level='AUTOCOMMIT')
    with admin.connect() as conn:
        if not conn.scalar(text("SELECT 1 FROM pg_database WHERE datname='acadmate_risk_demo_main_sprint2'")):
            conn.exec_driver_sql('CREATE DATABASE acadmate_risk_demo_main_sprint2')
    admin.dispose()
    engine = create_engine(URL)
    marker = snapshot/'risk-main-manifest.json'
    try:
        existing = inspect(engine).get_table_names()
        if existing and not marker.exists():
            raise ValueError('Existing integration database without provenance marker; refusing to alter it')
        if existing and json.loads(marker.read_text()).get('state') != 'academic_seeded':
            bundle = json.loads((snapshot/'risk-main-bundle.json').read_text())
            if main_data.fingerprint(main_data.snapshot(engine)) != bundle['manifest']['academic_sha256']:
                raise ValueError('Existing academic records changed; refusing automatic reseed')
            from risk_mvp.models import RISK_TABLES
            with engine.connect() as conn:
                for table in RISK_TABLES:
                    if conn.scalar(select(func.count()).select_from(table)) != bundle['manifest']['counts'][table.name]:
                        raise ValueError('Existing sidecar counts changed; refusing overwrite')
            print(json.dumps({'preserved':True, **{k:v for k,v in json.loads(marker.read_text()).items() if k!='checkpoints'}},indent=2))
            return
        if not existing:
            Base.metadata.create_all(engine)
            from sqlalchemy.orm import Session
            with Session(engine) as db:
                seed(db); db.commit()
        records = main_data.snapshot(engine)
        if existing and main_data.fingerprint(records) != json.loads(marker.read_text())['academic_sha256']:
            raise ValueError('Academic seed changed before sidecar load')
        marker.write_text(json.dumps({'state':'academic_seeded','academic_sha256':main_data.fingerprint(records),'main_commit':provenance['commit']}))
        bundle = main_data.generate(records)
        main_data.load(engine,bundle,records)
        report = dict(bundle['manifest'], main_commit=provenance['commit'],
                      academic_counts={k:len(v) for k,v in records.items()},
                      note='Main seed data unchanged; synthetic risk histories and activity only')
        (snapshot/'risk-main-bundle.json').write_text(json.dumps(bundle,indent=2)+'\n')
        marker.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({k:v for k,v in report.items() if k!='checkpoints'},indent=2))
    finally: engine.dispose()


def frontend(snapshot):
    """Apply an explicit UI overlay only to the disposable main export."""
    snapshot=snapshot.resolve()
    if not snapshot.is_relative_to(ROOT/'ml/outputs/main-integration'):
        raise ValueError('Isolated export required')
    import shutil
    dest=snapshot/'frontend/src/components/research/MainResearchRisk.jsx'
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(ROOT/'frontend/src/components/research/MainResearchRisk.jsx',dest)
    page=snapshot/'frontend/src/pages/advisor/StudentRecord.jsx'
    text=page.read_text(encoding='utf-8')
    if 'import MainResearchRisk ' not in text:
        text="import MainResearchRisk from '../../components/research/MainResearchRisk.jsx'\n"+text
    insertion='      <MainResearchRisk key={studentId} studentId={studentId} />\n\n'
    text=text.replace(insertion,'')
    anchor='      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">'
    if anchor not in text:raise ValueError('Student record structure changed; review insertion')
    text=text.replace(anchor,insertion+anchor,1)
    # The main submission tile reads a separate assignment source. Hide it here
    # rather than presenting it as consistent with the simulated model evidence.
    text=text.replace('data.stats.map((stat) => (', 'data.stats.filter(stat => stat.label !== "On-time submission").map((stat) => (')
    page.write_text(text,encoding='utf-8')
    print('Main student-record overlay prepared; source checkout unchanged')


def audit(snapshot):
    configure(snapshot)
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from risk_mvp import main_data, service
    from risk_mvp.generate import parse
    bundle = json.loads((snapshot/'risk-main-bundle.json').read_text())
    engine = create_engine(URL)
    from collections import Counter
    result = Counter(); probabilities = []
    before = main_data.fingerprint(main_data.snapshot(engine))
    with Session(engine) as db:
        for eid,cutoffs in bundle['manifest']['checkpoints'].items():
            for day,cutoff in cutoffs.items():
                row = service.assessment(db,int(eid),parse(cutoff))
                if row['status']!='scored_research_demo':raise AssertionError((eid,day,row['reason']))
                if not 0<=row['research_risk_probability']<=1:raise AssertionError('Invalid probability')
                result[day]+=1; probabilities.append(row['research_risk_probability'])
        current = Counter()
        cutoff = parse('2026-10-01T23:59:59.999999+00:00')
        for eid in bundle['manifest']['checkpoints']:
            row = service.assessment(db,int(eid),cutoff)
            current[row['status']]+=1
    after = main_data.fingerprint(main_data.snapshot(engine))
    assert before==after==bundle['manifest']['academic_sha256']
    report={'checkpoint_scored_counts':dict(result),'current_cutoff_statuses':dict(current),
            'probability_min':min(probabilities),'probability_max':max(probabilities),
            'academic_records_unchanged':True,'warning':'Synthetic flow validation, not accuracy evidence'}
    (snapshot/'risk-main-audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2));engine.dispose()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['export','prepare','audit','frontend'])
    parser.add_argument('--snapshot',required=True,type=Path)
    parser.add_argument('--source-ref',default='origin/main')
    args=parser.parse_args()
    if args.action=='export':export(args.snapshot,args.source_ref)
    else:{'prepare':prepare,'audit':audit,'frontend':frontend}[args.action](args.snapshot.resolve())
