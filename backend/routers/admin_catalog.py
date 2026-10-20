"""/admin/catalog/* (spec 33): courses, degree requirements and term dates. Saves are drafts; publish applies them."""
from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from core.deps import require_role
from database import get_db
from models import User
from schemas.catalog import (CatalogCourse, CatalogSummary, CourseIn, CoursePatch, CoursesOut, PublishOut,
                             RequirementsIn, RequirementsOut, TermIn, TermOut, TermPatch, TermsOut)
from services import admin_catalog
from services.audit import request_ip

router = APIRouter(prefix="/api/v1/admin/catalog", tags=["Admin · Catalog"])

admin_only = require_role("admin")


@router.get("/summary", response_model=CatalogSummary)
def summary(user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return admin_catalog.summary(db)


@router.get("/courses", response_model=CoursesOut)
def list_courses(q: str | None = None, term: int | None = None, user: User = Depends(admin_only),
                 db: Session = Depends(get_db)):
    return admin_catalog.courses(db, q, term)


@router.post("/courses", response_model=CatalogCourse, status_code=status.HTTP_201_CREATED)
def add_course(body: CourseIn, request: Request, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return admin_catalog.add_course(db, user, body.model_dump(), ip=request_ip(request))


@router.put("/courses/{code}", response_model=CatalogCourse)
def save_course(code: str, body: CoursePatch, request: Request, user: User = Depends(admin_only),
                db: Session = Depends(get_db)):
    return admin_catalog.save_course_draft(db, user, code, body.model_dump(exclude_unset=True), ip=request_ip(request))


@router.get("/requirements", response_model=RequirementsOut)
def get_requirements(program: int | None = None, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return admin_catalog.requirements(db, program)


@router.put("/requirements", response_model=RequirementsOut)
def save_requirements(body: RequirementsIn, request: Request, user: User = Depends(admin_only),
                      db: Session = Depends(get_db)):
    return admin_catalog.save_requirements_draft(db, user, body.model_dump(), ip=request_ip(request))


@router.get("/terms", response_model=TermsOut)
def list_terms(user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return admin_catalog.terms(db)


@router.post("/terms", response_model=TermOut, status_code=status.HTTP_201_CREATED)
def add_term(body: TermIn, request: Request, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return admin_catalog.create_term(db, user, body.model_dump(), ip=request_ip(request))


@router.put("/terms/{term_id}", response_model=TermOut)
def save_term(term_id: int, body: TermPatch, request: Request, user: User = Depends(admin_only),
              db: Session = Depends(get_db)):
    return admin_catalog.save_term_draft(db, user, term_id, body.model_dump(exclude_unset=True), ip=request_ip(request))


@router.post("/publish", response_model=PublishOut)
def publish(request: Request, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return admin_catalog.publish(db, user, ip=request_ip(request))


@router.delete("/drafts", status_code=status.HTTP_204_NO_CONTENT)
def discard_drafts(request: Request, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    admin_catalog.discard(db, user, ip=request_ip(request))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
