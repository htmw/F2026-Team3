"""Admin courses & catalog (spec 33). Every save stores a catalog_drafts row (one per course code, program or term; a
later save overwrites it, and a save that matches the published value again drops it). Lists show published rows
with the drafts laid over them, flagged `draft`. Publish applies every draft in one transaction, so students never
see half-edited data. New terms are the exception: they're published at once, since nothing uses a term until
courses are offered in it."""
import re
from collections import Counter
from datetime import date

from sqlalchemy.orm import Session

from core.errors import ApiError, bad_request, conflict, not_found
from models import CatalogDraft, Course, CourseOffering, CoursePrerequisite, Program, ProgramRequirement, Term, User
from services import audit
from services.ai import recommend
from services.catalog import (catalog_year, current_term, is_offered, next_term, offered_course_ids,
                              prerequisite_map)

COURSE_FIELDS = {"name": "course_name", "type": "type", "credits": "credits", "description": "description"}
TERM_FIELDS = {"start_date": "startDate", "end_date": "endDate", "registration_opens": "registrationOpens",
               "last_add": "lastAdd", "last_drop": "lastDrop"}
TERM_NAME = re.compile(r"^(Spring|Summer|Fall) (\d{4})$")
PUBLISHED = "Catalog published. Acadmate now uses these changes."


def _validation(field: str, message: str) -> ApiError:
    return ApiError(422, "VALIDATION_ERROR", "Check the highlighted fields.", [{"field": field, "message": message}])


def _number(value) -> int | float:
    value = float(value)
    return int(value) if value.is_integer() else value


def _drafts(db: Session, entity: str) -> dict[str, CatalogDraft]:
    return {draft.entity_key: draft for draft in db.query(CatalogDraft).filter(CatalogDraft.entity == entity)}


def _save_draft(db: Session, admin: User, entity: str, key: str, data: dict | None) -> None:
    """Upserts the draft, or deletes it when `data` is None (nothing differs from the published catalog any more)."""
    draft = db.query(CatalogDraft).filter(CatalogDraft.entity == entity, CatalogDraft.entity_key == key).one_or_none()
    if data is None:
        if draft is not None:
            db.delete(draft)
    elif draft is None:
        db.add(CatalogDraft(entity=entity, entity_key=key, data=data, created_by=admin.user_id))
    else:
        draft.data, draft.created_by = data, admin.user_id


def _term_or_next(db: Session, term_id: int | None) -> Term | None:
    if term_id is None:
        return next_term(db)
    term = db.get(Term, term_id)
    if term is None:
        raise not_found("Term")
    return term


def offer_label(term: Term) -> str:
    """"Spring 27"."""
    return f"{term.season} {term.year % 100:02d}"


def summary(db: Session) -> dict:
    upcoming = next_term(db)
    return {
        "draftCount": db.query(CatalogDraft).count(),
        "catalogYear": catalog_year(db),
        "nextTerm": {"id": upcoming.id, "name": upcoming.name} if upcoming else None,
    }


# --- courses ---------------------------------------------------------------------------------------------------------

class _Catalog:
    """Published courses and prerequisites as plain values (by code), loaded once per request."""

    def __init__(self, db: Session):
        self.courses = {course.course_code: course for course in db.query(Course)}
        codes = {course.course_id: code for code, course in self.courses.items()}
        self.prereqs = {codes[cid]: sorted(codes[p] for p in ids) for cid, ids in prerequisite_map(db).items()}
        self.drafts = _drafts(db, "course")

    def published(self, code: str, offered: set[int]) -> dict:
        course = self.courses[code]
        return {"name": course.course_name, "type": course.type, "credits": _number(course.credits),
                "description": course.description, "prerequisites": self.prereqs.get(code, []),
                "offered": course.course_id in offered}

    def known(self, code: str) -> bool:
        return code in self.courses or code in self.drafts

    def graph(self) -> dict[str, list[str]]:
        """Prerequisites with the drafted lists laid over the published ones."""
        graph = dict(self.prereqs)
        for code, draft in self.drafts.items():
            if "prerequisites" in draft.data:
                graph[code] = draft.data["prerequisites"]
        return graph


def _row(cat: _Catalog, code: str, term: Term | None, offered: set[int]) -> dict:
    draft = cat.drafts.get(code)
    data = draft.data if draft else {}
    course = cat.courses.get(code)
    values = cat.published(code, offered) if course else {"offered": False}
    values.update({key: data[key] for key in ("name", "type", "credits", "description", "prerequisites") if key in data})
    if term is not None and str(term.id) in data.get("offered", {}):
        values["offered"] = data["offered"][str(term.id)]
    return {
        "id": course.course_id if course else None,
        "code": code,
        "name": values["name"],
        "type": values["type"],
        "credits": values["credits"],
        "offered": values["offered"],
        "offerLabel": offer_label(term) if term is not None and values["offered"] else "Not offered",
        "prerequisites": values["prerequisites"],
        "description": values["description"],
        "draft": draft is not None,
    }


def courses(db: Session, q: str | None = None, term_id: int | None = None) -> dict:
    """Active courses (plus drafted new ones) by code; `offered` is for `term_id`, default the next term."""
    term = _term_or_next(db, term_id)
    cat = _Catalog(db)
    offered = offered_course_ids(db, term.id) if term else set()
    codes = {code for code, course in cat.courses.items() if course.is_active} | set(cat.drafts)
    rows = [_row(cat, code, term, offered) for code in sorted(codes)]
    if q and q.strip():
        needle = q.strip().lower()
        compact = needle.replace(" ", "")
        rows = [row for row in rows if needle in row["name"].lower() or compact in row["code"].lower().replace(" ", "")]
    return {"courses": rows, "term": {"id": term.id, "name": term.name} if term else None}


def _check_cycle(graph: dict[str, list[str]], code: str, prereqs: list[str]) -> None:
    """400 when `code` would end up requiring itself, directly or through one of `prereqs`."""
    if code in prereqs:
        raise bad_request(f"{code} can't require itself.")
    graph = {**graph, code: prereqs}
    for first in prereqs:
        stack, seen = [first], set()
        while stack:
            current = stack.pop()
            if current == code:
                raise bad_request(f"{code} can't require itself through {first}.")
            if current not in seen:
                seen.add(current)
                stack.extend(graph.get(current, []))


def _clean_codes(cat: _Catalog, field: str, codes: list[str]) -> list[str]:
    clean = []
    for raw in codes:
        code = " ".join(raw.split()).upper()
        if not cat.known(code):
            raise _validation(field, f"Unknown course: {code}.")
        if code not in clean:
            clean.append(code)
    return sorted(clean)


def add_course(db: Session, admin: User, body: dict, ip: str | None = None) -> dict:
    code = body["code"]
    cat = _Catalog(db)
    if cat.known(code):
        raise conflict(f"{code} already exists.")
    data = {"new": True, "name": body["name"], "type": body["type"], "credits": body["credits"], "description": None,
            "prerequisites": [], "offered": {}}
    _save_draft(db, admin, "course", code, data)
    audit.record(db, admin, "catalog.course.add", f"Added {code} {body['name']} as a draft", ("course", code),
                 {"name": [None, body["name"]], "credits": [None, body["credits"]]}, ip=ip)
    db.commit()
    return _row(_Catalog(db), code, next_term(db), set())


def save_course_draft(db: Session, admin: User, code: str, patch: dict, ip: str | None = None) -> dict:
    code = " ".join(code.split()).upper()
    cat = _Catalog(db)
    if not cat.known(code):
        raise not_found("Course")
    term = _term_or_next(db, patch.pop("term_id", None))
    offered = offered_course_ids(db, term.id) if term else set()
    before = _row(cat, code, term, offered)

    if "prerequisites" in patch:
        patch["prerequisites"] = _clean_codes(cat, "prerequisites", patch["prerequisites"])
        _check_cycle(cat.graph(), code, patch["prerequisites"])
    if "description" in patch:
        patch["description"] = (patch["description"] or "").strip() or None

    draft = cat.drafts.get(code)
    data = dict(draft.data) if draft else {"new": False}
    data["offered"] = dict(data.get("offered", {}))
    for key in ("name", "type", "credits", "description", "prerequisites"):
        if key in patch:
            data[key] = patch[key]
    if "offered" in patch:
        if term is None:
            raise _validation("offered", "There is no upcoming term to offer it in.")
        data["offered"][str(term.id)] = patch["offered"]

    if not data["new"]:
        # Drop values that match the published catalog again, and the draft once nothing differs.
        published = cat.published(code, set())
        course_id = cat.courses[code].course_id
        for key in ("name", "type", "credits", "description", "prerequisites"):
            if key in data and data[key] == published[key]:
                del data[key]
        data["offered"] = {tid: flag for tid, flag in data["offered"].items()
                           if flag != is_offered(db, course_id, int(tid))}
        if set(data) == {"new", "offered"} and not data["offered"]:
            data = None
    _save_draft(db, admin, "course", code, data)

    changes = {key: [before[key], patch[key]] for key in ("name", "type", "credits", "description", "prerequisites", "offered")
               if key in patch and patch[key] != before[key]}
    audit.record(db, admin, "catalog.course.draft", f"Saved a draft of {code}", ("course", code), changes or None, ip=ip)
    db.commit()
    return _row(_Catalog(db), code, term, offered)


# --- degree requirements ---------------------------------------------------------------------------------------------

def _program(db: Session, program_id: int | None) -> Program:
    program = (db.get(Program, program_id) if program_id is not None
               else db.query(Program).order_by(Program.program_id).first())
    if program is None:
        raise not_found("Program")
    return program


def _groups(db: Session, program: Program) -> list[ProgramRequirement]:
    return (db.query(ProgramRequirement).filter(ProgramRequirement.program_id == program.program_id)
            .order_by(ProgramRequirement.sort, ProgramRequirement.requirement_id).all())


def requirements(db: Session, program_id: int | None = None) -> dict:
    program = _program(db, program_id)
    codes = {course.course_id: course.course_code for course in db.query(Course)}
    draft = _drafts(db, "requirements").get(str(program.program_id))
    drafted = draft.data.get("groups", {}) if draft else {}
    groups = []
    for req in _groups(db, program):
        override = drafted.get(str(req.requirement_id), {})
        groups.append({
            "id": req.requirement_id,
            "label": req.group_name,
            "courses": override.get("courses", req.required_courses),
            "creditsPerCourse": req.credits_per_course,
            "eligible": override.get("eligible", sorted(codes[i] for i in req.eligible_courses_ids or [] if i in codes)),
            "requiresApproval": bool(req.requires_approval),
        })
    return {
        "program": {"id": program.program_id, "name": program.program_name},
        "programs": [{"id": p.program_id, "name": p.program_name} for p in db.query(Program).order_by(Program.program_id)],
        "catalogYear": program.catalog_year,
        "groups": groups,
        "totalCredits": sum(group["courses"] * group["creditsPerCourse"] for group in groups),
        "draft": draft is not None,
    }


def save_requirements_draft(db: Session, admin: User, body: dict, ip: str | None = None) -> dict:
    program = _program(db, body["program_id"])
    reqs = {str(req.requirement_id): req for req in _groups(db, program)}
    codes = {course.course_id: course.course_code for course in db.query(Course)}
    cat = _Catalog(db)
    draft = _drafts(db, "requirements").get(str(program.program_id))
    groups = {key: dict(value) for key, value in (draft.data.get("groups", {}) if draft else {}).items()}

    for group in body["groups"]:
        key = str(group["id"])
        req = reqs.get(key)
        if req is None:
            raise _validation("groups", f"Requirement group {group['id']} isn't part of {program.program_name}.")
        entry = groups.get(key, {})
        entry["courses"] = group["courses"]
        if group.get("eligible") is not None:
            entry["eligible"] = _clean_codes(cat, "eligible", group["eligible"])
        if entry.get("courses") == req.required_courses:
            entry.pop("courses")
        if entry.get("eligible") == sorted(codes[i] for i in req.eligible_courses_ids or [] if i in codes):
            entry.pop("eligible")
        if entry:
            groups[key] = entry
        else:
            groups.pop(key, None)

    _save_draft(db, admin, "requirements", str(program.program_id), {"groups": groups} if groups else None)
    db.flush()
    result = requirements(db, program.program_id)
    audit.record(db, admin, "catalog.requirements.draft",
                 f"Saved a requirements draft for {program.program_name} ({result['totalCredits']} credits)",
                 ("program", program.program_id), {"totalCredits": result["totalCredits"]}, ip=ip)
    db.commit()
    return result


# --- terms -----------------------------------------------------------------------------------------------------------

def _term_values(term: Term, data: dict) -> dict[str, date | None]:
    values = {field: getattr(term, field) for field in TERM_FIELDS}
    values.update({field: date.fromisoformat(value) if value else None for field, value in data.items() if field in TERM_FIELDS})
    return values


def _term_row(term: Term, data: dict, current: Term | None) -> dict:
    values = _term_values(term, data)
    return {"id": term.id, "name": term.name, **{TERM_FIELDS[field]: value for field, value in values.items()},
            "isCurrent": current is not None and term.id == current.id, "draft": bool(data)}


def terms(db: Session) -> dict:
    drafts = _drafts(db, "term")
    current, upcoming = current_term(db), next_term(db)
    return {
        "terms": [_term_row(term, drafts[str(term.id)].data if str(term.id) in drafts else {}, current)
                  for term in db.query(Term).order_by(Term.start_date)],
        "nextTermId": upcoming.id if upcoming else None,
    }


def _check_dates(values: dict[str, date | None]) -> None:
    start, end, add, drop = values["start_date"], values["end_date"], values["last_add"], values["last_drop"]
    if end <= start:
        raise _validation("endDate", "Classes end must be after classes begin.")
    if add is not None and add < start:
        raise _validation("lastAdd", "The last day to add can't be before classes begin.")
    if drop is not None and add is not None and drop < add:
        raise _validation("lastDrop", "The last day to drop can't be before the last day to add.")


def save_term_draft(db: Session, admin: User, term_id: int, patch: dict, ip: str | None = None) -> dict:
    term = db.get(Term, term_id)
    if term is None:
        raise not_found("Term")
    draft = _drafts(db, "term").get(str(term.id))
    data = dict(draft.data) if draft else {}
    before = _term_values(term, data)
    data.update({field: value.isoformat() if value else None for field, value in patch.items() if field in TERM_FIELDS})
    values = _term_values(term, data)
    _check_dates(values)

    data = {field: value for field, value in data.items() if values[field] != getattr(term, field)}
    _save_draft(db, admin, "term", str(term.id), data or None)
    changes = {TERM_FIELDS[field]: [str(before[field]) if before[field] else None, str(values[field]) if values[field] else None]
               for field in TERM_FIELDS if before[field] != values[field]}
    audit.record(db, admin, "catalog.term.draft", f"Saved a draft of the {term.name} dates", ("term", term.id),
                 changes or None, ip=ip)
    db.commit()
    return _term_row(term, data, current_term(db))


def create_term(db: Session, admin: User, body: dict, ip: str | None = None) -> dict:
    name = " ".join(body["name"].split()).title()
    match = TERM_NAME.match(name)
    if match is None:
        raise _validation("name", 'Use a name like "Spring 2028".')
    start, end = body["start_date"], body["end_date"]
    if end <= start:
        raise _validation("endDate", "Classes end must be after classes begin.")
    if db.query(Term).filter(Term.name == name).first() is not None:
        raise conflict(f"{name} already exists.")
    overlap = db.query(Term).filter(Term.start_date <= end, Term.end_date >= start).order_by(Term.start_date).first()
    if overlap is not None:
        raise conflict(f"{name} overlaps {overlap.name}.")
    term = Term(name=name, season=match.group(1), year=int(match.group(2)), start_date=start, end_date=end)
    db.add(term)
    db.flush()
    audit.record(db, admin, "catalog.term.add", f"Added the {name} term", ("term", term.id),
                 {"startDate": [None, str(start)], "endDate": [None, str(end)]}, ip=ip)
    db.commit()
    return _term_row(term, {}, current_term(db))


# --- publish ---------------------------------------------------------------------------------------------------------

def _apply_course(db: Session, course: Course, data: dict, by_code: dict[str, Course]) -> None:
    for key, column in COURSE_FIELDS.items():
        if key in data:
            setattr(course, column, data[key])
    if "prerequisites" in data:
        db.query(CoursePrerequisite).filter(CoursePrerequisite.course_id == course.course_id).delete()
        db.add_all(CoursePrerequisite(course_id=course.course_id, prerequisite_id=by_code[code].course_id)
                   for code in data["prerequisites"] if code in by_code)
    for term_id, flag in data.get("offered", {}).items():
        offering = db.get(CourseOffering, (course.course_id, int(term_id)))
        if flag and offering is None and db.get(Term, int(term_id)) is not None:
            db.add(CourseOffering(course_id=course.course_id, term_id=int(term_id)))
        elif not flag and offering is not None:
            db.delete(offering)


def _apply_requirements(db: Session, program: Program, data: dict, by_code: dict[str, Course]) -> None:
    reqs = _groups(db, program)
    for req in reqs:
        entry = data.get("groups", {}).get(str(req.requirement_id), {})
        if "courses" in entry:
            req.required_courses = entry["courses"]
        if "eligible" in entry:
            req.eligible_courses_ids = [by_code[code].course_id for code in entry["eligible"] if code in by_code]
        req.required_credits = req.required_courses * req.credits_per_course
    program.total_required_credits = sum(req.required_credits for req in reqs)


def publish(db: Session, admin: User, ip: str | None = None) -> dict:
    drafts = db.query(CatalogDraft).order_by(CatalogDraft.id).all()
    if not drafts:
        raise conflict("There are no changes to publish.")
    counts = Counter(draft.entity for draft in drafts)
    by_code = {course.course_code: course for course in db.query(Course)}

    course_drafts = [draft for draft in drafts if draft.entity == "course"]
    for draft in course_drafts:  # create new courses first, so prerequisites and requirements can name them
        if draft.entity_key not in by_code:
            course = Course(course_code=draft.entity_key, course_name=draft.data["name"], credits=draft.data["credits"],
                            type=draft.data["type"])
            db.add(course)
            by_code[draft.entity_key] = course
    db.flush()
    for draft in course_drafts:
        _apply_course(db, by_code[draft.entity_key], draft.data, by_code)
    for draft in drafts:
        if draft.entity == "requirements":
            program = db.get(Program, int(draft.entity_key))
            if program is not None:
                _apply_requirements(db, program, draft.data, by_code)
        elif draft.entity == "term":
            term = db.get(Term, int(draft.entity_key))
            if term is not None:
                for field, value in draft.data.items():
                    setattr(term, field, date.fromisoformat(value) if value else None)
        db.delete(draft)

    audit.record(db, admin, "catalog.publish", f"Published the {catalog_year(db)} catalog", ("catalog", catalog_year(db)),
                 {"courses": counts["course"], "requirements": counts["requirements"], "terms": counts["term"]}, ip=ip)
    db.commit()
    recommend._cache.clear()  # the dashboard's cached recommendation may name a course that changed
    return {"published": len(drafts), "message": PUBLISHED}


def discard(db: Session, admin: User, ip: str | None = None) -> None:
    count = db.query(CatalogDraft).delete()
    if count:
        audit.record(db, admin, "catalog.discard", f"Discarded {count} catalog draft{'s' if count != 1 else ''}",
                     ("catalog", catalog_year(db)), {"drafts": count}, ip=ip)
    db.commit()
