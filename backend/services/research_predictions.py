"""Server-controlled, read-only research inference. No database or network imports."""
import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from threading import Lock

ROOT=Path(__file__).resolve().parents[2]
LOGGER=logging.getLogger(__name__)


class DemoUnavailable(Exception): pass
class DemoEnrollmentNotFound(Exception): pass


class PredictionService:
    def __init__(self,root=ROOT):
        self.root=Path(root)
        self._artifacts=None
        self._lock=Lock()

    def _load(self):
        # Lazy imports keep existing student API startup independent of ML packages.
        import joblib
        from acadmate_ml.features import FEATURES
        from acadmate_ml.splits import digest
        import acadmate_ml.features as feature_module
        ml=self.root/'ml'
        config=json.loads((ml/'configs/FINAL_EXPERIMENT_V1.json').read_text(encoding='utf-8'))
        if config['primary']!='logistic_regression_with_existing_sigmoid' or config['features']!=FEATURES:
            raise ValueError('Invalid frozen configuration')
        paths=[ml/'outputs/baselines-v1/logistic_regression.joblib',ml/'outputs/calibration-v1/calibration_maps.joblib']
        if any(digest(p)!=config[k] for p,k in zip(paths,['model_sha256','maps_sha256'])):
            raise ValueError('Frozen artifact integrity failure')
        source=Path(feature_module.__file__).parent
        for name,expected in config['source_sha256'].items():
            if digest(source/name)!=expected: raise ValueError('Frozen source integrity failure')
        base,maps=[joblib.load(p) for p in paths]
        if base['features']!=FEATURES or maps['base_model_sha256']!=config['model_sha256']:
            raise ValueError('Artifact linkage failure')
        return base['pipeline'],maps['sigmoid']

    def get(self,enrollment_id):
        if os.getenv('ACADMATE_RESEARCH_DEMO_ENABLED','').lower()!='true':
            raise DemoUnavailable()
        try:
            from acadmate_ml.simulated_lms import build
            from acadmate_ml.predict import predict
            document=json.loads((self.root/'ml/fixtures/simulated_lms/events.json').read_text(encoding='utf-8-sig'))
            features=build(document,self.root/'data/synthetic')
            rows=[r for r in features['rows'] if r['enrollment_id']==str(enrollment_id)]
            if not rows: raise DemoEnrollmentNotFound()
            features['rows']=rows
            # Known missing coverage needs no model artifacts and is never scored.
            if rows[0]['status']=='unavailable':
                result=predict(features,None,None)
            else:
                with self._lock:
                    if self._artifacts is None:self._artifacts=self._load()
                    result=predict(features,*self._artifacts)
            row=result['rows'][0]
            return {**row,'enrollment_id':int(row['enrollment_id']),'student_id':int(row['student_id']),
                'course_id':int(row['course_id']),'generated_at_utc':result['generated_at_utc'],
                'schema_version':'1.0','research_only':True,'source_kind':'synthetic_lms_demo',
                'model_version':'final-experiment-v1','calibration_method':'sigmoid'}
        except DemoEnrollmentNotFound:
            raise
        except Exception:
            LOGGER.exception('Research prediction demo unavailable')
            raise DemoUnavailable() from None


@lru_cache(maxsize=1)
def get_prediction_service():
    return PredictionService()
