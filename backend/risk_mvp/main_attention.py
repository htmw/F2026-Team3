"""Shared demo deadline evidence; no model loading or database writes.
Administrative rules retain their existing threshold. No data source substitution
outside the explicitly opted-in disposable main demo.
"""
import os
from datetime import datetime, time, timezone
from sqlalchemy import select


def overdue_counts(rows, field="overdue_last_14_days"):
    """Unknown in any active course means the student total is unknown."""
    values = [r.get('evidence', {}).get(field) for r in rows]
    if not rows or any(r.get('status') != 'ready' for r in rows): return None
    if any(type(v) not in (int, float) or v < 0 for v in values): return None
    return sum(values)


def align_context(db, students, context):
    if os.environ.get('ACADMATE_RISK_MVP_ENABLED') != 'true': return
    from core.time import today
    url = db.get_bind().url
    if url.host not in ('localhost', '127.0.0.1') or url.database not in ('acadmate_risk_demo_main_sprint2', 'acadmate_risk_csv_sprint2', 'acadmate_risk_team_review_sprint2'): return
    from . import service
    cutoff = datetime.combine(today(), time.max, timezone.utc)
    e = service.T['enrollments'].c
    ids = [s.student_id for s in students]
    grouped = {sid: [] for sid in ids}
    for row in db.execute(select(e.student_id, e.enrollment_id).where(e.student_id.in_(ids), e.status == 'in_progress')).mappings():
        grouped[row.student_id].append(service.extract(db, row.enrollment_id, cutoff))
    context.course_overdue = {}
    for sid, rows in grouped.items():
        # Never fall back to a different assignment source within the demo.
        context.missed.pop(sid, None)
        count = overdue_counts(rows)
        if count is not None: context.missed[sid] = count
        outstanding = overdue_counts(rows, "overdue_assignments")
        if outstanding is not None: context.course_overdue[sid] = outstanding


def course_review_reason(student_id, context):
    """Workflow evidence, not a probability threshold or academic policy."""
    count = getattr(context, 'course_overdue', {}).get(student_id)
    if count is None or count <= 0: return None
    noun = 'assessment remains' if count == 1 else 'assessments remain'
    return f"{int(count)} {noun} overdue across active courses. Review the course record and discuss any barriers to completion."
