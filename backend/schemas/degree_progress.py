from schemas.base import ApiModel


class RequirementProgress(ApiModel):
    requirement_id: int
    group_name: str
    required_credits: float
    earned_credits: float
    remaining_credits: float
    is_satisfied: bool
    eligible_course_ids: list[int]


class DegreeProgressResponse(ApiModel):
    student_id: int
    program_id: int
    required_credits: float
    earned_credits: float
    remaining_credits: float
    completion_rate: float
    requirements: list[RequirementProgress]