"""Start only this checkout's disposable loopback PostgreSQL cluster and seed once."""
import json,os,subprocess,sys
from pathlib import Path
from sqlalchemy import create_engine,text,select,func
from .generate import generate,load,ROOT
from .models import Base

BIN=Path(r'C:\Program Files\PostgreSQL\18\bin')
DATA=ROOT/'ml/outputs/pg-risk-mvp'
URL='postgresql+psycopg://acadmate_demo@127.0.0.1:55439/acadmate_risk_demo_sprint2'

def command(name,*args,check=True):
    return subprocess.run([str(BIN/(name+'.exe')),*map(str,args)],check=check,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))

def main():
    if not (BIN/'pg_ctl.exe').is_file():raise RuntimeError('PostgreSQL 18 binaries not found; configure BIN after reviewing local setup')
    DATA.parent.mkdir(parents=True,exist_ok=True)
    if not DATA.exists():command('initdb','-D',DATA,'-U','acadmate_demo','-A','trust','--encoding=UTF8','--locale=C')
    if not (DATA/'PG_VERSION').is_file():raise RuntimeError('Refusing unknown cluster directory')
    if command('pg_ctl','-D',DATA,'status',check=False).returncode:
        command('pg_ctl','-D',DATA,'-l',DATA.parent/'pg-risk-mvp.log','-o','-h 127.0.0.1 -p 55439','-w','start')
    # Verify actual pidfile belongs to this cluster and fixed port before connecting.
    lines=(DATA/'postmaster.pid').read_text().splitlines()
    if Path(lines[1]).resolve()!=DATA.resolve() or lines[3]!='55439':raise RuntimeError('Unexpected PostgreSQL cluster/port')
    admin=create_engine(URL.rsplit('/',1)[0]+'/postgres',isolation_level='AUTOCOMMIT')
    with admin.connect() as db:
        if not db.execute(text("SELECT 1 FROM pg_database WHERE datname='acadmate_risk_demo_sprint2'")).scalar():
            db.execute(text('CREATE DATABASE acadmate_risk_demo_sprint2'))
    admin.dispose()
    engine=create_engine(URL)
    with engine.connect() as db:exists=db.execute(text("SELECT to_regclass('public.students')")).scalar()
    bundle=generate()
    if exists:
        with engine.connect() as db:
            if db.execute(select(func.count()).select_from(Base.metadata.tables['students'])).scalar()!=100:
                raise RuntimeError('Existing demo data unexpected; no automatic overwrite')
            for name,count in bundle['manifest']['counts'].items():
                if db.execute(select(func.count()).select_from(Base.metadata.tables[name])).scalar()!=count:
                    raise RuntimeError('Existing extension counts differ; no automatic migration or reseed')
        print('Existing disposable demo data preserved')
    else:load(engine,bundle)
    target=ROOT/'ml/outputs/risk-mvp-v1/bundle.json'
    if not target.exists():
        target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(bundle,indent=2)+'\n',encoding='utf-8')
    print('Disposable database ready. Set ACADMATE_RISK_DATABASE_URL='+URL)
    engine.dispose()

if __name__=='__main__':main()
