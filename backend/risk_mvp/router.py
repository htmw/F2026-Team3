from datetime import datetime
import logging,os
from fastapi import APIRouter,Depends,Path,Query
from fastapi.responses import JSONResponse
from sqlalchemy import select
from .database import session
from .models import Base
from .service import assessment,insights,MissingEnrollment,InvalidCutoff

router=APIRouter(prefix='/api/v1/research/database',tags=['Synthetic database research'])

def enabled():
    if os.getenv('ACADMATE_RISK_MVP_ENABLED','').lower()!='true':
        from fastapi import HTTPException
        raise HTTPException(503,'Synthetic database demo disabled')

def read_db():
    from sqlalchemy import text
    enabled()
    try:
        for db in session():
            db.execute(text('SET TRANSACTION READ ONLY'))
            yield db
    except Exception as exc:
        from fastapi import HTTPException
        if isinstance(exc,HTTPException):raise
        logging.getLogger(__name__).exception('Disposable risk database unavailable')
        raise HTTPException(503,'Synthetic database demo unavailable') from None

def error(code,message):return JSONResponse(status_code=code,content={'error':{'code':'NOT_FOUND' if code==404 else 'INVALID_CUTOFF','message':message,'details':[]}})

@router.get('/students')
def students(db=Depends(read_db)):
    t=Base.metadata.tables['students']
    return {'students':[dict(r) for r in db.execute(select(t.c.student_id,t.c.name).order_by(t.c.student_id)).mappings()]}

@router.get('/students/{student_id}/insights')
def student_insights(student_id:int=Path(gt=0),db=Depends(read_db)):
    try:return insights(db,student_id)
    except MissingEnrollment:return error(404,'Synthetic student not found')

@router.get('/enrollments/{enrollment_id}/risk-assessment')
def risk_assessment(enrollment_id:int=Path(gt=0),cutoff:datetime=Query(...),db=Depends(read_db)):
    try:return assessment(db,enrollment_id,cutoff)
    except MissingEnrollment:return error(404,'Synthetic enrollment not found')
    except InvalidCutoff as exc:return error(422,str(exc))
    except Exception:
        logging.getLogger(__name__).exception('Frozen inference failed')
        return JSONResponse(status_code=503,content={'error':{'code':'RESEARCH_DEMO_UNAVAILABLE','message':'Research inference unavailable','details':[]}})
