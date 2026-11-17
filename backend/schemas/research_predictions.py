from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, model_validator


class ResearchPredictionResponse(BaseModel):
    schema_version: Literal['1.0'] = '1.0'
    research_only: Literal[True] = True
    source_kind: Literal['synthetic_lms_demo'] = 'synthetic_lms_demo'
    enrollment_id: int = Field(gt=0)
    student_id: int = Field(gt=0)
    course_id: int = Field(gt=0)
    as_of_day: int = Field(ge=7)
    generated_at_utc: datetime
    status: Literal['scored_research_demo', 'unavailable']
    research_risk_probability: float | None = Field(default=None,ge=0,le=1,allow_inf_nan=False)
    reason: str | None = None
    model_version: Literal['final-experiment-v1'] = 'final-experiment-v1'
    calibration_method: Literal['sigmoid'] = 'sigmoid'
    warnings: list[str] = Field(min_length=1)

    @model_validator(mode='after')
    def consistent_status(self):
        if self.status=='unavailable' and (self.research_risk_probability is not None or not self.reason):
            raise ValueError('Unavailable prediction requires a reason and null probability')
        if self.status=='scored_research_demo' and (self.research_risk_probability is None or self.reason is not None):
            raise ValueError('Scored prediction requires a probability and no reason')
        return self
