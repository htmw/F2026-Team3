from typing import Annotated
from fastapi import APIRouter, Depends, Path
from fastapi.responses import JSONResponse
from schemas.research_predictions import ResearchPredictionResponse
from services.research_predictions import (DemoUnavailable,DemoEnrollmentNotFound,get_prediction_service)

router=APIRouter(prefix='/api/v1/research',tags=['Research predictions'])


def error(status,code,message):
    return JSONResponse(status_code=status,content={'error':{'code':code,'message':message,'details':[]}})


@router.get('/enrollments/{enrollment_id}/risk-prediction',response_model=ResearchPredictionResponse)
def get_prediction(enrollment_id:Annotated[int,Path(gt=0)],service=Depends(get_prediction_service)):
    try:
        return service.get(enrollment_id)
    except DemoEnrollmentNotFound:
        return error(404,'NOT_FOUND','Enrollment not found in research demonstration fixtures.')
    except DemoUnavailable:
        return error(503,'RESEARCH_DEMO_UNAVAILABLE','Research prediction demonstration is unavailable.')
