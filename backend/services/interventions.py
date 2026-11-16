from sqlalchemy.orm import Session

from core.deps import advisor_can_see
from core.errors import bad_request, not_found
from models import AcademicIntervention, Advisor


ALLOWED_TRANSITIONS = {
    "open": {"in_progress"},
    "in_progress": {"done"},
    "done": set(),
}


def list_for(
    db: Session,
    advisor: Advisor,
    student_id: int,
) -> list[AcademicIntervention]:

    advisor_can_see(
        db,
        advisor.advisor_id,
        student_id,
    )

    return (
        db.query(AcademicIntervention)
        .filter(
            AcademicIntervention.student_id == student_id,
            AcademicIntervention.advisor_id == advisor.advisor_id,
        )
        .order_by(
            AcademicIntervention.created_at.desc(),
            AcademicIntervention.id.desc(),
        )
        .all()
    )


def create(
    db: Session,
    advisor: Advisor,
    student_id: int,
    *,
    title: str,
    description: str | None,
    due_date,
) -> AcademicIntervention:

    advisor_can_see(
        db,
        advisor.advisor_id,
        student_id,
    )

    intervention = AcademicIntervention(
        student_id=student_id,
        advisor_id=advisor.advisor_id,
        title=title.strip(),
        description=description.strip() if description else None,
        due_date=due_date,
        status="open",
    )

    db.add(intervention)
    db.flush()

    return intervention


def get(
    db: Session,
    advisor: Advisor,
    intervention_id: int,
) -> AcademicIntervention:

    intervention = db.get(
        AcademicIntervention,
        intervention_id,
    )

    if intervention is None:
        raise not_found("Academic intervention")

    advisor_can_see(
        db,
        advisor.advisor_id,
        intervention.student_id,
    )

    if intervention.advisor_id != advisor.advisor_id:
        raise not_found("Academic intervention")

    return intervention


def update(
    db: Session,
    advisor: Advisor,
    intervention_id: int,
    data: dict,
) -> AcademicIntervention:

    intervention = get(
        db,
        advisor,
        intervention_id,
    )

    if "status" in data and data["status"] is not None:
        new_status = data["status"]

        if new_status != intervention.status:
            allowed = ALLOWED_TRANSITIONS.get(
                intervention.status,
                set(),
            )

            if new_status not in allowed:
                raise bad_request(
                    f"Intervention cannot move from "
                    f"{intervention.status} to {new_status}."
                )

            intervention.status = new_status

    if "title" in data and data["title"] is not None:
        intervention.title = data["title"].strip()

    if "description" in data:
        value = data["description"]
        intervention.description = (
            value.strip()
            if value
            else None
        )

    if "due_date" in data:
        intervention.due_date = data["due_date"]

    db.flush()

    return intervention