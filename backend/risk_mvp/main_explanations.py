"""Optional explanation layer; a failure never suppresses a valid prediction."""
from functools import lru_cache
from pathlib import Path
import logging
import numpy as np
from . import service

ROOT=Path(__file__).resolve().parents[2]
LOGGER=logging.getLogger(__name__)


@lru_cache(maxsize=32)
def training_background(root, reference_day):
    from acadmate_ml.explain import background
    from .explanation_references import RELATIVE, load
    if (Path(root)/RELATIVE).exists():
        values,metadata=load(Path(root),reference_day)
    else:
        values,metadata=background(Path(root),reference_day,size=128,seed=42)
    values.setflags(write=False)
    return values,metadata


def attach(result, db, enrollment_id, cutoff):
    if result['status']!='scored_research_demo':
        result['explanation']={'status':'unavailable','reason':'No explanation because this assessment was not scored.','contributions':[]}
        return result
    try:
        from acadmate_ml.explain import explain,stage_reference_day,REFERENCE_POLICY
        day=result['as_of_day'];ref_day=stage_reference_day(day)
        bg,metadata=training_background(str(ROOT),ref_day)
        reference=dict(metadata,policy=REFERENCE_POLICY,prediction_day=day,reference_day=ref_day,reference_age_days=day-ref_day)
        row=service.extract(db,enrollment_id,cutoff)
        if row['status']!='ready':raise ValueError('Source coverage changed')
        document={'schema_version':'1.0','source_kind':'synthetic_lms_demo','as_of_day':day,'rows':[
            {'enrollment_id':str(enrollment_id),'student_id':str(row['student_id']),'course_id':str(row['course_id']),
             'as_of_day':day,'case':'main_research','source_kind':'synthetic_lms_demo','status':'ready','reason':None,'features':row['features']}]}
        with service.MODEL._lock:
            if service.MODEL._artifacts is None:service.MODEL._artifacts=service.MODEL._load()
            output=explain(document,*service.MODEL._artifacts,{day:bg},reference=reference)
        explained=output['rows'][0]
        np.testing.assert_allclose(explained['research_risk_probability'],result['research_risk_probability'],rtol=1e-12,atol=1e-12)
        result['explanation']=dict(explained['explanation'],status='available',reason=None,
                                    background_reference=reference,method=output['method'],
                                    shap_version=output['shap_version'],warnings=output['limits'])
    except Exception:
        LOGGER.exception('Optional research explanation unavailable')
        result['explanation']={'status':'unavailable','reason':'A verified explanation is unavailable; the assessment is unchanged.','contributions':[]}
    return result
